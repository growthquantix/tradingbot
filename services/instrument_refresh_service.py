# service/instrument_refresh_service.py
"""
Simplified Trading Instrument Service for NSE and MCX instruments
"""

import asyncio
import gc
import gzip
import json
import logging
import time
import aiohttp
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
import aiofiles
from functools import wraps
from dataclasses import dataclass
import pandas as pd
from utils.logging_utils import log_structured

# Redis import with fallback
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False
logger = logging.getLogger(__name__)

# Configuration constants
UPSTOX_COMPLETE_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
)
CACHE_TTL = 86400  # 24 hours
MAX_WEBSOCKET_INSTRUMENTS = 1500  # Upstox limit


def performance_timer(func):
    """Decorator to measure function performance"""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start_time
        logger.info(f"⚡ {func.__name__} executed in {duration:.3f}s")
        return result

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        logger.info(f"⚡ {func.__name__} executed in {duration:.3f}s")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


@dataclass
class InstrumentData:
    """Optimized instrument data structure"""

    instrument_key: str
    trading_symbol: str
    name: str
    exchange: str
    segment: str
    instrument_type: str
    expiry: Optional[str]
    strike_price: Optional[float]
    lot_size: int
    tick_size: float
    underlying_symbol: Optional[str]
    asset_symbol: Optional[str]
    last_price: Optional[float]
    close_price: Optional[float]


@dataclass
class InitializationResult:
    """Initialization result"""

    status: str
    processing_time: float
    total_stocks: int
    filtered_instruments: int
    mapped_stocks: int
    websocket_instruments: int
    dashboard_instruments: int
    trading_instruments: int
    mcx_instruments: int
    cache_keys_created: int
    memory_saved_mb: float
    initialized_at: str
    error: Optional[str] = None


