# import asyncio
# import json
# import logging
# import redis
# from datetime import datetime, time
# from typing import Dict, List, Optional, Set, Any, Union
# from sqlalchemy.orm import Session
# from database.connection import get_db
# from database.models import User, BrokerConfig
# from services.market_schedule_service import MarketScheduleService
# from services.dashboard_ohlc_service import DashboardOHLCService
# from services.live_data_subscription_service import LiveDataSubscriptionService
# from services.trading_services.ai_trading_service import AITradingService

# logger = logging.getLogger(__name__)


# class TradingEngine:
#     def __init__(self):
#         self.market_scheduler = MarketScheduleService()
#         self.ohlc_service = DashboardOHLCService()
#         self.live_data_service = (
#             LiveDataSubscriptionService()
#         )  # Keep for backward compatibility
#         self.ai_trading_service = AITradingService()
#         self.live_trading_engines = {}  # {user_id: LiveTradingEngine}

#         self.is_running = False
#         self.selected_stocks = {}
#         self.active_users = set()
#         self.market_status = "unknown"
#         self.price_updates_count = 0
#         self.last_price_update_time = None

#         # NEW: Add Redis client initialization with error handling
#         try:
#             self.redis_client = redis.Redis(
#                 host="localhost", port=6379, db=0, decode_responses=True
#             )
#             self.redis_client.ping()
#             logger.info("✅ Redis connection established in TradingEngine")
#         except Exception as e:
#             logger.error(f"❌ Redis connection failed in TradingEngine: {e}")
#             self.redis_client = None

#         # NEW: Connect to centralized WebSocket manager
#         try:
#             from services.centralized_ws_manager import centralized_manager

#             self.centralized_manager = centralized_manager

#             # Register callbacks for real-time updates
#             self.centralized_manager.register_callback(
#                 "price_update", self.on_price_update
#             )
#             self.centralized_manager.register_callback(
#                 "market_status", self.on_market_status_change
#             )

#             logger.info(
#                 "✅ Trading Engine registered with Centralized WebSocket Manager"
#             )
#         except ImportError as e:
#             self.centralized_manager = None
#             logger.warning(f"⚠️ Centralized WebSocket Manager not available: {e}")

#     async def start_trading_engine(self):
#         """Start the complete trading engine"""
#         self.is_running = True
#         logger.info("🚀 Trading Engine starting...")

#         try:
#             # Start market scheduler
#             scheduler_task = asyncio.create_task(
#                 self.market_scheduler.start_daily_scheduler()
#             )

#             # Start main engine loop
#             engine_task = asyncio.create_task(self._run_main_engine_loop())

#             # NEW: Check centralized WebSocket status
#             if self.centralized_manager:
#                 status = self.centralized_manager.get_status()
#                 self.market_status = status.get("market_status", "unknown")
#                 logger.info(
#                     f"📈 Current market status from centralized system: {self.market_status}"
#                 )

#                 # If market is already open, initialize trading immediately
#                 if self.market_status == "open":
#                     logger.info(
#                         "🔔 Market already open - initializing trading phase immediately"
#                     )
#                     await self._handle_trading_phase(force_start=True)

#             # Wait for both tasks
#             await asyncio.gather(scheduler_task, engine_task)

#         except Exception as e:
#             logger.error(f"❌ Trading engine failed: {e}")
#             raise

#     async def _run_main_engine_loop(self):
#         """Main engine loop"""
#         while self.is_running:
#             try:
#                 # NEW: Get market status from centralized manager if available
#                 if self.centralized_manager:
#                     new_status = self.centralized_manager.get_market_status()
#                     if new_status != self.market_status:
#                         logger.info(
#                             f"📈 Market status changed: {self.market_status} -> {new_status}"
#                         )
#                         self.market_status = new_status

#                 current_time = datetime.now().time()

#                 # Pre-market phase (9:00-9:15)
#                 if time(9, 0) <= current_time < time(9, 15):
#                     await self._handle_premarket_phase()

#                 # Market open preparation (9:15-9:30)
#                 elif time(9, 15) <= current_time < time(9, 30):
#                     await self._handle_preparation_phase()

