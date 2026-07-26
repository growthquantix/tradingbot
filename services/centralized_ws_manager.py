"""
Centralized WebSocket Manager for Trading System

This module implements a singleton WebSocket manager that maintains ONE
persistent connection to Upstox using admin token and forwards processed
data to backend services. This service does NOT handle UI WebSocket connections.

Architecture:
- Single admin WebSocket connection to Upstox
- Receives and processes live market feed data
- Forwards processed data to backend services via callbacks
- NO direct UI WebSocket broadcasting (handled by other services)

Responsibilities:
1. Manage admin token and WebSocket connection lifecycle
2. Subscribe to instrument keys and receive market data
3. Process and normalize incoming Upstox feed format
4. Forward data to realtime_market_engine and other services
5. Handle reconnection strategy and token refresh automation
"""

import asyncio
import json
import logging
import os
import time as time_module
import traceback
from datetime import datetime, timedelta, time
from decimal import Decimal
from typing import Dict, Set, List, Optional, Callable, Any, Union
import aiohttp
import sqlalchemy.exc
from core.config import ADMIN_EMAIL
from utils.logging_utils import log_structured

logger = logging.getLogger(__name__)

# Import Redis manager with error handling
try:
    from services.trading_redis_manager import TradingSafeRedisManager

    redis_manager = TradingSafeRedisManager()
except ImportError as e:
    logger.warning(f"⚠️ Redis manager not available: {e}")
    redis_manager = None


# Import instrument service with proper error handling
def get_instrument_service():
    """Safely get instrument service instance"""
    try:
        from services.instrument_refresh_service import get_trading_service

        return get_trading_service()
    except ImportError:
        return None


# Import WebSocket client with fallback
try:
    from services.upstox.ws_client import UpstoxWebSocketClient
except ImportError:
    logger.warning("⚠️ UpstoxWebSocketClient not available - using dummy implementation")

    class UpstoxWebSocketClient:
        def __init__(self, **kwargs):
            self.is_connected = False

        async def connect_and_stream(self):
            pass

        def stop(self):
            pass

        def is_connected(self):
            return False


# Import database functions with error handling
try:
    from database.connection import get_db
    from database.models import BrokerConfig, User
except ImportError:
    logger.warning("⚠️ Database models not available - using dummy implementations")

    def get_db():
        yield None

    class BrokerConfig:
        pass

    class User:
        pass


# Import email service with error handling
try:
    from services.email.email_service import email_service
except ImportError:
    logger.warning("⚠️ Email service not available")

    class DummyEmailService:
        def send_notification(self, *args, **kwargs):
            return False

    email_service = DummyEmailService()

# Callback type definition
CallbackFunction = Callable[[Dict[str, Any]], Any]


class _ConnectionReadyProxy:
    """Proxy for asyncio.Event that works across different event loops"""
    def __init__(self, manager):
        self._manager = manager

    def set(self):
        self._manager._update_connection_ready(True)

    def clear(self):
        self._manager._update_connection_ready(False)

    def is_set(self):
        return self._manager._is_connection_ready

    async def wait(self):
        loop = asyncio.get_running_loop()
        event = self._manager._get_event_for_loop(loop)
        await event.wait()