class OptimizedCache:
    """High-performance in-memory cache with TTL support"""

    def __init__(self):
        self._data = {}
        self._expiry = {}
        self._locks = {}

    def _get_lock(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None
            
        if not hasattr(loop, '_instrument_cache_lock'):
            loop._instrument_cache_lock = asyncio.Lock()
        return loop._instrument_cache_lock

    async def ping(self):
        return True

    async def setex(self, key: str, ttl: int, value: str):
        async with self._get_lock():
            self._cleanup_expired()
            self._data[key] = value
            self._expiry[key] = time.time() + ttl

    async def get(self, key: str) -> Optional[str]:
        async with self._get_lock():
            self._cleanup_expired()
            if key in self._data:
                return self._data[key]
            return None

    async def mget(self, keys: List[str]) -> List[Optional[str]]:
        async with self._get_lock():
            self._cleanup_expired()
            return [self._data.get(key) for key in keys]

    async def keys(self, pattern: str) -> List[str]:
        import fnmatch

        async with self._get_lock():
            self._cleanup_expired()
            return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    async def delete(self, *keys):
        async with self._get_lock():
            for key in keys:
                self._data.pop(key, None)
                self._expiry.pop(key, None)

    def _cleanup_expired(self):
        current_time = time.time()
        expired_keys = [
            k for k, exp_time in self._expiry.items() if current_time > exp_time
        ]
        for k in expired_keys:
            self._data.pop(k, None)
            self._expiry.pop(k, None)


class TradingInstrumentService:
    """Simplified Trading Instrument Service for NSE and MCX instruments"""

    _instance = None
    _locks = {}

    @classmethod
    def _get_class_lock(cls):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None
            
        if not hasattr(loop, '_trading_instrument_service_class_lock'):
            loop._trading_instrument_service_class_lock = asyncio.Lock()
        return loop._trading_instrument_service_class_lock

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, redis_url: str = "redis://localhost:6379/1", use_redis: bool = True
    ):
        if hasattr(self, "_initialized_instance"):
            return

        self._initialized = False
        self.redis_client = None
        self.redis_url = redis_url
        self.use_redis = use_redis and REDIS_AVAILABLE

        # Data paths
        self.data_dir = Path("data")
        if self.has_stock_data():
            self.top_stocks_file = self.data_dir / "fno_stock_list.json"
        else:
            self.top_stocks_file = self.data_dir / "top_stocks.json"
        self.filtered_instruments_file = self.data_dir / "filtered_instruments.json"

        # Service state
        self._service_initialized = False
        self._initialization_time = None
        self._last_refresh = None
        self._stock_mappings = {}
        self._dashboard_keys = []
        self._websocket_keys = []
        self._mcx_keys = []
        
        # Error tracking
        self.last_error: Optional[str] = None

        self._initialized_instance = True
        logger.info("🔧 TradingInstrumentService instance created")

    def has_stock_data(self) -> bool:
        """Simple check if JSON file has stock data"""
        try:
            data_dir = Path("data")
            path = data_dir / "fno_stock_list.json"
            if not path.exists():
                return False
            with open(path, "r") as f:
                data = json.load(f)
                securities = data.get("securities", [])
                return len(securities) > 0
        except:
            return False

    def safe_upper(self, value):
        """Safely convert value to uppercase string"""
        if value is None:
            return ""
        try:
            return str(value).strip().upper()
        except (TypeError, AttributeError):
            return ""

    def safe_get_string(self, obj, key, default=""):
        """Safely get string value from dict/object"""
        try:
            if hasattr(obj, "get"):
                value = obj.get(key)
            else:
                value = getattr(obj, key, None)
            return str(value or default).strip()
        except (TypeError, AttributeError):
            return default

    def safe_get_float(self, obj, key, default=0.0):
        """Safely get float value from dict/object"""
        try:
            if hasattr(obj, "get"):
                value = obj.get(key)
            else:
                value = getattr(obj, key, None)
            return float(value) if value is not None else default
        except (TypeError, ValueError, AttributeError):
            return default

    def safe_get_int(self, obj, key, default=0):
        """Safely get int value from dict/object"""
        try:
            if hasattr(obj, "get"):
                value = obj.get(key)
            else:
                value = getattr(obj, key, None)
            return int(value) if value is not None else default
        except (TypeError, ValueError, AttributeError):
            return default

    async def _ensure_cache_connection(self):
        """Ensure cache connection is established"""
        if self.redis_client is None:
            if self.use_redis:
                try:
                    self.redis_client = redis.from_url(
                        self.redis_url,
                        decode_responses=True,
                        socket_connect_timeout=2,
                        socket_timeout=2,
                    )
                    await self.redis_client.ping()
                    logger.info("✅ Redis connection established")
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Redis unavailable, using in-memory cache: {e}")

            self.redis_client = OptimizedCache()
            logger.info("✅ Using optimized in-memory cache")

    @performance_timer
    async def download_and_filter_instruments(self) -> tuple[int, int]:
        """Download complete instruments and filter intelligently"""

        # Check if already refreshed today
        # if await self._is_already_refreshed_today():
        #     logger.info("✅ Instruments already refreshed today, skipping download")
        #     mcx_count = await self._count_existing_mcx_instruments()
        #     nse_count = await self._count_existing_nse_instruments()
        #     total_count = mcx_count + nse_count
        #     return total_count, total_count

        logger.info("⬇️ Downloading instruments from complete.json.gz...")
        log_structured(event="INSTRUMENT_DOWNLOAD_START", message="Downloading instrument list from Upstox")

        top_stocks = await self._load_top_stocks()
        if not top_stocks:
            raise ValueError("No top stocks found")

        logger.info(f"📋 Processing {len(top_stocks)} FnO stocks for simple extraction")

        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(UPSTOX_COMPLETE_URL) as response:
                if response.status != 200:
                    error_msg = f"Failed to download instruments: {response.status}"
                    log_structured(event="INSTRUMENT_DOWNLOAD_FAILED", level="ERROR", message=error_msg)
                    raise Exception(error_msg)

                content = await response.read()
                logger.info(f"📦 Downloaded {len(content)} bytes")

        # Process data
        filtered_instruments = []
        current_time = datetime.now()
        total_count = 0

        try:
            with gzip.GzipFile(fileobj=BytesIO(content)) as gz:
                all_instruments = json.load(gz)
                total_count = len(all_instruments)
                logger.info(f"📦 Parsed {total_count} total instruments")

                # Extract MCX options chain efficiently using pandas
                mcx_instruments = self._extract_mcx_options_chain(all_instruments)
                await self._save_mcx_instruments(mcx_instruments)

                # Extract NSE EQ FnO stock keys efficiently using pandas
                nse_instrument_keys, nse_mappings = await self._extract_nse_fno_keys(
                    all_instruments, top_stocks
                )
                await self._save_nse_instrument_keys(nse_instrument_keys, nse_mappings)

                # Add MCX instruments to filtered list
                filtered_instruments.extend(mcx_instruments)
                logger.info(
                    f"✅ Added {len(mcx_instruments)} MCX instruments + {len(nse_instrument_keys)} NSE keys saved separately"
                )

                # Clear the large array from memory
                del all_instruments
                gc.collect()

        except Exception as e:
            logger.error(f"❌ Failed to decompress/parse data: {e}")
            log_structured(event="INSTRUMENT_PARSE_ERROR", level="ERROR", message=str(e))
            self.last_error = f"Instrument download/parse failed: {str(e)}"
            raise
        finally:
            del content
            gc.collect()

        # Write filtered data efficiently
        self.data_dir.mkdir(exist_ok=True)
        async with aiofiles.open(self.filtered_instruments_file, "w") as f:
            await f.write(json.dumps(filtered_instruments, separators=(",", ":")))

        # Mark refresh as completed
        await self._mark_refresh_completed()

        logger.info(f"💾 Saved {len(filtered_instruments)} filtered instruments")
        
        from services.notifications.alert_manager import alert_manager
        asyncio.create_task(alert_manager.send_admin_system_status(
            "Instrument Refresh", 
            "SUCCESS", 
            f"Processed {total_count} total instruments. Extracted {len(nse_instrument_keys)} NSE stocks and {len(mcx_instruments)} MCX instruments."
        ))
        
        log_structured(
            event="INSTRUMENT_DOWNLOAD_COMPLETE", 
            message=f"Downloaded and processed {total_count} instruments",
            data={
                "total_downloaded": total_count,
                "filtered_count": len(filtered_instruments),
                "nse_keys": len(nse_instrument_keys),
                "mcx_instruments": len(mcx_instruments)
            }
        )
        
        return total_count, len(filtered_instruments)

    def _extract_mcx_options_chain(self, all_instruments: List[Dict]) -> List[Dict]:
        """Extract complete MCX options chain for GOLD and CRUDE OIL current expiry."""
        df = pd.DataFrame(all_instruments)

        # Filter MCX instruments for GOLD and CRUDE OIL
        mcx_df = df[
            (df["segment"] == "MCX_FO") & (df["name"].isin(["GOLD", "CRUDE OIL"]))
        ].copy()

        if mcx_df.empty:
            return []

        # Filter instruments with valid future expiry
        now_ms = int(time.time() * 1000)
        mcx_df = mcx_df[mcx_df["expiry"] >= now_ms]

        if mcx_df.empty:
            return []

        # Find nearest expiry for each commodity
        nearest_expiries = mcx_df.groupby("name")["expiry"].min().to_dict()
        mcx_current_expiry = mcx_df[
            mcx_df.apply(
                lambda row: row["expiry"] == nearest_expiries.get(row["name"]), axis=1
            )
        ]

        result_instruments = mcx_current_expiry.to_dict("records")
        logger.info(f"🏭 Extracted {len(result_instruments)} MCX instruments")
        del df, mcx_df, mcx_current_expiry
        gc.collect()
        return result_instruments

    async def _save_mcx_instruments(self, mcx_instruments: List[Dict]) -> None:
        """Save MCX instruments to separate JSON file."""
        mcx_file_path = self.data_dir / "mcx_instruments.json"

        try:
            self.data_dir.mkdir(exist_ok=True)
            async with aiofiles.open(mcx_file_path, "w") as f:
                await f.write(json.dumps(mcx_instruments, indent=2))
            logger.info(f"💾 Saved {len(mcx_instruments)} MCX instruments")
        except Exception as e:
            logger.error(f"❌ Failed to save MCX instruments: {e}")
            raise

    async def _extract_nse_fno_keys(
        self, all_instruments: List[Dict], top_stocks: List[Dict]
    ) -> tuple[List[str], Dict[str, Dict[str, str]]]:
        """Extract NSE EQ instrument keys for FnO stocks with symbol mappings."""
        df = pd.DataFrame(all_instruments)

        # Get FnO stock symbols and names for better matching
        fno_symbols = set()
        fno_names = set()
        for stock in top_stocks:
            symbol = stock.get("symbol", "").upper().strip()
            name = stock.get("name", "").upper().strip()
            if symbol:
                fno_symbols.add(symbol)
            if name:
                fno_names.add(name)

        logger.info(
            f"📊 Looking for {len(fno_symbols)} FnO symbols and {len(fno_names)} names"
        )

        # Filter for NSE EQ instruments matching FnO stocks
        # Match against multiple fields to ensure we catch all variations
        nse_eq_df = df[
            (df["exchange"] == "NSE")
            & (df["segment"] == "NSE_EQ")
            & (df["instrument_type"] == "EQ")
            & (
                (df["name"].str.upper().isin(fno_symbols))  # name field matches symbol
                | (
                    df["trading_symbol"].str.upper().isin(fno_symbols)
                )  # trading_symbol matches
                | (
                    df.get("symbol", pd.Series(dtype=str)).str.upper().isin(fno_symbols)
                )  # symbol field if exists
                | (
                    df["name"].str.upper().isin(fno_names)
                )  # name field matches actual name
            )
        ].copy()

        if nse_eq_df.empty:
            logger.warning("❌ No NSE EQ instruments found matching FnO stocks")
            return [], {}

        # One instrument key per stock - prioritize by trading_symbol match
        unique_stocks_df = nse_eq_df.drop_duplicates(
            subset=["trading_symbol"], keep="first"
        )
        instrument_keys = unique_stocks_df["instrument_key"].dropna().tolist()

        # Create instrument key to symbol mapping
        instrument_mappings = {}
        for _, row in unique_stocks_df.iterrows():
            instrument_key = row.get("instrument_key")
            if instrument_key:
                # Get the actual trading symbol from the data
                trading_symbol = self.safe_get_string(row, "trading_symbol")
                name = self.safe_get_string(row, "name")

                # Use trading_symbol if available, otherwise use name
                symbol = trading_symbol if trading_symbol else name

                instrument_mappings[instrument_key] = {
                    "symbol": symbol,
                    "name": name,
                    "trading_symbol": trading_symbol,
                }

        logger.info(f"📈 Extracted {len(instrument_keys)} NSE EQ instrument keys")
        logger.info(f"📋 Created {len(instrument_mappings)} symbol mappings")
        logger.info(
            f"📋 Sample keys: {instrument_keys[:5] if instrument_keys else 'None'}"
        )
        del df, nse_eq_df, unique_stocks_df
        gc.collect()
        return instrument_keys, instrument_mappings

    async def _save_nse_instrument_keys(
        self,
        instrument_keys: List[str],
        instrument_mappings: Dict[str, Dict[str, str]] = None,
    ) -> None:
        """Save NSE instrument keys and mappings to separate JSON files."""
        nse_file_path = self.data_dir / "nse_instrument_keys.json"
        nse_mappings_path = self.data_dir / "nse_symbol_mappings.json"

        try:
            self.data_dir.mkdir(exist_ok=True)

            # Save instrument keys
            async with aiofiles.open(nse_file_path, "w") as f:
                await f.write(json.dumps(instrument_keys, indent=2))
            logger.info(f"💾 Saved {len(instrument_keys)} NSE EQ instrument keys")

            # Save symbol mappings if provided
            if instrument_mappings:
                async with aiofiles.open(nse_mappings_path, "w") as f:
                    await f.write(json.dumps(instrument_mappings, indent=2))
                logger.info(f"💾 Saved {len(instrument_mappings)} NSE symbol mappings")

        except Exception as e:
            logger.error(f"❌ Failed to save NSE instrument data: {e}")
            raise

    async def is_already_refreshed_today(self) -> bool:
        """Check if instruments were already refreshed today."""
        try:
            mcx_file_path = self.data_dir / "mcx_instruments.json"
            nse_file_path = self.data_dir / "nse_instrument_keys.json"

            if not (mcx_file_path.exists() and nse_file_path.exists()):
                return False

            today = datetime.now().date()
            mcx_modified = datetime.fromtimestamp(mcx_file_path.stat().st_mtime).date()
            nse_modified = datetime.fromtimestamp(nse_file_path.stat().st_mtime).date()

            return mcx_modified == today and nse_modified == today
        except Exception:
            return False

    async def _count_existing_mcx_instruments(self) -> int:
        """Count existing MCX instruments from file."""
        try:
            mcx_file_path = self.data_dir / "mcx_instruments.json"
            if mcx_file_path.exists():
                async with aiofiles.open(mcx_file_path, "r") as f:
                    data = json.loads(await f.read())
                    return len(data)
        except Exception:
            pass
        return 0

    async def _count_existing_nse_instruments(self) -> int:
        """Count existing NSE instruments from file."""
        try:
            nse_file_path = self.data_dir / "nse_instrument_keys.json"
            if nse_file_path.exists():
                async with aiofiles.open(nse_file_path, "r") as f:
                    data = json.loads(await f.read())
                    return len(data)
        except Exception:
            pass
        return 0

    async def _mark_refresh_completed(self) -> None:
        """Mark refresh as completed by creating/updating timestamp file."""
        try:
            refresh_file = self.data_dir / ".last_refresh"
            async with aiofiles.open(refresh_file, "w") as f:
                await f.write(datetime.now().isoformat())
        except Exception:
            pass

    async def _load_nse_keys_from_file(self) -> List[str]:
        """Load NSE instrument keys from JSON file."""
        try:
            nse_file_path = self.data_dir / "nse_instrument_keys.json"
            if nse_file_path.exists():
                async with aiofiles.open(nse_file_path, "r") as f:
                    keys = json.loads(await f.read())
                    logger.info(f"📈 Loaded {len(keys)} NSE keys")
                    return keys
        except Exception:
            pass
        return []

    async def _load_mcx_keys_from_file(self) -> List[str]:
        """Load MCX instrument keys from JSON file."""
        try:
            mcx_file_path = self.data_dir / "mcx_instruments.json"
            if mcx_file_path.exists():
                async with aiofiles.open(mcx_file_path, "r") as f:
                    instruments = json.loads(await f.read())
                    keys = [
                        inst.get("instrument_key")
                        for inst in instruments
                        if inst.get("instrument_key")
                    ]
                    logger.info(f"🏭 Loaded {len(keys)} MCX keys")
                    return keys
        except Exception:
            pass
        return []

    async def _load_top_stocks(self) -> List[Dict]:
        """Load top stocks configuration"""
        try:
            if not self.top_stocks_file.exists():
                logger.warning(f"⚠️ Top stocks file not found: {self.top_stocks_file}")
                return self._get_fallback_stocks()

            async with aiofiles.open(self.top_stocks_file, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            if isinstance(data, dict) and "securities" in data:
                stocks = data["securities"]
            elif isinstance(data, list):
                stocks = data
            else:
                logger.warning("⚠️ Invalid top_stocks.json format")
                return self._get_fallback_stocks()

            logger.info(f"📋 Loaded {len(stocks)} stocks")
            return stocks

        except Exception:
            return []

    @performance_timer
    async def initialize_service(self) -> InitializationResult:
        """Complete service initialization"""
        start_time = time.time()
        logger.info("🚀 Initializing Trading Instrument Service...")
        log_structured(event="INSTRUMENT_SERVICE_INIT_START", message="Starting Trading Instrument Service initialization")

        try:
            await self._ensure_cache_connection()

            # Simple approach: always run download_and_filter_instruments
            total_downloaded, filtered_count = (
                await self.download_and_filter_instruments()
            )

            # Load simple keys from JSON files
            nse_keys = await self._load_nse_keys_from_file()
            mcx_keys = await self._load_mcx_keys_from_file()

            # Set minimal required variables for service operation
            self._stock_mappings = {}
            self._dashboard_keys = nse_keys[:100] if nse_keys else []
            self._websocket_keys = nse_keys + mcx_keys if nse_keys and mcx_keys else []
            self._mcx_keys = mcx_keys if mcx_keys else []

            cache_keys_created = len(self._websocket_keys)
            self._service_initialized = True
            self._initialization_time = datetime.now()
            self._last_refresh = datetime.now()

            logger.info(f"✅ Initialization complete:")
            logger.info(f"   NSE Keys: {len(nse_keys)}")
            logger.info(f"   MCX Keys: {len(mcx_keys)}")
            logger.info(f"   Dashboard Keys: {len(self._dashboard_keys)}")
            logger.info(f"   WebSocket Keys: {len(self._websocket_keys)}")

            end_time = time.time()
            processing_time = end_time - start_time

            result = InitializationResult(
                status="success",
                processing_time=processing_time,
                total_stocks=len(nse_keys) + len(mcx_keys),
                filtered_instruments=filtered_count,
                mapped_stocks=0,
                websocket_instruments=len(self._websocket_keys),
                dashboard_instruments=len(self._dashboard_keys),
                trading_instruments=0,
                mcx_instruments=len(mcx_keys),
                cache_keys_created=cache_keys_created,
                memory_saved_mb=0,
                initialized_at=datetime.now().isoformat(),
            )

            logger.info(f"✅ Service initialized in {processing_time:.2f}s")
            
            log_structured(
                event="INSTRUMENT_SERVICE_INIT_COMPLETE",
                message=f"Service initialized in {processing_time:.2f}s",
                data={
                    "total_stocks": result.total_stocks,
                    "websocket_keys": result.websocket_instruments,
                    "filtered_instruments": result.filtered_instruments
                }
            )
            
            self.last_error = None  # Clear error on success
            return result

        except Exception as e:
            error_msg = f"Service initialization failed: {e}"
            logger.error(f"❌ {error_msg}")
            log_structured(event="INSTRUMENT_SERVICE_INIT_ERROR", level="ERROR", message=str(e))
            
            self.last_error = error_msg  # Capture error
            
            return InitializationResult(
                status="error",
                processing_time=time.time() - start_time,
                total_stocks=0,
                filtered_instruments=0,
                mapped_stocks=0,
                websocket_instruments=0,
                dashboard_instruments=0,
                trading_instruments=0,
                mcx_instruments=0,
                cache_keys_created=0,
                memory_saved_mb=0,
                initialized_at=datetime.now().isoformat(),
                error=error_msg,
            )

    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        return self._service_initialized

    def get_status(self) -> Dict[str, Any]:
        """Get service status for system health monitoring"""
        return {
            "status": "healthy" if self._service_initialized and not self.last_error else "error" if self.last_error else "pending",
            "initialized": self._service_initialized,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "total_instruments": len(self._websocket_keys) if self._service_initialized else 0,
            "nse_keys": len(self._dashboard_keys) if self._service_initialized else 0,
            "mcx_keys": len(self._mcx_keys) if self._service_initialized else 0,
            "last_error": self.last_error,
            "timestamp": datetime.now().isoformat()
        }

    async def get_websocket_subscription_keys(
        self, max_keys: int = MAX_WEBSOCKET_INSTRUMENTS
    ) -> List[str]:
        """
        Get NSE-only instrument keys for centralized WebSocket subscription.
        MCX instruments are now handled by dedicated MCX WebSocket service.

        Priority order:
        1. NSE stocks (FnO stocks first)
        2. Indices (NSE + BSE SENSEX)
        3. Additional NSE F&O instruments if space allows

        Args:
            max_keys: Maximum number of keys to return (default: Upstox limit)

        Returns:
            List of NSE instrument keys in priority order (MCX excluded)
        """
        subscription_keys = []

        # 1. Load NSE stocks (highest priority)
        nse_keys = await self._load_nse_stock_keys()
        subscription_keys.extend(nse_keys)
        logger.info(f"📈 Added {len(nse_keys)} NSE stock keys")

        # 2. Load indices (NSE + BSE SENSEX)
        if len(subscription_keys) < max_keys:
            remaining_slots = max_keys - len(subscription_keys)
            index_keys = await self._load_index_keys(remaining_slots)
            subscription_keys.extend(index_keys)
            logger.info(f"📊 Added {len(index_keys)} index keys")

        # 3. MCX instruments are now handled by dedicated MCX WebSocket service
        # This ensures no conflicts between centralized manager and MCX service
        logger.info(
            "🏭 MCX instruments excluded - handled by dedicated MCX WebSocket service"
        )

        # Ensure we don't exceed the limit
        final_keys = subscription_keys[:max_keys]

        logger.info(
            f"🔗 Total NSE WebSocket subscription keys: {len(final_keys)}/{max_keys} (MCX excluded)"
        )
        return final_keys

    async def _load_nse_stock_keys(self) -> List[str]:
        """Load NSE stock instrument keys (FnO stocks priority)"""
        try:
            nse_file_path = self.data_dir / "nse_instrument_keys.json"
            if nse_file_path.exists():
                async with aiofiles.open(nse_file_path, "r") as f:
                    keys = json.loads(await f.read())
                    logger.info(f"📈 Loaded {len(keys)} NSE stock keys")
                    return keys
        except Exception as e:
            logger.warning(f"⚠️ Could not load NSE stock keys: {e}")
        return []

    async def _load_index_keys(self, max_keys: int) -> List[str]:
        """
        Load index instrument keys - using direct predefined keys for efficiency

        Args:
            max_keys: Maximum number of index keys to return

        Returns:
            List of index instrument keys
        """
        # Direct predefined index keys - no need to search through files
        # Format: EXCHANGE|Index_Name
        index_keys = [
            # Core Indices (Highest Priority)
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
            "NSE_INDEX|NIFTY OIL AND GAS",
            "NSE_INDEX|NIFTY CONSR DURBL",
            "NSE_INDEX|NIFTY HEALTHCARE",
        ]

        # Return up to max_keys, prioritized by order in list
        final_keys = index_keys[:max_keys]

        logger.info(
            f"📊 Loaded {len(final_keys)} predefined index keys (requested: {max_keys})"
        )
        return final_keys

    async def _load_mcx_options_chain(self, max_keys: int) -> List[str]:
        """
        Load MCX options chain ordered by strike price

        Args:
            max_keys: Maximum number of MCX keys to return

        Returns:
            List of MCX instrument keys ordered by strike price
        """
        mcx_keys = []

        try:
            mcx_file_path = self.data_dir / "mcx_instruments.json"
            if mcx_file_path.exists():
                async with aiofiles.open(mcx_file_path, "r") as f:
                    mcx_instruments = json.loads(await f.read())

                # Separate futures and options
                futures = []
                options = []

                for instrument in mcx_instruments:
                    instrument_type = instrument.get("instrument_type", "").upper()
                    instrument_key = instrument.get("instrument_key")

                    if not instrument_key:
                        continue

                    if instrument_type == "FUT":
                        futures.append(instrument)
                    elif instrument_type in ["CE", "PE"]:
                        options.append(instrument)

                # Add futures first (they have priority)
                for future in futures:
                    if len(mcx_keys) >= max_keys:
                        break
                    mcx_keys.append(future["instrument_key"])
                    logger.info(
                        f"🏭 Added future: {future.get('trading_symbol', 'N/A')}"
                    )

                # Sort options by strike price and add them
                if len(mcx_keys) < max_keys:
                    # Sort options by strike price (ascending)
                    options_sorted = sorted(
                        options, key=lambda x: float(x.get("strike_price", 0) or 0)
                    )

                    # Add options up to the limit
                    remaining_slots = max_keys - len(mcx_keys)
                    for option in options_sorted[:remaining_slots]:
                        mcx_keys.append(option["instrument_key"])
                        strike = option.get("strike_price", "N/A")
                        option_type = option.get("instrument_type", "N/A")
                        trading_symbol = option.get("trading_symbol", "N/A")
                        logger.info(
                            f"🏭 Added option: {trading_symbol} {strike} {option_type}"
                        )

        except Exception as e:
            logger.warning(f"⚠️ Could not load MCX options chain: {e}")

        return mcx_keys


# Global service instance
_service_instance = None


def get_trading_service() -> TradingInstrumentService:
    """Get singleton service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = TradingInstrumentService()
    return _service_instance


# ========== PUBLIC API FUNCTIONS ==========
async def initialize_trading_system() -> InitializationResult:
    """Initialize the complete trading system"""
    service = get_trading_service()
    return await service.initialize_service()


def is_service_ready() -> bool:
    """Check if service is ready"""
    service = get_trading_service()
    return service.is_initialized()


async def get_websocket_keys(max_keys: int = MAX_WEBSOCKET_INSTRUMENTS) -> List[str]:
    """
    Get prioritized instrument keys for WebSocket subscription.

    Priority order:
    1. NSE stocks (FnO stocks)
    2. Indices (NIFTY, BANK NIFTY, SENSEX, etc.)
    3. MCX options chain (ordered by strike price)

    Args:
        max_keys: Maximum number of keys to return (default: 1500)

    Returns:
        List of instrument keys ready for WebSocket subscription

    Example:
        ```python
        keys = await get_websocket_keys(1000)
        # Subscribe to WebSocket using these keys
        ```
    """
    service = get_trading_service()
    if not service.is_initialized():
        await service.initialize_service()

    return await service.get_websocket_subscription_keys(max_keys)


def get_spot_only_instruments() -> List[Dict]:
    """
    Get spot instruments for registry initialization with proper symbol mapping.

    Returns:
        List of spot instrument dictionaries with actual stock symbols
    """
    service = get_trading_service()

    # Create simplified spot instruments from NSE keys
    spot_instruments = []

    try:
        # Load NSE instrument keys
        nse_file_path = service.data_dir / "nse_instrument_keys.json"
        nse_mappings_path = service.data_dir / "nse_symbol_mappings.json"

        if nse_file_path.exists():
            import json

            with open(nse_file_path, "r") as f:
                nse_keys = json.load(f)

            # Load symbol mappings if available
            symbol_mappings = {}
            if nse_mappings_path.exists():
                try:
                    with open(nse_mappings_path, "r") as f:
                        symbol_mappings = json.load(f)
                    logger.info(f"📋 Loaded {len(symbol_mappings)} symbol mappings")
                except Exception as e:
                    logger.warning(f"⚠️ Could not load symbol mappings: {e}")

            # Create basic instrument data for each key
            for i, key in enumerate(nse_keys):
                # Try to get actual symbol from mappings first
                if key in symbol_mappings:
                    mapping = symbol_mappings[key]
                    symbol = mapping.get("symbol", "").strip()
                    name = mapping.get("name", "").strip()
                    trading_symbol = mapping.get("trading_symbol", "").strip()

                    # Use trading_symbol if available, otherwise symbol, otherwise name
                    display_symbol = trading_symbol or symbol or name
                else:
                    # Fallback: Extract ISIN from key (format: NSE_EQ|INE...)
                    display_symbol = f"STOCK_{i+1}"  # Default fallback
                    name = display_symbol
                    trading_symbol = display_symbol

                    try:
                        if "|" in key:
                            isin = (
                                key.split("|")[1]
                                if len(key.split("|")) > 1
                                else display_symbol
                            )
                            display_symbol = isin  # Use ISIN as last resort
                            name = isin
                            trading_symbol = isin
                    except:
                        pass

                # Ensure we have valid symbols
                if not display_symbol:
                    display_symbol = f"STOCK_{i+1}"
                if not name:
                    name = display_symbol
                if not trading_symbol:
                    trading_symbol = display_symbol

                spot_instruments.append(
                    {
                        "instrument_key": key,
                        "symbol": display_symbol,
                        "name": name,
                        "exchange": "NSE",
                        "segment": "NSE_EQ",
                        "instrument_type": "EQ",
                        "trading_symbol": trading_symbol,
                        "expiry": None,
                        "strike_price": None,
                        "lot_size": 1,
                        "tick_size": 0.05,
                    }
                )

            logger.info(
                f"📈 Created {len(spot_instruments)} spot instruments with proper symbols"
            )
            if symbol_mappings:
                logger.info(
                    f"✅ Using actual stock symbols from Upstox instrument data"
                )
            else:
                logger.warning("⚠️ No symbol mappings found, using fallback symbols")

    except Exception as e:
        logger.warning(f"⚠️ Could not load spot instruments: {e}")

    return spot_instruments


def get_fno_instrument_keys(symbol: str) -> Dict[str, Any]:
    """
    Get F&O instrument keys for a specific symbol.

    Args:
        symbol: Symbol to get F&O instruments for

    Returns:
        Dictionary with spot, futures, call_options, put_options lists
    """
    # Return simplified structure for compatibility
    result = {
        "symbol": symbol,
        "spot": [],
        "futures": [],
        "call_options": [],
        "put_options": [],
        "error": None,
    }

    try:
        service = get_trading_service()

        # Load NSE keys and find matching ones
        nse_file_path = service.data_dir / "nse_instrument_keys.json"
        if nse_file_path.exists():
            import json

            with open(nse_file_path, "r") as f:
                nse_keys = json.load(f)

            # Find keys that might match this symbol
            # This is simplified - in production you'd want better symbol matching
            for key in nse_keys:
                if symbol.upper() in key.upper():
                    result["spot"].append(
                        {
                            "instrument_key": key,
                            "symbol": symbol,
                            "trading_symbol": symbol,
                            "name": symbol,
                            "exchange": "NSE",
                            "segment": "NSE_EQ",
                            "instrument_type": "EQ",
                        }
                    )
                    break  # Only add one spot instrument per symbol

        # Load MCX instruments if this is a commodity symbol
        mcx_commodities = ["GOLD", "CRUDEOIL", "CRUDE", "SILVER"]
        if symbol.upper() in mcx_commodities:
            mcx_file_path = service.data_dir / "mcx_instruments.json"
            if mcx_file_path.exists():
                import json

                with open(mcx_file_path, "r") as f:
                    mcx_instruments = json.load(f)

                for instrument in mcx_instruments:
                    name = instrument.get("name", "").upper()
                    trading_symbol = instrument.get("trading_symbol", "").upper()

                    if symbol.upper() in name or symbol.upper() in trading_symbol:
                        instr_type = instrument.get("instrument_type", "").upper()

                        if instr_type == "FUT":
                            result["futures"].append(instrument)
                        elif instr_type == "CE":
                            result["call_options"].append(instrument)
                        elif instr_type == "PE":
                            result["put_options"].append(instrument)

        logger.info(
            f"📊 F&O data for {symbol}: {len(result['spot'])} spot, {len(result['futures'])} futures, {len(result['call_options'])} calls, {len(result['put_options'])} puts"
        )

    except Exception as e:
        logger.warning(f"⚠️ Error getting F&O data for {symbol}: {e}")
        result["error"] = str(e)

    return result


def build_analytics_metadata() -> List[Dict[str, Any]]:
    """
    Build instrument metadata for real-time market analytics engine

    Combines:
    - NSE instrument keys from instrument refresh service
    - Symbol mappings from Upstox data
    - Sector classifications from enhanced_sector_mapping.json
    - Market cap and other metadata for analytics calculations

    Returns:
        List of instrument metadata dictionaries for analytics engine
    """
    try:
        logger.info(
            "🔧 Building analytics metadata from instrument service and sector mapping..."
        )

        service = get_trading_service()
        metadata_list = []

        # Load enhanced sector mapping
        sector_mapping = _load_enhanced_sector_mapping()
        if not sector_mapping:
            logger.warning(
                "⚠️ Enhanced sector mapping not available, using fallback sectors"
            )

        # Load NSE instrument keys and symbol mappings
        nse_file_path = service.data_dir / "nse_instrument_keys.json"
        nse_mappings_path = service.data_dir / "nse_symbol_mappings.json"

        if not nse_file_path.exists():
            logger.error(
                "❌ NSE instrument keys not found - run instrument refresh first"
            )
            return []

        # Load NSE keys
        with open(nse_file_path, "r") as f:
            nse_keys = json.load(f)

        # Load symbol mappings if available
        symbol_mappings = {}
        if nse_mappings_path.exists():
            try:
                with open(nse_mappings_path, "r") as f:
                    symbol_mappings = json.load(f)
                logger.info(
                    f"📋 Loaded {len(symbol_mappings)} symbol mappings for analytics"
                )
            except Exception as e:
                logger.warning(f"⚠️ Could not load symbol mappings: {e}")

        # Build metadata for each NSE instrument
        for instrument_key in nse_keys:
            try:
                # Get symbol information
                if instrument_key in symbol_mappings:
                    mapping = symbol_mappings[instrument_key]
                    symbol = mapping.get("symbol", "").strip().upper()
                    name = mapping.get("name", "").strip()
                    trading_symbol = mapping.get("trading_symbol", "").strip().upper()
                else:
                    # Fallback: Extract from instrument key
                    symbol = _extract_symbol_from_key(instrument_key)
                    name = symbol
                    trading_symbol = symbol

                # Get sector from enhanced mapping
                sector_info = _get_sector_from_mapping(symbol, sector_mapping)
                sector = sector_info.get("sector", "UNKNOWN")

                # Build metadata dictionary
                metadata = {
                    "instrument_key": instrument_key,
                    "symbol": symbol,
                    "name": name,
                    "trading_symbol": trading_symbol,
                    "sector": sector,
                    "exchange": "NSE",
                    "segment": "NSE_EQ",
                    "instrument_type": "EQ",
                    # Market data for analytics
                    "market_cap": sector_info.get("market_cap", 0),
                    "lot_size": sector_info.get("lot_size", 1),
                    "tick_size": 0.05,
                    "avg_volume": sector_info.get("avg_volume", 0),
                    # Additional metadata
                    "isin": sector_info.get("isin", ""),
                    "industry": sector_info.get("industry", ""),
                    "last_updated": datetime.now().isoformat(),
                }

                metadata_list.append(metadata)

            except Exception as e:
                logger.warning(f"⚠️ Error processing instrument {instrument_key}: {e}")
                continue

        # Add MCX instruments if available
        # mcx_metadata = _build_mcx_analytics_metadata(service)
        # metadata_list.extend(mcx_metadata)

        # Add major indices for market breadth calculations
        index_metadata = _build_index_analytics_metadata()
        metadata_list.extend(index_metadata)

        logger.info(
            f"✅ Built analytics metadata for {len(metadata_list)} instruments "
            f"({len(nse_keys)} NSE,  {len(index_metadata)} indices)"
        )

        return metadata_list

    except Exception as e:
        logger.error(f"❌ Error building analytics metadata: {e}")
        return []


def _load_enhanced_sector_mapping() -> Dict[str, Any]:
    """Load enhanced sector mapping configuration"""
    try:
        config_path = Path("config") / "enhanced_sector_mapping.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Could not load enhanced sector mapping: {e}")
    return {}


def _get_sector_from_mapping(
    symbol: str, sector_mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get sector information for a symbol from enhanced mapping

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        sector_mapping: Enhanced sector mapping data

    Returns:
        Dictionary with sector info including market cap, lot size, etc.
    """
    if not sector_mapping or "sectors" not in sector_mapping:
        return {"sector": "UNKNOWN"}

    # Search through all sectors for the symbol
    for sector_code, sector_data in sector_mapping["sectors"].items():
        stocks = sector_data.get("stocks", [])
        for stock in stocks:
            stock_symbol = stock.get("symbol", "").upper()
            if stock_symbol == symbol.upper():
                return {
                    "sector": sector_code,
                    "sector_name": sector_data.get("display_name", sector_code),
                    "market_cap": stock.get("market_cap", 0),
                    "lot_size": stock.get("lot_size", 1),
                    "isin": stock.get("isin", ""),
                    "industry": stock.get("type", ""),
                    "avg_volume": stock.get("avg_volume", 0),
                }

    return {"sector": "UNKNOWN"}


def _extract_symbol_from_key(instrument_key: str) -> str:
    """Extract symbol from instrument key as fallback"""
    try:
        # Format: NSE_EQ|INE001A01036
        if "|" in instrument_key:
            parts = instrument_key.split("|")
            if len(parts) > 1:
                # For ISIN codes, return as is
                return parts[1].strip()
        return instrument_key
    except:
        return "UNKNOWN"


def _build_mcx_analytics_metadata(service) -> List[Dict[str, Any]]:
    """Build analytics metadata for MCX instruments"""
    mcx_metadata = []

    try:
        mcx_file_path = service.data_dir / "mcx_instruments.json"
        if mcx_file_path.exists():
            with open(mcx_file_path, "r") as f:
                mcx_instruments = json.load(f)

            for instrument in mcx_instruments:
                metadata = {
                    "instrument_key": instrument.get("instrument_key", ""),
                    "symbol": instrument.get("name", "").upper(),
                    "name": instrument.get("name", ""),
                    "trading_symbol": instrument.get("trading_symbol", ""),
                    "sector": "COMMODITY",
                    "exchange": "MCX",
                    "segment": "MCX_FO",
                    "instrument_type": instrument.get("instrument_type", "FUT"),
                    # MCX specific data
                    "market_cap": 0,  # Not applicable for commodities
                    "lot_size": instrument.get("lot_size", 1),
                    "tick_size": instrument.get("tick_size", 1.0),
                    "strike_price": instrument.get("strike_price"),
                    "expiry": instrument.get("expiry"),
                    "avg_volume": 0,
                    "last_updated": datetime.now().isoformat(),
                }

                mcx_metadata.append(metadata)

    except Exception as e:
        logger.warning(f"⚠️ Could not load MCX metadata: {e}")

    return mcx_metadata


def _build_index_analytics_metadata() -> List[Dict[str, Any]]:
    """
    Build analytics metadata for all major indices
    Matches the indices defined in _load_index_keys for consistency
    """
    indices = [
        # Core Indices (Highest Priority)
        {
            "instrument_key": "NSE_INDEX|Nifty 50",
            "symbol": "NIFTY",
            "name": "NIFTY 50",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Bank",
            "symbol": "BANKNIFTY",
            "name": "NIFTY BANK",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Fin Service",
            "symbol": "FINNIFTY",
            "name": "Nifty Fin Service",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "BSE_INDEX|SENSEX",
            "symbol": "SENSEX",
            "name": "BSE SENSEX",
            "sector": "INDEX",
            "exchange": "BSE",
        },
        # Major Sectoral Indices
        {
            "instrument_key": "NSE_INDEX|Nifty Auto",
            "symbol": "Nifty Auto",
            "name": "NIFTY AUTO",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty IT",
            "symbol": "Nifty IT",
            "name": "NIFTY IT",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Pharma",
            "symbol": "Nifty Pharma",
            "name": "NIFTY PHARMA",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty FMCG",
            "symbol": "Nifty FMCG",
            "name": "NIFTY FMCG",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Metal",
            "symbol": "Nifty Metal",
            "name": "NIFTY METAL",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Realty",
            "symbol": "Nifty Realty",
            "name": "NIFTY REALTY",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Media",
            "symbol": "Nifty Media",
            "name": "NIFTY MEDIA",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty PSU Bank",
            "symbol": "Nifty PSU Bank",
            "name": "NIFTY PSU BANK",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|Nifty Pvt Bank",
            "symbol": "Nifty Pvt Bank",
            "name": "NIFTY PRIVATE BANK",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|NIFTY OIL AND GAS",
            "symbol": "NIFTY OIL AND GAS",
            "name": "NIFTY OIL AND GAS",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|NIFTY CONSR DURBL",
            "symbol": "Nifty Consumer Durables",
            "name": "NIFTY CONSUMER DURABLES",
            "sector": "INDEX",
            "exchange": "NSE",
        },
        {
            "instrument_key": "NSE_INDEX|NIFTY HEALTHCARE",
            "symbol": "Nifty Healthcare",
            "name": "NIFTY HEALTHCARE",
            "sector": "INDEX",
            "exchange": "NSE",
        },
    ]

    index_metadata = []
    for index in indices:
        metadata = {
            **index,
            "trading_symbol": index["symbol"],
            "segment": f"{index['exchange']}_INDEX",
            "instrument_type": "INDEX",
            "market_cap": 0,
            "lot_size": 1,
            "tick_size": 0.05,
            "avg_volume": 0,
            "last_updated": datetime.now().isoformat(),
        }
        index_metadata.append(metadata)

    return index_metadata


def get_analytics_metadata() -> List[Dict[str, Any]]:
    """
    Public API to get analytics metadata

    Returns:
        List of instrument metadata for analytics engine initialization
    """
    return build_analytics_metadata()