#                 # Active trading (9:30-15:30)
#                 elif time(9, 30) <= current_time < time(15, 30):
#                     await self._handle_trading_phase()

#                 # Post-market (after 15:30)
#                 else:
#                     await self._handle_postmarket_phase()

#                 await asyncio.sleep(60)  # Check every minute

#             except Exception as e:
#                 logger.error(f"❌ Engine loop error: {e}")
#                 await asyncio.sleep(300)

#     # NEW: Callback for price updates from centralized WebSocket
#     async def on_price_update(self, data):
#         """Handle price updates from centralized WebSocket manager"""
#         try:
#             # Skip if engine is not running
#             if not self.is_running:
#                 return

#             # Skip if not in trading phase
#             if not hasattr(self, "_trading_started"):
#                 return

#             # Update stats
#             self.price_updates_count += 1
#             self.last_price_update_time = datetime.now()

#             # Only log occasionally to avoid flooding logs
#             if self.price_updates_count % 100 == 0:
#                 logger.info(f"📊 Processed {self.price_updates_count} price updates")

#             # Process each instrument update
#             for instrument_key, price_data in data.items():
#                 # Find corresponding stock
#                 stock_symbol = self._get_symbol_from_instrument_key(instrument_key)
#                 if not stock_symbol or stock_symbol not in self.selected_stocks:
#                     continue

#                 # Extract price
#                 price = self._extract_price(price_data)
#                 if price is None:
#                     continue

#                 # Update stock data
#                 stock_data = self.selected_stocks[stock_symbol]
#                 stock_data["last_price"] = price
#                 stock_data["last_update"] = datetime.now().isoformat()

#                 # Send to LiveTradingEngines for user-specific strategies
#                 for user_id, engine in self.live_trading_engines.items():
#                     try:
#                         await engine.process_price_update(
#                             stock_symbol, price, price_data
#                         )
#                     except Exception as e:
#                         logger.error(
#                             f"❌ Error in LiveTradingEngine for user {user_id}: {e}"
#                         )

#                 # Send to AI trading service
#                 try:
#                     await self.ai_trading_service.process_price_update(
#                         stock_symbol, price, price_data
#                     )
#                 except Exception as e:
#                     logger.error(f"❌ Error in AI trading service: {e}")

#         except Exception as e:
#             logger.error(f"❌ Error processing price update: {e}")

#     # NEW: Callback for market status changes from centralized WebSocket
#     async def on_market_status_change(self, data):
#         """Handle market status changes from centralized WebSocket manager"""
#         try:
#             status = data.get("status")
#             previous_status = self.market_status
#             self.market_status = status

#             logger.info(f"📈 Market status changed: {previous_status} -> {status}")

#             # Take action based on market status
#             if status == "open" and previous_status != "open":
#                 # Market just opened - start active trading if not already started
#                 if not hasattr(self, "_trading_started"):
#                     logger.info("🔔 Market opened - initializing trading phase")
#                     await self._handle_trading_phase(force_start=True)

#             elif status in ["close", "closed"] and previous_status not in [
#                 "close",
#                 "closed",
#             ]:
#                 # Market just closed - clean up
#                 logger.info("🔔 Market closed - cleaning up")
#                 await self._handle_postmarket_phase()

#         except Exception as e:
#             logger.error(f"❌ Error handling market status change: {e}")

#     async def _handle_premarket_phase(self):
#         """Handle pre-market analysis phase - ENHANCED"""
#         try:
#             logger.info("📊 Pre-market phase active")

#             # Get selected stocks from market scheduler
#             self.selected_stocks = self.market_scheduler.selected_stocks

#             # Also check cache if scheduler hasn't completed
#             if not self.selected_stocks:
#                 logger.info("⚠️ No stocks from scheduler, checking cache...")
#                 await self._load_stocks_from_cache()

#             if self.selected_stocks:
#                 logger.info(
#                     f"✅ {len(self.selected_stocks)} stocks selected for trading"
#                 )
#             else:
#                 logger.warning("⚠️ No stocks selected in pre-market phase")

#         except Exception as e:
#             logger.error(f"❌ Pre-market phase error: {e}")