class CentralizedWebSocketManager:
    """
    Singleton WebSocket manager for centralized Upstox market data feed.

    This service maintains a single persistent WebSocket connection to Upstox
    using admin credentials and forwards processed market data to backend services.
    It does NOT handle UI WebSocket connections or broadcasting to frontend clients.

    Architecture:
    - Single admin WebSocket connection to Upstox (using admin token)
    - Receives live market feed for up to 1500 instruments
    - Processes and normalizes Upstox feed format
    - Forwards data to realtime_market_engine for analytics
    - Notifies registered backend services via callbacks
    - Handles token refresh automation and reconnection strategies

    Key Responsibilities:
    1. Admin Token Management:
       - Load and validate admin token from database
       - Automated token refresh when expired
       - Token expiry monitoring and proactive refresh

    2. WebSocket Connection Management:
       - Single persistent connection to Upstox
       - Automatic reconnection with exponential backoff
       - Network connectivity monitoring
       - Connection health tracking

    3. Market Data Processing:
       - Subscribe to instrument keys (NSE equity, indices, F&O)
       - Receive and parse Upstox feed format
       - Normalize data to standard format
       - Extract LTPC, OHLC, volume, bid/ask data

    4. Service Integration:
       - Forward data to realtime_market_engine
       - Execute registered callbacks for other services
       - Track performance metrics
       - NO direct UI WebSocket broadcasting

    5. Error Handling & Monitoring:
       - Comprehensive error logging
       - Email alerts for critical failures
       - Performance metrics tracking
       - Health check endpoints

    Usage Example:
        # Get singleton instance
        manager = get_centralized_manager()

        # Initialize and start
        await manager.initialize()
        await manager.start_connection()

        # Register callback for market data
        def my_callback(data: dict):
            print(f"Received data: {data}")
        manager.register_market_data_callback(my_callback)

        # Stop connection
        await manager.stop()

    Thread Safety:
        This is a singleton class. Multiple calls to the constructor
        return the same instance. Safe for concurrent access.

    Note:
        This service does NOT broadcast to UI WebSocket connections.
        UI broadcasting is handled by unified_websocket_manager.py
        and other UI-specific services.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Connection state
        self.admin_token: Optional[str] = None
        self.admin_user_id: Optional[int] = None
        self.ws_client: Optional[UpstoxWebSocketClient] = None
        self.is_running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.last_connection_attempt = None
        self.last_websocket_url = None
        self._shutdown_scheduled = False

        # Startup flag to prevent token refresh during server startup
        self._is_startup_phase = True

        # Subscription management
        self.all_instrument_keys: Set[str] = set()
        self.active_instrument_keys: Set[str] = set()
        self.primary_instruments: Set[str] = set()
        self._is_connection_ready = False
        self._connection_ready_events = {}

        # Auto-trading specific subscriptions
        self.fno_stocks_keys: Set[str] = set()
        self.priority_instruments: Set[str] = (
            set()
        )  # High-frequency updates for selected stocks
        self.auto_trading_active = False
        self.selected_stocks_for_trading: Dict[str, Dict] = {}  # symbol -> metadata

        # Data caching
        self.market_data_cache: Dict[str, dict] = {}
        self.market_status = "unknown"
        self.market_segment_status = {}
        self.market_phases = {}
        self.active_segments = []
        self.all_markets_closed = True
        self.last_data_received = None
        self.data_count = 0
        self.update_count = 0

        self.background_tasks = set()

        # Callback management for backend services
        self.callbacks: Dict[str, List[CallbackFunction]] = {}

        # Performance metrics
        self.performance_metrics: Dict[str, int] = {
            "callbacks_executed": 0,
            "data_updates_processed": 0,
            "errors_encountered": 0,
            "reconnection_count": 0,
        }

        self._is_refreshing = False  # Track refresh status

        # Initialize market data service
        self._initialized = True
        logger.info("Centralized WebSocket manager initialized")

    @property
    def connection_ready(self):
        """Returns a proxy for connection_ready that is loop-aware and cross-loop synced"""
        return _ConnectionReadyProxy(self)

    def _get_event_for_loop(self, loop):
        """Get or create an asyncio.Event for a specific loop, synced with master flag"""
        # Store the event directly on the loop object for absolute safety
        if not hasattr(loop, '_centralized_ws_conn_ready_event'):
            event = asyncio.Event()
            if self._is_connection_ready:
                event.set()
            loop._centralized_ws_conn_ready_event = event
            
            # Also keep track of it for broadcasting updates
            self._connection_ready_events[id(loop)] = event
            
        return loop._centralized_ws_conn_ready_event

    def _update_connection_ready(self, value: bool):
        """Update the connection ready status across all event loops"""
        self._is_connection_ready = value
        # Clean up closed loops and update active ones
        for loop_id, event in list(self._connection_ready_events.items()):
            try:
                # We can't check loop.is_closed() easily from ID, 
                # but the event itself will be garbage collected if the loop is
                if value:
                    event.set()
                else:
                    event.clear()
            except Exception:
                pass

    async def initialize(self) -> bool:
        """
        Initialize the centralized WebSocket manager.

        This method loads the admin token from database, loads instrument keys,
        and prepares the manager for WebSocket connection. It also loads
        the latest market snapshot for quick data availability.

        Initialization Steps:
        1. Reset connection state
        2. Load admin token from database with validation
        3. Load instrument keys (NSE stocks, indices, F&O)
        4. Load market snapshot from Redis/file cache
        5. Determine market hours and decide connection strategy
        6. Start WebSocket connection if market is open

        Returns:
            True if initialization successful, False otherwise

        Raises:
            No exceptions raised - errors are logged and False is returned

        Note:
            This method should be called before start_connection().
            It's safe to call multiple times - will reinitialize state.
        """
        try:
            logger.info("🔧 Initializing Centralized WebSocket manager...")
            log_structured(event="WS_MANAGER_INIT_START", message="Initializing Centralized WebSocket Manager")

            # Reset connection event and shutdown flag
            self.connection_ready.clear()
            self._shutdown_scheduled = False

            # Load admin token
            if not await self._load_admin_token():
                logger.error("❌ Failed to load admin token")
                log_structured(event="WS_MANAGER_INIT_FAILED", level="ERROR", message="Failed to load admin token")
                return False

            # Load instrument keys
            await self._load_instrument_keys()

            # Verify we have keys
            if not self.all_instrument_keys:
                logger.error(
                    "❌ No instrument keys loaded - WebSocket initialization failed"
                )
                log_structured(event="WS_MANAGER_INIT_FAILED", level="ERROR", message="No instrument keys loaded")
                return False

            logger.info(f"✅ Loaded {len(self.all_instrument_keys)} instrument keys")

            # Load the latest market snapshot
            snapshot_loaded = await self._load_market_snapshot()

            # Determine market hours using IST timezone for accuracy
            import pytz
            ist = pytz.timezone("Asia/Kolkata")
            now_ist = datetime.now(ist)
            current_time = now_ist.time()
            current_day = now_ist.weekday()

            pre_market_start = time(9, 0)   # 9:00 AM IST - Pre-open starts
            market_close = time(15, 30)     # 3:30 PM IST - Market closes

            market_should_be_open = (
                current_day < 5  # Weekday check (Monday=0, Friday=4)
                and current_time >= pre_market_start
                and current_time <= market_close
            )

            # Update connection status
            self.is_running = True
            logger.info(
                f"✅ Centralized WebSocket manager initialized with {len(self.all_instrument_keys)} instruments"
            )
            
            log_structured(
                event="WS_MANAGER_INIT_COMPLETE", 
                message=f"Initialized with {len(self.all_instrument_keys)} instruments",
                data={"instrument_count": len(self.all_instrument_keys), "market_open": market_should_be_open}
            )

            # Stop existing connection if any
            if (
                self.ws_client
                and hasattr(self.ws_client, "is_connected")
                and self.ws_client.is_connected()
            ):
                logger.info("🔄 Restarting existing WebSocket connection with new keys")
                self.ws_client.stop()

            # CRITICAL FIX: ALWAYS start market open scheduler for automatic connections
            # This ensures WebSocket connects at 9:00 AM and 9:15 AM automatically
            logger.info("🕐 Starting market open scheduler for auto-connect at market hours")
            self._schedule_market_open_check()

            # Start connection immediately if market is currently open
            if market_should_be_open:
                logger.info("🔄 Market is currently open - starting WebSocket connection immediately")
                task = asyncio.create_task(self._maintain_connection())
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
            else:
                logger.info(
                    f"💤 Market is currently closed (IST time: {current_time.strftime('%H:%M:%S')}) - scheduler will auto-connect at 9:00 AM IST"
                )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize centralized manager: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            log_structured(event="WS_MANAGER_INIT_ERROR", level="ERROR", message=str(e))
            return False

    async def _validate_token_expiry(self, broker_config) -> dict:
        """Validate token expiry and return detailed status"""
        try:
            now = datetime.now()
            expiry = broker_config.access_token_expiry

            if not expiry:
                return {
                    "valid": False,
                    "reason": "no_expiry_info",
                    "message": "Token expiry information not available",
                }

            if expiry <= now:
                minutes_expired = int((now - expiry).total_seconds() / 60)
                return {
                    "valid": False,
                    "reason": "expired",
                    "message": f"Token expired {minutes_expired} minutes ago",
                    "expired_minutes": minutes_expired,
                }

            minutes_until_expiry = int((expiry - now).total_seconds() / 60)

            if minutes_until_expiry <= 10:
                return {
                    "valid": False,
                    "reason": "expiring_soon",
                    "message": f"Token expires in {minutes_until_expiry} minutes",
                    "minutes_remaining": minutes_until_expiry,
                }

            return {
                "valid": True,
                "reason": "valid",
                "message": f"Token valid for {minutes_until_expiry} minutes",
                "minutes_remaining": minutes_until_expiry,
            }

        except Exception as e:
            return {
                "valid": False,
                "reason": "validation_error",
                "message": f"Error validating token: {str(e)}",
            }

    async def _load_admin_token(self) -> bool:
        """Load admin token from database with retry logic"""
        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                db = next(get_db())
                if db is None:
                    logger.error("❌ Database not available")
                    if attempt < max_retries - 1:
                        logger.info(
                            f"🔄 Retrying database connection in {retry_delay}s (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    return False

                # Find admin user with Upstox broker config
                admin_broker = (
                    db.query(BrokerConfig)
                    .join(User, BrokerConfig.user_id == User.id)
                    .filter(
                        User.role == "admin",
                        BrokerConfig.broker_name.ilike("upstox"),
                        BrokerConfig.access_token.isnot(None),
                    )
                    .first()
                )

                if not admin_broker:
                    logger.error("❌ No admin user with Upstox access token found!")
                    return False

                # Validate token format
                token = admin_broker.access_token
                if not token or len(token.strip()) < 20:
                    logger.error(
                        f"❌ Invalid token format in database (length: {len(token) if token else 0})"
                    )
                    return False

                # Validate token expiry BEFORE storing
                validation_result = await self._validate_token_expiry(admin_broker)

                # If token is expired or expiring soon, schedule background refresh
                # CRITICAL FIX: NEVER block on token refresh during token loading
                if not validation_result["valid"] and validation_result["reason"] in [
                    "expired",
                    "expiring_soon",
                ]:
                    reason = validation_result["reason"]
                    message = validation_result["message"]

                    if reason == "expired":
                        logger.warning(f"⚠️ Admin token expired: {message}")
                    elif reason == "expiring_soon":
                        logger.warning(f"⚠️ Admin token expiring soon: {message}")

                    # CRITICAL FIX: SKIP token refresh during startup phase to prevent blocking
                    if self._is_startup_phase:
                        logger.info(
                            f"🔧 STARTUP MODE: Token refresh skipped during startup - {reason} token will be refreshed after startup completes"
                        )
                        self._needs_token_refresh = True
                    else:
                        logger.info(
                            f"🤖 Scheduling background token refresh for {reason} token..."
                        )
                        self._needs_token_refresh = True

                        # Schedule refresh in background WITHOUT blocking
                        try:
                            # This will return immediately without blocking
                            await self._try_automated_refresh()
                            logger.info(
                                "✅ Token refresh scheduled in background - continuing with current token"
                            )
                        except Exception as refresh_error:
                            logger.error(
                                f"❌ Error scheduling background token refresh: {refresh_error}"
                            )

                    # ALWAYS continue with the current token (even if expired)
                    # The background refresh will reload it when ready
                    # This ensures we NEVER block the application startup or connection attempts

                # Store token and user ID (only reached if valid OR refresh failed)
                self.admin_token = token.strip()
                self.admin_user_id = admin_broker.user_id
                self._token_validation_status = validation_result

                # Log with masked token for security
                token_preview = (
                    f"{self.admin_token[:5]}...{self.admin_token[-5:]}"
                    if len(self.admin_token) > 10
                    else "***"
                )

                if validation_result["valid"]:
                    logger.info(
                        f"✅ Admin token loaded for user ID: {self.admin_user_id} - Token: {token_preview}"
                    )
                    logger.info(f"ℹ️ {validation_result['message']}")
                else:
                    reason = validation_result["reason"]
                    message = validation_result["message"]
                    logger.info(
                        f"⚠️ Admin token loaded with issues for user ID: {self.admin_user_id} - {message}"
                    )

                # Set automation trigger flag for future cycles
                if not validation_result["valid"] and validation_result["reason"] in [
                    "expired",
                    "expiring_soon",
                ]:
                    self._needs_token_refresh = True
                    if validation_result["reason"] == "expired":
                        logger.info("🔄 Token expired but loaded for refresh attempt")
                else:
                    self._needs_token_refresh = False

                return True

            except (
                sqlalchemy.exc.TimeoutError,
                sqlalchemy.exc.OperationalError,
            ) as db_error:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Database connection failed (attempt {attempt + 1}/{max_retries}): {db_error}"
                    )
                    logger.info(f"🔄 Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(
                        f"❌ Database connection failed after {max_retries} attempts: {db_error}"
                    )
                    return False

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Token loading failed (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    logger.info(f"🔄 Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(
                        f"❌ Failed to load admin token after {max_retries} attempts: {e}"
                    )
                    traceback.print_exc()
                    return False

        logger.error(f"❌ Failed to load admin token after {max_retries} attempts")
        return False

    async def _try_automated_refresh(self) -> bool:
        """
        Attempt automated token refresh using the automation service
        CRITICAL FIX: This now runs in background WITHOUT blocking
        """
        try:
            # Check if refresh is already in progress to prevent spamming
            if getattr(self, "_is_refreshing", False):
                logger.info("⚠️ Token refresh already in progress - skipping duplicate background request")
                return False

            logger.info("🤖 Scheduling automated token refresh in background...")
            self._is_refreshing = True

            # Import automation service dynamically to avoid circular imports
            from services.upstox_automation_service import UpstoxAutomationService

            # CRITICAL FIX: Run token refresh in background task
            # Do NOT await it - let it run asynchronously
            automation_service = UpstoxAutomationService()

            async def background_refresh():
                """Background task for token refresh"""
                try:
                    logger.info("🔄 Background token refresh starting...")
                    result = await automation_service.refresh_admin_upstox_token(
                        emergency_bypass=True
                    )

                    if result.get("success", False):
                        logger.info("✅ Background token refresh completed successfully")
                        # Wait for database update
                        await asyncio.sleep(2)
                        # Reload token
                        await self._load_admin_token()
                        logger.info("✅ Token reloaded after background refresh")
                    else:
                        error_msg = result.get("error", "Unknown error")
                        logger.warning(f"⚠️ Background token refresh failed: {error_msg}")
                except Exception as e:
                    logger.error(f"❌ Background token refresh error: {e}")
                finally:
                    # Reset refreshing flag
                    self._is_refreshing = False

            # CRITICAL FIX: Create background task WITHOUT awaiting
            asyncio.create_task(background_refresh())
            logger.info("✅ Token refresh scheduled in background - NOT blocking connection")

            # Return False immediately to indicate we didn't wait for refresh
            # This allows WebSocket connection to proceed with existing token
            return False

        except Exception as e:
            logger.error(f"❌ Error scheduling token refresh: {e}")
            self._is_refreshing = False
            return False

    async def _validate_and_refresh_token(self) -> bool:
        """Proactively validate token and refresh if needed"""
        try:
            if not self.admin_token:
                logger.warning("⚠️ No admin token available, loading...")
                return await self._load_admin_token()

            # Check token expiry from database
            from database.connection import SessionLocal
            from database.models import BrokerConfig
            from core.config import ADMIN_EMAIL

            with SessionLocal() as db:
                # Build base query with explicit join with user and broker_config
                q = db.query(BrokerConfig).join(User, BrokerConfig.user_id == User.id)

                admin_user = q.filter(
                    User.role == "admin",
                    BrokerConfig.broker_name.ilike("upstox"),
                    BrokerConfig.access_token.isnot(None),
                ).first()

                if not admin_user or not admin_user.access_token_expiry:
                    logger.warning("⚠️ No admin broker config found")
                    return await self._load_admin_token()

                # Check if token is expired or expires soon (within 10 minutes)
                from datetime import datetime, timedelta

                now = datetime.now()
                buffer_time = timedelta(minutes=10)

                if admin_user.access_token_expiry <= (now + buffer_time):
                    logger.info(
                        f"🔄 Token expires soon ({admin_user.access_token_expiry}), scheduling background refresh..."
                    )

                    # CRITICAL FIX: Schedule refresh in background WITHOUT blocking
                    await self._try_automated_refresh()
                    logger.info("✅ Background token refresh scheduled - continuing with current token")

                    # CRITICAL FIX: Return True to allow connection to proceed
                    # The background task will handle the refresh
                    return True

                logger.debug(f"✅ Token valid until {admin_user.access_token_expiry}")
                return True

        except Exception as e:
            logger.error(f"❌ Error validating token: {e}")
            return False

    async def reload_admin_token(self) -> bool:
        """
        Reload admin token after successful refresh
        This method should be called by the automation service after token refresh
        """
        try:
            logger.info("🔄 Reloading admin token after successful refresh...")

            # Clear current token
            old_token = self.admin_token
            self.admin_token = None
            self.admin_user_id = None

            # Load fresh token from database
            token_loaded = await self._load_admin_token()

            if token_loaded and self.admin_token != old_token:
                logger.info("✅ Admin token successfully reloaded with new value")

                # Stop existing WebSocket connection if any
                if self.ws_client:
                    logger.info(
                        "🔄 Stopping existing WebSocket connection to use new token..."
                    )
                    self.ws_client.stop()

                # Clear connection ready flag to trigger reconnection
                self.connection_ready.clear()

                # Reset reconnect attempts to allow fresh connection with new token
                self.reconnect_attempts = 0

                # Start fresh connection with new token
                await self.start_connection()

                return True
            elif token_loaded:
                logger.warning("⚠️ Token reloaded but value unchanged")
                return True
            else:
                logger.error("❌ Failed to reload admin token")
                return False

        except Exception as e:
            logger.error(f"❌ Error reloading admin token: {e}")
            return False

    async def force_reconnect(self) -> bool:
        """
        Force reconnection with current token - useful after token refresh
        """
        try:
            logger.info("🔄 Forcing WebSocket reconnection...")

            # Stop existing connection
            if self.ws_client:
                self.ws_client.stop()

            # Clear connection state
            self.connection_ready.clear()
            self.reconnect_attempts = 0

            # Wait a moment for cleanup
            await asyncio.sleep(1)

            # Start fresh connection
            await self.start_connection()

            logger.info("✅ Force reconnection initiated")
            return True

        except Exception as e:
            logger.error(f"❌ Error during force reconnection: {e}")
            return False

    async def _load_instrument_keys(self):
        """Load instrument keys - CLEAN & SIMPLE approach with service initialization"""
        try:
            logger.info("🔄 Loading focused instrument keys...")

            # Use existing WebSocket keys function
            from services.instrument_refresh_service import (
                get_trading_service,
                get_websocket_keys,
            )

            service = get_trading_service()
            if not getattr(service, "_service_initialized", False):
                logger.info("🔧 Initializing instrument service for WebSocket...")
                try:
                    init_result = await service.initialize_service()
                    logger.info(
                        f"✅ Service initialization: {init_result.status if hasattr(init_result, 'status') else 'completed'}"
                    )
                except Exception as init_error:
                    logger.warning(
                        f"⚠️ Service initialization failed, continuing with available data: {init_error}"
                    )

            # Get WebSocket keys using your existing function
            websocket_keys = await get_websocket_keys(
                max_keys=int(os.getenv("MAX_WEBSOCKET_INSTRUMENTS", 1500))
            )

            if websocket_keys:
                self.all_instrument_keys = set(websocket_keys)

                # Simple logging
                total = len(self.all_instrument_keys)

                logger.info(f"✅ Loaded {total} WebSocket instrument keys")
                logger.info(
                    f"   📈 NSE instruments ready for subscription (MCX handled by dedicated service)"
                )

                return True
            else:
                logger.error("❌ Failed to load WebSocket instrument keys")
                # Simple fallback
                return await self._load_fallback_keys()

        except Exception as e:
            logger.error(f"❌ Error loading instrument keys: {e}")
            return await self._load_fallback_keys()

    async def _load_fallback_keys(self):
        """Simple fallback implementation"""
        try:
            # Use your existing service functions for fallback
            from services.instrument_refresh_service import get_trading_service

            service = get_trading_service()
            if not service:
                logger.error("❌ Trading service not available")
                return False

            # Try to get NSE keys as fallback
            nse_keys = await service._load_nse_stock_keys()
            if nse_keys:
                self.all_instrument_keys = set(nse_keys[:500])  # Limit for fallback
                logger.info(f"✅ Fallback loaded {len(nse_keys)} NSE keys")
                return True

            # Emergency fallback - Include FNO stocks and indices
            from services.fno_stock_service import get_fno_stocks_from_file

            emergency_keys = [
                # Core Indices
                "NSE_INDEX|Nifty 50",
                "NSE_INDEX|Nifty Bank",
                "NSE_INDEX|Nifty Fin Service",
                "BSE_INDEX|SENSEX",
                # Major Sectoral Indices
                "NSE_INDEX|Nifty Auto",
                "NSE_INDEX|Nifty IT",
                "NSE_INDEX|Nifty Pharma",
                "NSE_INDEX|Nifty FMCG",
                "NSE_INDEX|Nifty Metal",
                "NSE_INDEX|Nifty Realty",
                "NSE_INDEX|Nifty Media",
                "NSE_INDEX|Nifty PSU Bank",
                "NSE_INDEX|Nifty Pvt Bank",
                "NSE_INDEX|Nifty Oil & Gas",
                "NSE_INDEX|NIFTY CONSR DURBL",
                "NSE_INDEX|NIFTY HEALTHCARE",
            ]

            # Add top FNO stocks for better data coverage
            try:
                fno_stocks = get_fno_stocks_from_file()
                if fno_stocks:
                    # Add top 50 FNO stocks by volume/activity
                    top_fno = [
                        stock
                        for stock in fno_stocks
                        if stock.get("symbol") and stock.get("exchange") == "NSE"
                    ][:50]
                    for stock in top_fno:
                        if stock.get("symbol"):
                            # Use NSE_EQ format for equity stocks
                            emergency_keys.append(f"NSE_EQ|{stock['symbol']}")

                    logger.info(
                        f"✅ Added {len(top_fno)} top FNO stocks to emergency fallback"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Could not load FNO stocks for fallback: {e}")

            self.all_instrument_keys = set(emergency_keys)
            logger.warning(
                f"⚠️ Emergency fallback: {len(self.all_instrument_keys)} keys (indices + FNO stocks)"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Fallback failed: {e}")
            return False

    async def start_connection(self):
        """Start the centralized WebSocket connection"""
        # CRITICAL FIX: Run initialization in background to prevent blocking
        if not self.is_running:
            # Create background task for initialization
            async def initialize_and_connect():
                try:
                    if not await self.initialize():
                        logger.error("❌ Failed to initialize manager, cannot start connection")
                        return

                    # Reset for fresh start
                    self.reconnect_attempts = 0
                    self.last_connection_attempt = datetime.now()

                    # Start connection loop
                    await self._maintain_connection()
                except Exception as e:
                    logger.error(f"❌ Error in initialization and connection: {e}")

            # Start in background - don't block
            task = asyncio.create_task(initialize_and_connect())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)
        else:
            # Already running, just start maintain connection
            # Reset for fresh start
            self.reconnect_attempts = 0
            self.last_connection_attempt = datetime.now()

            # Start connection in background task
            task = asyncio.create_task(self._maintain_connection())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        logger.info("🚀 Centralized WebSocket connection starting in background...")
        return True

    async def subscribe_instruments(self, instrument_keys: List[str]) -> bool:
        """
        Dynamically subscribe to additional instrument keys.
        
        Args:
            instrument_keys: List of instrument keys to subscribe to
            
        Returns:
            True if successful, False otherwise
        """
        if not instrument_keys:
            return True
            
        try:
            logger.info(f"➕ Dynamically adding {len(instrument_keys)} instruments to subscription")
            
            # Add to set of all keys
            self.all_instrument_keys.update(instrument_keys)
            
            # If client is running, update its subscription
            if self.ws_client and self.ws_client.is_connected():
                # Get current keys + new keys (limited to 3000 max for safety)
                # Upstox limit is technically higher but safer to batch or restart
                current_keys = list(self.all_instrument_keys)
                
                # Option 1: If client supports dynamic update (check UpstoxWebSocketClient implementation)
                # For now, we'll use the 'restart' strategy if keys change significantly,
                # or just add them if the client supports it.
                # Assuming standard client needs restart for new keys or has a subscribe method.
                
                # Check if client has subscribe method
                if hasattr(self.ws_client, 'subscribe'):
                    self.ws_client.subscribe(instrument_keys)
                    logger.info("✅ Subscribed to new keys dynamically")
                else:
                    logger.info("🔄 Restarting WebSocket to apply new subscriptions")
                    # Stop and it will auto-reconnect with new keys via _maintain_connection
                    self.ws_client.stop() 
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to instruments: {e}")
            return False

    async def _check_network_connectivity(self) -> bool:
        """Check if basic network connectivity is available with multiple fallbacks"""
        test_urls = [
            "https://api.upstox.com",  # Primary broker API
            "https://www.google.com",  # Google DNS
            "https://1.1.1.1",  # Cloudflare DNS
            "https://httpbin.org/status/200",  # HTTP testing service
        ]

        for url in test_urls:
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            logger.debug(f"✅ Network connectivity confirmed via {url}")
                            return True
            except Exception as e:
                logger.debug(f"⚠️ Connectivity check failed for {url}: {e}")
                continue

        logger.warning("⚠️ All network connectivity checks failed")
        return False

    async def _maintain_connection(self):
        """Maintain WebSocket connection with auto-reconnect"""
        while self.is_running and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                # Check network connectivity
                if not await self._check_network_connectivity():
                    logger.warning(
                        "⚠️ Network connectivity issues detected - waiting before retry"
                    )
                    await asyncio.sleep(60)
                    continue

                # Refresh admin token if needed
                if self.reconnect_attempts > 0:
                    await self._load_admin_token()

                # Start WebSocket client
                await self._start_ws_client()

                # Wait for connection to end
                await asyncio.sleep(
                    3600
                )  # Long sleep, will be interrupted by exceptions

            except asyncio.CancelledError:
                logger.info("🛑 Connection maintenance task cancelled")
                break

            except Exception as e:
                self.reconnect_attempts += 1
                logger.error(f"❌ WebSocket connection failed: {e}")

                # Reset connection event
                self.connection_ready.clear()

                if self.reconnect_attempts < self.max_reconnect_attempts:
                    backoff_delay = min(
                        5 * (2**self.reconnect_attempts), 300
                    )  # Max 5 minutes
                    logger.info(
                        f"Reconnecting in {backoff_delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
                    )

                    # Enhanced reconnection recovery strategies
                    await self._apply_reconnection_strategy()

                    # Send warning email if approaching max attempts
                    if self.reconnect_attempts == self.max_reconnect_attempts - 2:
                        await self._send_reconnection_warning_email()

                    await asyncio.sleep(backoff_delay)

                    # Update performance metrics
                    self.performance_metrics["reconnection_count"] = (
                        self.reconnect_attempts
                    )
                else:
                    logger.error("Max reconnection attempts reached")
                    self.is_running = False
                    await self._send_max_reconnections_email()

    async def _start_ws_client(self):
        """Start the actual WebSocket client"""
        try:
            # Validate and refresh token before starting connection
            await self._validate_and_refresh_token()

            # Stop existing client
            if self.ws_client:
                self.ws_client.stop()

            # Limit instrument keys to Upstox maximum (~1500)
            active_keys = list(self.all_instrument_keys)
            if len(active_keys) > 1500:
                active_keys = active_keys[:1500]
                logger.warning(
                    f"⚠️ Limited to 1500 instruments (from {len(self.all_instrument_keys)})"
                )

            self.active_instrument_keys = set(active_keys)

            # Create client
            self.ws_client = UpstoxWebSocketClient(
                access_token=self.admin_token,
                instrument_keys=active_keys,
                callback=self._handle_market_data,
                stop_callback=self._handle_connection_stop,
                on_auth_error=self._handle_auth_error,
                connection_type="centralized_admin",
                subscription_mode="full",
                max_retries=3,
            )

            # Reset data count
            self.data_count = 0
            self.last_connection_attempt = datetime.now()
            logger.info(
                f"🔌 Starting WebSocket connection with {len(active_keys)} instruments"
            )

            # Clear connection ready event
            self.connection_ready.clear()

            # Start streaming (this will block until connection completes or fails)
            logger.info(
                "🔌 Attempting to connect to Upstox WebSocket... (this runs in background)"
            )
            await self.ws_client.connect_and_stream()

        except Exception as e:
            error_message = str(e)

            # Check if it's a network connectivity issue
            is_network_error = any(
                keyword in error_message.lower()
                for keyword in [
                    "getaddrinfo failed",
                    "name resolution",
                    "connection refused",
                    "timeout",
                    "network",
                ]
            )

            if is_network_error:
                logger.error(f"🌐 Network connectivity error: {error_message[:150]}")
                logger.warning("⚠️ Unable to reach Upstox servers - network may be down")
                logger.info(
                    "ℹ️ Application will continue running. WebSocket will retry automatically when network is restored."
                )
            else:
                logger.error(f"❌ Failed to start WebSocket client: {e}")
            raise

    async def _broadcast_connection_status(self, status_data: dict) -> None:
        """
        Log connection status changes for monitoring purposes.

        This method logs connection status changes but does NOT broadcast
        to UI WebSocket connections. UI broadcasting is handled by other services.

        Args:
            status_data: Dictionary containing connection status information
                - status: Connection status (connected/disconnected/reconnecting)
                - message: Human-readable status message
                - timestamp: Optional timestamp of status change

        Returns:
            None

        Raises:
            No exceptions raised - errors are logged internally
        """
        try:
            status = status_data.get("status", "unknown")
            message = status_data.get("message", "No message provided")
            timestamp = status_data.get("timestamp", datetime.now().isoformat())

            # Log connection status for monitoring
            log_message = (
                f"WebSocket connection status changed: {status} - {message} "
                f"(timestamp: {timestamp})"
            )

            if status == "connected":
                logger.info(log_message)
            elif status == "disconnected":
                logger.warning(log_message)
            elif status == "reconnecting":
                logger.info(log_message)
            else:
                logger.debug(log_message)
            
            log_structured(
                event="WS_CONNECTION_STATUS",
                message=f"Connection status: {status}",
                data=status_data
            )

            # Execute registered callbacks for connection status
            await self._execute_callbacks("connection_status", status_data)

        except Exception as e:
            logger.error(f"Error in _broadcast_connection_status: {e}")
            self.performance_metrics["errors_encountered"] += 1

    async def _apply_reconnection_strategy(self) -> None:
        """
        Apply intelligent reconnection strategy before attempting reconnection.

        This method performs necessary validations and token refresh
        before attempting to reconnect to ensure higher success rate.

        Strategy Steps:
        1. Validate current admin token expiry
        2. Attempt automated token refresh if expired/expiring
        3. Reload admin token from database
        4. Clear stale connection state
        5. Check network connectivity

        Returns:
            None

        Raises:
            No exceptions raised - errors are logged and handled gracefully
        """
        try:
            logger.info(
                f"Applying reconnection strategy (attempt {self.reconnect_attempts}/"
                f"{self.max_reconnect_attempts})"
            )

            # Step 1: Check if token needs refresh
            token_validation_needed = False

            if hasattr(self, "_token_validation_status"):
                validation_status = self._token_validation_status
                if not validation_status.get("valid", False):
                    token_validation_needed = True
                    logger.info(
                        f"Token validation required: {validation_status.get('reason', 'unknown')}"
                    )

            # Step 2: Schedule token refresh in background if needed
            # CRITICAL FIX: Never block on token refresh during reconnection
            if token_validation_needed or self.reconnect_attempts > 3:
                logger.info("Scheduling background token refresh before reconnection")
                try:
                    # This returns immediately without blocking
                    await self._try_automated_refresh()
                    logger.info("✅ Background token refresh scheduled - proceeding with reconnection")
                except Exception as refresh_error:
                    logger.error(f"Error scheduling token refresh: {refresh_error}")

            # Step 3: Reload admin token from database
            try:
                await self._load_admin_token()
            except Exception as token_error:
                logger.error(f"Error reloading admin token: {token_error}")

            # Step 4: Clear stale connection state
            self.connection_ready.clear()
            if self.ws_client:
                try:
                    self.ws_client.stop()
                    self.ws_client = None
                except Exception as stop_error:
                    logger.error(f"Error stopping stale WebSocket client: {stop_error}")

            # Step 5: Check network connectivity
            network_ok = await self._check_network_connectivity()
            if not network_ok:
                logger.warning(
                    "Network connectivity issues detected before reconnection"
                )

            # Step 6: Log connection status
            await self._broadcast_connection_status(
                {
                    "status": "reconnecting",
                    "message": f"Applying reconnection strategy (attempt {self.reconnect_attempts})",
                    "timestamp": datetime.now().isoformat(),
                }
            )

            logger.info("Reconnection strategy applied successfully")

        except Exception as e:
            logger.error(f"Error in _apply_reconnection_strategy: {e}")
            self.performance_metrics["errors_encountered"] += 1

    async def _send_reconnection_warning_email(self) -> None:
        """
        Send warning email when approaching maximum reconnection attempts.

        This method sends an alert email to the administrator when the system
        is approaching the maximum reconnection attempts threshold, allowing
        proactive intervention before complete failure.

        Returns:
            None

        Raises:
            No exceptions raised - errors are logged internally
        """
        try:
            attempts_remaining = self.max_reconnect_attempts - self.reconnect_attempts

            subject = "Warning: WebSocket Reconnection Approaching Limit"
            message = f"""
            TRADING SYSTEM RECONNECTION WARNING

            The centralized WebSocket manager is approaching maximum reconnection attempts.

            Current Status:
            - Reconnection Attempts: {self.reconnect_attempts}/{self.max_reconnect_attempts}
            - Attempts Remaining: {attempts_remaining}
            - Last Data Received: {self.last_data_received.isoformat() if self.last_data_received else 'Never'}
            - Last Connection Attempt: {self.last_connection_attempt.isoformat() if self.last_connection_attempt else 'Unknown'}

            System Impact:
            - Real-time market data feed is unstable
            - Trading signals may be delayed or missed
            - Dashboard updates may be interrupted

            Recommended Actions:
            1. Check Upstox API service status
            2. Verify admin token validity and expiration
            3. Check network connectivity and firewall settings
            4. Review system logs for error patterns
            5. Consider manual intervention if issues persist

            If the system reaches maximum attempts, real-time data will stop
            and manual restart will be required.

            Time: {datetime.now().isoformat()}
            Admin User ID: {self.admin_user_id}
            Active Instruments: {len(self.active_instrument_keys)}
            """

            logger.info("Sending reconnection warning email to administrator")

            try:
                email_sent = email_service.send_notification(
                    recipient_email=ADMIN_EMAIL, subject=subject, message=message
                )

                if email_sent:
                    logger.info("Reconnection warning email sent successfully")
                else:
                    logger.warning("Failed to send reconnection warning email")

            except Exception as email_error:
                logger.error(f"Error sending reconnection warning email: {email_error}")

        except Exception as e:
            logger.error(f"Error in _send_reconnection_warning_email: {e}")
            self.performance_metrics["errors_encountered"] += 1

    async def _handle_market_data(self, data: dict):
        """Handle incoming market data with enhanced format handling"""
        try:
            start_time = time_module.time()
            self._last_raw_data = data.copy() if isinstance(data, dict) else data
            self.last_data_received = datetime.now()

            # Signal connection is working
            if not self.connection_ready.is_set():
                self.connection_ready.set()
                logger.info("✅ WebSocket connection is receiving data")

            # Determine message type
            msg_type = data.get("type")
            has_feeds = "feeds" in data

            # Handle market_info messages
            if msg_type == "market_info" or "marketInfo" in data:
                await self._handle_market_info(data)

            # Handle feeds format (main data format)
            elif has_feeds:
                await self._handle_feeds_data(data)

            # Handle live_feed messages (older format)
            elif msg_type == "live_feed":
                await self._handle_live_feed_data(data)

            elif msg_type == "heartbeat":
                logger.debug("💓 Received heartbeat")

            elif msg_type == "error":
                logger.error(f"❌ Market data error: {data}")
                await self._execute_callbacks("error", data)
                # await self._broadcast_error(data)

            else:
                # Handle direct instrument data format
                if any(key for key in data if "|" in key):
                    await self._handle_direct_instrument_data(data)
                else:
                    logger.warning(f"⚠️ Unknown message format: {str(data)[:200]}...")

            # Calculate processing time
            processing_time = (time_module.time() - start_time) * 1000

            try:
                # This is a separate method to avoid circular imports
                # 🚀 CRITICAL FIX: Pass feeds data instead of complete message
                feeds_data = data.get("feeds", {}) if isinstance(data, dict) else {}
                if feeds_data:
                    await self._update_instrument_registry(feeds_data)
            except Exception as e:
                logger.debug(f"⚠️ Registry update error: {e}")

        except Exception as e:
            logger.error(f"❌ Error handling market data: {e}")
            logger.error(traceback.format_exc())

    async def _handle_market_info(self, data: dict):
        """Handle market info/status messages"""
        segment_status = data.get("status", {})
        if not segment_status and "marketInfo" in data:
            segment_status = data.get("marketInfo", {}).get("segmentStatus", {})

        # Process market status
        phases = {}
        active_segments = data.get("active_segments", [])
        all_markets_closed = data.get("all_markets_closed", True)

        # Extract phases and active segments
        if not active_segments:
            for segment, status in segment_status.items():
                exchange = segment.split("_")[0] if "_" in segment else segment
                is_open = "OPEN" in status
                phases[exchange] = "open" if is_open else "closed"
                if is_open and exchange not in active_segments:
                    active_segments.append(exchange)
            all_markets_closed = len(active_segments) == 0

        # Update market status
        prev_status = self.market_status
        self.market_status = phases.get("NSE", "unknown").lower()
        self.market_segment_status = segment_status
        self.market_phases = phases
        self.active_segments = active_segments
        self.all_markets_closed = all_markets_closed

        if prev_status != self.market_status:
            logger.info(
                f"Market status updated: {self.market_status} (active segments: {active_segments})"
            )
            
            log_structured(
                event="MARKET_STATUS_CHANGE",
                message=f"Market status changed to {self.market_status}",
                data={
                    "status": self.market_status,
                    "previous": prev_status,
                    "active_segments": active_segments
                }
            )

            # Notify registered services via callbacks (NO UI broadcasting)
            await self._execute_callbacks(
                "market_status",
                {
                    "status": self.market_status,
                    "segment_status": segment_status,
                    "phases": phases,
                    "active_segments": active_segments,
                    "all_markets_closed": all_markets_closed,
                    "previous_status": prev_status,
                    "timestamp": data.get("currentTs", datetime.now().isoformat()),
                },
            )

            # Check if markets closed and schedule shutdown
            if all_markets_closed and self.data_count > 0:
                logger.info("🔔 Market closed - initiating cleanup process")
                log_structured(event="MARKET_CLOSED", message="All markets closed, initiating cleanup")
                await self._store_market_snapshot()
                self._schedule_market_close_shutdown()

    async def _handle_feeds_data(self, data: dict):
        """Handle feeds format data - simplified routing only"""
        feeds = data.get("feeds", {})
        update_count = len(feeds)
        is_snapshot = self.update_count == 0

        if update_count > 0:
            self.data_count += update_count
            self.update_count += 1

            # Log data reception
            if is_snapshot:
                logger.info(
                    f"📸 Received initial snapshot with {update_count} instruments"
                )
            elif self.update_count % 50 == 0:
                logger.info(
                    f"📊 Received update #{self.update_count} with {update_count} instruments (total: {self.data_count})"
                )

            # Simple routing - send raw data to processing services
            # await self._route_feeds_data(feeds, is_snapshot, data)

            # 🚀 NEW: Update real-time analytics engine with market data
            await self._update_analytics_engine(feeds)

            logger.debug(f"✅ Data routing completed for {len(feeds)} instruments")

    async def _update_analytics_engine(self, feeds: dict) -> None:
        """
        Forward processed market data to realtime analytics engine.

        This method normalizes Upstox feed format and forwards it to the
        realtime_market_engine service for analytics calculations. It does NOT
        broadcast to UI - that is handled by other services.

        Architecture:
        1. Extract and normalize market data from Upstox feeds
        2. Forward to realtime_market_engine via update_live_data()
        3. Execute registered callbacks for other backend services
        4. Track performance metrics

        Args:
            feeds: Dictionary of Upstox feed data keyed by instrument_key
                Format: {instrument_key: {fullFeed: {...}}}

        Returns:
            None

        Raises:
            No exceptions raised - errors are logged and tracked in metrics
        """
        try:
            # Input validation
            if not feeds or not isinstance(feeds, dict):
                logger.debug("No feeds data to process for analytics engine")
                return

            # Import analytics engine safely to avoid circular imports
            try:
                from services.realtime_market_engine import update_market_data
            except ImportError as import_error:
                logger.warning(f"Analytics engine import failed: {import_error}")
                logger.warning(
                    "Real-time analytics engine will not receive data updates"
                )
                return

            # Normalize Upstox feed format to analytics engine format
            normalized_updates = {}
            normalization_errors = 0

            for instrument_key, feed_data in feeds.items():
                try:
                    # Validate instrument key format
                    if not instrument_key or "|" not in instrument_key:
                        continue

                    # Extract live price data from Upstox format
                    ltp_data = self._extract_ltp_from_feed(feed_data)

                    # Validate extracted data
                    if ltp_data and ltp_data.get("ltp", 0) > 0:
                        normalized_updates[instrument_key] = {
                            "ltp": float(ltp_data["ltp"]),
                            "volume": int(ltp_data.get("volume", 0)),
                            "timestamp": ltp_data.get("timestamp"),
                            "high": (
                                float(ltp_data.get("high"))
                                if ltp_data.get("high")
                                else None
                            ),
                            "low": (
                                float(ltp_data.get("low"))
                                if ltp_data.get("low")
                                else None
                            ),
                            "open": (
                                float(ltp_data.get("open"))
                                if ltp_data.get("open")
                                else None
                            ),
                            "close": (
                                float(ltp_data.get("prev_close"))
                                if ltp_data.get("prev_close")
                                else None
                            ),
                            "cp": (
                                float(ltp_data.get("prev_close"))
                                if ltp_data.get("prev_close")
                                else None
                            ),
                        }

                except Exception as normalization_error:
                    normalization_errors += 1
                    logger.debug(
                        f"Error normalizing {instrument_key}: {normalization_error}"
                    )
                    continue

            # Forward to analytics engine if we have valid data
            if normalized_updates:
                # Log first update with sample data for debugging
                if not hasattr(self, "_analytics_first_update_logged"):
                    self._analytics_first_update_logged = True
                    sample_keys = list(normalized_updates.keys())[:3]
                    logger.info(
                        f"Sending first update to analytics engine: {len(normalized_updates)} instruments"
                    )
                    logger.info(f"Sample keys: {sample_keys}")
                    if sample_keys:
                        logger.info(
                            f"Sample data: {normalized_updates[sample_keys[0]]}"
                        )

                # Forward to realtime market engine
                update_market_data(normalized_updates)

                # Update performance metrics
                self.performance_metrics["data_updates_processed"] += len(
                    normalized_updates
                )

                logger.debug(
                    f"Updated analytics engine with {len(normalized_updates)} instruments"
                )

                # Execute registered callbacks for price updates (for WebSocket broadcasting)
                await self._execute_callbacks("price_update", normalized_updates)

                # Execute registered callbacks for analytics updates
                await self._execute_callbacks(
                    "analytics_update",
                    {
                        "instrument_count": len(normalized_updates),
                        "timestamp": datetime.now().isoformat(),
                        "sample_keys": list(normalized_updates.keys())[:5],
                    },
                )

            # Log normalization errors if significant
            if normalization_errors > 10:
                logger.warning(
                    f"High normalization error rate: {normalization_errors} errors "
                    f"out of {len(feeds)} feeds"
                )
                self.performance_metrics["errors_encountered"] += normalization_errors

        except Exception as e:
            logger.error(f"Analytics engine update error: {e}")
            logger.error(traceback.format_exc())
            self.performance_metrics["errors_encountered"] += 1

    def _extract_ltp_from_feed(self, feed_data: dict) -> Optional[dict]:
        """
        Extract LTP and prev_close strictly using ltpc.cp for previous close.
        Returns dict or None.
        """
        try:
            if not isinstance(feed_data, dict):
                return None
            full_feed = feed_data.get("fullFeed") or {}
            # Equity/stock
            if "marketFF" in full_feed:
                market_ff = full_feed["marketFF"] or {}
                ltpc = market_ff.get("ltpc") or {}

                # require ltp present
                if "ltp" not in ltpc:
                    return None

                # Strict prev_close from ltpc.cp (may be None)
                prev_close = ltpc.get("cp")  # <--- USE THIS ONLY

                # Parse 1d OHLC for open/high/low/ohlc_close (but do NOT treat as prev_close)
                ohlc_data = {}
                for ohlc_item in market_ff.get("marketOHLC", {}).get("ohlc", []) or []:
                    if ohlc_item.get("interval") == "1d":
                        ohlc_data = {
                            "open": ohlc_item.get("open"),
                            "high": ohlc_item.get("high"),
                            "low": ohlc_item.get("low"),
                            "ohlc_close": ohlc_item.get("close"),
                        }
                        break

                return {
                    "ltp": float(ltpc.get("ltp")),
                    "prev_close": float(prev_close) if prev_close else None,
                    "open": (
                        float(ohlc_data.get("open")) if ohlc_data.get("open") else None
                    ),
                    "high": (
                        float(ohlc_data.get("high")) if ohlc_data.get("high") else None
                    ),
                    "low": (
                        float(ohlc_data.get("low")) if ohlc_data.get("low") else None
                    ),
                    "ohlc_close": (
                        float(ohlc_data.get("ohlc_close"))
                        if ohlc_data.get("ohlc_close")
                        else None
                    ),
                    "volume": int(market_ff.get("vtt")) if market_ff.get("vtt") else 0,
                    "avg_price": (
                        float(market_ff.get("atp")) if market_ff.get("atp") else None
                    ),
                    "timestamp": ltpc.get("ltt"),
                    "last_qty": int(ltpc.get("ltq", 0)) if ltpc.get("ltq") else 0,
                }

            # Index handling (same idea)
            if "indexFF" in full_feed:
                index_ff = full_feed["indexFF"] or {}
                ltpc = index_ff.get("ltpc") or {}
                if "ltp" not in ltpc:
                    return None
                prev_close = ltpc.get("cp")
                ohlc_data = {}
                for ohlc_item in index_ff.get("marketOHLC", {}).get("ohlc", []) or []:
                    if ohlc_item.get("interval") == "1d":
                        ohlc_data = {
                            "open": ohlc_item.get("open"),
                            "high": ohlc_item.get("high"),
                            "low": ohlc_item.get("low"),
                            "ohlc_close": ohlc_item.get("close"),
                        }
                        break
                return {
                    "ltp": float(ltpc.get("ltp")),
                    "prev_close": float(prev_close) if prev_close else None,
                    "open": (
                        float(ohlc_data.get("open")) if ohlc_data.get("open") else None
                    ),
                    "high": (
                        float(ohlc_data.get("high")) if ohlc_data.get("high") else None
                    ),
                    "low": (
                        float(ohlc_data.get("low")) if ohlc_data.get("low") else None
                    ),
                    "ohlc_close": (
                        float(ohlc_data.get("ohlc_close"))
                        if ohlc_data.get("ohlc_close")
                        else None
                    ),
                    "volume": 0,  # Indices don't have volume
                    "avg_price": None,
                    "timestamp": ltpc.get("ltt"),
                    "last_qty": 0,
                }

            return None
        except Exception as e:
            logger.debug(f"⚠️ Error extracting LTP data: {e}")
            logger.debug(traceback.format_exc())
            return None

    def register_analytics_callback(self, callback: CallbackFunction) -> bool:
        """
        Register callback for analytics events.

        Services can register callbacks to receive real-time analytics updates
        when market data is processed and forwarded to the analytics engine.

        Args:
            callback: Async or sync function to call with analytics updates
                Callback signature: callback(data: dict) -> None
                Data structure:
                {
                    "instrument_count": int,
                    "timestamp": str (ISO format),
                    "sample_keys": List[str]
                }

        Returns:
            True if registered successfully, False otherwise

        Raises:
            No exceptions raised - errors are logged internally
        """
        return self.register_callback("analytics_update", callback)

    def unregister_analytics_callback(self, callback: CallbackFunction) -> bool:
        """
        Unregister analytics callback.

        Args:
            callback: Previously registered callback function to remove

        Returns:
            True if unregistered successfully, False if not found

        Raises:
            No exceptions raised - errors are logged internally
        """
        return self.unregister_callback("analytics_update", callback)

    def register_market_data_callback(self, callback: CallbackFunction) -> bool:
        """
        Register callback for raw market data updates.

        Services can register callbacks to receive market data updates
        as they are received from Upstox WebSocket feed.

        Args:
            callback: Async or sync function to call with market data
                Callback signature: callback(data: dict) -> None

        Returns:
            True if registered successfully

        Raises:
            No exceptions raised - errors are logged internally
        """
        return self.register_callback("price_update", callback)

    def unregister_market_data_callback(self, callback: CallbackFunction) -> bool:
        """
        Unregister market data callback.

        Args:
            callback: Previously registered callback function to remove

        Returns:
            True if unregistered successfully, False if not found

        Raises:
            No exceptions raised - errors are logged internally
        """
        return self.unregister_callback("price_update", callback)

    async def _handle_live_feed_data(self, data: dict):
        """Handle live_feed format data with ZERO-DELAY streaming"""
        feeds = data.get("data", {})
        update_count = len(feeds)
        is_snapshot = data.get("is_snapshot", False)

        if update_count > 0:
            self.data_count += update_count
            self.update_count += 1

            # 🚀 CRITICAL: ZERO-DELAY streaming FIRST
            try:
                from services.realtime_data_streamer import realtime_streamer

                await realtime_streamer.stream_raw_market_data(data)
            except Exception as e:
                logger.debug(f"Real-time streaming error: {e}")

            if is_snapshot or self.update_count == 1:
                logger.info(
                    f"📸 Received initial snapshot with {update_count} instruments (ZERO-DELAY)"
                )
            elif self.update_count % 10 == 0:
                logger.info(
                    f"📊 Received update #{self.update_count} with {update_count} instruments (total: {self.data_count})"
                )

            # ⚡ PERFORMANCE FIX: Run cache updates in parallel for faster response
            await asyncio.gather(
                self._update_cache(feeds),
                self._update_instrument_registry(feeds),
                return_exceptions=True,  # Don't let one failure block others
            )

            # Removed callbacks execution - single source architecture
            # await self._execute_callbacks("price_update", {...})

    async def _handle_direct_instrument_data(self, data: dict):
        """Handle direct instrument data format with ZERO-DELAY streaming"""
        is_snapshot = self.update_count == 0
        update_count = len(data)
        self.data_count += update_count
        self.update_count += 1

        # 🚀 CRITICAL: ZERO-DELAY streaming FIRST
        try:
            from services.realtime_data_streamer import realtime_streamer

            await realtime_streamer.stream_raw_market_data(data)
        except Exception as e:
            logger.debug(f"Real-time streaming error: {e}")

        logger.info(
            f"📊 Received direct instrument data format with {update_count} instruments (ZERO-DELAY)"
        )

        await self._update_cache(data)
        await self._update_instrument_registry(data)

        # Removed callbacks execution - single source architecture
        # await self._execute_callbacks("price_update", {...})

    async def _update_instrument_registry(self, feed_data: dict):
        """✅ OPTIMIZED: Update both registry and optimized service"""
        try:
            if not feed_data:
                return

            # 🚀 FIXED: Update optimized market data service with extracted data
            try:
                from services.optimized_market_data_service import (
                    optimized_market_service,
                )

                # 🚀 FIXED: Extract raw data without enrichment for optimized service
                extracted_data = self._extract_for_optimized_service(feed_data)
                if extracted_data:
                    optimized_market_service.update_live_data(extracted_data)
                    logger.debug(
                        f"⚡ Updated optimized service with {len(extracted_data)} instruments"
                    )
                else:
                    # Only log this as debug for market_info messages without feeds
                    logger.debug(
                        "⚠️ No valid data to send to optimized service after extraction (likely market_info message)"
                    )
            except Exception as e:
                logger.error(f"⚠️ Optimized service update error: {e}")

            # Registry update (background) - WITHOUT duplicate optimized service call
            try:

                normalized_data = self._normalize_market_data(feed_data)
                if normalized_data:
                    # ✅ FIXED: Only update registry, not optimized service (already updated above)
                    # instrument_registry.update_live_prices(normalized_data)
                    logger.debug(
                        f"📊 Updated registry with {len(normalized_data)} instruments"
                    )
            except Exception as e:
                logger.error(f"⚠️ Registry update error: {e}")

        except Exception as e:
            logger.error(f"❌ Error in _update_instrument_registry: {e}")

    def _extract_for_optimized_service(self, feed_data: dict) -> dict:
        """Extract data for optimized service without enrichment"""
        extracted = {}

        for instrument_key, raw_data in feed_data.items():
            try:
                # Validate input
                if not self._validate_raw_input(instrument_key, raw_data):
                    continue

                # Extract data directly without enrichment
                extracted_fields = self._extract_by_format(raw_data)
                if extracted_fields and extracted_fields.get("ltp", 0) > 0:
                    extracted[instrument_key] = extracted_fields

            except Exception as e:
                logger.debug(f"⚠️ Error extracting {instrument_key}: {e}")
                continue

        return extracted

    def _normalize_market_data(self, feed_data: dict) -> dict:
        """COMPLETE: Handle all Upstox formats with full error handling"""
        normalized = {}
        stats = {"success": 0, "errors": 0, "empty": 0, "invalid_format": 0}

        for instrument_key, raw_data in feed_data.items():
            try:
                # Validate input
                if not self._validate_raw_input(instrument_key, raw_data):
                    stats["invalid_format"] += 1
                    continue

                # Extract based on format
                extracted = self._extract_by_format(raw_data)
                if not extracted:
                    stats["empty"] += 1
                    continue

                # Enrich with metadata
                enriched = self._enrich_with_metadata(instrument_key, extracted)
                if enriched:
                    normalized[instrument_key] = enriched
                    stats["success"] += 1
                else:
                    stats["errors"] += 1

            except Exception as e:
                stats["errors"] += 1
                # Enhanced error logging for NoneType comparison debugging
                if (
                    "'>' not suppported between instances of 'NoneType' and 'int'"
                    in str(e)
                ):
                    logger.warning(f"⚠️ DETAILED ERROR for {instrument_key}:")
                    logger.warning(
                        f"   Raw data keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'Not dict'}"
                    )
                    if isinstance(raw_data, dict) and "fullFeed" in raw_data:
                        market_ff = raw_data.get("fullFeed", {}).get("marketFF", {})
                        ltpc = market_ff.get("ltpc", {})
                        logger.warning(
                            f"   LTPC data: ltp={ltpc.get('ltp')}, cp={ltpc.get('cp')}"
                        )
                        logger.warning(
                            f"   LTPC types: ltp={type(ltpc.get('ltp'))}, cp={type(ltpc.get('cp'))}"
                        )
                    import traceback

                    logger.warning(f"   Full traceback: {traceback.format_exc()}")

                logger.warning(f"⚠️ Error processing {instrument_key}: {e}")

        if stats["success"] > 0:
            logger.debug(
                f"📊 Processed: {stats['success']} success, {stats['errors']} errors, {stats['empty']} empty"
            )

        return normalized

    def _validate_raw_input(self, instrument_key: str, raw_data: Any) -> bool:
        """Validate raw input data"""
        if not instrument_key or "|" not in instrument_key:
            return False
        if not isinstance(raw_data, dict):
            return False
        if "fullFeed" not in raw_data:
            return False
        return True

    def _extract_by_format(self, raw_data: dict) -> Optional[dict]:
        """Extract data based on Upstox format type"""
        full_feed = raw_data.get("fullFeed", {})

        # Format 1: Market Data (NSE_EQ, NSE_FO) - MCX_FO handled by dedicated service
        if "marketFF" in full_feed:
            return self._extract_market_format(full_feed["marketFF"])

        # Format 2: Index Data (NSE_INDEX, BSE_INDEX)
        elif "indexFF" in full_feed:
            return self._extract_index_format(full_feed["indexFF"])

        return None

    def _extract_market_format(self, market_ff: dict) -> dict:
        """Extract from marketFF format"""
        data = {}

        # Core price data with enhanced safety
        if "ltpc" in market_ff and market_ff["ltpc"]:
            ltpc = market_ff["ltpc"]
            ltp_val = self._safe_float(ltpc.get("ltp"))
            cp_val = self._safe_float(ltpc.get("cp"))
            ltq_val = self._safe_int(ltpc.get("ltq"))
            ltt_val = self._safe_string(ltpc.get("ltt"))

            data.update(
                {
                    "ltp": ltp_val,
                    "cp": cp_val,
                    "ltq": ltq_val,
                    "ltt": ltt_val,
                }
            )

        # Volume data
        if "vtt" in market_ff:
            vtt_value = self._safe_int(market_ff.get("vtt"))
            data["volume"] = vtt_value  # For registry compatibility
            data["vtt"] = vtt_value  # For optimized service compatibility

        # OHLC data
        if "marketOHLC" in market_ff:
            ohlc_data = market_ff["marketOHLC"].get("ohlc", [])
            daily_data = self._extract_daily_ohlc(ohlc_data)
            if daily_data:
                data.update(daily_data)

        # Options data (if present)
        if "optionGreeks" in market_ff and market_ff["optionGreeks"]:
            greeks = market_ff["optionGreeks"]
            data["option_greeks"] = {
                "delta": self._safe_float(greeks.get("delta")),
                "theta": self._safe_float(greeks.get("theta")),
                "gamma": self._safe_float(greeks.get("gamma")),
                "vega": self._safe_float(greeks.get("vega")),
                "rho": self._safe_float(greeks.get("rho")),
            }

        # Open Interest (for derivatives)
        if "oi" in market_ff:
            data["open_interest"] = self._safe_float(market_ff.get("oi"))

        # Average Trade Price
        if "atp" in market_ff:
            atp_value = self._safe_float(market_ff.get("atp"))
            data["avg_trade_price"] = atp_value  # For registry compatibility
            data["atp"] = atp_value  # For optimized service compatibility

        # Bid/Ask data
        if "marketLevel" in market_ff and "bidAskQuote" in market_ff["marketLevel"]:
            bid_ask = market_ff["marketLevel"]["bidAskQuote"]
            if bid_ask and len(bid_ask) > 0 and bid_ask[0]:
                first_level = bid_ask[0]
                data.update(
                    {
                        "bid_price": self._safe_float(first_level.get("bidP")),
                        "bid_qty": self._safe_int(first_level.get("bidQ")),
                        "ask_price": self._safe_float(first_level.get("askP")),
                        "ask_qty": self._safe_int(first_level.get("askQ")),
                    }
                )

        return data

    def _extract_index_format(self, index_ff: dict) -> dict:
        """Extract from indexFF format"""
        data = {}

        # Index LTPC
        if "ltpc" in index_ff and index_ff["ltpc"]:
            ltpc = index_ff["ltpc"]
            data.update(
                {
                    "ltp": self._safe_float(ltpc.get("ltp")),
                    "cp": self._safe_float(ltpc.get("cp")),
                    "ltt": self._safe_string(ltpc.get("ltt")),
                }
            )

        # Index OHLC
        if "marketOHLC" in index_ff:
            ohlc_data = index_ff["marketOHLC"].get("ohlc", [])
            daily_data = self._extract_daily_ohlc(ohlc_data)
            if daily_data:
                data.update(daily_data)

        return data

    def _extract_daily_ohlc(self, ohlc_list: list) -> Optional[dict]:
        """Extract daily OHLC from list"""
        if not isinstance(ohlc_list, list):
            return None

        # Find daily interval
        for ohlc in ohlc_list:
            if isinstance(ohlc, dict) and ohlc.get("interval") == "1d":
                return {
                    "open": self._safe_float(ohlc.get("open")),
                    "high": self._safe_float(ohlc.get("high")),
                    "low": self._safe_float(ohlc.get("low")),
                    "close": self._safe_float(ohlc.get("close")),
                    "daily_volume": self._safe_int(ohlc.get("vol")),
                }

        return None

    def _enrich_with_metadata(
        self, instrument_key: str, extracted_data: dict
    ) -> Optional[dict]:
        """Enrich data with symbol metadata"""
        try:
            # Resolve symbol
            symbol_info = self._resolve_instrument_symbol(instrument_key)
            if not symbol_info:
                return None

            # Calculate derived metrics
            self._calculate_price_metrics(extracted_data)

            # Create enriched structure with frontend-compatible field names
            enriched = {
                # Identifiers
                "instrument_key": instrument_key,
                "symbol": symbol_info["symbol"],
                "name": symbol_info["name"],
                "exchange": symbol_info["exchange"],
                "sector": symbol_info["sector"],
                "instrument_type": symbol_info["type"],
                # Price data with frontend-compatible field names
                **extracted_data,
                # CRITICAL FIX: Add frontend-compatible field mapping
                "last_price": extracted_data.get(
                    "ltp", 0
                ),  # Map ltp → last_price for frontend
                # Metadata
                "timestamp": datetime.now().isoformat(),
                "data_source": "upstox_live",
                "processing_time": datetime.now().isoformat(),
            }

            return enriched

        except Exception as e:
            logger.debug(f"Error enriching {instrument_key}: {e}")
            return None

    def _resolve_instrument_symbol(self, instrument_key: str) -> Optional[dict]:
        """Resolve instrument key to symbol and metadata"""
        try:
            parts = instrument_key.split("|")
            if len(parts) != 2:
                return None

            exchange_segment, identifier = parts

            # NSE Equity with ISIN
            if "NSE_EQ" in exchange_segment:
                return self._resolve_nse_equity(identifier, instrument_key)

            # NSE Index
            elif "NSE_INDEX" in exchange_segment:
                return self._resolve_nse_index(identifier)

            # BSE Index
            elif "BSE_INDEX" in exchange_segment:
                return self._resolve_bse_index(identifier)

            # NSE F&O
            elif "NSE_FO" in exchange_segment:
                return self._resolve_nse_fo(instrument_key, identifier)

            # MCX F&O - now handled by dedicated MCX WebSocket service
            elif "MCX_FO" in exchange_segment:
                logger.debug(
                    f"MCX instrument {instrument_key} - handled by dedicated MCX service"
                )
                return None

            return None

        except Exception as e:
            logger.debug(f"Error resolving {instrument_key}: {e}")
            return None

    def _resolve_nse_equity(self, isin: str, instrument_key: str) -> Optional[dict]:
        """Resolve NSE equity ISIN to symbol"""
        # Comprehensive ISIN mapping
        isin_mapping = {
            "INE002A01018": {
                "symbol": "RELIANCE",
                "name": "Reliance Industries Limited",
            },
            "INE467B01029": {
                "symbol": "TCS",
                "name": "Tata Consultancy Services Limited",
            },
            "INE040A01034": {"symbol": "HDFCBANK", "name": "HDFC Bank Limited"},
            "INE090A01013": {"symbol": "ICICIBANK", "name": "ICICI Bank Limited"},
            "INE090A01021": {"symbol": "INFY", "name": "Infosys Limited"},
            "INE216A01030": {"symbol": "AXISBANK", "name": "Axis Bank Limited"},
            "INE238A01034": {"symbol": "SBIN", "name": "State Bank of India"},
            "INE397D01024": {"symbol": "BHARTIARTL", "name": "Bharti Airtel Limited"},
            "INE726G01019": {"symbol": "WIPRO", "name": "Wipro Limited"},
            "INE213A01029": {"symbol": "HCLTECH", "name": "HCL Technologies Limited"},
            "INE001A01036": {"symbol": "EICHERMOT", "name": "Eicher Motors Limited"},
            "INE545U01014": {"symbol": "TECHM", "name": "Tech Mahindra Limited"},
            # Add from your sample data
            "INE498L01015": {"symbol": "INDIGO", "name": "InterGlobe Aviation Limited"},
            "INE176B01034": {
                "symbol": "BPCL",
                "name": "Bharat Petroleum Corporation Limited",
            },
            "INE053F01010": {"symbol": "ANILINDIA", "name": "Anil Chemicals Limited"},
            "INE121J01017": {"symbol": "PAGEIND", "name": "Page Industries Limited"},
            "INE200M01039": {"symbol": "RELAXO", "name": "Relaxo Footwears Limited"},
            "INE288B01029": {"symbol": "NESTLEIND", "name": "Nestle India Limited"},
            "INE935A01035": {
                "symbol": "ADANIGREEN",
                "name": "Adani Green Energy Limited",
            },
            "INE918I01026": {"symbol": "ZOMATO", "name": "Zomato Limited"},
        }

        instrument_service = get_instrument_service()

        if instrument_service and hasattr(instrument_service, "_instrument_by_key"):
            instrument_data = instrument_service._instrument_by_key.get(instrument_key)

            symbol = getattr(instrument_data, "trading_symbol", None)
            if not symbol:
                symbol = getattr(instrument_data, "symbol", "unknown")

            name = getattr(instrument_data, "name", isin)

            # stock_info = isin_mapping.get(isin)
            sector = self._get_sector_for_symbol(symbol)
            return {
                "symbol": symbol,
                "name": name,
                "exchange": "NSE",
                "sector": sector,
                "type": "EQ",
            }
        else:
            logger.debug(
                f"Instrument data not found in service for key: {instrument_key} (ISIN: {isin})"
            )

        return None

    def _resolve_nse_index(self, identifier: str) -> Optional[dict]:
        """FIXED: Resolve NSE index with better matching"""
        index_mapping = {
            "Nifty 50": {"symbol": "NIFTY", "name": "Nifty 50"},
            "Nifty Bank": {"symbol": "BANKNIFTY", "name": "Nifty Bank"},
            "BANKNIFTY": {"symbol": "BANKNIFTY", "name": "Nifty Bank"},
            "Nifty Fin Service": {
                "symbol": "FINNIFTY",
                "name": "Nifty Financial Services",
            },
            "Nifty Financial Services": {
                "symbol": "FINNIFTY",
                "name": "Nifty Financial Services",
            },
            "FIN NIFTY": {"symbol": "FINNIFTY", "name": "Nifty Financial Services"},
            "Nifty Midcap 50": {"symbol": "MIDCPNIFTY", "name": "Nifty Midcap 50"},
            "NIFTY MID SELECT": {"symbol": "MIDCPNIFTY", "name": "Nifty Midcap 50"},
            "MIDCPNIFTY": {"symbol": "MIDCPNIFTY", "name": "Nifty Midcap 50"},
            "Nifty IT": {"symbol": "NIFTYIT", "name": "Nifty IT"},
            "NIFT YIT": {"symbol": "NIFTYIT", "name": "Nifty IT"},
            "Nifty Pharma": {"symbol": "NIFTYPHARM", "name": "Nifty Pharma"},
            "NIFTYPHARM": {"symbol": "NIFTYPHARM", "name": "Nifty Pharma"},
            "Nifty Auto": {"symbol": "NIFTAUTO", "name": "  Nifty Auto"},
            "NIFT AUTO": {"symbol": "NIFTAUTO", "name": "  Nifty Auto"},
            "Nifty FMCG": {"symbol": "NIFTYFMCG", "name": "Nifty FMCG"},
            "Nifty Metal": {"symbol": "NIFTYMETAL", "name": "Nifty Metal"},
            "NIFTY METAL": {"symbol": "NIFTYMETAL", "name": "Nifty Metal"},
            "Nifty Realty": {"symbol": "NIFTYREALTY", "name": "Nifty Realty"},
            "NIFTY REALTY": {"symbol": "NIFTYREALTY", "  name": "Nifty Realty"},
            "Nifty Energy": {"symbol": "NIFTYENERGY", "name": "Nifty Energy"},
            "NIFTY ENERGY": {"symbol": "NIFTYENERGY", "name": "Nifty Energy"},
            "Nifty PSU Bank": {"symbol": "PSUBNK", "name": "Nifty PSU Bank"},
            "NIFTY HEALTHCARE": {
                "symbol": "NIFTY HEALTHCARE",
                "name": "NIFTY HEALTHCARE",
            },
            "PSUBNK": {"symbol": "PSUBNK", "name": "Nifty PSU Bank"},
            "NIFTY OIL AND GAS": {
                "symbol": "Nifty Oil and Gas",
                "name": "Nifty Oil and Gas",
            },
            "Nifty Media": {"symbol": "NIFTYMEDIA", "name": "Nifty Media"},
            "Nifty Pvt Bank": {
                "symbol": "Nifty Pvt Bank",
                "name": "Nifty Private Bank",
            },
            "NIFTY CONSR DURBL": {
                "symbol": "NIFTY CONSR DURBL",
                "name": "NIFTY CONSR DURBL",
            },
        }

        # Try exact match first
        index_info = index_mapping.get(identifier)
        if index_info:
            logger.debug(f"✅ Index resolved: {identifier} → {index_info['symbol']}")
            return {
                "symbol": index_info["symbol"],
                "name": index_info["name"],
                "exchange": "NSE",
                "sector": "INDEX",
                "type": "INDEX",
            }

        # Try partial matching
        for key, info in index_mapping.items():
            if identifier in key or key in identifier:
                logger.debug(
                    f"✅ Index resolved (partial): {identifier} → {info['symbol']}"
                )
                return {
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "exchange": "NSE",
                    "sector": "INDEX",
                    "type": "INDEX",
                }

        logger.warning(f"⚠️ Unknown NSE index: {identifier}")
        return None

    def _resolve_bse_index(self, identifier: str) -> Optional[dict]:
        """FIXED: Resolve BSE index with better matching"""
        if "SENSEX" in identifier or identifier == "SENSEX":
            logger.debug(f"✅ BSE Index resolved: {identifier} → SENSEX")
            return {
                "symbol": "SENSEX",
                "name": "S&P BSE Sensex",
                "exchange": "BSE",
                "sector": "INDEX",
                "type": "INDEX",
            }

        logger.warning(f"⚠️ Unknown BSE index: {identifier}")
        return None

    def _resolve_nse_fo(self, instrument_key: str, identifier: str) -> Optional[dict]:
        """Resolve NSE F&O instruments"""
        try:
            # Try to get from instrument registry
            from services.instrument_registry import instrument_registry

            if hasattr(instrument_registry, "_instrument_by_key"):
                instr = instrument_registry._instrument_by_key.get(instrument_key)
                if instr:
                    symbol = getattr(instr, "symbol", None) or getattr(
                        instr, "underlying_symbol", None
                    )
                    if symbol:
                        sector = self._get_sector_for_symbol(symbol)
                        return {
                            "symbol": symbol,
                            "name": getattr(instr, "name", symbol),
                            "exchange": "NSE",
                            "sector": sector,
                            "type": getattr(instr, "instrument_type", "FO"),
                        }

            return None

        except Exception:
            return None

    def _resolve_mcx_fo(self, instrument_key: str, identifier: str) -> Optional[dict]:
        """DEPRECATED: MCX F&O instruments are now handled by dedicated MCX WebSocket service"""
        # MCX instruments are no longer processed by the centralized manager
        # They are handled by the dedicated MCX WebSocket service in services/websocket/mcx/
        logger.debug(
            f"MCX instrument {instrument_key} - redirected to dedicated MCX service"
        )
        return None

    def _get_sector_for_symbol(self, symbol: str) -> str:
        """FIXED: Get sector for symbol with better error handling"""
        try:
            from services.sector_mapping import SYMBOL_TO_SECTOR

            sector = SYMBOL_TO_SECTOR.get(symbol.upper(), "OTHER")
            logger.debug(f"📊 Sector mapping: {symbol} → {sector}")
            return sector

        except ImportError:
            logger.warning("⚠️ Sector mapping not available")
            return "OTHER"
        except Exception as e:
            logger.warning(f"⚠️ Error getting sector for {symbol}: {e}")
            return "OTHER"

    def _calculate_price_metrics(self, data: dict):
        """Calculate derived price metrics with comprehensive null safety"""
        try:
            ltp = data.get("ltp")
            cp = data.get("cp")

            # Ensure all values are properly converted and validated
            if ltp is not None and cp is not None:
                try:
                    ltp = float(ltp) if ltp is not None else None
                    cp = float(cp) if cp is not None else None
                except (ValueError, TypeError):
                    ltp = None
                    cp = None

            # Price change calculation with enhanced safety
            if ltp is not None and cp is not None and cp > 0:
                try:
                    change = ltp - cp
                    change_percent = (change / cp) * 100

                    # Ensure calculated values are valid numbers
                    if change is not None and change_percent is not None:
                        data.update(
                            {
                                "change": round(change, 2),
                                "change_percent": round(change_percent, 2),
                            }
                        )

                        # Price trend with null-safe comparisons
                        if change_percent is not None and isinstance(
                            change_percent, (int, float)
                        ):
                            if change_percent > 2:
                                data["trend"] = "strong_bullish"
                            elif change_percent > 0:
                                data["trend"] = "bullish"
                            elif change_percent < -2:
                                data["trend"] = "strong_bearish"
                            elif change_percent < 0:
                                data["trend"] = "bearish"
                            else:
                                data["trend"] = "neutral"
                except (ValueError, TypeError, ZeroDivisionError):
                    # Skip price change calculation if any error occurs
                    pass

            # Volatility calculation with enhanced safety
            high = data.get("high")
            low = data.get("low")

            # Convert and validate high/low values
            try:
                high = float(high) if high is not None else None
                low = float(low) if low is not None else None
                ltp = float(ltp) if ltp is not None else None
            except (ValueError, TypeError):
                high = None
                low = None
                ltp = None

            if (
                high is not None
                and low is not None
                and ltp is not None
                and isinstance(high, (int, float))
                and isinstance(low, (int, float))
                and isinstance(ltp, (int, float))
                and ltp > 0
            ):
                try:
                    range_percent = ((high - low) / ltp) * 100
                    if range_percent is not None and isinstance(
                        range_percent, (int, float)
                    ):
                        if range_percent > 5:
                            data["volatility"] = "high"
                        elif range_percent > 2:
                            data["volatility"] = "medium"
                        else:
                            data["volatility"] = "low"
                except (ValueError, TypeError, ZeroDivisionError):
                    # Skip volatility calculation if any error occurs
                    pass

        except Exception as e:
            # Log but don't raise the error to prevent processing interruption
            logger.debug(f"Error calculating price metrics: {e}")
            pass

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safe float conversion"""
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        """Safe int conversion"""
        try:
            return int(float(value)) if value is not None else None
        except (ValueError, TypeError):
            return None

    def _safe_string(self, value: Any) -> Optional[str]:
        """Safe string conversion"""
        try:
            return str(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    async def _store_market_snapshot(self):
        """Store the current market data snapshot to Redis"""
        try:
            if not redis_manager:
                logger.warning(
                    "⚠️ Cannot store market snapshot: Redis manager not available"
                )
                return False

            snapshot_data = {
                "market_data": self.market_data_cache,
                "market_status": self.market_status,
                "market_segment_status": self.market_segment_status,
                "market_phases": self.market_phases,
                "active_segments": self.active_segments,
                "last_update_time": datetime.now().isoformat(),
                "update_count": self.update_count,
                "data_count": self.data_count,
                "snapshot_time": datetime.now().isoformat(),
            }

            # Store with 24-hour TTL
            success = redis_manager.set(
                "market_data_snapshot", snapshot_data, ttl=86400
            )

            if success:
                logger.info(
                    f"💾 Stored market data snapshot with {len(self.market_data_cache)} instruments to Redis"
                )

                # Store individual instruments for faster access
                for instrument_key, data in self.market_data_cache.items():
                    redis_key = f"market_data:{instrument_key}"
                    redis_manager.set(redis_key, data, ttl=86400)

                return True
            else:
                logger.warning("⚠️ Failed to store market data snapshot to Redis")
                return False

        except Exception as e:
            logger.error(f"❌ Error storing market snapshot: {e}")
            logger.error(traceback.format_exc())
            return False

    def _schedule_market_close_shutdown(self):
        """Schedule a delayed shutdown after market close"""
        if self._shutdown_scheduled:
            return

        self._shutdown_scheduled = True

        async def delayed_shutdown():
            logger.info(
                "⏳ Scheduled shutdown after market close - waiting 2 minutes for final data"
            )
            await asyncio.sleep(60)

            await self._store_market_snapshot()

            if self.ws_client:
                self.ws_client.stop()
                self.ws_client = None

            logger.info("🛑 WebSocket connection stopped due to market close")

            await self._execute_callbacks(
                "connection_status",
                {
                    "status": "market_closed_shutdown",
                    "message": "WebSocket connection stopped due to market close",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            self._schedule_market_open_check()

        task = asyncio.create_task(delayed_shutdown())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _load_market_snapshot(self):
        """Load the latest market data snapshot from Redis"""
        try:
            if not redis_manager:
                logger.warning(
                    "⚠️ Cannot load market snapshot: Redis manager not available"
                )
                return False

            snapshot_data = redis_manager.get("market_data_snapshot")
            if not snapshot_data:
                logger.info("ℹ️ No market data snapshot found in Redis")
                return False

            # Restore data from snapshot
            self.market_data_cache = snapshot_data.get("market_data", {})
            self.market_status = snapshot_data.get("market_status", "unknown")
            self.market_segment_status = snapshot_data.get("market_segment_status", {})
            self.market_phases = snapshot_data.get("market_phases", {})
            self.active_segments = snapshot_data.get("active_segments", [])
            self.update_count = snapshot_data.get("update_count", 0)
            self.data_count = snapshot_data.get("data_count", 0)

            snapshot_time = snapshot_data.get("snapshot_time")
            logger.info(
                f"📂 Restored market data snapshot with {len(self.market_data_cache)} instruments from {snapshot_time}"
            )

            # Broadcast restored snapshot to clients

        except Exception as e:
            logger.error(f"❌ Error loading market snapshot: {e}")
            logger.error(traceback.format_exc())
            return False

    def _schedule_market_open_check(self):
        """
        Schedule periodic checks for market open times.

        This method creates a persistent background task that monitors current time
        and automatically starts WebSocket connection at market open (9:00 AM IST).

        Behavior:
        - Checks every 60 seconds when market hours are approaching
        - Checks every 300 seconds when market is definitely closed
        - Automatically connects at 9:00 AM IST (pre-open session)
        - Reconnects at 9:15 AM IST if connection failed during pre-open
        - Stops checking during active trading hours (9:00 AM - 3:30 PM IST)

        Note:
            Uses IST timezone for accurate market timing detection.
        """
        import pytz

        async def check_market_open():
            ist = pytz.timezone("Asia/Kolkata")
            logger.info("🕐 Market open scheduler started - will auto-connect at 9:00 AM IST")
            heartbeat_counter = 0

            while self.is_running:
                try:
                    # Get current IST time
                    now_ist = datetime.now(ist)
                    current_time = now_ist.time()
                    current_day = now_ist.weekday()

                    # Heartbeat every 15 minutes
                    heartbeat_counter += 1
                    # Since loop sleep varies, we just use a simple counter for 60s intervals 
                    # or better, check time.
                    if now_ist.minute % 15 == 0:
                         logger.debug(f"💓 Centralized WS Manager Heartbeat: Market scheduler active at {now_ist.strftime('%H:%M:%S')} IST")
                         # Log status summary
                         logger.debug(f"📊 Status: Running={self.is_running}, Ready={self._is_connection_ready}, Data Count={self.data_count}")

                    # Define market timings in IST
                    pre_market_start = time(9, 0)   # 9:00 AM - Pre-open starts
                    market_open = time(9, 15)       # 9:15 AM - Regular market opens
                    market_close = time(15, 30)     # 3:30 PM - Market closes

                    # Check if it's a weekday
                    is_weekday = current_day < 5  # Monday=0, Friday=4

                    # Determine if market should be open (9:00 AM - 3:30 PM IST on weekdays)
                    market_should_be_open = (
                        is_weekday
                        and current_time >= pre_market_start
                        and current_time <= market_close
                    )

                    # Special handling for 9:00 AM and 9:15 AM connection triggers
                    is_pre_open_time = (
                        is_weekday
                        and current_time >= pre_market_start
                        and current_time < market_open
                    )

                    is_market_open_time = (
                        is_weekday
                        and current_time >= market_open
                        and current_time <= market_close
                    )

                    # Auto-connect logic
                    if market_should_be_open and not self.connection_ready.is_set():
                        if is_pre_open_time:
                            logger.info(
                                "🔔 PRE-OPEN TIME (9:00 AM IST) - Auto-starting WebSocket connection"
                            )
                        elif is_market_open_time:
                            logger.info(
                                "🔔 MARKET OPEN TIME (9:15 AM+ IST) - Auto-starting WebSocket connection"
                            )
                        else:
                            logger.info(
                                "🔔 Market hours detected - Starting WebSocket connection"
                            )

                        self._shutdown_scheduled = False

                        # Start connection in background
                        task = asyncio.create_task(self._maintain_connection())
                        self.background_tasks.add(task)
                        task.add_done_callback(self.background_tasks.discard)

                        # Wait a bit before next check
                        await asyncio.sleep(60)

                    # Dynamic sleep time based on market status
                    if not is_weekday:
                        # Weekend - check every 30 minutes
                        sleep_time = 1800
                        logger.debug("📅 Weekend - Next check in 30 minutes")
                    elif market_should_be_open:
                        # During market hours - check every 30 minutes (connection should be stable)
                        sleep_time = 1800
                        logger.debug("📊 Market hours - Next check in 30 minutes")
                    elif current_time < pre_market_start:
                        # Before market open - check more frequently as we approach 9:00 AM
                        time_to_open = (
                            datetime.combine(datetime.today(), pre_market_start)
                            - datetime.combine(datetime.today(), current_time)
                        ).total_seconds()

                        if time_to_open <= 600:  # Within 10 minutes of market open
                            sleep_time = 60  # Check every minute
                            logger.info(f"⏰ Market opens in {int(time_to_open/60)} minutes - Checking every minute")
                        elif time_to_open <= 1800:  # Within 30 minutes
                            sleep_time = 300  # Check every 5 minutes
                            logger.debug(f"⏰ Market opens in {int(time_to_open/60)} minutes - Checking every 5 minutes")
                        else:
                            sleep_time = 600  # Check every 10 minutes
                            logger.debug("💤 Pre-market - Checking every 10 minutes")
                    else:
                        # After market close - check every 10 minutes
                        sleep_time = 600
                        logger.debug("💤 Post-market - Checking every 10 minutes")

                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    logger.error(f"❌ Error in market open check: {e}")
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
                    await asyncio.sleep(300)  # Wait 5 minutes on error

            logger.info("🛑 Market open scheduler stopped")

        task = asyncio.create_task(check_market_open())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        logger.info("✅ Market open scheduler task created successfully")

    async def _update_cache(self, feed_data: dict):
        """Update market data cache with proper data extraction and field mapping"""
        if not feed_data:
            return

        processed_count = 0
        indices_count = 0
        stocks_count = 0

        # Process each instrument
        for instrument_key, raw_data in feed_data.items():
            try:
                # Extract data based on Upstox feed structure
                extracted_data = self._extract_by_format(raw_data)

                if extracted_data and extracted_data.get("ltp", 0) > 0:
                    # CRITICAL FIX: Add frontend-compatible field mapping
                    processed_data = {
                        **extracted_data,
                        "last_price": extracted_data.get(
                            "ltp", 0
                        ),  # Map ltp → last_price for frontend
                        "symbol": self._extract_symbol_from_key(instrument_key),
                        "timestamp": datetime.now().isoformat(),
                    }

                    # Update cache with processed data
                    self.market_data_cache[instrument_key] = processed_data
                    processed_count += 1

                    # Count by type
                    if "INDEX|" in instrument_key:
                        indices_count += 1
                    else:
                        stocks_count += 1
                else:
                    # Still store raw data for debugging but mark as incomplete
                    incomplete_data = {
                        "raw_data": raw_data,
                        "symbol": self._extract_symbol_from_key(instrument_key),
                        "ltp": 0,
                        "last_price": 0,
                        "status": "incomplete",
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.market_data_cache[instrument_key] = incomplete_data

            except Exception as e:
                logger.warning(f"⚠️ Error processing {instrument_key}: {e}")

        # Log processing stats
        if processed_count > 0:
            logger.info(
                f"📊 Processed {processed_count} instruments ({indices_count} indices, {stocks_count} stocks)"
            )

        # Store in Redis if available
        if redis_manager and processed_count > 0:
            try:
                essential_data = {}
                for key, data in self.market_data_cache.items():
                    if isinstance(data, dict) and data.get("ltp", 0) > 0:
                        essential_data[key] = {
                            "ltp": data.get("ltp", 0),
                            "last_price": data.get(
                                "last_price", 0
                            ),  # Include frontend field
                            "ltq": data.get("ltq"),
                            "cp": data.get("cp"),
                            "symbol": data.get("symbol"),
                            "timestamp": data.get(
                                "timestamp", datetime.now().isoformat()
                            ),
                        }

                redis_manager.set("market_data_cache", essential_data, ttl=3600)
            except Exception as e:
                logger.warning(f"⚠️ Failed to store market data in Redis: {e}")

    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key with proper resolution"""
        try:
            # Format: "NSE_EQ|ISIN" or "NSE_INDEX|Nifty 50"
            if "|" in instrument_key:
                parts = instrument_key.split("|", 1)
                if len(parts) == 2:
                    exchange_segment, identifier = parts

                    # For NSE_EQ with ISIN, try to resolve to trading symbol
                    if (
                        "NSE_EQ" in exchange_segment
                        and len(identifier) == 12
                        and identifier.startswith("INE")
                    ):
                        # Try to get trading symbol from cached data or instrument registry
                        cached_data = self.market_data_cache.get(instrument_key)
                        if cached_data and cached_data.get("trading_symbol"):
                            return cached_data["trading_symbol"]

                        # Try to get from instrument registry
                        symbol_info = self._resolve_instrument_symbol(instrument_key)
                        if symbol_info and symbol_info.get("symbol"):
                            return symbol_info["symbol"]

                        # Fallback to identifier if resolution fails
                        return identifier
                    else:
                        # For indices and other formats, use identifier directly
                        return identifier

                return instrument_key.split("|", 1)[1]
            return instrument_key
        except:
            return instrument_key

    async def _handle_connection_stop(self):
        """Handle WebSocket connection stop"""
        logger.warning("🛑 WebSocket connection stopped")
        self.ws_client = None
        self.connection_ready.clear()

        await self._broadcast_connection_status(
            {"status": "disconnected", "message": "WebSocket connection lost"}
        )

        await self._execute_callbacks(
            "connection_status",
            {
                "status": "disconnected",
                "message": "WebSocket connection lost",
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def _handle_auth_error(self):
        """Handle authentication errors"""
        logger.error("🔐 Admin token authentication failed")
        self.connection_ready.clear()

        # CRITICAL FIX: Schedule token refresh in background WITHOUT blocking
        logger.info("🔄 Scheduling automated token refresh in background...")
        await self._try_automated_refresh()
        logger.info("✅ Token refresh scheduled in background - will reload automatically when ready")

        # Try to reload token from database (in case it was recently refreshed)
        token_refreshed = await self._load_admin_token()

        if not token_refreshed:
            # Send error notification with enhanced troubleshooting
            subject = "🚨 Critical: Trading Bot Admin Token Expired"
            message = f"""
            The admin token for the centralized WebSocket manager has expired.
            Automated refresh failed - manual intervention required.
            
            Immediate action required:
            1. Log in to the admin dashboard
            2. Refresh the Upstox broker connection manually
            3. Verify the new token is valid
            
            If running on Windows and automation fails:
            1. Browser automation may not work due to subprocess limitations
            2. Consider running from WSL for automated token refresh
            3. Use manual token refresh via Upstox website as workaround
            
            System Impact:
            - Real-time market data will not be available
            - Trading signals may be delayed
            - Dashboard updates will stop
            
            Time: {datetime.now()}
            Reconnect attempts: {self.reconnect_attempts}/{self.max_reconnect_attempts}
            """

            try:
                email_sent = email_service.send_notification(
                    recipient_email=ADMIN_EMAIL, subject=subject, message=message
                )
                if email_sent:
                    logger.info("📧 Sent admin token expiration alert")
            except Exception as e:
                logger.error(f"Error sending token expiration email: {e}")

            # Notify registered services via callbacks (NO UI broadcasting)
            await self._execute_callbacks(
                "error",
                {
                    "reason": "admin_token_expired",
                    "message": "Admin authentication failed",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            self.is_running = False

    async def _execute_callbacks(self, event_type: str, data: dict):
        """Execute registered callbacks for an event type"""
        if event_type not in self.callbacks:
            return

        callbacks = self.callbacks[event_type]
        if not callbacks:
            return

        if not isinstance(data, dict):
            logger.error(
                f"Invalid data type for {event_type}: expected dict, got {type(data).__name__}. "
                f"Data: {str(data)[:200]}"
            )
            return

        if "timestamp" not in data:
            data["timestamp"] = datetime.now().isoformat()

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)

                self.performance_metrics["callbacks_executed"] += 1

            except Exception as e:
                logger.error(
                    f"Error in {event_type} callback {callback.__name__}: {e}",
                    exc_info=True,
                )

    async def _send_max_reconnections_email(self):
        """Send critical email when max reconnection attempts reached"""
        subject = "🚨 CRITICAL: WebSocket Connection Failed"
        message = f"""
        The centralized WebSocket manager has failed after maximum reconnection attempts.
        
        Critical Details:
        - Max Attempts Reached: {self.max_reconnect_attempts}
        - Last Successful Connection: {self.last_data_received.isoformat() if self.last_data_received else 'Never'}
        
        System Impact:
        - Real-time market data has stopped
        - Trading signals will be delayed
        - Dashboard updates are frozen
        
        Immediate Action Required:
        1. Check Upstox API status
        2. Verify admin token validity
        3. Restart the WebSocket manager service
        """

        try:
            email_sent = email_service.send_notification(
                recipient_email=ADMIN_EMAIL, subject=subject, message=message
            )
            if email_sent:
                logger.info("📧 Sent max reconnections alert")
        except Exception as e:
            logger.error(f"❌ Error sending max reconnections email: {e}")

    # ===== PUBLIC API METHODS =====

    def register_callback(self, event_type: str, callback: CallbackFunction) -> bool:
        """
        Register a callback function for specific event types.

        Services can register callbacks to receive notifications for
        various events like market data updates, connection status changes,
        analytics updates, etc.

        Supported Event Types:
        - price_update: Market data updates
        - analytics_update: Analytics engine updates
        - connection_status: Connection state changes
        - market_status: Market open/close status
        - error: Error notifications
        - emergency_disconnect: Emergency disconnection events

        Args:
            event_type: Type of event to listen for (see supported types above)
            callback: Async or sync function to call when event occurs
                Signature: callback(data: dict) -> None

        Returns:
            True if registered successfully

        Raises:
            No exceptions raised - errors are logged internally

        Example:
            def handle_price_update(data: dict):
                print(f"Received price update: {data}")

            manager.register_callback("price_update", handle_price_update)
        """
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []

        self.callbacks[event_type].append(callback)
        logger.debug(f"Registered callback for {event_type}")
        return True

    def unregister_callback(self, event_type: str, callback: CallbackFunction) -> bool:
        """
        Unregister a previously registered callback.

        Args:
            event_type: Type of event the callback was registered for
            callback: The callback function to unregister

        Returns:
            True if unregistered successfully, False if callback not found

        Raises:
            No exceptions raised - errors are logged internally
        """
        if event_type in self.callbacks and callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
            logger.debug(f"Unregistered callback for {event_type}")
            return True
        return False

    async def stop(self):
        """Stop the centralized manager"""
        logger.info("🛑 Stopping centralized WebSocket manager")
        self.is_running = False

        if self.ws_client:
            self.ws_client.stop()
            self.ws_client = None

        self.connection_ready.clear()
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()

        return True

    # ===== DATA ACCESS METHODS =====

    def get_latest_data(self, instrument_key: str) -> Optional[dict]:
        """Get latest data for a specific instrument"""
        return self.market_data_cache.get(instrument_key)

    def get_market_status(self) -> str:
        """Get current market status"""
        return self.market_status

    def get_last_update_time(self, instrument_key: str = None) -> Optional[str]:
        """Get timestamp of last update"""
        if instrument_key:
            data = self.market_data_cache.get(instrument_key)
            return data.get("timestamp") if data else None

        return self.last_data_received.isoformat() if self.last_data_received else None

    # ===== STATUS METHODS =====

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the manager"""
        return {
            "is_running": self.is_running,
            "admin_user_id": self.admin_user_id,
            "ws_connected": self.connection_ready.is_set(),
            "market_status": self.market_status,
            "market_phases": self.market_phases,
            "active_segments": self.active_segments,
            "total_instruments": len(self.all_instrument_keys),
            "active_instruments": len(self.active_instrument_keys),
            "data_stats": {
                "cached_instruments": len(self.market_data_cache),
                "update_count": self.update_count,
                "data_count": self.data_count,
            },
            "reconnect_attempts": self.reconnect_attempts,
            "last_data_received": (
                self.last_data_received.isoformat() if self.last_data_received else None
            ),
            "timestamp": datetime.now().isoformat(),
        }

    def mark_startup_complete(self):
        """Mark startup phase as complete and allow token refreshes"""
        self._is_startup_phase = False
        logger.info("✅ Startup phase completed - token refresh now enabled")

        # Schedule deferred token refresh if needed
        if hasattr(self, "_needs_token_refresh") and self._needs_token_refresh:
            logger.info("🔄 Scheduling deferred token refresh...")
            asyncio.create_task(self._perform_deferred_token_refresh())

    async def _perform_deferred_token_refresh(self):
        """Perform the token refresh that was deferred during startup"""
        try:
            logger.info("🔄 Performing deferred token refresh...")
            refresh_success = await self._try_automated_refresh()
            if refresh_success:
                logger.info("✅ Deferred token refresh completed successfully")
                # Reload the token
                await self._load_admin_token()
            else:
                logger.warning("⚠️ Deferred token refresh failed")
        except Exception as e:
            logger.error(f"❌ Error in deferred token refresh: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        status = self.get_status()

        # Calculate health score
        health_score = 100
        issues = []

        if not self.is_running:
            health_score -= 50
            issues.append("Service not running")

        if not status["ws_connected"]:
            health_score -= 30
            issues.append("WebSocket not connected")

        if self.reconnect_attempts > 0:
            health_score -= min(5 * self.reconnect_attempts, 25)
            issues.append(f"Recent reconnection attempts: {self.reconnect_attempts}")

        if not self.market_data_cache:
            health_score -= 10
            issues.append("No cached market data")

        # Check data freshness
        if self.last_data_received:
            time_since_data = (datetime.now() - self.last_data_received).total_seconds()
            if time_since_data > 300:  # 5 minutes
                health_score -= 15
                issues.append(f"No data received for {int(time_since_data/60)} minutes")

        status.update(
            {
                "health_score": max(0, health_score),
                "status": (
                    "healthy"
                    if health_score > 70
                    else "degraded" if health_score > 30 else "unhealthy"
                ),
                "issues": issues,
            }
        )

        return status

    async def _enrich_price_data(self, feeds: dict) -> dict:
        """🚀 FAST: Enrich price data with metadata (sector, symbol, etc.) in <3ms"""
        try:
            from services.instrument_registry import instrument_registry

            # Update and get enriched data in one operation (fast)
            enriched_data = instrument_registry.update_and_enrich_prices(feeds)
            return enriched_data if enriched_data else feeds

        except Exception as e:
            logger.debug(f"Price enrichment error: {e}")
            # Return original feeds if enrichment fails
            return feeds

    async def _process_analytics_background(
        self, feeds: dict, enriched_feeds: dict, is_snapshot: bool, data: dict
    ):
        """Background processing for analytics (non-blocking, can have slight delay)"""
        try:
            from services.unified_websocket_manager import unified_manager

            # Update cache (background)
            await self._update_cache(feeds)

            # Update registry (background)
            # await self._legacy_registry_update(feeds)

            # Queue analytics dashboard update (can have delay)
            dashboard_data = {
                "data": enriched_feeds,
                "market_open": self.market_status == "open",
                "timestamp": data.get("currentTs", datetime.now().isoformat()),
                "update_count": self.update_count,
                "is_snapshot": is_snapshot,
            }

            logger.debug(
                f"📊 BACKGROUND: Analytics processing started for {len(enriched_feeds)} instruments"
            )

            # 🚀 REMOVED: Redundant unified manager call
            # Dashboard updates now handled by instrument registry UI callbacks

            # Execute other callbacks
            await self._execute_callbacks(
                "price_update",
                {
                    "data": enriched_feeds,
                    "is_snapshot": is_snapshot,
                    "timestamp": datetime.now().isoformat(),
                    "source": "background_analytics",
                },
            )

        except Exception as e:
            logger.debug(f"Background analytics processing error: {e}")

    # ===== AUTO-TRADING SPECIFIC METHODS =====

    def get_fno_stocks_list(self) -> List[str]:
        """Get only F&O stocks from 5 indices for auto-trading"""
        try:
            fno_stocks = []
            indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]

            # Get all instrument keys and filter for F&O stocks
            for instrument_key in self.all_instrument_keys:
                try:
                    # Parse instrument key format: NSE_EQ|INE002A01018
                    if "NSE_FO|" in instrument_key:  # F&O instruments
                        # Extract symbol from F&O instrument key
                        symbol_part = (
                            instrument_key.split("|")[1]
                            if "|" in instrument_key
                            else instrument_key
                        )

                        # Check if it belongs to our 5 indices
                        # This is a simplified check - in practice, you'd have a mapping
                        if any(
                            idx in symbol_part.upper()
                            for idx in ["NIFTY", "BANK", "FINN", "MIDCAP", "SENSEX"]
                        ):
                            fno_stocks.append(instrument_key)

                except Exception as e:
                    logger.debug(f"Error parsing instrument key {instrument_key}: {e}")
                    continue

            logger.info(f"📊 Found {len(fno_stocks)} F&O stocks from 5 indices")
            self.fno_stocks_keys = set(fno_stocks)
            return fno_stocks

        except Exception as e:
            logger.error(f"❌ Error getting F&O stocks list: {e}")
            return []

    def market_hours_validation(self) -> Dict[str, Any]:
        """Validate F&O trading hours and market session status"""
        try:
            now = datetime.now()
            current_time = now.time()
            current_day = now.weekday()  # 0=Monday, 6=Sunday

            # F&O trading hours: 9:15 AM to 3:30 PM, Monday to Friday
            fno_start_time = datetime.strptime("09:15:00", "%H:%M:%S").time()
            fno_end_time = datetime.strptime("15:30:00", "%H:%M:%S").time()

            # Pre-market preparation time: 8:45 AM to 9:15 AM
            pre_market_start = datetime.strptime("08:45:00", "%H:%M:%S").time()

            # Post-market processing time: 3:30 PM to 4:00 PM
            post_market_end = datetime.strptime("16:00:00", "%H:%M:%S").time()

            is_weekday = current_day < 5  # Monday to Friday
            is_fno_hours = fno_start_time <= current_time <= fno_end_time
            is_pre_market = pre_market_start <= current_time < fno_start_time
            is_post_market = fno_end_time < current_time <= post_market_end

            market_session = "closed"
            auto_trading_allowed = False

            if is_weekday:
                if is_fno_hours:
                    market_session = "active"
                    auto_trading_allowed = True
                elif is_pre_market:
                    market_session = "pre_market"
                    auto_trading_allowed = False  # Stock selection only
                elif is_post_market:
                    market_session = "post_market"
                    auto_trading_allowed = False
                else:
                    market_session = "closed"
                    auto_trading_allowed = False

            return {
                "market_session": market_session,
                "auto_trading_allowed": auto_trading_allowed,
                "is_weekday": is_weekday,
                "is_fno_hours": is_fno_hours,
                "is_pre_market": is_pre_market,
                "is_post_market": is_post_market,
                "current_time": current_time.strftime("%H:%M:%S"),
                "fno_start": fno_start_time.strftime("%H:%M:%S"),
                "fno_end": fno_end_time.strftime("%H:%M:%S"),
            }

        except Exception as e:
            logger.error(f"❌ Error in market hours validation: {e}")
            return {
                "market_session": "unknown",
                "auto_trading_allowed": False,
                "error": str(e),
            }

    async def emergency_disconnection_handling(self, reason: str = "emergency") -> bool:
        """Emergency disconnect for system safety during trading"""
        try:
            logger.critical(f"🚨 EMERGENCY DISCONNECTION TRIGGERED: {reason}")

            # Immediately stop auto-trading
            self.auto_trading_active = False

            # Clear priority subscriptions
            self.priority_instruments.clear()
            self.selected_stocks_for_trading.clear()

            # Stop WebSocket connection
            if self.ws_client:
                try:
                    self.ws_client.stop()
                    logger.info("✅ WebSocket connection stopped")
                except Exception as e:
                    logger.error(f"❌ Error stopping WebSocket: {e}")

            # Notify registered services via callbacks (NO UI broadcasting)
            emergency_message = {
                "type": "emergency_disconnect",
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "action_required": "manual_restart",
            }

            # Execute callbacks to notify services
            await self._execute_callbacks("emergency_disconnect", emergency_message)

            # Update connection status
            self.is_running = False
            self.connection_ready.clear()

            logger.critical(f"🚨 Emergency disconnection completed: {reason}")
            return True

        except Exception as e:
            logger.critical(f"❌ Error in emergency disconnection: {e}")
            return False

    def get_auto_trading_status(self) -> Dict[str, Any]:
        """Get current auto-trading status and metrics"""
        try:
            return {
                "auto_trading_active": self.auto_trading_active,
                "priority_instruments_count": len(self.priority_instruments),
                "selected_stocks_count": len(self.selected_stocks_for_trading),
                "fno_stocks_count": len(self.fno_stocks_keys),
                "market_validation": self.market_hours_validation(),
                "performance_metrics": self.performance_metrics.copy(),
                "websocket_connected": (
                    self.ws_client
                    and hasattr(self.ws_client, "is_connected")
                    and self.ws_client.is_connected()
                ),
                "last_data_received": (
                    self.last_data_received.isoformat()
                    if self.last_data_received
                    else None
                ),
            }
        except Exception as e:
            logger.error(f"❌ Error getting auto-trading status: {e}")
            return {"error": str(e)}


# Create singleton instance
centralized_manager = CentralizedWebSocketManager()

# ===== CONVENIENCE FUNCTIONS FOR EASY IMPORT =====


def get_centralized_manager() -> CentralizedWebSocketManager:
    """Get the singleton centralized manager instance"""
    return centralized_manager


async def initialize_centralized_websocket() -> bool:
    """Initialize the centralized WebSocket manager"""
    return await centralized_manager.initialize()


async def start_centralized_websocket() -> bool:
    """Start the centralized WebSocket connection"""
    return await centralized_manager.start_connection()


def register_market_data_callback(callback: CallbackFunction) -> bool:
    """Register a callback for market data updates"""
    return centralized_manager.register_callback("price_update", callback)


def register_market_status_callback(callback: CallbackFunction) -> bool:
    """Register a callback for market status updates"""
    return centralized_manager.register_callback("market_status", callback)


def get_latest_market_price(instrument_key: str) -> Optional[float]:
    """Get the latest price for an instrument"""
    return centralized_manager.get_latest_price(instrument_key)


def get_market_status() -> str:
    """Get current market status"""
    return centralized_manager.get_market_status()


def get_centralized_websocket_status() -> Dict[str, Any]:
    """Get status of the centralized WebSocket manager"""
    return centralized_manager.get_status()


async def stop_centralized_websocket() -> bool:
    """Stop the centralized WebSocket manager"""
    return await centralized_manager.stop()


# ===== AUTO-TRADING CONVENIENCE FUNCTIONS =====


def get_fno_stocks() -> List[str]:
    """Get F&O stocks from 5 indices"""
    return centralized_manager.get_fno_stocks_list()


def get_market_hours_status() -> Dict[str, Any]:
    """Get F&O market hours validation"""
    return centralized_manager.market_hours_validation()


async def emergency_stop(reason: str = "manual") -> bool:
    """Emergency stop auto-trading system"""
    return await centralized_manager.emergency_disconnection_handling(reason)


def get_auto_trading_metrics() -> Dict[str, Any]:
    """Get auto-trading status and performance metrics"""
    return centralized_manager.get_auto_trading_status()


# For any existing imports that might be looking for these
websocket_manager = centralized_manager  # Alias for backwards compatibility
manager = centralized_manager  # Short alias
