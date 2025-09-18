# router/unified_websocket_routes.py - ENHANCED VERSION
"""
Enhanced Unified WebSocket Routes with better error handling
"""

from typing import Any, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import json
from datetime import datetime
import logging
import asyncio
import uuid
import traceback

from services.unified_websocket_manager import unified_manager


logger = logging.getLogger(__name__)


router = APIRouter()


@router.websocket("/ws/unified")
async def unified_websocket_endpoint(websocket: WebSocket):
    """
    ENHANCED: Single WebSocket endpoint with user-based connection deduplication
    """
    client_id = None
    user_id = None

    try:
        # FIXED: Accept the WebSocket connection directly in the route handler
        await websocket.accept()
        logger.info("✅ WebSocket connection accepted")

        # Extract user information from query parameters
        query_params = dict(websocket.query_params)
        user_id = query_params.get('user_id')
        session_id = query_params.get('session_id')
        client_type = query_params.get('client_type', 'dashboard')
        
        logger.info(f"🔍 Connection params: user_id={user_id}, session_id={session_id}, client_type={client_type}")
        logger.info(f"🔍 All query params: {query_params}")

        # Enhanced client ID generation with better fallback handling and deduplication
        if user_id and session_id:
            # Extract last part of session_id for shorter client_id
            session_suffix = session_id.split('_')[-1] if '_' in session_id else session_id[:8]
            client_id = f"{client_type}_{user_id.replace('user_', '')}_{session_suffix}"
            logger.info(f"✅ Generated user-specific client_id: {client_id}")
        else:
            # Enhanced fallback: Check for existing temp connection to avoid duplicates
            client_ip = websocket.client.host if hasattr(websocket, 'client') and websocket.client else 'unknown'
            user_agent = query_params.get('user_agent', 'unknown')
            
            # Create a stable temp user ID based on client info to reduce duplicates
            import hashlib
            stable_hash = hashlib.md5(f"{client_ip}_{user_agent}_{client_type}".encode()).hexdigest()[:8]
            temp_user_id = f"temp_{stable_hash}"
            client_id = f"{client_type}_{temp_user_id}"
            user_id = temp_user_id
            
            # Clean up any existing temp connections from the same source
            await _cleanup_temp_connections(client_ip, client_type, client_id)
            
            logger.info(f"✅ Generated stable temp client_id: {client_id} (IP: {client_ip})")

        # CRITICAL: Close existing connections for this user to prevent duplicates
        if user_id:  # Only cleanup if we have a valid user_id
            await _cleanup_user_connections(user_id, client_type, client_id)
        else:
            logger.warning(f"⚠️ Connection without user_id - cannot deduplicate!")

        # Register with the unified manager
        unified_manager.connections[client_id] = websocket
        unified_manager.client_types[client_id] = client_type
        unified_manager.client_subscriptions[client_id] = set()
        
        # Track user-to-client mapping for deduplication
        if not hasattr(unified_manager, 'user_connections'):
            unified_manager.user_connections = {}
        if user_id:
            if user_id not in unified_manager.user_connections:
                unified_manager.user_connections[user_id] = {}
            unified_manager.user_connections[user_id][client_type] = client_id
        
        # AUTO-SUBSCRIBE: Automatically subscribe clients to relevant events based on client type
        default_subscriptions = {
            'dashboard': [
                'top_movers_update', 
                'intraday_stocks_update', 
                'volume_analysis_update',
                'market_sentiment_update', 
                'indices_data_update',
                'price_update',
                'dashboard_update',
                'breakout_analysis_update'
            ],
            'trading': [
                'price_update', 
                'live_prices_enriched',
                'index_update',
                'dashboard_update'
            ],
            'analytics': [
                'top_movers_update', 
                'intraday_stocks_update',
                'market_sentiment_update',
                'volume_analysis_update'
            ]
        }
        
        # Subscribe client to default events for their type
        client_events = default_subscriptions.get(client_type, default_subscriptions['dashboard'])
        unified_manager.client_subscriptions[client_id].update(client_events)
        logger.info(f"📡 Auto-subscribed {client_id} to {len(client_events)} events: {client_events}")

        # Send welcome message directly with connection state check
        try:
            welcome_message = {
                "type": "connection_established",
                "client_id": client_id,
                "client_type": client_type,
                "user_id": user_id,
                "available_events": unified_manager.get_available_events(),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Ensure message is JSON serializable
            import json
            json.dumps(welcome_message)  # Test serialization
            
            await websocket.send_json(welcome_message)
            logger.info(f"🔌 Sent welcome message to {client_id}")
        except Exception as welcome_error:
            logger.error(f"❌ Error sending welcome message: {welcome_error}")
            # Connection might be closed, cleanup and return
            return

        logger.info(f"🔌 New client connected: {client_id} (user: {user_id}, type: {client_type})")

        # DON'T send initial data immediately - let client request it
        # This prevents premature connection closure during setup
        logger.info(f"✅ Client {client_id} ready for subscriptions and requests")

        # Message handling loop with connection validation
        while True:
            try:
                # Validate connection is still active before waiting for message
                if client_id not in unified_manager.connections:
                    logger.info(f"🔌 Client {client_id} no longer in connections, exiting loop")
                    break
                
                if not _is_websocket_connected(websocket):
                    logger.info(f"🔌 WebSocket for {client_id} is no longer connected, exiting loop")
                    break
                
                # Receive message from client with timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=300.0
                )  # 5 min timeout

                try:
                    message = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"❌ Invalid JSON from {client_id}: {e}")
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Invalid JSON format",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    continue

                # Handle the message
                await handle_unified_message(client_id, websocket, message)

            except asyncio.TimeoutError:
                # Send ping to check if client is still alive
                success = await _safe_send_json(websocket, client_id, {
                    "type": "ping", 
                    "timestamp": datetime.now().isoformat()
                })
                if not success:
                    logger.info(f"❌ Ping failed for {client_id}, closing connection")
                    break  # Client is dead

            except WebSocketDisconnect:
                logger.info(f"🔌 Client {client_id} disconnected normally")
                break

            except Exception as e:
                logger.error(f"❌ Message handling error for {client_id}: {e}")
                # Only try to send error if connection is still tracked
                if client_id in unified_manager.connections:
                    success = await _safe_send_json(websocket, client_id, {
                        "type": "error",
                        "message": f"Message processing error: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    })
                    if not success:
                        logger.info(f"❌ Cannot send error message to {client_id}, closing connection")
                        break  # Can't send error, connection is probably dead
                else:
                    # Connection already cleaned up, just break
                    break

    except WebSocketDisconnect:
        logger.info(f"🔌 Client disconnected during setup")
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")
        logger.error(traceback.format_exc())

    finally:
        # Clean up
        if client_id:
            if client_id in unified_manager.connections:
                del unified_manager.connections[client_id]
            if client_id in unified_manager.client_types:
                del unified_manager.client_types[client_id]
            if client_id in unified_manager.client_subscriptions:
                del unified_manager.client_subscriptions[client_id]
            
            # Clean up user connection mapping
            if user_id and hasattr(unified_manager, 'user_connections'):
                user_connections = unified_manager.user_connections.get(user_id, {})
                if client_type in user_connections and user_connections[client_type] == client_id:
                    del user_connections[client_type]
                    if not user_connections:  # Remove user entry if no connections left
                        del unified_manager.user_connections[user_id]
            
            logger.info(f"🧹 Cleaned up client: {client_id} (user: {user_id})")


async def _cleanup_temp_connections(client_ip: str, client_type: str, new_client_id: str):
    """Clean up existing temporary connections from the same IP/client to prevent duplicates"""
    try:
        connections_to_remove = []
        for conn_id, conn_ws in list(unified_manager.connections.items()):
            # Check if this is a temp connection for the same client type
            if (conn_id.startswith(f"{client_type}_temp_") and 
                conn_id != new_client_id and
                hasattr(conn_ws, 'client') and conn_ws.client and
                conn_ws.client.host == client_ip):
                connections_to_remove.append(conn_id)
        
        for conn_id in connections_to_remove:
            logger.info(f"🧹 Closing duplicate temp connection: {conn_id} (IP: {client_ip})")
            try:
                existing_ws = unified_manager.connections[conn_id]
                if _is_websocket_connected(existing_ws):
                    await existing_ws.close(code=1000, reason=f"Duplicate {client_type} connection from same client")
                
                # Clean up immediately
                unified_manager.connections.pop(conn_id, None)
                unified_manager.client_types.pop(conn_id, None)
                unified_manager.client_subscriptions.pop(conn_id, None)
                
                logger.info(f"✅ Successfully closed duplicate temp connection: {conn_id}")
                
            except Exception as e:
                logger.error(f"❌ Error closing temp connection {conn_id}: {e}")
    
    except Exception as e:
        logger.error(f"❌ Error cleaning up temp connections for IP {client_ip}: {e}")


async def _cleanup_user_connections(user_id: str, client_type: str, new_client_id: str):
    """Clean up existing connections for a user and client type to prevent duplicates"""
    if not user_id:
        return
        
    try:
        # Initialize user_connections if it doesn't exist
        if not hasattr(unified_manager, 'user_connections'):
            unified_manager.user_connections = {}
            
        user_connections = unified_manager.user_connections.get(user_id, {})
        existing_client_id = user_connections.get(client_type)
        
        # Only cleanup if there's an existing connection that's different from the new one
        if existing_client_id and existing_client_id != new_client_id and existing_client_id in unified_manager.connections:
            logger.info(f"🧹 Closing existing {client_type} connection for user {user_id}: {existing_client_id}")
            
            try:
                existing_ws = unified_manager.connections[existing_client_id]
                if _is_websocket_connected(existing_ws):
                    await existing_ws.close(code=1000, reason=f"New {client_type} connection established")
                
                # Clean up immediately
                del unified_manager.connections[existing_client_id]
                if existing_client_id in unified_manager.client_types:
                    del unified_manager.client_types[existing_client_id]
                if existing_client_id in unified_manager.client_subscriptions:
                    del unified_manager.client_subscriptions[existing_client_id]
                
                logger.info(f"✅ Successfully closed existing connection: {existing_client_id}")
                
            except Exception as e:
                logger.error(f"❌ Error closing existing connection {existing_client_id}: {e}")
        
        # Also cleanup any dangling connections for the same user that may have lost tracking
        connections_to_remove = []
        for conn_id, conn_ws in list(unified_manager.connections.items()):
            # Check if this connection belongs to the same user but different client_id
            if (user_id in conn_id and 
                conn_id != new_client_id and 
                conn_id.startswith(client_type) and
                not _is_websocket_connected(conn_ws)):
                connections_to_remove.append(conn_id)
        
        for conn_id in connections_to_remove:
            logger.info(f"🧹 Removing dangling connection: {conn_id}")
            unified_manager.connections.pop(conn_id, None)
            unified_manager.client_types.pop(conn_id, None)
            unified_manager.client_subscriptions.pop(conn_id, None)
    
    except Exception as e:
        logger.error(f"❌ Error cleaning up connections for user {user_id}: {e}")

def _is_websocket_connected(websocket: WebSocket) -> bool:
    """Check if WebSocket is still connected and ready to send"""
    try:
        return (
            websocket is not None and 
            hasattr(websocket, 'client_state') and 
            websocket.client_state.value <= 1  # CONNECTING or CONNECTED
        )
    except:
        return False

async def _safe_send_json(websocket: WebSocket, client_id: str, data: dict) -> bool:
    """Safely send JSON data with connection validation"""
    try:
        if not _is_websocket_connected(websocket):
            logger.warning(f"⚠️ Attempted to send to disconnected client {client_id}")
            return False
        
        # Validate JSON serializability
        json.dumps(data, default=str)
        await websocket.send_json(data)
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send message to {client_id}: {e}")
        return False

async def handle_unified_message(
    client_id: str, websocket: WebSocket, message: Dict[str, Any]
):
    """Handle messages from clients with improved error handling"""
    try:
        message_type = message.get("type")

        if not message_type:
            success = await _safe_send_json(websocket, client_id, {
                "type": "error",
                "message": "Missing message type",
                "timestamp": datetime.now().isoformat(),
            })
            if not success:
                return  # Connection is dead
            return

        if message_type == "subscribe":
            # Subscribe to specific events
            events = message.get("events", [])
            real_time_mode = message.get("real_time", False)  # NEW: Real-time mode flag
            
            if not isinstance(events, list):
                success = await _safe_send_json(websocket, client_id, {
                    "type": "error",
                    "message": "Events must be a list",
                    "timestamp": datetime.now().isoformat(),
                })
                if not success:
                    return  # Connection is dead
                return

            unified_manager.subscribe_to_events(client_id, events)
            
            # If real-time mode requested, trigger immediate updates
            if real_time_mode:
                try:
                    # ✅ FIX: Ensure analytics service is available and handle gracefully
                    from services.enhanced_market_analytics import enhanced_analytics
                    
                    # Get priority analytics with error handling
                    priority_analytics = enhanced_analytics.get_priority_analytics()
                    
                    if priority_analytics and isinstance(priority_analytics, dict):
                        broadcast_count = 0
                        for feature, data in priority_analytics.items():
                            if feature not in ["generated_at", "processing_time_ms", "is_priority_update"]:
                                unified_manager.emit_event(f"{feature}_update", data, priority=1)
                                broadcast_count += 1
                        
                        logger.info(f"✅ Real-time mode activated for client {client_id} - {broadcast_count} features broadcasted")
                    else:
                        logger.warning(f"⚠️ Real-time mode requested but no analytics data available for client {client_id}")
                        
                except ImportError:
                    logger.warning(f"⚠️ Enhanced analytics service not available for real-time mode activation")
                except Exception as e:
                    logger.error(f"❌ Error activating real-time mode: {e}")

            await _safe_send_json(websocket, client_id, {
                "type": "subscription_confirmed",
                "events": events,
                "real_time_mode": real_time_mode,
                "available_events": unified_manager.get_available_events(),
                "timestamp": datetime.now().isoformat(),
            })

        elif message_type == "get_dashboard_data":
            # FIXED: Enhanced dashboard data with proper error handling
            from services.enhanced_market_analytics import enhanced_analytics

            try:
                # Get complete analytics
                complete_dashboard_data = enhanced_analytics.get_complete_analytics()

                if not isinstance(complete_dashboard_data, dict):
                    logger.error(
                        f"get_complete_analytics expected dict, got {type(complete_dashboard_data)}"
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Invalid analytics data format",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    return

                # CRITICAL FIX: Log what we're sending
                logger.info(
                    f"📊 Dashboard data features: {list(complete_dashboard_data.keys())}"
                )

                # Verify each feature has data
                for feature, data in complete_dashboard_data.items():
                    if feature in [
                        "top_movers",
                        "sector_heatmap",
                        "gap_analysis",
                        "volume_analysis",
                    ]:
                        if isinstance(data, dict):
                            logger.info(
                                f"✅ {feature}: {len(data)} keys - sample: {list(data.keys())[:3]}"
                            )
                        else:
                            logger.warning(f"⚠️ {feature}: unexpected type {type(data)}")

                # FIXED: Ensure all required fields are present with defaults
                dashboard_data = {
                    "type": "dashboard_data",
                    "timestamp": datetime.now().isoformat(),
                    # Core analytics
                    "top_movers": complete_dashboard_data.get(
                        "top_movers", {"gainers": [], "losers": []}
                    ),
                    "sector_heatmap": complete_dashboard_data.get(
                        "sector_heatmap", {"sectors": []}
                    ),
                    "gap_analysis": complete_dashboard_data.get(
                        "gap_analysis", {"gap_up": [], "gap_down": []}
                    ),
                    "breakout_analysis": complete_dashboard_data.get(
                        "breakout_analysis", {"breakouts": [], "breakdowns": []}
                    ),
                    "market_sentiment": complete_dashboard_data.get(
                        "market_sentiment", {"sentiment": "neutral"}
                    ),
                    "volume_analysis": complete_dashboard_data.get(
                        "volume_analysis", {"volume_leaders": []}
                    ),
                    "intraday_highlights": complete_dashboard_data.get(
                        "intraday_highlights", {"all_candidates": []}
                    ),
                    "intraday_stocks": complete_dashboard_data.get(
                        "intraday_stocks", {"all_candidates": []}
                    ),
                    "record_movers": complete_dashboard_data.get(
                        "record_movers", {"new_highs": [], "new_lows": []}
                    ),
                    "indices_data": complete_dashboard_data.get(  # NEW: Added indices data
                        "indices_data",
                        {"indices": [], "major_indices": [], "sector_indices": []},
                    ),
                    # Metadata
                    "generated_at": complete_dashboard_data.get("generated_at"),
                    "processing_time_ms": complete_dashboard_data.get(
                        "processing_time_ms"
                    ),
                    "cache_status": complete_dashboard_data.get("cache_status", {}),
                }

                success = await _safe_send_json(websocket, client_id, dashboard_data)
                if success:
                    logger.info(f"✅ Sent enhanced dashboard data to {client_id}")
                else:
                    return  # Connection is dead

            except Exception as e:
                logger.error(f"❌ Error getting dashboard data: {e}")
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")

                await _safe_send_json(websocket, client_id, {
                    "type": "error",
                    "message": f"Error getting dashboard data: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                })

        elif message_type == "get_live_prices":
            try:
                from services.instrument_registry import instrument_registry

                symbols = message.get("symbols", [])

                if symbols and isinstance(symbols, list):
                    # Get specific enriched data for requested symbols
                    enriched_prices = {}
                    enriched_data = instrument_registry.get_enriched_prices()

                    for symbol in symbols:
                        symbol_upper = symbol.upper()
                        for instrument_key, data in enriched_data.items():
                            if data.get("symbol") == symbol_upper:
                                enriched_prices[instrument_key] = data
                                break
                else:
                    # Get all enriched data
                    enriched_prices = instrument_registry.get_enriched_prices()

                await websocket.send_json(
                    {
                        "type": "live_prices_enriched",  # Changed type to indicate enriched data
                        "data": enriched_prices,  # ✅ NOW HAS SYMBOL, NAME, SECTOR
                        "total_instruments": len(enriched_prices),
                        "data_format": "enriched",  # Indicator for frontend
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"Error getting enriched live prices: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error getting live prices: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_options_chain":
            # Get options chain for symbol
            symbol = message.get("symbol")
            expiry = message.get("expiry")

            if not symbol:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Symbol is required for options chain",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return

            try:
                from services.instrument_registry import instrument_registry

                options_data = instrument_registry.get_options_chain(
                    symbol.upper(), expiry
                )

                await websocket.send_json(
                    {
                        "type": "options_chain",
                        "symbol": symbol.upper(),
                        "expiry": expiry,
                        "data": options_data,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"❌ Error getting options chain for {symbol}: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error getting options chain: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_stock_data":
            # Get specific stock data
            symbol = message.get("symbol")

            if not symbol:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Symbol is required",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return

            try:
                from services.instrument_registry import instrument_registry

                stock_data = instrument_registry.get_spot_price(symbol.upper())

                await websocket.send_json(
                    {
                        "type": "stock_data",
                        "symbol": symbol.upper(),
                        "data": stock_data,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"❌ Error getting stock data for {symbol}: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error getting stock data: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_indices_data":
            try:
                from services.enhanced_market_analytics import enhanced_analytics

                indices_data = enhanced_analytics.get_indices_data()

                await websocket.send_json(
                    {
                        "type": "indices_data",
                        "data": indices_data,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                logger.info(
                    f"📈 Sent indices data to {client_id}: {indices_data.get('summary', {}).get('total_indices', 0)} indices"
                )

            except Exception as e:
                logger.error(f"❌ Error getting indices data: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error getting indices data: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "get_sector_data":
            try:
                from services.instrument_registry import instrument_registry

                # Group enriched data by sector
                enriched_data = instrument_registry.get_enriched_prices()
                sector_groups = {}

                for instrument_key, data in enriched_data.items():
                    sector = data.get("sector", "OTHER")
                    if sector not in sector_groups:
                        sector_groups[sector] = []
                    sector_groups[sector].append(data)

                await websocket.send_json(
                    {
                        "type": "sector_data",
                        "data": sector_groups,
                        "total_sectors": len(sector_groups),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"Error getting sector data: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error getting sector data: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "search_stocks":
            try:
                from services.instrument_registry import instrument_registry

                query = message.get("query", "").upper()
                if not query:
                    return

                # Search in enriched data
                enriched_data = instrument_registry.get_enriched_prices()
                search_results = []

                for instrument_key, data in enriched_data.items():
                    symbol = data.get("symbol", "")
                    name = data.get("name", "")

                    if query in symbol or query in name.upper():
                        search_results.append(data)

                        if len(search_results) >= 10:  # Limit results
                            break

                await websocket.send_json(
                    {
                        "type": "search_results",
                        "data": search_results,
                        "query": query,
                        "total_results": len(search_results),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"Error searching stocks: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error searching stocks: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        elif message_type == "ping":
            # Respond to ping
            await websocket.send_json(
                {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "server_time": datetime.now().isoformat(),
                }
            )

        elif message_type == "get_system_status":
            # Get system status
            try:
                status = unified_manager.get_status()

                await websocket.send_json(
                    {
                        "type": "system_status",
                        "data": status,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"❌ Error getting system status: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Error getting system status: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        else:
            # Unknown message type
            await websocket.send_json(
                {
                    "type": "unknown_message",
                    "received_type": message_type,
                    "available_types": [
                        "subscribe",
                        "get_dashboard_data",
                        "get_live_prices",
                        "get_options_chain",
                        "get_stock_data",
                        "get_indices_data",
                        "get_system_status",
                        "ping",
                    ],
                    "timestamp": datetime.now().isoformat(),
                }
            )

    except Exception as e:
        logger.error(f"❌ Error handling message from {client_id}: {e}")
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Internal error processing message: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception:
            logger.error(f"Failed to send error message to {client_id}")


# REST API endpoints for unified system
@router.get("/api/unified/status")
async def get_unified_status():
    """Get status of unified WebSocket system"""
    try:
        status = unified_manager.get_status()
        return {
            "success": True,
            "status": status,
            "available_events": unified_manager.get_available_events(),
            "websocket_url": "/ws/unified",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error getting unified status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.post("/api/unified/emit-event")
async def emit_test_event(event_data: Dict[str, Any]):
    """Emit a test event (for debugging)"""
    try:
        event_type = event_data.get("type")
        data = event_data.get("data", {})

        if not event_type:
            raise HTTPException(status_code=400, detail="Event type is required")

        unified_manager.emit_event(event_type, data)

        return {
            "success": True,
            "message": f"Event {event_type} emitted",
            "event_type": event_type,
            "data_size": len(str(data)),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error emitting test event: {e}")
        raise HTTPException(status_code=500, detail=f"Error emitting event: {str(e)}")


@router.get("/api/unified/indices")
async def get_indices_data():
    """Get current indices data"""
    try:
        from services.enhanced_market_analytics import enhanced_analytics

        indices_data = enhanced_analytics.get_indices_data()

        return {
            "success": True,
            "data": indices_data,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error getting indices data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting indices data: {str(e)}"
        )


@router.get("/api/unified/indices/{symbol}")
async def get_specific_index_data(symbol: str):
    """Get specific index data by symbol"""
    try:
        from services.instrument_registry import instrument_registry

        index_data = instrument_registry.get_spot_price(symbol.upper())

        if not index_data:
            raise HTTPException(status_code=404, detail=f"Index {symbol} not found")

        return {
            "success": True,
            "symbol": symbol.upper(),
            "data": index_data,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting index data for {symbol}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting index data: {str(e)}"
        )


@router.post("/api/unified/trigger-indices-refresh")
async def trigger_indices_refresh():
    """Manually trigger indices data refresh"""
    try:
        from services.enhanced_market_analytics import enhanced_analytics

        # Clear indices cache
        if "indices_data" in enhanced_analytics.cache:
            del enhanced_analytics.cache["indices_data"]
        if "indices_data" in enhanced_analytics.last_calculated:
            del enhanced_analytics.last_calculated["indices_data"]

        # Get fresh indices data
        indices_data = enhanced_analytics.get_indices_data()

        # Emit the update event
        unified_manager.emit_event("indices_data_update", indices_data)

        return {
            "success": True,
            "message": "Indices data refreshed successfully",
            "total_indices": indices_data.get("summary", {}).get("total_indices", 0),
            "major_indices": len(indices_data.get("major_indices", [])),
            "sector_indices": len(indices_data.get("sector_indices", [])),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error refreshing indices data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error refreshing indices data: {str(e)}"
        )


@router.get("/api/unified/market-summary")
async def get_market_summary_with_indices():
    """Get comprehensive market summary including indices"""
    try:
        from services.enhanced_market_analytics import enhanced_analytics
        from services.instrument_registry import instrument_registry

        # Get analytics data
        analytics = enhanced_analytics.get_complete_analytics()

        # Get registry market summary
        try:
            registry_summary = instrument_registry.get_market_summary()
        except AttributeError:
            registry_summary = {}

        # Combine data
        market_summary = {
            "indices": analytics.get("indices_data", {}),
            "market_sentiment": analytics.get("market_sentiment", {}),
            "market_breadth": registry_summary,
            "top_movers": analytics.get("top_movers", {}),
            "sector_performance": analytics.get("sector_heatmap", {}),
            "volume_analysis": analytics.get("volume_analysis", {}),
            "timestamp": datetime.now().isoformat(),
        }

        return {
            "success": True,
            "data": market_summary,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error getting market summary: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting market summary: {str(e)}"
        )


@router.get("/api/unified/analytics")
async def get_current_analytics():
    """Get current analytics data"""
    try:
        return {
            "success": True,
            "data": unified_manager.analytics_cache,
            "live_prices_count": len(unified_manager.live_prices),
            "cache_keys": list(unified_manager.analytics_cache.keys()),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error getting analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting analytics: {str(e)}"
        )


@router.get("/api/unified/connections")
async def get_connection_info():
    """Get information about active connections"""
    try:
        status = unified_manager.get_status()

        return {
            "success": True,
            "connections": {
                "total": status["total_connections"],
                "by_type": status["client_types"],
                "active_subscriptions": len(unified_manager.client_subscriptions),
            },
            "system": {
                "event_queue_size": status["event_queue_size"],
                "background_tasks": status["background_tasks"],
                "is_running": status["is_running"],
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error getting connection info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting connection info: {str(e)}"
        )


@router.post("/api/unified/restart")
async def restart_unified_system():
    """Restart the unified WebSocket system (admin only)"""
    try:
        logger.info("🔄 Restarting unified WebSocket system...")

        # Stop current system
        await unified_manager.stop()

        # Wait a moment
        await asyncio.sleep(2)

        # Start again
        await unified_manager.start()

        return {
            "success": True,
            "message": "Unified WebSocket system restarted successfully",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error restarting unified system: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error restarting system: {str(e)}"
        )


@router.get("/api/unified/health")
async def health_check():
    """Health check endpoint"""
    try:
        status = unified_manager.get_status()

        health_score = 100
        issues = []

        if not status["is_running"]:
            health_score -= 50
            issues.append("System not running")

        if status["total_connections"] == 0:
            health_score -= 10
            issues.append("No active connections")

        if status["event_queue_size"] > 900:  # Near queue limit
            health_score -= 20
            issues.append("Event queue nearly full")

        if len(status["cached_analytics"]) == 0:
            health_score -= 15
            issues.append("No cached analytics")

        health_status = (
            "healthy"
            if health_score >= 80
            else "degraded" if health_score >= 50 else "unhealthy"
        )

        return {
            "success": True,
            "health": {
                "status": health_status,
                "score": max(0, health_score),
                "issues": issues,
            },
            "system": status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error in health check: {e}")
        return {
            "success": False,
            "health": {
                "status": "error",
                "score": 0,
                "issues": [f"Health check failed: {str(e)}"],
            },
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/api/unified/trigger-analytics")
async def trigger_analytics_refresh():
    """Manually trigger analytics refresh"""
    try:
        try:
            from services.enhanced_market_analytics import enhanced_analytics

            analytics_data = enhanced_analytics.get_complete_analytics()

            # Store in unified manager cache
            unified_manager.analytics_cache = analytics_data

            # Emit events for each feature
            for feature, data in analytics_data.items():
                if feature not in [
                    "generated_at",
                    "processing_time_ms",
                    "cache_status",
                ]:
                    unified_manager.emit_event(f"{feature}_update", data)

            return {
                "success": True,
                "message": "Analytics refreshed successfully",
                "features": list(analytics_data.keys()),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"❌ Error refreshing analytics: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error refreshing analytics: {str(e)}"
            )
    except Exception as e:
        logger.error(f"❌ Unhandled error in trigger_analytics_refresh: {e}")
        raise HTTPException(status_code=500, detail=f"Unhandled error: {str(e)}")