#     async def _handle_preparation_phase(self):
#         """ENHANCED: Market preparation using optimized instruments and centralized WebSocket"""
#         try:
#             logger.info("🔧 Market preparation phase active")

#             # Ensure we have stocks
#             if not self.selected_stocks:
#                 logger.warning(
#                     "⚠️ No stocks in preparation phase, loading from cache..."
#                 )
#                 await self._load_stocks_from_cache()

#             if not self.selected_stocks:
#                 logger.warning("⚠️ No cached stocks, creating emergency selection...")
#                 await self._create_emergency_stock_selection()

#             if self.selected_stocks:
#                 logger.info(f"✅ Preparing with {len(self.selected_stocks)} stocks")

#                 # INTEGRATION: Use OptimizedInstrumentService for dashboard
#                 await self._prepare_dashboard_instruments()

#                 # NEW: Ensure centralized WebSocket is ready
#                 if self.centralized_manager:
#                     status = self.centralized_manager.get_status()
#                     if status["ws_connected"]:
#                         logger.info("✅ Centralized WebSocket is ready")
#                     else:
#                         logger.warning("⚠️ Centralized WebSocket is not connected")

#                 # KEEP: Your legacy live data preparation for backward compatibility
#                 await self._prepare_live_subscriptions()

#                 logger.info("✅ Market preparation completed")
#             else:
#                 logger.error("❌ Market preparation failed - no stocks available")

#         except Exception as e:
#             logger.error(f"❌ Preparation phase error: {e}")

#     async def _handle_trading_phase(self, force_start=False):
#         """Handle active trading phase - ENHANCED with better error handling and centralized WebSocket"""
#         try:
#             if not hasattr(self, "_trading_started") or force_start:
#                 logger.info("⚡ Active trading phase started")

#                 # Ensure we have stocks selected
#                 if not self.selected_stocks:
#                     logger.warning(
#                         "⚠️ No stocks selected, attempting to load from cache..."
#                     )
#                     await self._load_stocks_from_cache()

#                 if not self.selected_stocks:
#                     logger.warning(
#                         "⚠️ No cached stocks found, creating emergency selection..."
#                     )
#                     await self._create_emergency_stock_selection()

#                 if not self.selected_stocks:
#                     logger.error("❌ Cannot start trading phase without stocks")
#                     return

#                 logger.info(
#                     f"✅ Starting trading phase with {len(self.selected_stocks)} stocks"
#                 )

#                 # NEW: Check centralized WebSocket status
#                 if self.centralized_manager:
#                     status = self.centralized_manager.get_status()
#                     if not status["ws_connected"]:
#                         logger.warning(
#                             "⚠️ Centralized WebSocket not connected - using legacy data"
#                         )

#                 # LEGACY: Start live data subscriptions for backward compatibility
#                 if not self.centralized_manager:
#                     await self._start_live_subscriptions()

#                 # Start LiveTradingEngine for each user
#                 await self._start_live_trading_engines()

#                 # Start AI trading
#                 await self._start_ai_trading()

#                 self._trading_started = True
#                 logger.info("✅ Trading phase initialization completed")

#         except Exception as e:
#             logger.error(f"❌ Trading phase error: {e}")
#             # Try emergency recovery
#             await self._emergency_recovery()

#     async def _handle_postmarket_phase(self):
#         """Handle post-market phase"""
#         try:
#             if hasattr(self, "_trading_started"):
#                 logger.info("🌅 Post-market phase - cleaning up")

#                 # Stop all services
#                 await self._stop_all_services()

#                 # Reset for next day
#                 del self._trading_started
#                 # Don't clear selected_stocks here - keep them for reporting

#         except Exception as e:
#             logger.error(f"❌ Post-market phase error: {e}")

#     async def _prepare_live_subscriptions(self):
#         """Prepare live data subscriptions - FIXED DB handling"""
#         db = None  # Initialize db variable
#         try:
#             # Get active users with Upstox tokens
#             db = next(get_db())
#             active_brokers = (
#                 db.query(BrokerConfig)
#                 .filter(
#                     BrokerConfig.broker_name.ilike("upstox"),
#                     BrokerConfig.is_active == True,
#                     BrokerConfig.access_token.isnot(None),
#                 )
#                 .all()
#             )

