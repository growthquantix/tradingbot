# services/unified_websocket_manager.py - FIXED COMPLETE VERSION
"""
Fixed Unified Event-Driven WebSocket Manager (complete file)

This version:
- Avoids circular import by lazily loading analytics module at runtime.
- Uses a single, consistent event handler registry (self.event_handlers).
- Keeps robust error handling and rate-limiting logic from the original.
- Exposes a singleton `unified_manager` and helper start/stop functions.
"""
import asyncio
import json
import logging
import importlib
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Callable, Optional
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


def safe_float(value, default=0.0):
    """Safely convert a value to float"""
    try:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return float(value)
        return float(value)
    except (ValueError, TypeError):
        logger.debug(f"Invalid float value: {value}, using default {default}")
        return default


def safe_int(value, default=0):
    """Safely convert a value to int"""
    try:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (ValueError, TypeError):
        logger.debug(f"Invalid int value: {value}, using default {default}")
        return default


class UnifiedWebSocketManager:
    """
    FIXED: Single WebSocket manager for ALL features using event-driven architecture
    """

    def __init__(self):
        # Connection management
        self.connections: Dict[str, WebSocket] = {}
        self.client_subscriptions: Dict[str, Set[str]] = {}
        self.client_types: Dict[str, str] = {}
        self.is_active: bool = True  # Manager status

        # Event system
        # Use a normal dict of lists for handlers (defaultdict for convenience)
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_queue = asyncio.Queue(maxsize=5000)

        # OPTIMIZED: Balanced rate limiting
        self.last_event_time = {}
        self.event_rate_limits = {
            "price_update": 0.01,
            "dashboard_update": 0.05,
            "live_prices_enriched": 0.02,
            "index_update": 0.1,
            "top_movers_update": 0.5,
            "intraday_stocks_update": 0.5,
            "market_sentiment_update": 1.0,
            "indices_data_update": 0.5,
            "volume_analysis_update": 1.0,
            "analytics_update": 2.0,
            "gap_signals_update": 0.1,
            "breakout_signals_update": 0.1,
        }

        # SAFETY: Trading mode configuration
        self.trading_mode = True
        self.emergency_mode = False
        self.pending_events = {}

        # Feature-specific data caches
        self.live_prices = {}
        self.analytics_cache = {}
        self.heatmap_cache = {}
        self.movers_cache = {}

        # Background tasks
        self.background_tasks = set()
        self.is_running = False

        # Analytics service (lazy loaded)
        self.analytics_service = None
        self._analytics_loader_task: Optional[asyncio.Task] = None
        self._init_analytics_service()  # prepares lazy loader

        # Market Data Hub integration placeholder
        self.market_hub = None
        self._init_market_hub()

        # Sequence number for messages
        self._seq_num = 0

    # ========== Handler registration ==========
    def register_handler(self, event_type: str, handler_func: Callable):
        """Register a handler function for a specific event type"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler_func)
        logger.info(f"✅ Registered handler for {event_type} events")
        return True

    # ========== Analytics lazy load ==========
    def _init_analytics_service(self):
        """
        Prepare lazy analytics loader. Do NOT import analytics here to avoid circular imports.
        The real import happens in _load_analytics_service which is invoked at start().
        """
        self.analytics_service = None
        self._analytics_loader_task = None
        logger.debug("🔧 Analytics service loader prepared (lazy load)")

    async def _load_analytics_service(self):
        """
        Async loader to import enhanced_market_analytics at runtime.
        We do this asynchronously during start() to avoid circular import issues.
        """
        if self.analytics_service is not None:
            return  # Already loaded
        try:
            module = importlib.import_module("services.enhanced_market_analytics")
            analytics_obj = getattr(module, "enhanced_analytics", None)
            if analytics_obj is None:
                analytics_obj = module
            self.analytics_service = analytics_obj
            logger.info("✅ Analytics service dynamically loaded")
        except Exception as e:
            self.analytics_service = None
            logger.warning(f"⚠️ Could not load analytics service at runtime: {e}")

    # ========== Market hub init ==========
    def _init_market_hub(self):
        """Initialize Market Data Hub integration (if available)"""
        try:
            from services.market_data_hub import market_data_hub

            self.market_hub = market_data_hub

            def hub_price_callback(data):
                """Ultra-fast callback from market hub"""
                try:
                    if "prices" in data:
                        self.emit_event("price_update", data["prices"], priority=0)
                        self.emit_event(
                            "dashboard_update",
                            {
                                "data": data["prices"],
                                "source": "market_hub_direct",
                                "timestamp": data.get("timestamp"),
                                "count": data.get("count", 0),
                            },
                            priority=0,
                        )
                        logger.debug(
                            f"⚡ Hub -> UI: {data.get('count', 0)} instruments"
                        )

                    elif data.get("type") == "indices_data_update" and "data" in data:
                        self.emit_event("indices_data_update", data["data"], priority=0)
                        if data["data"].get("indices"):
                            index_prices = {}
                            for index in data["data"]["indices"]:
                                index_prices[index["instrument_key"]] = {
                                    "instrument_key": index["instrument_key"],
                                    "symbol": index["symbol"],
                                    "ltp": index["ltp"],
                                    "last_price": index["ltp"],
                                    "change": index["change"],
                                    "change_percent": index["change_percent"],
                                    "timestamp": index["timestamp"],
                                    "type": "INDEX",
                                }
                            if index_prices:
                                self.emit_event(
                                    "index_update", index_prices, priority=0
                                )

                        logger.debug(
                            f"📊 Hub -> UI: {len(data['data']['indices'])} indices"
                        )

                except Exception as e:
                    logger.error(f"❌ Error in hub callback: {e}")

            self.market_hub_callback = hub_price_callback
            logger.info("✅ Market Data Hub integration initialized")

        except ImportError as e:
            logger.warning(f"⚠️ Market Data Hub not available: {e}")
            self.market_hub = None

    # ========== Lifecycle: start / stop ==========
    async def start(self):
        """Start the unified WebSocket system"""
        if self.is_running:
            return

        self.is_running = True
        self.is_active = True

        # Start event processor
        processor_task = asyncio.create_task(self._process_events())
        self.background_tasks.add(processor_task)
        processor_task.add_done_callback(lambda t: self.background_tasks.discard(t))

        # Start analytics updater
        analytics_task = asyncio.create_task(self._update_analytics())
        self.background_tasks.add(analytics_task)
        analytics_task.add_done_callback(lambda t: self.background_tasks.discard(t))

        # Start pending event processor
        pending_task = asyncio.create_task(self._process_pending_events())
        self.background_tasks.add(pending_task)
        pending_task.add_done_callback(lambda t: self.background_tasks.discard(t))

        # LAZY LOAD analytics service (do not block start)
        try:
            self._analytics_loader_task = asyncio.create_task(
                self._load_analytics_service()
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to launch analytics loader task: {e}")

        # Register with Market Data Hub if available
        if self.market_hub and hasattr(self, "market_hub_callback"):
            try:
                success = self.market_hub.register_consumer(
                    consumer_name="unified_websocket_manager",
                    callback=self.market_hub_callback,
                    topics=["prices", "indices", "all"],
                    priority=1,
                    max_queue_size=2000,
                )
                if success:
                    logger.info(
                        "🚀 Registered with Market Data Hub for ultra-fast updates"
                    )
                else:
                    logger.warning("⚠️ Failed to register with Market Data Hub")
            except Exception as e:
                logger.error(f"❌ Error registering with Market Data Hub: {e}")

        logger.info("🚀 Unified WebSocket Manager started")

    async def stop(self):
        """Stop the unified WebSocket system"""
        self.is_running = False
        self.is_active = False

        # Cancel background tasks
        for task in list(self.background_tasks):
            if not task.done():
                task.cancel()

        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Close all websockets
        for client_id, ws in list(self.connections.items()):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close()
            except Exception as e:
                logger.debug(f"Error closing connection {client_id}: {e}")

        self.connections.clear()
        logger.info("🛑 Unified WebSocket Manager stopped")

    # ========== Connection management ==========
    async def add_client(
        self, websocket: WebSocket, client_type: str = "dashboard"
    ) -> str:
        """Add a new WebSocket client"""
        try:
            # Accept connection first
            await websocket.accept()
            logger.info("🔌 WebSocket connection accepted")

            client_id = f"{client_type}_{uuid.uuid4().hex[:8]}"

            self.connections[client_id] = websocket
            self.client_types[client_id] = client_type
            self.client_subscriptions[client_id] = set()

            # Start event processor if this was the first connection and not running
            if len(self.connections) == 1 and self.is_running:
                try:
                    if not any(
                        task for task in self.background_tasks if not task.done()
                    ):
                        task = asyncio.create_task(self._process_events())
                        self.background_tasks.add(task)
                        logger.info(
                            "🔄 Started event processor for new client connection"
                        )
                except Exception as e:
                    logger.error(f"❌ Error starting event processor: {e}")

            # Send welcome message
            try:
                await websocket.send_json(
                    {
                        "type": "connection_established",
                        "client_id": client_id,
                        "client_type": client_type,
                        "available_events": self.get_available_events(),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"❌ Error sending welcome message: {e}")

            # Send initial data
            await self._send_initial_data(client_id, client_type)

            logger.info(f"🔌 Client connected: {client_id} ({client_type})")
            return client_id

        except Exception as e:
            logger.error(f"❌ Error adding client: {e}")
            try:
                await websocket.close(code=1011, reason=f"Error during setup: {str(e)}")
            except Exception:
                pass
            raise

    async def remove_client(self, client_id: str):
        """Remove a WebSocket client"""
        if client_id in self.connections:
            try:
                ws = self.connections[client_id]
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket for {client_id}: {e}")

            self.connections.pop(client_id, None)
            self.client_types.pop(client_id, None)
            self.client_subscriptions.pop(client_id, None)
            logger.info(f"🔌 Client disconnected: {client_id}")

    # ========== Subscription API ==========
    def subscribe_to_events(self, client_id: str, events: List[str]):
        """Subscribe client to specific events with deduplication"""
        if client_id in self.client_subscriptions:
            existing_events = self.client_subscriptions[client_id]
            new_events = set(events) - existing_events
            if new_events:
                existing_events.update(new_events)
                logger.info(
                    f"📡 Client {client_id} subscribed to {len(new_events)} new events (total: {len(existing_events)})"
                )
            else:
                logger.debug(
                    f"📡 Client {client_id} already subscribed to all requested events"
                )
        else:
            self.client_subscriptions[client_id] = set(events)
            logger.info(
                f"📡 Client {client_id} subscribed to {len(events)} events (first time)"
            )

    # ========== Ultra-fast direct broadcast helpers ==========
    async def emit_realtime_price(self, enriched_tick: Dict[str, Any]):
        """Ultra-fast direct real-time price broadcast bypassing queue"""
        if not enriched_tick or not self.connections:
            return
        try:
            price_message = {
                "type": "price_update",
                "data": enriched_tick,
                "timestamp": datetime.now().isoformat(),
                "realtime": True,
            }
            message_str = json.dumps(price_message, default=str)
            tasks = []
            for client_id, websocket in list(self.connections.items()):
                if websocket.client_state == WebSocketState.CONNECTED:
                    tasks.append(
                        self._send_direct_message(client_id, websocket, message_str)
                    )
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ Real-time price broadcast error: {e}")

    async def emit_direct_price_batch(self, price_batch: Dict[str, Dict[str, Any]]):
        """Ultra-fast: Direct batch price broadcast to ALL UI sections"""
        if not price_batch or not self.connections:
            return
        try:
            timestamp = datetime.now().isoformat()
            individual_price_messages = []
            for instrument_key, price_data in price_batch.items():
                if price_data and price_data.get("ltp"):
                    individual_message = {
                        "type": "price_update",
                        "data": price_data,
                        "timestamp": timestamp,
                        "realtime": True,
                        "direct_feed": True,
                    }
                    individual_price_messages.append(individual_message)

            batch_price_message = {
                "type": "price_update",
                "data": price_batch,
                "timestamp": timestamp,
                "count": len(price_batch),
                "direct_feed": True,
                "realtime": True,
                "batch_update": True,
            }

            dashboard_message = {
                "type": "dashboard_update",
                "data": price_batch,
                "timestamp": timestamp,
                "count": len(price_batch),
                "source": "direct_feed",
                "market_open": True,
                "update_sections": ["overview", "movers", "sectors", "analytics"],
            }

            trading_message = {
                "type": "live_prices_enriched",
                "data": price_batch,
                "timestamp": timestamp,
                "count": len(price_batch),
                "enriched": True,
                "direct_feed": True,
                "trading_ready": True,
            }

            indices_data = {}
            stocks_data = {}
            for instrument_key, price_data in price_batch.items():
                if any(
                    idx in instrument_key.upper()
                    for idx in [
                        "NIFTY",
                        "SENSEX",
                        "BANKEX",
                        "INDEX",
                        "FINNIFTY",
                        "MIDCPNIFTY",
                    ]
                ):
                    indices_data[instrument_key] = price_data
                else:
                    stocks_data[instrument_key] = price_data

            indices_message = None
            if indices_data:
                indices_message = {
                    "type": "index_update",
                    "data": indices_data,
                    "timestamp": timestamp,
                    "count": len(indices_data),
                    "direct_feed": True,
                }

            messages_to_send = []
            messages_to_send.append(json.dumps(batch_price_message, default=str))
            messages_to_send.append(json.dumps(dashboard_message, default=str))
            messages_to_send.append(json.dumps(trading_message, default=str))
            if indices_message:
                messages_to_send.append(json.dumps(indices_message, default=str))

            tasks = []
            for client_id, websocket in list(self.connections.items()):
                if websocket.client_state == WebSocketState.CONNECTED:
                    for message_str in messages_to_send:
                        tasks.append(
                            self._send_direct_message(client_id, websocket, message_str)
                        )

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in results if r is True)
                logger.debug(
                    f"⚡ COMPREHENSIVE BROADCAST: {len(price_batch)} prices → {len(self.connections)} clients, success: {successful}/{len(results)}"
                )

        except Exception as e:
            logger.error(f"❌ Direct batch price broadcast error: {e}")

    async def _send_direct_message(
        self, client_id: str, websocket: WebSocket, message: str
    ):
        """Send message directly to WebSocket client with proper state checking"""
        try:
            if hasattr(websocket, "client_state"):
                if websocket.client_state in [
                    WebSocketState.DISCONNECTED,
                    WebSocketState.CLOSED,
                ]:
                    logger.debug(f"🔌 Skipping send to disconnected client {client_id}")
                    await self.remove_client(client_id)
                    return False

            if hasattr(websocket, "application_state"):
                if websocket.application_state in [
                    WebSocketState.DISCONNECTED,
                    WebSocketState.CLOSED,
                ]:
                    logger.debug(f"🔌 Skipping send to closed client {client_id}")
                    await self.remove_client(client_id)
                    return False

            await websocket.send_text(message)
            return True

        except RuntimeError as e:
            if "close message has been sent" in str(e) or "Connection is closed" in str(
                e
            ):
                logger.debug(f"🔌 Client {client_id} connection already closed")
            else:
                logger.error(f"❌ Runtime error sending to {client_id}: {e}")
            await self.remove_client(client_id)
        except Exception as e:
            logger.error(f"❌ Failed to send to client {client_id}: {e}")
            await self.remove_client(client_id)
        return False

    # ========== Emit to all (queued) ==========
    async def emit_to_all(self, event: str, data: Dict[str, Any]):
        """Enhanced emit with circuit breaker integration"""
        if not self.connections:
            try:
                from services.circuit_breaker import circuit_breaker

                await circuit_breaker.update_system_health(
                    {"websocket_connected": False, "api_failure": True}
                )
            except ImportError:
                pass
            return

        try:
            message = {
                "type": event,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "sequence_number": getattr(self, "_seq_num", 0),
            }
            self._seq_num = getattr(self, "_seq_num", 0) + 1

            disconnected_clients = []
            successful_sends = 0
            connections_copy = list(self.connections.items())

            for client_id, websocket in connections_copy:
                try:
                    is_connected = True
                    if hasattr(websocket, "client_state"):
                        if websocket.client_state in [
                            WebSocketState.DISCONNECTED,
                            WebSocketState.CLOSED,
                        ]:
                            is_connected = False
                    if hasattr(websocket, "application_state") and is_connected:
                        if websocket.application_state in [
                            WebSocketState.DISCONNECTED,
                            WebSocketState.CLOSED,
                        ]:
                            is_connected = False
                    if not is_connected:
                        logger.debug(
                            f"🔌 Skipping broadcast to disconnected client {client_id}"
                        )
                        disconnected_clients.append(client_id)
                        continue

                    await websocket.send_text(json.dumps(message))
                    successful_sends += 1

                except RuntimeError as e:
                    if "close message has been sent" in str(
                        e
                    ) or "Connection is closed" in str(e):
                        logger.debug(
                            f"🔌 Client {client_id} connection already closed during broadcast"
                        )
                    else:
                        logger.warning(f"Failed to send to client {client_id}: {e}")
                    disconnected_clients.append(client_id)
                except Exception as e:
                    logger.warning(f"Failed to send to client {client_id}: {e}")
                    disconnected_clients.append(client_id)

            for client_id in disconnected_clients:
                self.connections.pop(client_id, None)

            connection_health = successful_sends > 0
            try:
                from services.circuit_breaker import circuit_breaker

                await circuit_breaker.update_system_health(
                    {
                        "websocket_connected": connection_health,
                        "last_price_update": (
                            datetime.now(timezone.utc)
                            if event == "price_update"
                            else None
                        ),
                        "api_success": True,
                    }
                )
            except ImportError:
                pass

        except Exception as e:
            logger.error(f"❌ Error emitting to all clients: {e}")
            try:
                from services.circuit_breaker import circuit_breaker

                await circuit_breaker.update_system_health(
                    {"websocket_connected": False, "api_failure": True}
                )
            except ImportError:
                pass

    # ========== Event queueing ==========
    def emit_event(self, event_type: str, data: Dict[str, Any], priority: int = 5):
        """Emit an event to the queue with optimized rate limiting"""
        now = datetime.now()

        # Rate limiting (unless emergency)
        if not self.emergency_mode and event_type in self.event_rate_limits:
            rate_limit = self.event_rate_limits[event_type]
            if rate_limit > 0 and event_type in self.last_event_time:
                time_since_last = (
                    now - self.last_event_time[event_type]
                ).total_seconds()
                if time_since_last < rate_limit:
                    # Add to pending rather than dropping
                    self.pending_events[event_type] = {
                        "data": data,
                        "priority": priority,
                        "timestamp": now,
                    }
                    logger.debug(
                        f"⏱️ Rate limited {event_type}, adding to pending (last: {time_since_last:.3f}s, limit: {rate_limit}s)"
                    )
                    return

        logger.debug(f"✅ Processing {event_type} (priority: {priority})")
        self.last_event_time[event_type] = now

        if event_type in [
            "price_update",
            "dashboard_update",
            "live_prices_enriched",
            "index_update",
            "top_movers_update",
            "intraday_stocks_update",
            "indices_data_update",
        ]:
            priority = 1

        if not isinstance(priority, int):
            priority = self._determine_event_priority(event_type, data)

        normalized_event_type = self._normalize_event_type(event_type)
        event = {
            "type": normalized_event_type,
            "data": data,
            "timestamp": now.isoformat(),
            "priority": priority,
        }

        try:
            self.event_queue.put_nowait(event)
            if normalized_event_type in [
                "price_update",
                "dashboard_update",
                "live_prices_enriched",
                "index_update",
            ]:
                data_size = 0
                if isinstance(data, dict):
                    data_size = len(data)
                elif isinstance(data, list):
                    data_size = len(data)
                logger.info(
                    f"⚡ ZERO-DELAY queued {normalized_event_type} (priority: {priority}, data: {data_size} items, queue: {self.event_queue.qsize()})"
                )
            else:
                logger.debug(
                    f"✅ Queued {normalized_event_type} (priority: {priority})"
                )
        except asyncio.QueueFull:
            if priority == 1:
                logger.warning(
                    f"🚨 FORCE-QUEUING critical trading event: {normalized_event_type}"
                )
                try:
                    dropped_event = self.event_queue.get_nowait()
                    self.event_queue.put_nowait(event)
                    logger.info(
                        f"🔄 Dropped {dropped_event.get('type', 'unknown')} for critical {normalized_event_type}"
                    )
                except asyncio.QueueEmpty:
                    logger.error(
                        f"❌ Queue empty but still full - critical error for {normalized_event_type}"
                    )
            else:
                logger.warning(
                    f"⚠️ Event queue full, dropping non-critical event: {normalized_event_type}"
                )

    def _normalize_event_type(self, event_type: str) -> str:
        """Normalize event types to prevent duplicates from typos"""
        fixes = {
            "price_upddate": "price_update",
            "pprice_update": "price_update",
            "dashboardd_update": "dashboard_update",
            "ddashboard_update": "dashboard_update",
            "top_moverrs_update": "top_movers_update",
            "ttop_movers_update": "top_movers_update",
            "intraday__stocks_update": "intraday_stocks_update",
            "iintraday_stocks_update": "intraday_stocks_update",
            "market_seentiment_update": "market_sentiment_update",
            "mmarket_sentiment_update": "market_sentiment_update",
            "indices_ddata_update": "indices_data_update",
            "iindices_data_update": "indices_data_update",
        }
        return fixes.get(event_type, event_type)

    def _determine_event_priority(self, event_type: str, data: Dict[str, Any]) -> int:
        """Determine event priority based on type and content"""
        if "indices" in event_type.lower() or event_type in ["market_status_update"]:
            return 1
        if (
            ("fno" in event_type.lower())
            or (isinstance(data, dict) and data.get("fno_candidates"))
            or self._contains_fno_symbols(data)
        ):
            return 2
        if event_type in ["price_update", "dashboard_update", "live_prices_update"]:
            return 2
        if event_type in ["top_movers_update", "intraday_stocks_update"]:
            return 3
        if "sentiment" in event_type.lower():
            return 4
        if "analytics" in event_type.lower():
            return 6
        return 5

    def _contains_fno_symbols(self, data: Dict[str, Any]) -> bool:
        """Check if data contains FNO symbols"""
        try:
            fno_symbols = {
                "RELIANCE",
                "TCS",
                "HDFCBANK",
                "ICICIBANK",
                "INFY",
                "SBIN",
                "WIPRO",
                "MARUTI",
                "HINDUNILVR",
                "ITC",
                "BAJFINANCE",
            }
            if isinstance(data, dict):
                for value in data.values():
                    if isinstance(value, str) and value.upper() in fno_symbols:
                        return True
                    elif isinstance(value, list):
                        for item in value:
                            if (
                                isinstance(item, dict)
                                and item.get("symbol", "").upper() in fno_symbols
                            ):
                                return True
                            elif isinstance(item, str) and item.upper() in fno_symbols:
                                return True
            return False
        except Exception:
            return False

    # ========== Event processing ==========
    async def _process_events(self):
        """Process events from the queue with improved error handling"""
        logger.info("🔄 Event processor started")
        processed_count = 0

        while self.is_running:
            try:
                if not self.is_running:
                    logger.info("🛑 Event processor stopping - is_running=False")
                    break

                event = await asyncio.wait_for(self.event_queue.get(), timeout=0.001)
                processed_count += 1

                if processed_count % 50 == 0:
                    logger.info(
                        f"🔄 Processed {processed_count} events, queue size: {self.event_queue.qsize()}"
                    )

                if event.get("type") == "trigger_analytics":
                    try:
                        if self.analytics_service:
                            analytics_data = (
                                self.analytics_service.get_complete_analytics()
                            )
                            for feature, data in analytics_data.items():
                                if feature not in [
                                    "generated_at",
                                    "processing_time_ms",
                                    "cache_status",
                                ]:
                                    self.emit_event(
                                        f"{feature}_update", data, priority=6
                                    )
                            logger.info(
                                f"✅ Analytics refreshed and broadcast: {list(analytics_data.keys())}"
                            )
                    except Exception as e:
                        logger.error(f"❌ Error refreshing analytics: {e}")

                event_type = event.get("type", "")
                await self._handle_event(event)
                self.event_queue.task_done()

            except asyncio.TimeoutError:
                if processed_count % 100 == 0 and processed_count > 0:
                    logger.debug(
                        f"🔄 Event processor alive, processed {processed_count} events"
                    )
                continue
            except asyncio.CancelledError:
                logger.info("🛑 Event processor cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Event processing error: {e}")
                await asyncio.sleep(0.1)

        logger.info(
            f"🛑 Event processor stopped after processing {processed_count} events"
        )

    async def _handle_event(self, event: Dict[str, Any]):
        """Handle a single event with registered handlers"""
        try:
            event_type = event["type"]

            # Call registered handlers first
            if event_type in self.event_handlers:
                for handler in list(self.event_handlers[event_type]):
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event["data"])
                        else:
                            handler(event["data"])
                    except Exception as e:
                        logger.error(
                            f"❌ Error in registered handler for {event_type}: {e}"
                        )

            # Update cache
            await self._update_cache_for_event(event)

            # Broadcast to subscribed clients
            await self._broadcast_event(event)

        except Exception as e:
            logger.error(f"❌ Error handling event {event.get('type')}: {e}")

    # ========== Analytics update loops ==========
    async def _update_analytics(self):
        """Update analytics data periodically with optimized cycles"""
        cycle_count = 0
        while self.is_running:
            try:
                if self.analytics_service:
                    cycle_count += 1
                    if cycle_count % 6 == 0:
                        await self._calculate_all_analytics()
                        logger.info("🔄 Full analytics update cycle")
                    else:
                        await self._calculate_priority_analytics()
                        logger.debug("⚡ Priority analytics update cycle")
                else:
                    await self._calculate_basic_analytics()

                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Analytics update error: {e}")
                await asyncio.sleep(60)

    async def _calculate_all_analytics(self):
        """Calculate full analytics in background"""
        try:
            if not self.analytics_service:
                return

            import concurrent.futures

            def get_analytics():
                return self.analytics_service.get_complete_analytics()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                loop = asyncio.get_running_loop()
                complete_analytics = await loop.run_in_executor(
                    executor, get_analytics
                )

            self.analytics_cache = complete_analytics

            for feature, data in complete_analytics.items():
                if feature in ["generated_at", "cache_status", "processing_time_ms"]:
                    continue

                event_type = f"{feature}_update"
                if feature == "intraday_stocks" and isinstance(data, dict):
                    if "fno_candidates" in data:
                        logger.info(
                            f"📊 Broadcasting {len(data.get('fno_candidates', []))} FNO candidates"
                        )
                    if "all_candidates" in data:
                        logger.info(
                            f"📊 Broadcasting {len(data.get('all_candidates', []))} total candidates"
                        )

                self.emit_event(event_type, data, priority=3)
                await asyncio.sleep(0.001)

            logger.info("📊 All analytics calculated and emitted (non-blocking)")

        except Exception as e:
            logger.error(f"❌ Error calculating analytics: {e}")

    async def _calculate_priority_analytics(self):
        """Calculate priority analytics in background"""
        try:
            if not self.analytics_service:
                return

            import concurrent.futures

            def get_priority_analytics():
                return self.analytics_service.get_priority_analytics()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                loop = asyncio.get_running_loop()
                priority_analytics = await loop.run_in_executor(
                    executor, get_priority_analytics
                )

            self.analytics_cache.update(priority_analytics)

            for feature, data in priority_analytics.items():
                if feature in [
                    "generated_at",
                    "cache_status",
                    "processing_time_ms",
                    "is_priority_update",
                ]:
                    continue
                event_type = f"{feature}_update"
                priority = (
                    1
                    if feature in ["top_movers", "intraday_stocks", "volume_analysis"]
                    else 2
                )
                self.emit_event(event_type, data, priority=priority)
                await asyncio.sleep(0.0001)

            logger.debug("📊 Priority analytics calculated and emitted (non-blocking)")

        except Exception as e:
            logger.error(f"❌ Error calculating priority analytics: {e}")

    async def _process_pending_events(self):
        """Process rate-limited pending events periodically"""
        logger.info("⏰ Pending event processor started")
        while self.is_running:
            try:
                now = datetime.now()
                events_to_process = []
                for event_type, pending in list(self.pending_events.items()):
                    rate_limit = self.event_rate_limits.get(event_type, 1.0)
                    if event_type in self.last_event_time:
                        time_since_last = (
                            now - self.last_event_time[event_type]
                        ).total_seconds()
                        if time_since_last >= rate_limit:
                            events_to_process.append(event_type)
                    else:
                        events_to_process.append(event_type)

                for event_type in events_to_process:
                    if event_type in self.pending_events:
                        pending = self.pending_events.pop(event_type)
                        self.emit_event(
                            event_type, pending["data"], pending["priority"]
                        )
                        logger.debug(f"⏰ Processed pending event: {event_type}")

                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"❌ Pending event processor error: {e}")
                await asyncio.sleep(5)

    async def _calculate_basic_analytics(self):
        """Fallback basic analytics if enhanced service unavailable"""
        try:
            from services.instrument_registry import instrument_registry

            all_stocks = []
            excluded_symbols = {
                "NIFTY",
                "BANKNIFTY",
                "FINNIFTY",
                "SENSEX",
                "MIDCPNIFTY",
            }

            for symbol in instrument_registry._symbols_map:
                if symbol in excluded_symbols:
                    continue
                try:
                    price = instrument_registry.get_spot_price(symbol)
                    if price and price.get("last_price"):
                        processed_price = {
                            "symbol": symbol,
                            "last_price": safe_float(price.get("last_price")),
                            "change_percent": safe_float(price.get("change_percent")),
                            "volume": safe_float(price.get("volume")),
                            "high": safe_float(price.get("high")),
                            "low": safe_float(price.get("low")),
                            "open": safe_float(price.get("open")),
                            "close": safe_float(price.get("close")),
                        }
                        if processed_price["last_price"] > 0:
                            all_stocks.append(processed_price)
                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")
                    continue

            if not all_stocks:
                return

            gainers = sorted(
                [s for s in all_stocks if s.get("change_percent", 0) > 0],
                key=lambda x: x.get("change_percent", 0),
                reverse=True,
            )[:20]
            losers = sorted(
                [s for s in all_stocks if s.get("change_percent", 0) < 0],
                key=lambda x: x.get("change_percent", 0),
            )[:20]
            volume_leaders = sorted(
                all_stocks, key=lambda x: x.get("volume", 0), reverse=True
            )[:20]

            total_stocks = len(all_stocks)
            advancing = len([s for s in all_stocks if s.get("change_percent", 0) > 0])
            declining = len([s for s in all_stocks if s.get("change_percent", 0) < 0])

            sentiment_score = (
                (advancing - declining) / total_stocks if total_stocks > 0 else 0
            )
            sentiment = (
                "bullish"
                if sentiment_score > 0.1
                else "bearish" if sentiment_score < -0.1 else "neutral"
            )

            self.emit_event(
                "top_movers_update", {"gainers": gainers[:10], "losers": losers[:10]}
            )
            self.emit_event(
                "volume_analysis_update", {"volume_leaders": volume_leaders[:10]}
            )
            self.emit_event(
                "market_sentiment_update",
                {
                    "sentiment": sentiment,
                    "sentiment_score": sentiment_score,
                    "advancing": advancing,
                    "declining": declining,
                    "total": total_stocks,
                },
            )

        except Exception as e:
            logger.error(f"❌ Basic analytics calculation error: {e}")

    # ========== Cache management ==========
    async def _update_cache_for_event(self, event: Dict[str, Any]):
        """Update relevant caches based on event type"""
        try:
            event_type = event["type"]
            data = event["data"]
            if event_type == "price_update":
                if isinstance(data, dict):
                    self.live_prices.update(data)
            elif event_type.endswith("_update"):
                feature_name = event_type.replace("_update", "")
                self.analytics_cache[feature_name] = data
        except Exception as e:
            logger.error(f"❌ Cache update error: {e}")

    # ========== Broadcasting ==========
    async def _broadcast_event(self, event: Dict[str, Any]):
        """Broadcast event to subscribed clients"""
        event_type = event["type"]
        clients_to_notify = []
        for client_id, subscriptions in self.client_subscriptions.items():
            if event_type in subscriptions or "all" in subscriptions:
                clients_to_notify.append(client_id)

        if event_type in ["price_update", "dashboard_update", "live_prices_enriched"]:
            data_size = 0
            if isinstance(event.get("data"), dict):
                data_size = len(event["data"])
            elif isinstance(event.get("data"), list):
                data_size = len(event["data"])
            logger.info(
                f"⚡ Broadcasting {event_type} to {len(clients_to_notify)} clients (data: {data_size} items)"
            )

        if clients_to_notify:
            results = await asyncio.gather(
                *[
                    self.send_to_client(client_id, event)
                    for client_id in clients_to_notify
                ],
                return_exceptions=True,
            )
            successful_sends = sum(1 for result in results if result is True)
            if successful_sends == 0 and len(clients_to_notify) > 0:
                logger.warning(
                    f"⚠️ No clients received {event_type} (attempted {len(clients_to_notify)})"
                )
        elif event_type in ["price_update", "dashboard_update", "live_prices_enriched"]:
            logger.warning(
                f"⚠️ No clients subscribed to {event_type}! Available clients: {len(self.client_subscriptions)}"
            )
            if len(self.client_subscriptions) > 0:
                logger.info(
                    f"📋 Client subscriptions: {dict(self.client_subscriptions)}"
                )

    async def send_to_client(self, client_id: str, data: Dict[str, Any]) -> bool:
        """Send data to client with ultra-fast error handling"""
        if client_id not in self.connections:
            return False

        websocket = self.connections[client_id]

        try:
            await websocket.send_json(data)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Unexpected timeout for client {client_id}")
            await self.remove_client(client_id)
        except RuntimeError as e:
            if "not connected" in str(e).lower():
                logger.debug(f"🔌 Client {client_id} disconnected")
            else:
                logger.error(f"❌ Runtime error sending to {client_id}: {e}")
            await self.remove_client(client_id)
        except Exception as e:
            logger.error(f"❌ Failed to send to client {client_id}: {e}")
            await self.remove_client(client_id)
        return False

    async def _send_initial_data(self, client_id: str, client_type: str):
        """Send initial data based on client type"""
        if client_id not in self.connections:
            logger.warning(f"⚠️ Cannot send initial data: Client {client_id} not found")
            return

        websocket = self.connections[client_id]

        try:
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.warning(
                    f"⚠️ Cannot send initial data to {client_id}: WebSocket not connected"
                )
                return

            try:
                # Try to get analytics from enhanced service if available
                if self.analytics_service:
                    analytics_data = None
                    if hasattr(self.analytics_service, "get_complete_analytics"):
                        analytics_data = self.analytics_service.get_complete_analytics()
                    elif hasattr(self.analytics_service, "get"):
                        analytics_data = self.analytics_service.get(
                            "complete_analytics"
                        )

                    if isinstance(analytics_data, dict) and analytics_data:
                        await websocket.send_json(
                            {
                                "type": "initial_data",
                                "data": analytics_data,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        logger.info(f"📊 Sent initial analytics to {client_id}")
            except Exception as e:
                logger.error(f"❌ Error getting initial analytics: {e}")
                if self.analytics_cache:
                    try:
                        await websocket.send_json(
                            {
                                "type": "analytics_data",
                                "data": self.analytics_cache,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        logger.info(f"📊 Sent cached analytics to {client_id}")
                    except Exception as e:
                        logger.error(f"❌ Error sending cached analytics: {e}")

            if self.live_prices:
                try:
                    await websocket.send_json(
                        {
                            "type": "live_prices",
                            "data": self.live_prices,
                            "count": len(self.live_prices),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    logger.info(
                        f"📊 Sent live prices to {client_id} ({len(self.live_prices)} instruments)"
                    )
                except Exception as e:
                    logger.error(f"❌ Error sending live prices: {e}")
        except Exception as e:
            logger.error(f"❌ Error in _send_initial_data for {client_id}: {e}")

    # ========== Public helpers ==========
    def get_available_events(self) -> List[str]:
        return [
            "price_update",
            "dashboard_update",
            "index_update",
            "top_movers_update",
            "volume_analysis_update",
            "gap_analysis_update",
            "breakout_analysis_update",
            "market_sentiment_update",
            "heatmap_update",
            "intraday_stocks_update",
            "record_movers_update",
            "options_chain_update",
            "market_status_update",
            "live_prices_enriched",
            "auto_trading_update",
            "fibonacci_signal",
            "position_update",
            "performance_update",
            "system_status",
            "emergency_alert",
            "session_update",
            "fno_selection_update",
        ]

    def get_status(self) -> Dict[str, Any]:
        queue_size = self.event_queue.qsize()
        queue_percentage = (queue_size / self.event_queue.maxsize) * 100
        return {
            "is_running": self.is_running,
            "total_connections": len(self.connections),
            "client_types": dict(
                defaultdict(
                    int,
                    {
                        ct: sum(1 for t in self.client_types.values() if t == ct)
                        for ct in set(self.client_types.values())
                    },
                )
            ),
            "cached_analytics": list(self.analytics_cache.keys()),
            "live_prices_count": len(self.live_prices),
            "event_queue_size": queue_size,
            "event_queue_percentage": round(queue_percentage, 1),
            "queue_status": (
                "CRITICAL"
                if queue_percentage > 80
                else "WARNING" if queue_percentage > 60 else "OK"
            ),
            "background_tasks": len(self.background_tasks),
            "analytics_service_available": self.analytics_service is not None,
            "trading_mode": self.trading_mode,
            "emergency_mode": self.emergency_mode,
            "pending_events_count": len(self.pending_events),
            "rate_limits": self.event_rate_limits,
        }

    def enable_emergency_mode(self):
        self.emergency_mode = True
        logger.warning(
            "🚨 EMERGENCY MODE ENABLED - Rate limiting bypassed for all events"
        )

    def disable_emergency_mode(self):
        self.emergency_mode = False
        logger.info("✅ EMERGENCY MODE DISABLED - Normal rate limiting restored")

    def adjust_rate_limits(self, new_limits: Dict[str, float]):
        self.event_rate_limits.update(new_limits)
        logger.info(f"⚙️ Rate limits adjusted: {new_limits}")


# Singleton instance
unified_manager = UnifiedWebSocketManager()


# Integration helpers
def integrate_with_centralized_manager():
    try:
        from services.centralized_ws_manager import centralized_manager

        gap_service = None
        breakout_service = None
        try:
            from services.enhanced_breakout_engine import enhanced_breakout_engine

            breakout_service = enhanced_breakout_engine
            logger.info(
                "✅ Enhanced breakout engine loaded (gap detection via premarket_candle_builder)"
            )
        except ImportError as e:
            logger.warning(f"⚠️ Detection services not available: {e}")

        def price_update_callback(data):
            try:
                price_data = data.get("data", {})
                if price_data:
                    unified_manager.emit_event("price_update", price_data, priority=1)
                    unified_manager.emit_event(
                        "dashboard_update",
                        {
                            "type": "dashboard_update",
                            "data": price_data,
                            "market_open": data.get("market_open", True),
                            "timestamp": data.get(
                                "timestamp", datetime.now().isoformat()
                            ),
                        },
                        priority=1,
                    )
                    if gap_service or breakout_service:
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(
                                process_analytics_background(
                                    price_data, gap_service, breakout_service
                                )
                            )
                        except RuntimeError:
                            # No event loop is running, skip background analytics
                            logger.debug("⚠️ No event loop running, skipping background analytics")
                        except Exception as e:
                            logger.error(f"❌ Error creating background analytics task: {e}")
            except Exception as e:
                logger.error(f"❌ Error in real-time price update callback: {e}")

        async def process_analytics_background(
            price_data, gap_service, breakout_service
        ):
            try:
                if gap_service:
                    try:
                        new_gaps = gap_service.process_live_feed_data(price_data)
                        if new_gaps:
                            gap_signals_data = [
                                {
                                    "symbol": gap.symbol,
                                    "gap_type": gap.gap_type,
                                    "gap_percentage": round(gap.gap_percentage, 2),
                                    "open_price": gap.open_price,
                                    "previous_close": gap.previous_close,
                                    "current_price": gap.current_price,
                                    "volume_ratio": round(gap.volume_ratio, 1),
                                    "gap_strength": gap.gap_strength,
                                    "confidence_score": round(gap.confidence_score, 2),
                                    "sector": gap.sector,
                                    "timestamp": gap.timestamp.isoformat(),
                                }
                                for gap in new_gaps
                            ]
                            unified_manager.emit_event(
                                "gap_signals_update",
                                {
                                    "signals": gap_signals_data,
                                    "count": len(gap_signals_data),
                                    "market_open_time": "09:15:00",
                                    "timestamp": datetime.now().isoformat(),
                                },
                                priority=2,
                            )
                            logger.info(
                                f"🚨 Background processed {len(new_gaps)} gap signals"
                            )
                    except Exception as e:
                        logger.error(f"❌ Error in background gap detection: {e}")

                logger.debug("📊 Background market data processing completed")

            except Exception as e:
                logger.error(f"❌ Error in background analytics processing: {e}")

        try:
            centralized_manager.register_callback("price_update", price_update_callback)
            logger.info(
                "✅ CRITICAL FIX: Price update callback registered with centralized manager"
            )
        except Exception as e:
            logger.error(f"❌ Failed to register price update callback: {e}")

        try:

            def market_status_callback(data):
                try:
                    unified_manager.emit_event("market_status_update", data, priority=2)
                except Exception as e:
                    logger.error(f"❌ Error in market status callback: {e}")

            centralized_manager.register_callback(
                "market_status", market_status_callback
            )
            logger.info("✅ Market status callback registered with centralized manager")
        except Exception as e:
            logger.error(f"❌ Failed to register market status callback: {e}")

        logger.info("✅ Integration with centralized manager completed successfully")

    except ImportError:
        logger.warning("⚠️ Centralized manager not available")
    except Exception as e:
        logger.error(f"❌ Integration error: {e}")


# Convenience functions
async def start_unified_websocket():
    try:
        await unified_manager.start()
        logger.info("✅ Unified WebSocket system started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start unified WebSocket: {e}")


async def stop_unified_websocket():
    try:
        await unified_manager.stop()
        logger.info("✅ Unified WebSocket system stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping unified WebSocket: {e}")


def emit_market_event(event_type: str, data: Dict[str, Any]):
    try:
        unified_manager.emit_event(event_type, data)
    except Exception as e:
        logger.error(f"❌ Error emitting event {event_type}: {e}")
