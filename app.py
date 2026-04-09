# app.py

import asyncio
import logging
import os
import platform
from datetime import datetime, time, timezone
from contextlib import asynccontextmanager
import uvicorn
import socketio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from utils.logging_utils import log_structured

# Windows-specific fix: Set ProactorEventLoop policy BEFORE any asyncio operations
# This is required for Playwright subprocess support on Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Windows-specific: Suppress ConnectionResetError in asyncio
    # This prevents "[WinError 10054] An existing connection was forcibly closed" errors
    def _windows_exception_handler(loop, context):
        """Custom exception handler for Windows asyncio to suppress connection reset errors"""
        exception = context.get("exception")

        # Suppress ConnectionResetError and ConnectionAbortedError (common on Windows)
        if isinstance(exception, (ConnectionResetError, ConnectionAbortedError)):
            # These are expected when connections close - don't log them
            return

        # For all other exceptions, use default handling
        loop.default_exception_handler(context)

    # Apply the custom exception handler to the event loop
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(_windows_exception_handler)
    except RuntimeError:
        # If no event loop exists yet, create one and set the handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(_windows_exception_handler)

# Load environment variables FIRST
load_dotenv()

# Configure PRODUCTION logging EARLY
# This silences noisy libraries (TF, Torch, etc.), enables structured JSON in prod
# and applies ThrottledFilter to stop "Log Storms" from market ticks.
from core.production_logging import get_trading_logger
get_trading_logger()

logger = logging.getLogger(__name__)


# Custom Filter to suppress noisy Uvicorn access logs (Polling & OPTIONS)
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Uvicorn access logs put the request line in args[1] and status in args[2]
            if record.args and len(record.args) >= 3:
                req_line = str(record.args[1])
                status_code = record.args[2]

                # Filter out successful polling and OPTIONS requests
                if status_code == 200:
                    if "GET /api/notifications" in req_line:
                        return False
                    if "OPTIONS" in req_line:
                        return False
            return True
        except Exception:
            return True


try:
    from services.centralized_ws_manager import centralized_manager
    from router.market_ws import (
        router as centralized_market_ws_router,
        initialize_websocket_system,
    )

    CENTRALIZED_WS_AVAILABLE = True
    CENTRALIZED_ROUTES_AVAILABLE = True
    logger.debug("✅ NEW: Centralized WebSocket manager imported successfully")
    logger.debug("✅ NEW: Centralized WebSocket routes imported successfully")
except ImportError as e:
    CENTRALIZED_WS_AVAILABLE = False
    CENTRALIZED_ROUTES_AVAILABLE = False
    logger.error(f"❌ NEW: Centralized WebSocket manager not available: {e}")
    logger.error(f"❌ NEW: Centralized WebSocket routes not available: {e}")
    centralized_manager = None
    from fastapi import APIRouter

    centralized_market_ws_router = APIRouter()  # Dummy router

# LEGACY: Use the same router for backward compatibility
if CENTRALIZED_WS_AVAILABLE:
    legacy_market_ws_router = centralized_market_ws_router
    LEGACY_MARKET_WS_AVAILABLE = True
    logger.debug(
        "✅ Legacy market WebSocket routes available for backward compatibility"
    )
else:
    legacy_market_ws_router = centralized_market_ws_router  # Same dummy router
    LEGACY_MARKET_WS_AVAILABLE = False
    logger.warning("⚠️ Legacy market WebSocket routes not available")

# Import other services
from typing import Optional, Any
import redis
from redis.exceptions import ConnectionError, RedisError
import json

# Import your existing database and models
from core.middleware import TokenRefreshMiddleware
from database.connection import SessionLocal, get_db
from database.init_db import init_db
from database.models import BrokerConfig, TradePerformance, TradeSignal, User

# SAFE: Import analytics router without circular dependencies
try:
    from router.market_analytics_router import router as market_analytics_router

    MARKET_ANALYTICS_ROUTER_AVAILABLE = True
    logger.debug("✅ Market analytics router imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Market analytics router not available: {e}")
    from fastapi import APIRouter

    market_analytics_router = APIRouter()  # Dummy router
    MARKET_ANALYTICS_ROUTER_AVAILABLE = False

from services.realtime_market_engine import (
    get_market_engine,
    get_live_analytics,
    is_analytics_data_ready,
    get_analytics_status,
)


# Import other services
# Removed auto_stock_selection_service - using intelligent_stock_selection_service instead

# Import your existing routers
from router import analytics_router, order_router
from router.user_router import router as user_router
from router.auth_router import auth_router
from router.broker_router import broker_router
from router.stock_list_router import stock_list_router
from router.dhan_router import dhan_router

# from router.trading_config_router import router as trading_config_router
from router.config_router import router as config_router
from router.upstox_router import upstox_router

try:
    from router.upstox_order_router import router as upstox_order_router

    UPSTOX_ORDER_ROUTER_AVAILABLE = True
    logger.debug("✅ Upstox Order Management router imported successfully")
except ImportError as e:
    from fastapi import APIRouter

    upstox_order_router = APIRouter()
    UPSTOX_ORDER_ROUTER_AVAILABLE = False
    logger.warning(f"⚠️ Upstox Order Management router not available: {e}")

try:
    from router.fyers_router import fyers_router

    FYERS_AVAILABLE = True
except ImportError:
    logger.warning("Fyers router not available - fyers_apiv3 module not installed")
    FYERS_AVAILABLE = False
from router.broker_profile_router import broker_profile_router
from router.margin_aware_trading_router import margin_trading_router

from ws_router.upstox_ltp_ws import ws_upstox_router
from router.backtest_router import backtesting_router
from router.stock_router import router as stock_router
from router.profile_router import router as profile_router

# from router.paper_trading_router import router as paper_trading_router
from router.notification_router import router as notification_router

from router.instrument_routes import router as instrument_router

# from services.instrument_registry import instrument_registry
from router.websocket_routes import router as websocket_router
from router.debug_routes import router as debug_router
from router.heatmap_router import router as heatmap_router

# from router.unified_websocket_routes import router as unified_ws_router
from router.paper_trading_routes import router as paper_trading_router
from router.option_routes import option_router
try:
    from router.system_health_router import router as system_health_router
    SYSTEM_HEALTH_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    from fastapi import APIRouter
    system_health_router = APIRouter()
    SYSTEM_HEALTH_AVAILABLE = False
    logger.warning(f"⚠️ System Health router not available: {e}")

try:
    from router.trading_execution_router import router as trading_execution_router

    TRADING_EXECUTION_AVAILABLE = True
    logger.debug("✅ Trading Execution routes imported successfully")
except ImportError as e:
    from fastapi import APIRouter

    trading_execution_router = APIRouter()
    TRADING_EXECUTION_AVAILABLE = False
    logger.warning(f"⚠️ Trading Execution services not available: {e}")