#             for broker in active_brokers:
#                 self.active_users.add(broker.user_id)

#             logger.info(f"📡 Prepared subscriptions for {len(self.active_users)} users")

#         except Exception as e:
#             logger.error(f"❌ Subscription preparation failed: {e}")
#         finally:
#             # Only close if db was successfully created
#             if db is not None:
#                 db.close()

#     async def _start_live_subscriptions(self):
#         """
#         Start live data subscriptions - LEGACY METHOD
#         Only used if centralized WebSocket manager is not available
#         """
#         db = None  # Initialize db variable
#         try:
#             if not self.selected_stocks:
#                 logger.warning("⚠️ No stocks selected for live data")
#                 await self._load_stocks_from_cache()

#             if not self.selected_stocks:
#                 logger.warning(
#                     "⚠️ Still no stocks after cache load, creating emergency selection"
#                 )
#                 await self._create_emergency_stock_selection()

#             if not self.selected_stocks:
#                 logger.error("❌ Cannot start live subscriptions without stocks")
#                 return

#             # Get first available Upstox token
#             db = next(get_db())
#             broker = (
#                 db.query(BrokerConfig)
#                 .filter(
#                     BrokerConfig.broker_name.ilike("upstox"),
#                     BrokerConfig.is_active == True,
#                     BrokerConfig.access_token.isnot(None),
#                 )
#                 .first()
#             )

#             if broker:
#                 await self.live_data_service.subscribe_selected_stocks(
#                     self.selected_stocks, broker.access_token
#                 )
#                 logger.info("✅ LEGACY: Live data subscriptions started")
#             else:
#                 logger.error("❌ No Upstox token available for live data")

#         except Exception as e:
#             logger.error(f"❌ Live subscription start failed: {e}")
#         finally:
#             # Only close if db was successfully created
#             if db is not None:
#                 db.close()

#     async def _start_ai_trading(self):
#         """Start AI trading service - ENHANCED with centralized data support"""
#         try:
#             if self.selected_stocks:
#                 # NEW: Pass centralized manager if available
#                 if self.centralized_manager:
#                     await self.ai_trading_service.start_trading(
#                         self.selected_stocks,
#                         data_service=self.live_data_service,
#                         centralized_manager=self.centralized_manager,
#                     )
#                 else:
#                     # Legacy mode
#                     await self.ai_trading_service.start_trading(
#                         self.selected_stocks, self.live_data_service
#                     )

#                 logger.info("✅ AI trading service started")
#             else:
#                 logger.warning("⚠️ Cannot start AI trading without selected stocks")

#         except Exception as e:
#             logger.error(f"❌ AI trading start failed: {e}")

#     async def _stop_all_services(self):
#         """ENHANCED: Stop all trading services including LiveTradingEngine"""
#         try:
#             # KEEP: Stop existing services with error handling
#             try:
#                 self.ohlc_service.stop_polling()
#             except Exception as e:
#                 logger.error(f"Error stopping OHLC service: {e}")

#             try:
#                 await self.live_data_service.stop_all_subscriptions()
#             except Exception as e:
#                 logger.error(f"Error stopping live data service: {e}")

#             try:
#                 await self.ai_trading_service.stop_trading()
#             except Exception as e:
#                 logger.error(f"Error stopping AI trading service: {e}")

#             # Stop all LiveTradingEngines
#             for user_id, engine in list(self.live_trading_engines.items()):
#                 try:
#                     await engine.stop_trading_session()
#                     del self.live_trading_engines[user_id]
#                     logger.info(f"✅ LiveTradingEngine stopped for user {user_id}")
#                 except Exception as e:
#                     logger.error(f"❌ Error stopping engine for user {user_id}: {e}")

#             logger.info("⏹️ All trading services stopped")

#         except Exception as e:
#             logger.error(f"❌ Service shutdown error: {e}")

#     def stop_engine(self):
#         """Stop the trading engine - ENHANCED with centralized WebSocket callback cleanup"""
#         self.is_running = False
#         logger.info("🛑 Trading engine stopping...")

#         # NEW: Unregister callbacks from centralized manager
#         if hasattr(self, "centralized_manager") and self.centralized_manager:
#             try:
#                 self.centralized_manager.unregister_callback(
#                     "price_update", self.on_price_update
#                 )
#                 self.centralized_manager.unregister_callback(
#                     "market_status", self.on_market_status_change
#                 )
#                 logger.info("✅ Unregistered callbacks from centralized manager")
#             except Exception as e:
#                 logger.error(f"❌ Error unregistering callbacks: {e}")

#     async def _prepare_trading_instruments(self):
#         """Prepare instrument keys for focused trading WebSocket"""
#         try:
#             if not self.selected_stocks:
#                 return

#             # Generate comprehensive instrument keys for selected stocks
#             from services.optimized_instrument_service import get_instrument_service

#             instrument_service = get_instrument_service()
#             if not instrument_service:
#                 logger.warning("⚠️ Optimized instrument service not available")
#                 return

#             # Cache trading instruments for WebSocket use
#             trading_instruments = []
#             for symbol, stock_data in self.selected_stocks.items():
#                 # Get comprehensive instrument keys for this stock
#                 stock_instruments = await self._get_stock_trading_instruments(
#                     symbol, instrument_service
#                 )
#                 trading_instruments.extend(stock_instruments)

#             # Cache for WebSocket access
#             await self._cache_trading_instruments(trading_instruments)

#             logger.info(f"🎯 Prepared {len(trading_instruments)} trading instruments")

#         except Exception as e:
#             logger.error(f"❌ Trading instrument preparation failed: {e}")

#     async def _get_stock_trading_instruments(self, symbol, instrument_service=None):
#         """Get all trading instruments for a stock - ENHANCED"""
#         try:
#             # Try to get from optimized instrument service first
#             from services.optimized_instrument_service import (
#                 get_stock_trading_data_keys,
#                 get_instrument_service,
#             )

#             if instrument_service is None:
#                 instrument_service = get_instrument_service()

#             if instrument_service:
#                 result = get_stock_trading_data_keys(symbol)
#                 if result and "instrument_keys" in result:
#                     return result["instrument_keys"]

#             # Fallback: get just the main instrument key from stock data
#             stock_data = self.selected_stocks.get(symbol, {})
#             instrument_key = stock_data.get("stock_data", {}).get("instrument_key")

#             if instrument_key:
#                 return [instrument_key]

#             return []

#         except Exception as e:
#             logger.error(f"❌ Error getting trading instruments for {symbol}: {e}")
#             return []

#     async def _start_live_trading_engines(self):
#         """Start LiveTradingEngine for each active user - ENHANCED with centralized data support"""
#         try:
#             if not self.active_users:
#                 logger.warning("⚠️ No active users for live trading engines")
#                 return

#             from services.trading_services.live_trading_engine import LiveTradingEngine

#             for user_id in self.active_users:
#                 if user_id not in self.live_trading_engines:
#                     try:
#                         # Create and start LiveTradingEngine for user
#                         engine = LiveTradingEngine(user_id)

#                         # NEW: Pass centralized manager if available
#                         if (
#                             hasattr(self, "centralized_manager")
#                             and self.centralized_manager
#                         ):
#                             result = await engine.start_trading_session(
#                                 centralized_manager=self.centralized_manager
#                             )
#                         else:
#                             result = await engine.start_trading_session()

#                         if result.get("status") == "success":
#                             self.live_trading_engines[user_id] = engine
#                             logger.info(
#                                 f"🚀 LiveTradingEngine started for user {user_id}"
#                             )
#                         else:
#                             logger.warning(
#                                 f"⚠️ Failed to start LiveTradingEngine for user {user_id}"
#                             )

#                     except Exception as user_error:
#                         logger.error(
#                             f"❌ LiveTradingEngine startup failed for user {user_id}: {user_error}"
#                         )
#                         continue

#         except Exception as e:
#             logger.error(f"❌ LiveTradingEngine startup failed: {e}")