# Import from market_analytics_router safely
try:
    from router.market_analytics_router import INSTRUMENT_REGISTRY_AVAILABLE
except ImportError:
    INSTRUMENT_REGISTRY_AVAILABLE = False

# Import gap detection service (formerly premarket candle builder)
try:
    from services.gapdetection_service import (
        get_gap_detection_service,
        start_gap_detection_scheduler,
    )

    GAP_DETECTION_AVAILABLE = True
    logger.debug("✅ Gap detection service imported successfully")
except ImportError as e:
    GAP_DETECTION_AVAILABLE = False
    logger.warning(f"⚠️ Gap detection service not available: {e}")

    # Dummy functions for fallback
    def get_gap_detection_service():
        return None

    async def start_gap_detection_scheduler():
        pass


# KEEP: Your existing Redis manager (it's already well-designed)
class TradingSafeRedisManager:
    """Redis manager specifically designed for trading applications with graceful fallbacks"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_connected = False
        self.fallback_cache = {}
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection with comprehensive error handling"""
        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"

        if not redis_enabled:
            logger.debug("🔧 Redis disabled via REDIS_ENABLED environment variable")
            return

        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
                health_check_interval=30,
            )

            # Test connection
            self.redis_client.ping()
            self.is_connected = True
            logger.debug("✅ Redis connected successfully for trading system")

        except ConnectionError:
            logger.warning(
                "⚠️ Redis connection failed - trading system will use fallback cache"
            )
            self.redis_client = None
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ Redis initialization error: {e} - using fallback cache")
            self.redis_client = None
            self.is_connected = False

    def get(self, key: str, default: Any = None) -> Any:
        """Get value with fallback to in-memory cache for critical trading data"""
        if self.is_connected and self.redis_client:
            try:
                result = self.redis_client.get(key)
                if result is None:
                    return self.fallback_cache.get(key, default)

                try:
                    parsed_result = json.loads(result)
                    if any(
                        critical in key
                        for critical in [
                            "live_price",
                            "selected_stocks",
                            "trading_data",
                        ]
                    ):
                        self.fallback_cache[key] = parsed_result
                    return parsed_result
                except (json.JSONDecodeError, TypeError):
                    if any(
                        critical in key
                        for critical in [
                            "live_price",
                            "selected_stocks",
                            "trading_data",
                        ]
                    ):
                        self.fallback_cache[key] = result
                    return result

            except RedisError as e:
                logger.warning(f"Redis GET error for key '{key}': {e} - using fallback")
                return self.fallback_cache.get(key, default)

        return self.fallback_cache.get(key, default)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value with fallback storage for critical data"""
        success = False

        if self.is_connected and self.redis_client:
            try:
                if isinstance(value, (dict, list)):
                    serialized_value = json.dumps(value)
                else:
                    serialized_value = value

                result = self.redis_client.set(key, serialized_value, ex=ttl)
                success = bool(result)

            except RedisError as e:
                logger.warning(f"Redis SET error for key '{key}': {e}")
                success = False

        # Always update fallback cache for critical trading data
        if any(
            critical in key
            for critical in [
                "live_price",
                "selected_stocks",
                "trading_data",
                "market_status",
            ]
        ):
            self.fallback_cache[key] = value
            if not success:
                logger.debug(f"Stored '{key}' in fallback cache")

        return success

    def delete(self, *keys: str) -> int:
        """Delete keys with fallback cache cleanup"""
        deleted_count = 0

        if self.is_connected and self.redis_client:
            try:
                deleted_count = self.redis_client.delete(*keys)
            except RedisError as e:
                logger.warning(f"Redis DELETE error: {e}")

        for key in keys:
            if key in self.fallback_cache:
                del self.fallback_cache[key]
                deleted_count += 1

        return deleted_count

    def exists(self, key: str) -> bool:
        """Check existence in Redis or fallback cache"""
        if self.is_connected and self.redis_client:
            try:
                return bool(self.redis_client.exists(key))
            except RedisError:
                pass

        return key in self.fallback_cache

    def keys(self, pattern: str = "*") -> list:
        """Get keys with fallback support"""
        redis_keys = []

        if self.is_connected and self.redis_client:
            try:
                redis_keys = self.redis_client.keys(pattern)
            except RedisError as e:
                logger.warning(f"Redis KEYS error: {e}")

        import fnmatch

        fallback_keys = [
            key for key in self.fallback_cache.keys() if fnmatch.fnmatch(key, pattern)
        ]

        all_keys = list(set(redis_keys + fallback_keys))
        return all_keys

    def health_check(self) -> dict:
        """Comprehensive health check for trading system"""
        if not self.redis_client:
            return {
                "status": "fallback_mode",
                "message": "Redis disabled - using in-memory fallback cache",
                "fallback_cache_size": len(self.fallback_cache),
            }

        try:
            self.redis_client.ping()
            self.is_connected = True
            return {
                "status": "healthy",
                "message": "Redis connection is working",
                "fallback_cache_size": len(self.fallback_cache),
            }
        except Exception as e:
            self.is_connected = False
            return {
                "status": "degraded",
                "message": f"Redis connection failed: {str(e)} - using fallback",
                "fallback_cache_size": len(self.fallback_cache),
            }

    def get_trading_cache_stats(self) -> dict:
        """Get statistics specific to trading data caching"""
        stats = {
            "redis_connected": self.is_connected,
            "fallback_cache_size": len(self.fallback_cache),
            "critical_data_cached": 0,
            "cache_mode": "redis" if self.is_connected else "fallback",
        }

        critical_keys = [
            "live_price",
            "selected_stocks",
            "trading_data",
            "market_status",
        ]
        stats["critical_data_cached"] = len(
            [
                key
                for key in self.fallback_cache.keys()
                if any(critical in key for critical in critical_keys)
            ]
        )

        return stats


# Initialize global Redis manager
trading_redis = TradingSafeRedisManager()

# Global instances
trading_engine = None
trading_scheduler = None
market_scheduler = None
instrument_service_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced lifespan with NEW centralized WebSocket system integration"""
    global trading_engine, market_scheduler, instrument_service_instance

    logger.debug(
        "🚀 Starting Enhanced Trading Application with NEW Centralized WebSocket System..."
    )
    log_structured(
        event="APP_STARTUP_START", message="Starting Enhanced Trading Application"
    )

    # Initialize execution handlers with event loop for thread-safe dispatch
    try:
        loop = asyncio.get_running_loop()
        from services.trading_execution.execution_handler import execution_handler
        from services.trading_execution.trade_prep import trade_prep_service

        execution_handler.initialize(loop)
        trade_prep_service.initialize(loop)
        logger.debug(
            "✅ Execution handlers initialized with event loop for thread-safe dispatch."
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize execution handlers with loop: {e}")

    try:
        # 1. DB initialization
        db = next(get_db())
        logger.debug("✅ DB session initialized.")
        db.close()

        # 2. Redis health check
        redis_status = trading_redis.health_check()
        logger.debug(f"🔧 Redis status: {redis_status['message']}")


        # 🚀 BACKGROUND INITIALIZATION: Move heavy tasks to background to prevent startup blocking
        async def initialize_services_background():
            """Initialize heavy services in background"""
            global instrument_service_instance

            try:
                # 3. Initialize instrument service FIRST
                logger.debug("🔧 Initializing Instrument Service in background...")
                from services.instrument_refresh_service import get_trading_service

                instrument_service = get_trading_service()
                # Await here in background task
                initialization_result = await instrument_service.initialize_service()

                if initialization_result.status == "success":
                    logger.debug(
                        f"✅ Instrument service initialized with {initialization_result.mapped_stocks} stocks"
                    )
                    instrument_service_instance = instrument_service
                else:
                    logger.error(
                        f"❌ Instrument service initialization failed: {initialization_result.error}"
                    )
                    log_structured(
                        event="APP_STARTUP_ERROR",
                        level="ERROR",
                        message=f"Instrument service init failed: {initialization_result.error}",
                    )

                # 4. Initialize optimized market data service
                try:
                    logger.debug("🚀 Initializing Optimized Market Data Service...")
                    from services.optimized_market_data_service import (
                        optimized_market_service,
                    )

                    await optimized_market_service.initialize_instruments()
                    stats = optimized_market_service.get_stats()
                    logger.debug(
                        f"✅ Optimized Market Service initialized with {stats['total_instruments']} instruments, {stats['active_instruments']} active"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Optimized market service initialization failed: {e}"
                    )
                    log_structured(
                        event="APP_STARTUP_ERROR",
                        level="ERROR",
                        message=f"Optimized market service init failed: {str(e)}",
                    )

                # 4.5. Initialize Real-Time Market Analytics Engine
                try:
                    logger.debug("📊 Initializing Real-Time Market Analytics Engine...")
                    from services.realtime_market_engine import initialize_market_engine
                    from services.instrument_refresh_service import (
                        get_analytics_metadata,
                    )

                    # Get analytics metadata from instrument service
                    analytics_metadata = get_analytics_metadata()

                    if analytics_metadata:
                        # Initialize analytics engine with metadata
                        initialize_market_engine(analytics_metadata)

                        from services.realtime_market_engine import get_market_engine

                        engine = get_market_engine()
                        stats = engine.get_stats()

                        logger.debug(
                            f"✅ Real-Time Analytics Engine initialized with {stats['total_instruments']} instruments "
                            f"across {stats['sectors']} sectors"
                        )
                        logger.debug(
                            f"📈 Analytics latency: {stats['analytics_latency_ms']:.2f}ms"
                        )
                    else:
                        logger.warning(
                            "⚠️ No analytics metadata available - analytics engine not initialized"
                        )

                except Exception as e:
                    logger.error(
                        f"❌ Real-Time Analytics Engine initialization failed: {e}"
                    )
                    import traceback

                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
                    log_structured(
                        event="APP_STARTUP_ERROR",
                        level="ERROR",
                        message=f"Analytics engine init failed: {str(e)}",
                    )

            except Exception as e:
                logger.error(f"❌ Background service initialization failed: {e}")
                log_structured(
                    event="APP_STARTUP_CRITICAL_FAILURE",
                    level="CRITICAL",
                    message=f"Background init failed: {str(e)}",
                )

        # Start the background initialization task
        asyncio.create_task(initialize_services_background())
        logger.debug("✅ Core services initialization started in background")

        # 4.6. 🚀 NEW: Initialize Enhanced Breakout Detection Engine
        try:
            logger.debug("🎯 Initializing Enhanced Breakout Detection Engine...")
            from services.enhanced_breakout_engine import (
                initialize_breakout_engine,
                connect_to_market_engine,
                get_breakout_stats,
            )

            # Get WebSocket managers for broadcasting
            unified_manager = None
            try:
                from services.unified_websocket_manager import (
                    unified_manager as unified_ws,
                )

                unified_manager = unified_ws
            except ImportError:
                logger.debug(
                    "Unified WebSocket manager not available for breakout broadcasting"
                )

            # Initialize breakout engine
            breakout_engine = initialize_breakout_engine(
                unified_manager=unified_manager,
                centralized_manager=(
                    centralized_manager if CENTRALIZED_WS_AVAILABLE else None
                ),
                min_volume=1000,  # Minimum 1000 volume
                min_price=10,  # Minimum price Rs. 10
                momentum_threshold=0.015,  # 1.5% momentum threshold
                history_len=50,  # Track last 50 data points
            )

            # Connect to realtime market engine for live data feed
            if connect_to_market_engine():
                stats = get_breakout_stats()
                logger.debug(
                    f"✅ Enhanced Breakout Engine initialized and connected to market data"
                )
                logger.debug(
                    f"📊 Breakout Detection: Min Volume={stats['min_volume']}, "
                    f"Min Price={stats['min_price']}, Momentum Threshold={stats['momentum_threshold']*100}%"
                )
                logger.debug("🔥 Real-time breakout/breakdown detection is now active!")
            else:
                logger.warning(
                    "⚠️ Breakout engine initialized but not connected to market data"
                )

        except ImportError as e:
            logger.warning(f"⚠️ Enhanced Breakout Engine not available: {e}")
        except Exception as e:
            logger.error(f"❌ Enhanced Breakout Engine initialization failed: {e}")
            import traceback

            logger.error(f"❌ Traceback: {traceback.format_exc()}")

        # Gap Detection Service analyzes market gaps at 9:08 AM daily

        # 7c. Start Gap Detection Service
        if GAP_DETECTION_AVAILABLE:
            logger.debug("Starting Gap Detection Service...")
            try:
                # Start as background task to avoid blocking startup
                asyncio.create_task(start_gap_detection_scheduler())
                logger.debug(
                    "Gap Detection Service started - scheduled for 9:08 AM IST daily"
                )
            except Exception as e:
                logger.error(f"Failed to start Gap Detection Service: {e}")

        # 8. NEW: Initialize Centralized WebSocket System (non-blocking)
        if CENTRALIZED_WS_AVAILABLE:
            logger.debug("🔌 Initializing NEW Centralized WebSocket System...")
            try:
                # CRITICAL FIX: DON'T await - just create background task
                # start_connection() will handle initialization internally
                logger.debug(
                    "🔌 Starting Centralized WebSocket connection in background..."
                )
                asyncio.create_task(centralized_manager.start_connection())
                logger.debug(
                    "✅ Centralized WebSocket background task started - continuing with other services"
                )

                # 🚀 ZERO-DELAY real-time streaming will be activated on-demand
                # when a client connects to the /api/v1/realtime/stream WebSocket
                logger.debug("🚀 ZERO-DELAY real-time streaming available (on-demand)")

                # Log initial status (don't await health check to avoid blocking)
                logger.debug(
                    "📊 Centralized WebSocket Status: Starting in background..."
                )
                logger.debug("📊 WebSocket will connect automatically when ready")

                # 🚀 ENHANCED: Connect centralized manager to unified WebSocket manager with Real-Time Analytics
                logger.debug(
                    "🔗 Connecting centralized WebSocket manager to enhanced unified system..."
                )

            except Exception as e:
                logger.error(f"❌ NEW: Centralized WebSocket system error: {e}")
                logger.warning("⚠️ Application will continue without live market data")
                log_structured(
                    event="APP_STARTUP_ERROR",
                    level="ERROR",
                    message=f"Centralized WS system error: {str(e)}",
                )
        else:
            logger.warning(
                "⚠️ NEW: Centralized WebSocket system not available - using legacy only"
            )

        # 7.1. Initialize Upstox Token Automation (IN BACKGROUND - NON-BLOCKING)
        logger.debug("🔄 Queueing Upstox Token Automation startup...")
        try:

            async def start_upstox_in_background():
                """Start Upstox automation in background to avoid blocking startup"""
                try:
                    # Reduced wait time to ensure it starts reliably and visibly
                    logger.debug(
                        "⏳ Waiting 5s for server startup before initializing Upstox automation..."
                    )
                    await asyncio.sleep(5)

                    logger.debug("🚀 Triggering Upstox Automation Service start...")
                    from services.upstox_automation_service import (
                        start_upstox_automation,
                    )

                    upstox_automation = start_upstox_automation()
                    if upstox_automation:
                        logger.debug(
                            "✅ Upstox token automation started successfully - Scheduler Active"
                        )
                    else:
                        logger.warning(
                            "⚠️ Upstox token automation failed to start (returned None)"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Upstox automation background task error: {e}")

            # Start in background - DON'T WAIT FOR IT!
            asyncio.create_task(start_upstox_in_background())
            logger.debug("✅ Upstox automation queued in background")
        except Exception as e:
            logger.warning(f"⚠️ Upstox automation task creation failed: {e}")

        # 7.2. Initialize MarketScheduleService - CRITICAL for FNO and Instrument automation
        logger.debug("📅 Starting MarketScheduleService...")
        try:
            from services.market_schedule_service import get_market_scheduler

            market_scheduler = get_market_scheduler()
            # Start as background task to avoid blocking startup
            market_scheduler_task = asyncio.create_task(
                market_scheduler.start_daily_scheduler()
            )
            logger.debug(
                "✅ MarketScheduleService started - will handle daily FNO refresh, instrument updates, and market timing coordination"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ MarketScheduleService failed to start: {e} - continuing without market scheduling"
            )
            logger.warning(
                "💡 This means FNO stocks and instruments will not auto-refresh. Manual refresh required."
            )

        # 7.3. Initialize Notification Scheduler - NEW comprehensive notification system
        logger.debug("📨 Starting Notification Scheduler...")
        try:
            from services.notification_scheduler import notification_scheduler

            notification_scheduler.start_scheduler()
            logger.debug(
                "✅ Notification Scheduler started - handling token expiry, daily summaries, and system alerts"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ Notification Scheduler failed to start: {e} - continuing without notification scheduling"
            )
            logger.warning(
                "💡 This means automated token expiry alerts and daily summaries will not work"
            )

        # Now using enhanced services started earlier in the startup process
        logger.debug(
            "🎯 Using enhanced gap and breakout detection services (numpy/pandas optimized)"
        )

        # 13. ✅ NEW: Start Auto Trading WebSocket Service
        # TODO Handled this later to start when it needed
        if True:
            logger.debug("🔴 Starting Auto Trading WebSocket Service...")
            try:

                logger.debug("✅ Auto Trading WebSocket Service started")
            except Exception as e:
                logger.error(f"❌ Auto Trading WebSocket Service failed to start: {e}")

        # 15.6. 🚀 NEW: Start Auto-Trade Scheduler for automatic WebSocket management
        if TRADING_EXECUTION_AVAILABLE:
            logger.debug("⏰ Starting Auto-Trade Scheduler...")
            try:
                from services.trading_execution.auto_trade_scheduler import (
                    auto_trade_scheduler,
                )
                from services.trading_execution.capital_manager import TradingMode

                # Start scheduler - it will automatically monitor ALL users with broker configs
                # No need to pass user_id - scheduler finds users automatically
                asyncio.create_task(
                    auto_trade_scheduler.start_scheduler(
                        trading_mode=TradingMode.PAPER  # Default to paper trading for safety
                    )
                )
                logger.debug("✅ Auto-Trade Scheduler started (multi-user mode)")
                logger.debug(
                    "📌 Auto-trading will start at 9:15 AM when ANY user has stocks selected"
                )
                logger.debug(
                    "📌 Monitoring ALL users with active broker configs automatically"
                )

            except Exception as e:
                logger.error(f"❌ Auto-Trade Scheduler failed to start: {e}")

        # 16. 🚀 NEW: Initialize Intelligent Stock Selection Service
        logger.debug("🧠 Initializing Intelligent Stock Selection Service...")
        try:
            from services.intelligent_stock_selection_service import (
                intelligent_stock_selector,
            )

            # CRITICAL FIX: Don't await - run in background to prevent blocking
            asyncio.create_task(intelligent_stock_selector.initialize_services())
            logger.debug(
                "✅ Intelligent Stock Selection Service initialization started in background"
            )
        except ImportError as e:
            logger.warning(f"⚠️ Intelligent Stock Selection Service not available: {e}")
        except Exception as e:
            logger.error(
                f"❌ Intelligent Stock Selection Service failed to initialize: {e}"
            )

        # 17. 🚀 NEW: Initialize MCX WebSocket Service
        logger.debug("📊 Initializing MCX WebSocket Service...")
        try:
            from services.websocket.mcx.integration import initialize_mcx_service

            # CRITICAL FIX: Don't await - run in background to prevent blocking
            asyncio.create_task(initialize_mcx_service())
            logger.debug("✅ MCX WebSocket Service initialization started in background")
        except ImportError as e:
            logger.warning(f"⚠️ MCX WebSocket Service not available: {e}")
        except Exception as e:
            logger.error(f"❌ MCX WebSocket Service failed to initialize: {e}")

        logger.debug("=" * 80)
        logger.info("🟢 ALL SERVICES STARTED SUCCESSFULLY!")
        logger.debug("=" * 80)
        logger.debug("📊 Trading Application is ready to accept requests")
        logger.debug("🔌 WebSocket connections are running in background")
        logger.debug(
            "⚠️ If WebSocket shows network errors, the app will still work without live data"
        )
        logger.debug("=" * 80)

        # Signal that startup is complete and token refresh can now proceed
        if CENTRALIZED_WS_AVAILABLE and centralized_manager:
            try:
                centralized_manager.mark_startup_complete()
                logger.debug("✅ Marked startup complete - token refresh enabled")
            except Exception as e:
                logger.warning(f"⚠️ Error marking startup complete: {e}")

        # Start simple unified WebSocket broadcast task
        try:
            logger.debug("🚀 Starting Simple Unified WebSocket System...")
            from router.unified_websocket_routes import register_engine_listeners

            register_engine_listeners()
            logger.debug("✅ Simple Unified WebSocket broadcast started")
        except Exception as e:
            logger.error(f"❌ Failed to start Unified WebSocket broadcast: {e}")

        logger.info("🎯 Application is fully operational and ready for trading!")

        log_structured(
            event="APP_STARTUP_COMPLETE",
            message="Application startup completed successfully",
        )

        yield

    except Exception as e:
        logger.exception("🔥 Enhanced lifespan startup failed - but app will continue")
        log_structured(
            event="APP_STARTUP_CRITICAL_FAILURE", level="CRITICAL", message=str(e)
        )
        yield
    finally:
        # Enhanced cleanup
        logger.info("🛑 Starting enhanced shutdown...")
        log_structured(
            event="APP_SHUTDOWN_START", message="Starting application shutdown"
        )

        # Unified WebSocket connections cleanup (handled automatically by FastAPI)
        logger.debug("✅ Unified WebSocket connections will be cleaned up by FastAPI")

        # NEW: Stop centralized WebSocket system
        if CENTRALIZED_WS_AVAILABLE and centralized_manager:
            try:
                await centralized_manager.stop()
                logger.debug("✅ NEW: Centralized WebSocket system stopped")
            except Exception as e:
                logger.error(f"Error stopping centralized WebSocket: {e}")

        # NEW: Stop MCX WebSocket service
        try:
            from services.websocket.mcx.integration import stop_mcx_service

            await stop_mcx_service()
            logger.debug("✅ MCX WebSocket service stopped")
        except ImportError:
            pass  # MCX service not available
        except Exception as e:
            logger.error(f"❌ Error stopping MCX WebSocket service: {e}")

        # Premarket Candle Builder Service stops automatically when premarket window closes

        # Stop trading engine
        if trading_engine:
            try:
                logger.info("🛑 Stopping Trading Engine...")
                trading_engine.stop_engine()
            except Exception as e:
                logger.error(f"Error stopping trading engine: {e}")

        if trading_scheduler:
            try:
                logger.info("🛑 Stopping Trading Scheduler...")
                trading_scheduler.stop_scheduler()
            except Exception as e:
                logger.error(f"Error stopping trading scheduler: {e}")

        # Stop MarketScheduleService
        if market_scheduler:
            try:
                logger.info("🛑 Stopping Market Scheduler...")
                market_scheduler.stop_scheduler()
            except Exception as e:
                logger.error(f"Error stopping market scheduler: {e}")

        logger.debug(
            "🎯 Enhanced gap and breakout detection services shutdown completed"
        )

        # Stop Upstox automation
        try:
            from services.upstox_automation_service import stop_upstox_automation

            stop_upstox_automation()
            logger.debug("✅ Upstox token automation stopped")
        except Exception as e:
            logger.error(f"Error stopping Upstox automation: {e}")

        logger.info("🛑 Enhanced lifespan shutdown complete.")
        log_structured(
            event="APP_SHUTDOWN_COMPLETE", message="Application shutdown completed"
        )
        
        # FINAL MEMORY CLEANUP
        import gc
        gc.collect()
        logger.debug("🧹 Final garbage collection completed")


# FIXED: Enhanced trading engine startup function
async def start_enhanced_trading_engine():
    """Enhanced trading engine startup with proper instrument service checking"""
    global trading_engine, instrument_service_instance
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.debug(
                f"🚀 Starting Enhanced Trading Engine (attempt {retry_count + 1}/{max_retries})"
            )

            # Start the trading engine
            if trading_engine:
                await trading_engine.start_trading_engine()
                logger.debug("✅ Enhanced Trading Engine started successfully")
                break
            else:
                logger.error("Trading engine not initialized")
                break

        except Exception as e:
            retry_count += 1
            logger.error(
                f"❌ Enhanced Trading Engine failed (attempt {retry_count}): {e}"
            )

            if retry_count < max_retries:
                wait_time = 60 * retry_count
                logger.debug(f"⏳ Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    "❌ Enhanced Trading Engine failed to start after all retries - continuing without engine"
                )


# FastAPI app initialization
app = FastAPI(
    title="Enhanced Trading Bot API with NEW Centralized WebSocket",
    description="AI-powered trading system with NEW single admin WebSocket + optimized architecture",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS setup
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://resplendent-shortbread-e830d3.netlify.app",
    "https://growthquantix.com",
    "https://www.growthquantix.com",
    "https://api.growthquantix.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Refresh-Token",
        "X-CSRFToken",
    ],
    expose_headers=["Content-Disposition", "Authorization"],
)

app.add_middleware(TokenRefreshMiddleware)

# Include all routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(broker_router, prefix="/api/broker", tags=["Broker API"])
app.include_router(config_router, tags=["Configuration"])
app.include_router(stock_list_router, prefix="/api/stocks", tags=["Stock Data"])
app.include_router(upstox_router, prefix="/api/broker/upstox", tags=["Upstox API"])
if UPSTOX_ORDER_ROUTER_AVAILABLE:
    app.include_router(upstox_order_router, tags=["Upstox Order Management V3"])
if FYERS_AVAILABLE:
    app.include_router(fyers_router, prefix="/api/broker/fyers", tags=["Fyers API"])
app.include_router(broker_profile_router, tags=["Broker Profile & Funds"])
app.include_router(margin_trading_router, tags=["Margin-Aware Trading"])
app.include_router(dhan_router, prefix="/api/dhan", tags=["Dhan API"])
app.include_router(analytics_router.router, tags=["Analytics"])
app.include_router(order_router.router, tags=["Orders"])
app.include_router(ws_upstox_router, tags=["🗑️ Legacy WebSocket (REDUNDANT)"])
app.include_router(backtesting_router, prefix="/api/backtesting", tags=["Backtesting"])
app.include_router(stock_router, tags=["Stocks"])
app.include_router(profile_router, tags=["Profile"])
app.include_router(
    paper_trading_router, tags=["Paper Trading"]
)  # app.include_router(trading_config_router, prefix="/api", tags=["Trading Configuration"])
app.include_router(notification_router, tags=["Notifications"])
# app.include_router(dashboard_router, tags=["Dashboard & Trading Engine"])
app.include_router(instrument_router, tags=["Instruments"])
app.include_router(websocket_router, tags=["🗑️ WebSocket Management (REDUNDANT)"])
app.include_router(debug_router, tags=["Debug"])
app.include_router(
    market_analytics_router, prefix="/api/analytics", tags=["Market Analytics"]
)
app.include_router(heatmap_router, tags=["Heatmap & Sector Analysis"])
# 🚀 NEW: Simple Unified WebSocket System for Real-Time Market Data
try:
    from router.unified_websocket_routes import router as unified_websocket_router

    app.include_router(
        unified_websocket_router, tags=["🚀 Unified WebSocket - Real-Time"]
    )
    logger.debug("✅ Simple Unified WebSocket routes registered")
except ImportError as e:
    logger.warning(f"⚠️ Unified WebSocket routes not available: {e}")

app.include_router(paper_trading_router, tags=["Paper Trading"])
app.include_router(option_router, tags=["Options & Futures"])
app.include_router(system_health_router, tags=["System Health"])
# app.include_router(auto_trading_router, tags=["Auto Trading"])
app.include_router(trading_execution_router, tags=["Trading Execution"])
# app.include_router(trading_stock_selection_router, tags=["Trading Stock Selection"])

# NIFTY 09:40 Strategy Router
try:
    from router.nifty_strategy_router import nifty_strategy_router

    app.include_router(nifty_strategy_router, tags=["NIFTY 09:40 Strategy"])
    logger.debug("✅ NIFTY 09:40 Strategy routes registered")
except ImportError as e:
    logger.warning(f"⚠️ NIFTY strategy routes not available: {e}")


# 🚀 NEW: Add ZERO-DELAY real-time streaming routes
try:
    from router.realtime_stream_router import router as realtime_stream_router

    app.include_router(
        realtime_stream_router, tags=["🚀 ZERO-DELAY Real-time Streaming"]
    )
    logger.debug("✅ 🚀 ZERO-DELAY real-time streaming routes registered")
except ImportError as e:
    logger.warning(f"⚠️ Real-time streaming routes not available: {e}")
    # Breakout router removed - using enhanced_breakout_engine instead
    logger.debug("✅ Using enhanced_breakout_engine for breakout functionality")

# NEW: Add centralized WebSocket routes
if CENTRALIZED_ROUTES_AVAILABLE:
    app.include_router(
        centralized_market_ws_router,
        prefix="/api/v1",
        tags=["NEW: Centralized WebSocket"],
    )
    logger.debug("✅ NEW: Centralized WebSocket routes registered")
else:
    logger.error("❌ NEW: Centralized WebSocket routes not available")

# Legacy market WebSocket for backward compatibility
if LEGACY_MARKET_WS_AVAILABLE:
    app.include_router(legacy_market_ws_router, tags=["Legacy Market WebSocket"])
    logger.debug(
        "✅ Legacy market WebSocket routes available for backward compatibility"
    )


# Preflight handler
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return JSONResponse(content={"message": "Preflight OK"}, status_code=200)


# ============================================================================
# SOCKET.IO SETUP - Simplified Integration for Stability
# ============================================================================
# Temporarily use basic Socket.IO setup to avoid ASGI compatibility issues
logger.debug("🔧 Initializing Socket.IO with basic setup for stability")
sio = socketio.AsyncServer(
    async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS, engineio_logger=False
)
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)
SOCKET_IO_AVAILABLE = True


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with NEW centralized WebSocket system status"""
    redis_status = trading_redis.health_check()

    # Get centralized system status
    try:
        centralized_status = (
            await centralized_manager.health_check()
            if CENTRALIZED_WS_AVAILABLE and centralized_manager
            else {"status": "not_available"}
        )
    except Exception:
        centralized_status = {"status": "error"}

    def sync_check_market_engine():
        engine = get_market_engine()
        last_calc_ts = getattr(engine.analytics, "last_calculation", 0)
        last_update_ts = getattr(engine, "last_analytics_update", 0)
        prices = engine.get_live_prices()

        instruments_with_prices = sum(
            1 for i in engine.instruments.values() if i.current_price > 0
        )
        total_instruments = len(engine.instruments)

        analytics_ready = is_analytics_data_ready()
        analytics_dict = (
            engine.analytics.to_dict() if hasattr(engine, "analytics") else {}
        )
        status_info = get_analytics_status()

        top_gainers = analytics_dict["top_movers"]["gainers"]
        top_loosers = analytics_dict["top_movers"]["losers"]
        marekt_breadth = analytics_dict["market_breadth"]
        sector_analysis = analytics_dict["sector_analytics"]
        volume_analysis = analytics_dict["volume_analytics"]
        marekt_sentiment = analytics_dict["market_sentiment"]

        return {
            "last_calc_ts": last_calc_ts,
            "last_update_ts": last_update_ts,
            "analytics_ready": analytics_ready,
            "analytics_dict": analytics_dict,
            "instruments_with_prices": instruments_with_prices,
            "total_instruments": total_instruments,
            "status_info": status_info,
            "top_gainers": top_gainers,
            "top_loosers": top_loosers,
            "market_breadth": marekt_breadth,
            "market_sentiment": marekt_sentiment,
            "sector_analysis": sector_analysis,
            "volume_analysis": volume_analysis,
        }

    checks = await asyncio.to_thread(sync_check_market_engine)
    now_ts = datetime.now(tz=timezone.utc).timestamp()
    analytics_age = now_ts - checks["last_calc_ts"] if checks["last_calc_ts"] else None
    checks["analytics_age_seconds"] = analytics_age
    checks["is_fresh"] = (
        analytics_age is not None and analytics_age <= 3.0
    )  # 3 sec window

    # derive readiness
    overall_ok = (
        checks["analytics_ready"]
        and checks["instruments_with_prices"] > 0
        and checks["is_fresh"]
    )
    return {
        "status": "running",
        "version": "3.0.0",
        "architecture": "hybrid_optimized_with_NEW_centralized_websocket",
        "new_centralized_websocket_system": {
            "available": CENTRALIZED_WS_AVAILABLE,
            "health_score": centralized_status.get("health_score", 0),
            "status": centralized_status.get("status", "unknown"),
            "ws_connected": centralized_status.get("ws_connected", False),
            "total_instruments": centralized_status.get("total_instruments", 0),
            "admin_token_strategy": True,
        },
        "existing_systems": {
            "optimized_instrument_service": instrument_service_instance is not None,
            "trading_engine": trading_engine.is_running if trading_engine else False,
            "redis_safety": redis_status["status"],
            "legacy_websocket": LEGACY_MARKET_WS_AVAILABLE,
        },
        "websocket_endpoints": {
            "new_centralized_dashboard": (
                "/api/v1/ws/dashboard"
                if CENTRALIZED_ROUTES_AVAILABLE
                else "not_available"
            ),
            "new_centralized_trading": (
                "/api/v1/ws/trading"
                if CENTRALIZED_ROUTES_AVAILABLE
                else "not_available"
            ),
            "legacy_market": (
                "/ws/market" if LEGACY_MARKET_WS_AVAILABLE else "not_available"
            ),
        },
        "redis_status": redis_status["status"],
        "timestamp": datetime.now().isoformat(),
        "market_analytics_system": {
            "available": "",
            "websocket_endpoint": "/ws/market-analytics",
            "active_connections": 0,  # Will be updated dynamically
            "features": [
                "real_time_market_data",
                "top_movers",
                "volume_analysis",
                "market_sentiment",
            ],
            "rest_endpoints": [
                "/api/analytics/top-movers",
                "/api/analytics/volume-analysis",
                "/api/analytics/market-sentiment",
                "/api/analytics/status",
                "/api/analytics/quick-data",
            ],
        },
        # --- market analytics system (direct engine access check) ---
        "market_analytics_system": {
            "available": overall_ok,
            "is_fresh": checks["is_fresh"],
            "analytics_age_seconds": (
                round(checks["analytics_age_seconds"], 3)
                if checks["analytics_age_seconds"]
                else None
            ),
            "total_instruments": checks["total_instruments"],
            "instruments_with_prices": checks["instruments_with_prices"],
            "analytics_ready": checks["analytics_ready"],
            "last_update_ts": checks["last_update_ts"],
            "top_gainers_count": len(
                checks["analytics_dict"].get("top_movers", {}).get("gainers", [])
            ),
            "top_gainers": checks["top_gainers"],
            "top_losers_count": len(
                checks["analytics_dict"].get("top_movers", {}).get("losers", [])
            ),
            "top_loosers": checks["top_loosers"],
            "market_breadth": checks["analytics_dict"]
            .get("market_breadth", {})
            .get("total_stocks", 0),
            "engine_status": checks["status_info"],
            "features": [
                "real_time_market_data",
                "top_movers",
                "volume_analysis",
                "market_sentiment",
            ],
            "analytics": checks,
        },
    }


@app.post("/api/v1/system/refresh-instruments")
async def refresh_instruments():
    """Admin endpoint to refresh instrument data"""
    try:
        logger.info("🔄 Manual instrument refresh requested")

        # Get trading service instance
        from services.instrument_refresh_service import get_trading_service

        instrument_service = get_trading_service()

        # Re-initialize the service
        result = await instrument_service.initialize_service()

        # Refresh centralized WebSocket manager
        if CENTRALIZED_WS_AVAILABLE and centralized_manager:
            await centralized_manager.initialize()

        # NEW: Refresh instrument registry
        # await instrument_registry.initialize_registry()

        return {
            "success": True,
            "message": "Instrument refresh completed successfully",
            "refresh_result": {
                "status": result.status,
                "websocket_keys": result.websocket_instruments,
                "dashboard_keys": result.dashboard_instruments,
                "filtered_instruments": result.filtered_instruments,
                "processing_time": result.processing_time,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Error refreshing instruments: {e}")
        return {"success": False, "error": str(e)}


# FIXED: Health check endpoint
@app.get("/health")
async def enhanced_health_check():
    """Enhanced health check with NEW centralized WebSocket system"""
    global trading_engine, trading_scheduler, market_scheduler, instrument_service_instance

    redis_status = trading_redis.health_check()
    cache_stats = trading_redis.get_trading_cache_stats()

    # Get centralized system health
    try:
        centralized_health = (
            await centralized_manager.health_check()
            if CENTRALIZED_WS_AVAILABLE and centralized_manager
            else {"status": "not_available"}
        )
    except Exception as e:
        centralized_health = {"status": "error", "error": str(e)}

    # Dynamic versioning from VERSION file or environment
    try:
        with open("VERSION", "r") as f:
            project_version = f.read().strip()
    except Exception:
        project_version = os.getenv("APP_VERSION", "2.0.0")

    app_tag = os.getenv("APP_TAG", f"v{project_version}")
    release_name = os.getenv("RELEASE_NAME", "Advanced Trading Release")

    # FIXED: Initialize health_status FIRST
    health_status = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": project_version,
        "tag": app_tag,
        "release": release_name,
        "architecture": "hybrid_optimized_with_NEW_centralized_websocket",
        "services": {
            "database": "ok",
            "new_centralized_websocket": centralized_health.get("status", "unknown"),
            "trading_engine": "unknown",
            "trading_scheduler": "unknown",
            "market_scheduler": "unknown",
            "instrument_service": "unknown",
            "redis": redis_status["status"],
        },
        "new_centralized_websocket_details": centralized_health,
        "redis_details": redis_status,
        "cache_stats": cache_stats,
    }

    # Check trading engine

    # Check trading scheduler
    if trading_scheduler:
        try:
            health_status["services"]["trading_scheduler"] = (
                "running" if trading_scheduler.is_running else "stopped"
            )
        except Exception:
            health_status["services"]["trading_scheduler"] = "error"

    # Check market scheduler
    if market_scheduler:
        try:
            health_status["services"]["market_scheduler"] = (
                "running" if market_scheduler.is_running else "stopped"
            )
        except Exception:
            health_status["services"]["market_scheduler"] = "error"

    # FIXED: Return the health_status
    return health_status


# Breakout Engine status endpoint
@app.get("/api/v1/system/breakout-status")
async def get_breakout_engine_status():
    """Get Enhanced Breakout Detection Engine status"""
    try:
        from services.enhanced_breakout_engine import (
            get_breakout_stats,
            get_breakout_engine,
        )

        stats = get_breakout_stats()
        engine = get_breakout_engine()

        return {
            "success": True,
            "breakout_engine": stats,
            "data_flow": {
                "connected_to_market_engine": stats.get("initialized", False),
                "realtime_detection_active": stats.get("active", False),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except ImportError:
        return {
            "success": False,
            "error": "Breakout engine not available",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# FIXED: Centralized WebSocket system management endpoints (always available)
@app.get("/api/v1/system/centralized-status")
async def get_centralized_system_status():
    """Get detailed NEW centralized WebSocket system status"""
    try:
        if not CENTRALIZED_WS_AVAILABLE or not centralized_manager:
            return {
                "success": False,
                "error": "Centralized WebSocket system not available",
                "timestamp": datetime.now().isoformat(),
            }

        status = centralized_manager.get_status()
        health = await centralized_manager.health_check()

        return {
            "success": True,
            "system": "centralized_single_admin_websocket",
            "status": status,
            "health": health,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/admin/restart-centralized-ws")
async def restart_centralized_websocket():
    """Admin endpoint to restart NEW centralized WebSocket system"""
    try:
        if not CENTRALIZED_WS_AVAILABLE or not centralized_manager:
            return {
                "success": False,
                "error": "Centralized WebSocket system not available",
                "timestamp": datetime.now().isoformat(),
            }

        logger.info("🔄 Admin requested NEW centralized WebSocket restart")

        await centralized_manager.stop()
        await asyncio.sleep(2)

        if await centralized_manager.initialize():
            await centralized_manager.start_connection()
            health = await centralized_manager.health_check()
            return {
                "success": True,
                "message": "NEW centralized WebSocket system restarted successfully",
                "health": health,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "success": False,
                "message": "Failed to restart NEW centralized WebSocket system",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"❌ Error restarting NEW centralized WebSocket: {e}")
        return {"success": False, "error": str(e)}


# Engine status endpoint
@app.get("/api/engine/status")
async def get_enhanced_engine_status():
    """Get comprehensive trading engine status"""
    global trading_engine, trading_scheduler, market_scheduler, instrument_service_instance

    if not trading_engine:
        return {"error": "Trading engine not initialized"}

    try:
        current_time = datetime.now().time()

        # Determine current market phase
        if time(9, 0) <= current_time < time(9, 15):
            phase = "pre_market_analysis"
        elif time(9, 15) <= current_time < time(9, 30):
            phase = "market_preparation"
        elif time(9, 30) <= current_time < time(15, 30):
            phase = "active_trading"
        else:
            phase = "post_market"

        redis_status = trading_redis.health_check()

        # Get centralized system status
        try:
            centralized_status = (
                centralized_manager.get_status()
                if CENTRALIZED_WS_AVAILABLE and centralized_manager
                else {}
            )
            centralized_health = (
                await centralized_manager.health_check()
                if CENTRALIZED_WS_AVAILABLE and centralized_manager
                else {}
            )
        except Exception:
            centralized_status = {}
            centralized_health = {}

        status = {
            "engine": {
                "is_running": trading_engine.is_running,
                "current_phase": phase,
                "selected_stocks": {
                    "count": len(trading_engine.selected_stocks),
                    "symbols": list(trading_engine.selected_stocks.keys())[:10],
                },
                "active_users": len(trading_engine.active_users),
            },
            "scheduler": {
                "trading_scheduler_running": (
                    trading_scheduler.is_running if trading_scheduler else False
                ),
                "market_scheduler_running": (
                    market_scheduler.is_running if market_scheduler else False
                ),
            },
            "new_centralized_websocket_system": {
                "available": CENTRALIZED_WS_AVAILABLE,
                "health_score": centralized_health.get("health_score", 0),
                "ws_connected": centralized_status.get("ws_connected", False),
                "total_instruments": centralized_status.get("total_instruments", 0),
                "admin_token_strategy": True,
            },
            "redis_system": {
                "status": redis_status["status"],
                "is_connected": trading_redis.is_connected,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return status

    except Exception as e:
        logger.error(f"❌ Error getting enhanced engine status: {e}")
        return {"error": str(e)}


@app.post("/api/engine/restart")
async def restart_trading_engine():
    """Restart the trading engine"""
    global trading_engine

    try:
        if trading_engine and trading_engine.is_running:
            logger.info("🔄 Restarting Enhanced Trading Engine...")
            trading_engine.stop_engine()
            await asyncio.sleep(5)

        if trading_engine:
            asyncio.create_task(start_enhanced_trading_engine())
            return {
                "message": "Enhanced trading engine restart initiated",
                "status": "restarting",
                "centralized_ws_compatible": CENTRALIZED_WS_AVAILABLE,
            }
        else:
            return {"error": "Trading engine not available"}

    except Exception as e:
        logger.error(f"❌ Enhanced engine restart failed: {e}")
        return {"error": str(e)}


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error on {request.url}: {str(exc)}")
    log_structured(
        event="GLOBAL_EXCEPTION",
        level="ERROR",
        message=f"Unhandled exception on {request.url}",
        data={"error": str(exc), "url": str(request.url)},
    )

    # Don't expose Redis connection errors
    if "redis" in str(exc).lower() or "connection" in str(exc).lower():
        logger.warning("Redis-related error handled gracefully")
        return JSONResponse(
            status_code=200,
            content={
                "message": "Service running in safe mode",
                "note": "Some caching features may be limited",
                "timestamp": datetime.now().isoformat(),
            },
        )

    if os.getenv("ENVIRONMENT") == "production":
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An error occurred. Please try again later.",
                "timestamp": datetime.now().isoformat(),
            },
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "message": "An internal server error occurred. Please check the logs.",
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url),
            },
        )


@sio.event
async def disconnect(sid):
    logger.info(f"📡 Client disconnected: {sid}")


@sio.event
async def get_engine_status(sid, data):
    """Enhanced SocketIO endpoint with NEW centralized WebSocket system info"""
    global trading_engine, instrument_service_instance

    try:
        if trading_engine:
            redis_status = trading_redis.health_check()

            # Get centralized system status
            try:
                centralized_status = (
                    centralized_manager.get_status()
                    if CENTRALIZED_WS_AVAILABLE and centralized_manager
                    else {}
                )
            except Exception:
                centralized_status = {}

            status = {
                "is_running": trading_engine.is_running,
                "selected_stocks_count": len(trading_engine.selected_stocks),
                "active_users_count": len(trading_engine.active_users),
                "instrument_service_active": instrument_service_instance is not None,
                "redis_status": redis_status["status"],
                "new_centralized_websocket_system": {
                    "available": CENTRALIZED_WS_AVAILABLE,
                    "ws_connected": centralized_status.get("ws_connected", False),
                    "admin_token_strategy": True,
                },
                "architecture": "hybrid_optimized_with_NEW_centralized_websocket",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            status = {"error": "Trading engine not available"}

        await sio.emit("engine_status_update", status, to=sid)

    except Exception as e:
        await sio.emit("error", {"message": str(e)}, to=sid)


# Main runner
if __name__ == "__main__":
    # Apply filter to suppress noisy access logs
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    logger.debug(
        "🚀 Launching Enhanced Trading Platform with NEW Centralized WebSocket System..."
    )

    # Log system configuration
    logger.debug(f"🔧 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.debug(f"🔧 Redis Enabled: {os.getenv('REDIS_ENABLED', 'true')}")
    logger.debug(
        f"🔧 NEW Centralized WebSocket: {'Available' if CENTRALIZED_WS_AVAILABLE else 'Not Available'}"
    )
    logger.debug(
        f"🔧 NEW Centralized Routes: {'Available' if CENTRALIZED_ROUTES_AVAILABLE else 'Not Available'}"
    )
    logger.debug(
        f"🔧 Legacy WebSocket: {'Available' if LEGACY_MARKET_WS_AVAILABLE else 'Not Available'}"
    )

    uvicorn.run(
        "app:sio_app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="warning",
        reload=os.getenv("DEBUG", "false").lower() == "true",
        workers=1,
    )