#     async def _cache_trading_instruments(self, instruments):
#         """Cache trading instruments for WebSocket use"""
#         try:
#             if not self.redis_client:
#                 logger.warning("⚠️ Redis not available, cannot cache instruments")
#                 return

#             cache_data = {
#                 "instruments": instruments,
#                 "cached_at": datetime.now().isoformat(),
#                 "count": len(instruments),
#             }

#             self.redis_client.setex(
#                 "trading_instruments_cache", 3600, json.dumps(cache_data)
#             )
#             logger.info(f"💾 Cached {len(instruments)} trading instruments")

#         except Exception as e:
#             logger.error(f"❌ Error caching instruments: {e}")

#     async def _prepare_dashboard_instruments(self):
#         """Prepare dashboard instruments using OptimizedInstrumentService"""
#         try:
#             # INTEGRATION: Use instrument refresh service for all dashboard instruments
#             from services.instrument_refresh_service import get_dashboard_keys

#             # Get all WebSocket keys for dashboard (all 233+ stocks)
#             all_dashboard_keys = get_dashboard_keys()

#             # Cache for LTP API use
#             if self.redis_client:
#                 self.redis_client.setex(
#                     "dashboard_instruments_cache",
#                     3600,
#                     json.dumps(
#                         {
#                             "instruments": all_dashboard_keys,
#                             "cached_at": datetime.now().isoformat(),
#                             "count": len(all_dashboard_keys),
#                         }
#                     ),
#                 )

#                 logger.info(
#                     f"📊 Prepared {len(all_dashboard_keys)} dashboard instruments"
#                 )
#             else:
#                 logger.warning(
#                     "⚠️ Redis not available, cannot cache dashboard instruments"
#                 )

#         except Exception as e:
#             logger.error(f"❌ Error preparing dashboard instruments: {e}")

#     # NEW METHODS: Added to fix the stock selection issues

#     async def _load_stocks_from_cache(self):
#         """Load selected stocks from Redis cache"""
#         try:
#             if not self.redis_client:
#                 logger.warning("⚠️ Redis not available for cache loading")
#                 return

#             cached_data = self.redis_client.get("trading_stocks_cache")
#             if cached_data:
#                 data = json.loads(cached_data)
#                 selected_stocks_list = data.get("selected_stocks", [])

#                 # Convert list back to dict format
#                 self.selected_stocks = {}
#                 for stock in selected_stocks_list:
#                     symbol = stock.get("symbol")
#                     if symbol:
#                         self.selected_stocks[symbol] = stock

#                 logger.info(f"📊 Loaded {len(self.selected_stocks)} stocks from cache")
#             else:
#                 logger.warning("⚠️ No cached stocks found")

#         except Exception as e:
#             logger.error(f"❌ Failed to load stocks from cache: {e}")

#     async def _create_emergency_stock_selection(self):
#         """Create emergency stock selection when no stocks are available"""
#         try:
#             logger.warning("🚨 Creating emergency stock selection...")

#             emergency_stocks = {
#                 "RELIANCE": {
#                     "symbol": "RELIANCE",
#                     "stock_data": {
#                         "symbol": "RELIANCE",
#                         "name": "Reliance Industries",
#                         "instrument_key": "NSE_EQ|INE002A01018",
#                         "exchange": "NSE",
#                     },
#                     "analysis": {
#                         "score": 0.7,
#                         "current_price": 2500,
#                         "recommendation": "HOLD",
#                         "source": "emergency",
#                     },
#                 },
#                 "TCS": {
#                     "symbol": "TCS",
#                     "stock_data": {
#                         "symbol": "TCS",
#                         "name": "Tata Consultancy Services",
#                         "instrument_key": "NSE_EQ|INE467B01029",
#                         "exchange": "NSE",
#                     },
#                     "analysis": {
#                         "score": 0.75,
#                         "current_price": 3500,
#                         "recommendation": "BUY",
#                         "source": "emergency",
#                     },
#                 },
#                 "HDFCBANK": {
#                     "symbol": "HDFCBANK",
#                     "stock_data": {
#                         "symbol": "HDFCBANK",
#                         "name": "HDFC Bank",
#                         "instrument_key": "NSE_EQ|INE040A01034",
#                         "exchange": "NSE",
#                     },
#                     "analysis": {
#                         "score": 0.72,
#                         "current_price": 1600,
#                         "recommendation": "BUY",
#                         "source": "emergency",
#                     },
#                 },
#             }

#             self.selected_stocks = emergency_stocks

#             # Cache emergency selection
#             if self.redis_client:
#                 emergency_cache = {
#                     "selected_stocks": [
#                         {
#                             "symbol": symbol,
#                             "stock_data": data.get("stock_data", {}),
#                             "analysis": data.get("analysis", {}),
#                         }
#                         for symbol, data in emergency_stocks.items()
#                     ],
#                     "cached_at": datetime.now().isoformat(),
#                     "source": "emergency_trading_engine",
#                 }

#                 self.redis_client.setex(
#                     "trading_stocks_cache", 3600, json.dumps(emergency_cache)
#                 )

#             logger.warning(
#                 f"🚨 Emergency selection created: {len(self.selected_stocks)} stocks"
#             )

#         except Exception as e:
#             logger.error(f"❌ Emergency stock selection failed: {e}")

#     async def _emergency_recovery(self):
#         """Emergency recovery when trading phase fails"""
#         try:
#             logger.warning("🚨 Starting emergency recovery...")

#             # Reset trading state
#             if hasattr(self, "_trading_started"):
#                 del self._trading_started

#             # Clear and recreate stock selection
#             self.selected_stocks = {}
#             await self._create_emergency_stock_selection()

#             logger.warning("🚨 Emergency recovery completed")

#         except Exception as e:
#             logger.error(f"❌ Emergency recovery failed: {e}")

#     # NEW: Helper methods for centralized WebSocket integration

#     def _get_symbol_from_instrument_key(self, instrument_key):
#         """Get stock symbol from instrument key - ADDED FOR CENTRALIZED WS"""
#         if not instrument_key:
#             return None

#         # Method 1: Direct lookup in our selected stocks
#         for symbol, data in self.selected_stocks.items():
#             stock_data = data.get("stock_data", {})
#             if stock_data.get("instrument_key") == instrument_key:
#                 return symbol

#         # Method 2: Try optimized instrument service
#         try:
#             from services.optimized_instrument_service import get_instrument_by_key

#             instrument_data = get_instrument_by_key(instrument_key)
#             if instrument_data:
#                 # Get symbol from instrument data
#                 symbol = instrument_data.get("symbol") or instrument_data.get(
#                     "trading_symbol"
#                 )
#                 if symbol:
#                     return symbol
#         except ImportError:
#             pass

#         return None

#     def _extract_price(self, price_data):
#         """Extract price from various data formats - ADDED FOR CENTRALIZED WS"""
#         if not price_data:
#             return None

#         try:
#             # Direct value
#             if isinstance(price_data, (int, float)):
#                 return float(price_data)

#             # Dict formats
#             if isinstance(price_data, dict):
#                 # Format 1: Direct LTP
#                 if "ltp" in price_data:
#                     return float(price_data["ltp"])

#                 # Format 2: Nested Upstox structure
#                 if "fullFeed" in price_data:
#                     feed = price_data.get("fullFeed", {}).get("marketFF", {})
#                     ltpc = feed.get("ltpc", {})
#                     if "ltp" in ltpc:
#                         return float(ltpc["ltp"])

#             return None

#         except (TypeError, ValueError) as e:
#             logger.warning(f"⚠️ Error extracting price from data: {e}")
#             return None

#     def get_latest_price(self, symbol):
#         """Get latest price for a symbol - ADDED FOR CENTRALIZED WS"""
#         # Method 1: Check if we have it in our selected_stocks
#         if (
#             symbol in self.selected_stocks
#             and "last_price" in self.selected_stocks[symbol]
#         ):
#             return self.selected_stocks[symbol]["last_price"]

#         # Method 2: Try to get from centralized manager
#         if self.centralized_manager:
#             # Get instrument key for this symbol
#             instrument_key = None
#             if symbol in self.selected_stocks:
#                 instrument_key = (
#                     self.selected_stocks[symbol]
#                     .get("stock_data", {})
#                     .get("instrument_key")
#                 )

#             if instrument_key:
#                 return self.centralized_manager.get_latest_price(instrument_key)

#         # Method 3: Fallback to legacy service
#         return self.live_data_service.get_latest_price(symbol)

#     def get_latest_price_by_instrument_key(self, instrument_key):
#         """Get latest price using instrument key directly - ADDED FOR CENTRALIZED WS"""
#         if not instrument_key:
#             return None

#         # Try centralized manager first
#         if self.centralized_manager:
#             return self.centralized_manager.get_latest_price(instrument_key)

#         # Fallback: try to convert to symbol and use legacy service
#         symbol = self._get_symbol_from_instrument_key(instrument_key)
#         if symbol:
#             return self.live_data_service.get_latest_price(symbol)

#         return None

#     async def get_engine_status(self):
#         """Get current engine status for debugging - ENHANCED WITH CENTRALIZED WS"""
#         try:
#             # Get centralized WebSocket status if available
#             centralized_status = {}
#             if hasattr(self, "centralized_manager") and self.centralized_manager:
#                 try:
#                     status = self.centralized_manager.get_status()
#                     health = await self.centralized_manager.health_check()

#                     centralized_status = {
#                         "available": True,
#                         "connected": status.get("ws_connected", False),
#                         "market_status": status.get("market_status", "unknown"),
#                         "health_score": health.get("health_score", 0),
#                         "last_data_received": status.get("last_data_received"),
#                         "price_updates_count": self.price_updates_count,
#                         "last_price_update": (
#                             self.last_price_update_time.isoformat()
#                             if self.last_price_update_time
#                             else None
#                         ),
#                     }
#                 except Exception as e:
#                     centralized_status = {
#                         "available": True,
#                         "error": str(e),
#                         "connected": False,
#                     }
#             else:
#                 centralized_status = {"available": False}

#             return {
#                 "is_running": self.is_running,
#                 "selected_stocks_count": len(self.selected_stocks),
#                 "active_users_count": len(self.active_users),
#                 "live_engines_count": len(self.live_trading_engines),
#                 "trading_started": hasattr(self, "_trading_started"),
#                 "redis_connected": self.redis_client is not None,
#                 "market_status": self.market_status,
#                 "centralized_websocket": centralized_status,
#                 "selected_stocks": (
#                     list(self.selected_stocks.keys()) if self.selected_stocks else []
#                 ),
#                 "timestamp": datetime.now().isoformat(),
#             }
#         except Exception as e:
#             logger.error(f"Error getting engine status: {e}")
#             return {"error": str(e)}

#     async def force_stock_refresh(self):
#         """Force refresh of selected stocks"""
#         try:
#             logger.info("🔄 Force refreshing selected stocks...")

#             # Clear current selection
#             self.selected_stocks = {}

#             # Load from cache
#             await self._load_stocks_from_cache()

#             # If still no stocks, create emergency selection
#             if not self.selected_stocks:
#                 await self._create_emergency_stock_selection()

#             # NEW: Update initial prices from centralized WebSocket
#             if self.centralized_manager and self.selected_stocks:
#                 for symbol, stock_data in self.selected_stocks.items():
#                     instrument_key = stock_data.get("stock_data", {}).get(
#                         "instrument_key"
#                     )
#                     if instrument_key:
#                         price_data = self.centralized_manager.get_latest_data(
#                             instrument_key
#                         )
#                         if price_data:
#                             price = self._extract_price(price_data)
#                             if price:
#                                 self.selected_stocks[symbol]["last_price"] = price
#                                 self.selected_stocks[symbol][
#                                     "last_update"
#                                 ] = datetime.now().isoformat()
#                                 logger.info(
#                                     f"💰 Updated initial price for {symbol}: {price}"
#                                 )

#             logger.info(
#                 f"✅ Stock refresh complete: {len(self.selected_stocks)} stocks"
#             )
#             return {"status": "success", "stocks_count": len(self.selected_stocks)}

#         except Exception as e:
#             logger.error(f"❌ Force stock refresh failed: {e}")
#             return {"status": "error", "message": str(e)}
