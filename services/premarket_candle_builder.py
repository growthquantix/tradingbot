#!/usr/bin/env python3
"""
Premarket Candle Builder Service - 9:00 AM to 9:08 AM IST

This service builds OHLC candles from live WebSocket tick data during the premarket
window (9:00 AM to 9:08 AM IST) and performs gap detection analysis.

Key Features:
- Real-time candle building from tick-by-tick data
- Precise 8-minute premarket window handling
- Gap detection with volume confirmation
- Database persistence with automatic cleanup
- High-performance tick processing with minimal latency
"""

import asyncio
import logging
from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

# Defensive numeric parsing utilities
def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert value to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def normalize_feed_data(callback_data):
    """Normalize various feed data formats to consistent structure"""
    if isinstance(callback_data, dict):
        return callback_data.get("data", callback_data.get("feeds", callback_data))
    elif isinstance(callback_data, list):
        # Convert list to dict format
        return {f"item_{i}": item for i, item in enumerate(callback_data)}
    return callback_data

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

# Database imports
from database.connection import get_db
from database.models import PremarketCandle, GapDetectionAlert

# Service imports
try:
    from services.instrument_registry import instrument_registry
    from services.unified_websocket_manager import unified_manager

    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    logging.warning(f"Dependencies not available: {e}")

logger = logging.getLogger(__name__)

# Premarket trading hours (IST)
PREMARKET_START_TIME = time(9, 0)  # 9:00 AM
PREMARKET_END_TIME = time(9, 8)  # 9:08 AM
MARKET_OPEN_TIME = time(9, 15)  # 9:15 AM


@dataclass
class TickData:
    """Single tick data point"""

    timestamp: datetime
    price: Decimal
    volume: int
    instrument_key: str
    symbol: str


@dataclass
class CandleBuilder:
    """Real-time candle builder for a single instrument"""

    symbol: str
    instrument_key: str
    start_time: datetime
    end_time: datetime

    # OHLC data
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    close_price: Optional[Decimal] = None

    # Volume and trade data
    total_volume: int = 0
    total_trades: int = 0
    tick_count: int = 0

    # Previous close for gap calculation
    previous_close: Optional[Decimal] = None

    # Price accumulation for average
    price_sum: Decimal = field(default_factory=lambda: Decimal("0"))

    # Quality tracking
    first_tick_time: Optional[datetime] = None
    last_tick_time: Optional[datetime] = None

    def add_tick(self, tick: TickData) -> None:
        """Add a single tick to the candle"""
        if not self._is_valid_tick(tick):
            return

        price = tick.price
        volume = tick.volume

        # Set open price (first tick)
        if self.open_price is None:
            self.open_price = price
            self.first_tick_time = tick.timestamp

        # Update high/low
        if self.high_price is None or price > self.high_price:
            self.high_price = price

        if self.low_price is None or price < self.low_price:
            self.low_price = price

        # Always update close (last price)
        self.close_price = price
        self.last_tick_time = tick.timestamp

        # Accumulate volume and trades
        self.total_volume += volume
        self.total_trades += 1
        self.tick_count += 1

        # Accumulate weighted price for average
        self.price_sum += price * volume

    def _is_valid_tick(self, tick: TickData) -> bool:
        """Validate tick data"""
        return (
            tick.price > 0
            and tick.volume > 0
            and self.start_time <= tick.timestamp <= self.end_time
            and tick.instrument_key == self.instrument_key
        )

    def is_complete(self) -> bool:
        """Check if candle has minimum required data"""
        return (
            self.open_price is not None
            and self.close_price is not None
            and self.tick_count > 0
        )

    def get_avg_price(self) -> Decimal:
        """Calculate volume-weighted average price"""
        if self.total_volume > 0:
            return (self.price_sum / self.total_volume).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        elif self.close_price:
            return self.close_price
        else:
            return Decimal("0")

    def calculate_gap_percentage(self) -> Optional[Decimal]:
        """Calculate gap percentage against previous close"""
        if not self.previous_close or not self.open_price or self.previous_close <= 0:
            return None

        gap_pct = (self.open_price - self.previous_close) / self.previous_close * 100
        return gap_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def get_gap_type(self) -> str:
        """Determine gap type"""
        gap_pct = self.calculate_gap_percentage()
        if gap_pct is None:
            return "NO_GAP"
        elif gap_pct > Decimal("0.5"):
            return "GAP_UP"
        elif gap_pct < Decimal("-0.5"):
            return "GAP_DOWN"
        else:
            return "NO_GAP"

    def get_gap_strength(self) -> str:
        """Calculate gap strength based on percentage"""
        gap_pct = self.calculate_gap_percentage()
        if gap_pct is None:
            return "WEAK"

        abs_gap = abs(gap_pct)
        if abs_gap >= Decimal("8.0"):
            return "VERY_STRONG"
        elif abs_gap >= Decimal("5.0"):
            return "STRONG"
        elif abs_gap >= Decimal("2.5"):
            return "MODERATE"
        else:
            return "WEAK"

    def get_data_quality_score(self) -> Decimal:
        """Calculate data quality score (0-1)"""
        if self.tick_count == 0:
            return Decimal("0")

        # Base score from tick count (more ticks = better quality)
        tick_score = min(Decimal(self.tick_count) / Decimal("100"), Decimal("0.5"))

        # Time coverage score (how much of the 8-minute window we have data for)
        if self.first_tick_time and self.last_tick_time:
            coverage_duration = (
                self.last_tick_time - self.first_tick_time
            ).total_seconds()
            expected_duration = 8 * 60  # 8 minutes in seconds
            coverage_score = min(
                Decimal(coverage_duration) / Decimal(expected_duration), Decimal("0.4")
            )
        else:
            coverage_score = Decimal("0")

        # Completeness score (have all OHLC)
        completeness_score = Decimal("0.1") if self.is_complete() else Decimal("0")

        total_score = tick_score + coverage_score + completeness_score
        return total_score.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


class PremarketCandleBuilderService:
    """Service for building premarket candles and detecting gaps"""

    def __init__(self):
        # Market timing
        self.premarket_start = PREMARKET_START_TIME
        self.premarket_end = PREMARKET_END_TIME
        self.market_open = MARKET_OPEN_TIME

        # Active candle builders (symbol -> CandleBuilder)
        self.active_builders: Dict[str, CandleBuilder] = {}

        # Previous close prices (symbol -> Decimal)
        self.previous_closes: Dict[str, Decimal] = {}

        # State management
        self.is_premarket_active = False
        self.current_session_date = date.today()
        self.processed_symbols: Set[str] = set()

        # Performance tracking
        self.ticks_processed_today = 0
        self.candles_built_today = 0
        self.gaps_detected_today = 0
        self.alerts_generated_today = 0

        # Direct WebSocket integration (ZERO-DELAY)
        self.direct_ws_subscribed = False
        self.monitored_instruments = set()

        logger.info("✅ Premarket Candle Builder Service initialized")

    async def setup_direct_ws_integration(self):
        """Setup time-aware WebSocket integration via unified real-time hub"""
        try:
            # NEW: Register with real-time data hub for optimized premarket processing
            from services.realtime_data_hub import get_realtime_data_hub
            
            hub = get_realtime_data_hub()
            
            # Only register during or approaching premarket hours
            current_time = datetime.now().time()

            # Allow registration 5 minutes before premarket starts for preparation
            early_start = time(8, 55)  # 8:55 AM
            late_end = time(9, 15)  # 9:15 AM

            logger.info(f"🕘 Checking premarket registration window: {current_time}")
            logger.info(f"🕘 Valid window: {early_start} to {late_end}")

            if not (early_start <= current_time <= late_end):
                logger.info(
                    f"⏰ Outside premarket window - registration skipped (current: {current_time})"
                )
                return False

            # Register with the unified hub for optimized premarket processing
            success = hub.register_premarket_candle_service(
                callback=self._handle_direct_market_data
            )

            if success:
                self.direct_ws_subscribed = True
                logger.info(
                    "🕘 ✅ PREMARKET SERVICE REGISTERED WITH UNIFIED HUB - Zero-delay data access"
                )
                logger.info(f"🔍 Callback function: {self._handle_direct_market_data}")
                logger.info(f"🔍 Service type: PREMARKET_CANDLE (CRITICAL priority)")
                logger.info(f"🔍 Time window filter: {self.premarket_start} - {self.premarket_end}")
                
                return True
            else:
                logger.error(
                    "❌ FAILED to register premarket service with unified hub"
                )
                # Fallback to legacy method
                return await self._setup_legacy_ws_integration()

        except ImportError as e:
            logger.error(f"Real-time data hub not available: {e}")
            # Fallback to legacy method
            return await self._setup_legacy_ws_integration()
        except Exception as e:
            logger.error(f"Error setting up real-time hub integration: {e}")
            return False

    async def _setup_legacy_ws_integration(self):
        """Fallback to legacy WebSocket integration"""
        try:
            from services.centralized_ws_manager import centralized_manager

            logger.info("🔄 Falling back to legacy WebSocket integration")

            # *** FIX: Register for live_feed to get RAW data immediately ***
            success = centralized_manager.register_callback(
                "live_feed", self._handle_direct_market_data
            )

            if success:
                self.direct_ws_subscribed = True
                logger.info(
                    "🕘 ✅ LEGACY PREMARKET CALLBACK REGISTERED - Direct WebSocket integration active"
                )
                return True
            else:
                logger.error(
                    "❌ FAILED to register premarket callback with centralized WebSocket manager"
                )
                return False

        except ImportError as e:
            logger.error(f"Centralized WebSocket manager not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error setting up legacy WebSocket integration: {e}")
            return False

    async def _unregister_websocket_callback(self):
        """Unregister WebSocket callback when outside premarket hours"""
        try:
            from services.centralized_ws_manager import centralized_manager

            if self.direct_ws_subscribed:
                success = centralized_manager.unregister_callback(
                    "live_feed", self._handle_direct_market_data
                )

                if success:
                    self.direct_ws_subscribed = False
                    logger.info(
                        "🔌 WebSocket direct callback unregistered - outside premarket window"
                    )
                else:
                    logger.warning("Failed to unregister WebSocket callback")

        except Exception as e:
            logger.error(f"Error unregistering WebSocket callback: {e}")

    async def _test_callback_mechanism(self, centralized_manager):
        """Test if the callback mechanism is working"""
        try:
            logger.info("🧪 Testing callback mechanism with dummy data...")

            # Create test data similar to what centralized_ws_manager would send
            test_data = {
                "data": {
                    "TEST_KEY": {
                        "symbol": "TEST",
                        "ltp": 100.0,
                        "cp": 99.0,
                        "volume": 1000,
                    }
                },
                "is_snapshot": True,
                "timestamp": datetime.now().isoformat(),
                "source": "test",
            }

            # Try to call our callback directly (works whether registered or not)
            await self._handle_direct_market_data(test_data)
            logger.info("✅ Direct callback test completed")

        except Exception as e:
            logger.error(f"❌ Callback mechanism test failed: {e}")

    def _filter_premarket_data(self, live_data) -> bool:
        """Filter function to only process data during premarket hours"""
        try:
            # Only process during premarket hours
            if not self.is_premarket_hours():
                return False

            # Only process if premarket session is active
            if not self.is_premarket_active:
                return False

            # Filter out low-volume ticks during premarket
            # Note: some feeds may use 'ltq' or 'last_quantity' for tick qty
            volume = (
                getattr(live_data, "volume", None) or live_data.get("volume", None)
                if isinstance(live_data, dict)
                else None
            )
            if volume is not None and volume < 100:
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Error in premarket filter: {e}")
            return False

    async def _handle_direct_market_data(self, callback_data: dict):
        """Handle market data ONLY during 8-minute premarket window (9:00-9:08 AM IST)"""
        try:
            # Normalize feed data format first
            market_feeds = normalize_feed_data(callback_data)
            
            # Log that we received a callback
            current_time = datetime.now().time()
            logger.info(f"📡 PREMARKET CALLBACK RECEIVED at {current_time}")
            logger.debug(
                f"🔍 Callback data keys: {list(callback_data.keys()) if callback_data else 'None'}"
            )
            logger.debug(
                f"🔍 Normalized feeds count: {len(market_feeds) if isinstance(market_feeds, dict) else 'Not dict'}"
            )

            # STRICT: Only process during exact 8-minute premarket window
            if not self.is_premarket_hours():
                # Stop processing immediately if outside premarket hours
                if self.is_premarket_active:
                    logger.info("PREMARKET WINDOW ENDED - Stopping data processing")
                    await self.finalize_session()
                else:
                    logger.debug(
                        f"⏰ Callback received outside premarket hours ({current_time}) - ignoring"
                    )
                return

            # Activate premarket session ONLY during the 8-minute window
            if not self.is_premarket_active:
                self.is_premarket_active = True
                logger.info(
                    "🕘 🚨 PREMARKET SESSION STARTED - Building 8-minute candles (9:00-9:08 AM ONLY)"
                )
                logger.info(
                    f"📊 Expected to process ALL market instruments during this 8-minute window"
                )

            # Use normalized market feeds
            is_snapshot = isinstance(market_feeds, dict) and len(market_feeds) > 10

            if is_snapshot:
                logger.info(
                    f"Processing premarket snapshot with {len(market_feeds)} instruments"
                )

            # Process ALL instruments for comprehensive gap analysis
            processed_count = 0
            total_instruments = len(market_feeds)

            # Debug log the data format for first few instruments
            if is_snapshot and total_instruments > 0:
                sample_key = list(market_feeds.keys())[0]
                sample_data = market_feeds[sample_key]
                logger.debug(
                    f"🔍 Sample data format for {sample_key}: {list(sample_data.keys())}"
                )

            for instrument_key, feed_data in market_feeds.items():
                try:
                    # Extract price data from centralized WebSocket manager format
                    price_info = self._extract_price_data_from_feed(
                        instrument_key, feed_data
                    )
                    if not price_info:
                        # Debug log failed extractions occasionally
                        if processed_count < 5:
                            logger.debug(
                                f"⚠️ Failed to extract data for {instrument_key}: {list(feed_data.keys()) if isinstance(feed_data, dict) else type(feed_data)}"
                            )
                        continue

                    # Skip if price is zero or invalid
                    if safe_float(price_info.get("ltp", 0)) <= 0:
                        continue

                    # Create tick data with enhanced information
                    tick = TickData(
                        timestamp=datetime.now(),
                        price=Decimal(str(safe_float(price_info["ltp"]))),
                        volume=safe_int(price_info.get("volume", price_info.get("ltq", 1))),
                        instrument_key=instrument_key,
                        symbol=price_info["symbol"],
                    )

                    # Get or create candle builder for this instrument
                    builder = self._get_or_create_builder(
                        price_info["symbol"],
                        instrument_key,
                        Decimal(str(price_info.get("prev_close", price_info["ltp"]))),
                    )

                    # Set opening price from feed data (critical for gap calculation)
                    if builder.open_price is None and "open" in price_info:
                        builder.open_price = Decimal(str(price_info["open"]))

                    # Add tick to 8-minute candle builder
                    builder.add_tick(tick)
                    processed_count += 1

                except Exception as e:
                    logger.debug(f"Error processing instrument {instrument_key}: {e}")
                    continue

            # Update totals
            self.ticks_processed_today += processed_count

            # Log processing stats
            if processed_count > 0:
                logger.debug(
                    f"Processed {processed_count} instruments for premarket candles"
                )

            # Auto-finalize all candles at end of premarket window
            current_time = datetime.now().time()
            if current_time >= self.premarket_end:
                logger.info("Premarket window ending - finalizing ALL 8-minute candles")
                finalization_tasks = []
                for builder in self.active_builders.values():
                    if builder.symbol not in self.processed_symbols:
                        finalization_tasks.append(self._finalize_candle(builder))

                # Process all finalizations concurrently
                if finalization_tasks:
                    await asyncio.gather(*finalization_tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error processing direct market data: {e}")

    def _extract_price_data_from_feed(
        self, instrument_key: str, feed_data: dict
    ) -> Optional[dict]:
        """Extract price data from centralized WebSocket manager normalized format"""
        try:
            logger.debug(
                f"🔍 EXTRACT: Processing {instrument_key} with keys: {list(feed_data.keys())}"
            )

            # The data comes from centralized_ws_manager in normalized format (not raw Upstox)
            # According to LIVE_FEED_DATA_FORMAT.md, data is already processed and enriched

            # Check if this is raw Upstox format (with fullFeed)
            if isinstance(feed_data, dict) and "fullFeed" in feed_data:
                logger.debug(
                    f"🔍 EXTRACT: Raw Upstox format detected for {instrument_key}"
                )
                return self._extract_from_raw_upstox_format(instrument_key, feed_data)

            # Handle normalized format from centralized_ws_manager
            # The data structure should be enriched with frontend-compatible fields
            if isinstance(feed_data, dict) and (
                "ltp" in feed_data or "last_price" in feed_data
            ):
                ltp = feed_data.get("ltp") or feed_data.get("last_price", 0)
                prev_close = feed_data.get("cp") or feed_data.get("previous_close", ltp)
                symbol = feed_data.get("symbol") or self._extract_symbol_from_key(
                    instrument_key
                )

                logger.debug(
                    f"📊 EXTRACT: {symbol} LTP:{ltp} CP:{prev_close} from normalized format"
                )

                return {
                    "symbol": symbol,
                    "ltp": float(ltp) if ltp else 0,
                    "ltq": int(feed_data.get("ltq", feed_data.get("last_quantity", 1))),
                    "prev_close": (
                        float(prev_close) if prev_close else float(ltp) if ltp else 0
                    ),
                    "open": (
                        float(feed_data.get("open", ltp))
                        if feed_data.get("open") is not None
                        else float(ltp)
                    ),
                    "high": (
                        float(feed_data.get("high", ltp))
                        if feed_data.get("high") is not None
                        else float(ltp)
                    ),
                    "low": (
                        float(feed_data.get("low", ltp))
                        if feed_data.get("low") is not None
                        else float(ltp)
                    ),
                    "volume": int(feed_data.get("volume", 0)),
                    "sector": feed_data.get("sector", "OTHER"),
                    "exchange": feed_data.get("exchange", "NSE"),
                    "instrument_type": feed_data.get("instrument_type", "EQ"),
                }

            return None

        except Exception as e:
            logger.error(
                f"Error extracting price data from normalized feed for {instrument_key}: {e}"
            )
            return None

    def _extract_from_raw_upstox_format(
        self, instrument_key: str, feed_data: dict
    ) -> Optional[dict]:
        """Extract from raw Upstox WebSocket format (fallback)"""
        try:
            full_feed = feed_data.get("fullFeed", {})

            # Try market feed (equity stocks)
            market_ff = full_feed.get("marketFF", {})
            if market_ff:
                ltpc = market_ff.get("ltpc", {})
                ohlc_data = market_ff.get("marketOHLC", {}).get("ohlc", [])

                # Get daily OHLC data
                daily_ohlc = next(
                    (item for item in ohlc_data if item.get("interval") == "1d"), {}
                )

                return {
                    "symbol": self._extract_symbol_from_key(instrument_key),
                    "ltp": float(ltpc.get("ltp", 0)),
                    "ltq": int(ltpc.get("ltq", 1)),
                    "prev_close": float(ltpc.get("cp", ltpc.get("ltp", 0))),
                    "open": float(daily_ohlc.get("open", ltpc.get("ltp", 0))),
                    "high": float(daily_ohlc.get("high", ltpc.get("ltp", 0))),
                    "low": float(daily_ohlc.get("low", ltpc.get("ltp", 0))),
                    "volume": (
                        int(daily_ohlc.get("vol", 0)) if daily_ohlc.get("vol") else 0
                    ),
                    "sector": "OTHER",
                    "exchange": "NSE",
                    "instrument_type": "EQ",
                }

            # Try index feed format
            index_ff = full_feed.get("indexFF", {})
            if index_ff:
                ltpc = index_ff.get("ltpc", {})
                ohlc_data = index_ff.get("marketOHLC", {}).get("ohlc", [])
                daily_ohlc = next(
                    (item for item in ohlc_data if item.get("interval") == "1d"), {}
                )

                return {
                    "symbol": self._extract_symbol_from_key(instrument_key),
                    "ltp": float(ltpc.get("ltp", 0)),
                    "ltq": 1,  # Indices don't have quantity
                    "prev_close": float(ltpc.get("cp", ltpc.get("ltp", 0))),
                    "open": float(daily_ohlc.get("open", ltpc.get("ltp", 0))),
                    "high": float(daily_ohlc.get("high", ltpc.get("ltp", 0))),
                    "low": float(daily_ohlc.get("low", ltpc.get("ltp", 0))),
                    "volume": 0,  # Indices don't have volume
                    "sector": "INDEX",
                    "exchange": "NSE",
                    "instrument_type": "INDEX",
                }

            return None

        except Exception as e:
            logger.error(f"Error extracting from raw Upstox format: {e}")
            return None

    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        try:
            # Format: NSE_EQ|INE318A01026 or NSE_INDEX|Nifty Bank
            if "|" in instrument_key:
                parts = instrument_key.split("|")
                symbol_part = parts[-1]

                # Handle index names
                if "INDEX" in instrument_key:
                    return symbol_part

                # Handle equity - try to get actual symbol from registry
                if DEPENDENCIES_AVAILABLE and instrument_registry:
                    spot_data = instrument_registry._spot_instruments.get(
                        instrument_key, {}
                    )
                    if spot_data and "symbol" in spot_data:
                        return spot_data["symbol"]

                # Fallback to clean symbol extraction
                return symbol_part.replace("-EQ", "").replace("_EQ", "")

            return instrument_key

        except Exception as e:
            logger.debug(f"Error extracting symbol: {e}")
            return (
                instrument_key.split("|")[-1]
                if "|" in instrument_key
                else instrument_key
            )

    def _register_websocket_callback(self):
        """Legacy WebSocket callback registration (fallback)"""
        try:
            if DEPENDENCIES_AVAILABLE and instrument_registry:
                # Get watchlist instruments for premarket gap detection
                watchlist = self._get_premarket_watchlist()

                if watchlist:
                    # Register callback for tick data
                    success = instrument_registry.register_strategy_callback(
                        strategy_name="premarket_candle_builder",
                        instruments=watchlist,
                        callback=self._process_tick_callback,
                    )

                    if success:
                        logger.info(
                            f"✅ Legacy: Registered for {len(watchlist)} instruments for premarket candle building"
                        )
                    else:
                        logger.error(
                            "❌ Failed to register premarket candle builder callback"
                        )

        except Exception as e:
            logger.error(f"❌ Error registering WebSocket callback: {e}")

    async def _get_premarket_watchlist(self) -> List[str]:
        """Get instrument keys for premarket monitoring from actual data sources"""
        try:
            from services.auto_stock_selection_service import (
                get_premarket_watchlist_instruments,
            )

            watchlist = await get_premarket_watchlist_instruments()

            if not watchlist:
                logger.error("❌ No instruments available for premarket monitoring")
                return []

            return watchlist

        except ImportError as e:
            logger.error(f"❌ Auto stock selection service not available: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error getting premarket watchlist: {e}")
            return []

    def is_premarket_hours(self) -> bool:
        """Check if current time is within EXACT 8-minute premarket window (9:00-9:08 AM IST)"""
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()

        # Reset daily state if new day
        if current_date != self.current_session_date:
            self._reset_daily_state()
            self.current_session_date = current_date

        # STRICT: Only within exact 8-minute window on weekdays
        is_weekday = current_date.weekday() < 5  # Monday to Friday only
        is_premarket_window = self.premarket_start <= current_time <= self.premarket_end

        # Additional validation: Must be exactly 8 minutes
        if is_premarket_window and is_weekday:
            premarket_start_dt = datetime.combine(current_date, self.premarket_start)
            premarket_end_dt = datetime.combine(current_date, self.premarket_end)
            window_duration = (premarket_end_dt - premarket_start_dt).total_seconds()

            # Ensure it's exactly 8 minutes (480 seconds)
            if abs(window_duration - 480) > 5:  # Allow 5 second tolerance
                logger.warning(
                    f"⚠️ Premarket window duration incorrect: {window_duration}s (expected 480s)"
                )
                return False

            logger.debug(f"✅ Within 8-minute premarket window: {current_time}")
            return True

        return False

    def _reset_daily_state(self):
        """Reset state for new trading day"""
        self.active_builders.clear()
        self.processed_symbols.clear()
        self.ticks_processed_today = 0
        self.candles_built_today = 0
        self.gaps_detected_today = 0
        self.alerts_generated_today = 0
        self.is_premarket_active = False

        # Load previous closes for new day
        try:
            asyncio.create_task(self._load_previous_closes())
        except RuntimeError:
            # If no event loop is running, we'll load previous closes when needed
            pass

        logger.info("🌅 New trading day - premarket candle builder state reset")

    async def _load_previous_closes(self):
        """Load previous day's closing prices from database"""
        try:
            yesterday = self.current_session_date - timedelta(days=1)

            # Skip weekends
            while yesterday.weekday() > 4:  # Saturday=5, Sunday=6
                yesterday -= timedelta(days=1)

            db = next(get_db())

            # Query previous day's closing prices
            previous_candles = (
                db.query(PremarketCandle)
                .filter(PremarketCandle.candle_date == yesterday)
                .all()
            )

            self.previous_closes.clear()
            for candle in previous_candles:
                self.previous_closes[candle.symbol] = candle.close_price

            logger.info(
                f"📊 Loaded {len(self.previous_closes)} previous closes from {yesterday}"
            )

        except Exception as e:
            logger.error(f"❌ Error loading previous closes: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

    def _process_tick_callback(self, instrument_key: str, price_data: dict):
        """Process incoming tick data during premarket hours"""
        try:
            # Only process during premarket hours
            if not self.is_premarket_hours():
                return

            # Activate premarket session
            if not self.is_premarket_active:
                self.is_premarket_active = True
                logger.info(
                    "🚨 PREMARKET SESSION STARTED - Building candles from ticks"
                )

            # ✅ FIXED: Extract data from NORMALIZED format (not raw WebSocket)
            # The data comes from instrument_registry.update_live_prices() in normalized format
            symbol = price_data.get("symbol") or self._get_symbol_from_instrument_key(
                instrument_key
            )
            if not symbol:
                return

            # Extract current price and previous close from normalized data
            current_price = price_data.get("ltp")
            previous_close = price_data.get("cp")
            open_price = price_data.get("open")
            volume = price_data.get("volume", 0)

            # Validate essential data
            if not all([current_price, previous_close, open_price]):
                return

            if current_price <= 0 or previous_close <= 0:
                return

            # Create tick data with current LTP
            tick = TickData(
                timestamp=datetime.now(),
                price=Decimal(str(current_price)),
                volume=int(volume) if volume else 1,
                instrument_key=instrument_key,
                symbol=symbol,
            )

            # Get or create candle builder for this symbol
            builder = self._get_or_create_builder(
                symbol, instrument_key, Decimal(str(previous_close))
            )

            # Set the opening price from the feed if this is the first tick
            if builder.open_price is None:
                builder.open_price = Decimal(str(open_price))

            # Add tick to builder
            builder.add_tick(tick)
            self.ticks_processed_today += 1

            # Check if we should finalize the candle (end of premarket window)
            if datetime.now().time() >= self.premarket_end:
                # Schedule finalization as a background task instead of awaiting
                asyncio.create_task(self._finalize_candle(builder))

        except Exception as e:
            logger.error(f"❌ Error processing tick for premarket candle: {e}")

    def _get_symbol_from_instrument_key(self, instrument_key: str) -> Optional[str]:
        """Extract symbol from instrument key"""
        try:
            if instrument_registry:
                spot_data = instrument_registry._spot_instruments.get(instrument_key)
                if spot_data:
                    return spot_data.get("symbol")
        except Exception:
            pass
        return None

    def _get_or_create_builder(
        self, symbol: str, instrument_key: str, previous_close: Decimal = None
    ) -> CandleBuilder:
        """Get existing builder or create new one"""
        if symbol not in self.active_builders:
            now = datetime.now()
            start_time = datetime.combine(now.date(), self.premarket_start)
            end_time = datetime.combine(now.date(), self.premarket_end)

            # Use the previous close from live feed if available, otherwise from cache
            prev_close = previous_close or self.previous_closes.get(symbol)

            builder = CandleBuilder(
                symbol=symbol,
                instrument_key=instrument_key,
                start_time=start_time,
                end_time=end_time,
                previous_close=prev_close,
            )

            self.active_builders[symbol] = builder

        return self.active_builders[symbol]

    async def _finalize_candle(self, builder: CandleBuilder):
        """Finalize and save candle to database"""
        try:
            if not builder.is_complete():
                logger.warning(f"⚠️ Incomplete candle for {builder.symbol} - skipping")
                return

            # Check if already processed
            if builder.symbol in self.processed_symbols:
                return

            self.processed_symbols.add(builder.symbol)

            # Calculate gap analysis
            gap_percentage = builder.calculate_gap_percentage()
            gap_type = builder.get_gap_type()
            gap_strength = builder.get_gap_strength()

            # Determine if significant gap
            is_significant = gap_percentage and abs(gap_percentage) >= Decimal("1.0")

            # Create premarket candle record
            candle = PremarketCandle(
                symbol=builder.symbol,
                instrument_key=builder.instrument_key,
                candle_date=self.current_session_date,
                candle_start_time=builder.start_time,
                candle_end_time=builder.end_time,
                open_price=builder.open_price,
                high_price=builder.high_price,
                low_price=builder.low_price,
                close_price=builder.close_price,
                total_volume=builder.total_volume,
                total_trades=builder.total_trades,
                avg_price=builder.get_avg_price(),
                previous_close=builder.previous_close,
                gap_percentage=gap_percentage,
                gap_type=gap_type,
                gap_strength=gap_strength,
                volume_ratio=self._calculate_volume_ratio(builder),
                volume_confirmation=self._has_volume_confirmation(builder),
                ticks_received=builder.tick_count,
                data_quality_score=builder.get_data_quality_score(),
                sector=self._get_sector(builder.symbol),
                market_cap_category=self._get_market_cap_category(builder.close_price),
                is_significant_gap=is_significant or False,
            )

            # Save to database
            db = next(get_db())
            try:
                db.add(candle)
                db.commit()
                db.refresh(candle)

                self.candles_built_today += 1

                # Generate alert for significant gaps
                if is_significant:
                    await self._generate_gap_alert(candle, db)
                    self.gaps_detected_today += 1

                logger.info(
                    f"✅ Candle saved: {builder.symbol} "
                    f"Gap: {gap_percentage}% ({gap_strength}) "
                    f"Quality: {candle.data_quality_score}"
                )

            finally:
                try:
                    db.close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ Error finalizing candle for {builder.symbol}: {e}")

    def _calculate_volume_ratio(self, builder: CandleBuilder) -> Optional[Decimal]:
        """Calculate volume ratio vs historical average"""
        # This would need historical volume data - simplified for now
        return Decimal("1.0")  # Placeholder

    def _has_volume_confirmation(self, builder: CandleBuilder) -> bool:
        """Check if volume confirms the price gap"""
        # Simplified - would need historical volume analysis
        return builder.total_volume > 1000  # Basic threshold

    def _get_sector(self, symbol: str) -> str:
        """Get sector for symbol"""
        # Simplified mapping - could be enhanced with real data
        sector_map = {
            "RELIANCE": "ENERGY",
            "TCS": "IT",
            "INFY": "IT",
            "WIPRO": "IT",
            "HDFCBANK": "BANKING",
            "ICICIBANK": "BANKING",
            "SBIN": "BANKING",
            "MARUTI": "AUTO",
            "M&M": "AUTO",
            "BAJFINANCE": "FINANCE",
        }
        return sector_map.get(symbol, "OTHER")

    def _get_market_cap_category(self, price: Decimal) -> str:
        """Estimate market cap category based on price"""
        if price > Decimal("1000"):
            return "LARGE_CAP"
        elif price > Decimal("200"):
            return "MID_CAP"
        else:
            return "SMALL_CAP"

    async def _generate_gap_alert(self, candle: PremarketCandle, db: Session):
        """Generate gap detection alert"""
        try:
            # Calculate alert priority
            gap_pct = abs(candle.gap_percentage or Decimal("0"))
            if gap_pct >= Decimal("8.0"):
                priority = "CRITICAL"
            elif gap_pct >= Decimal("5.0"):
                priority = "HIGH"
            elif gap_pct >= Decimal("2.5"):
                priority = "MEDIUM"
            else:
                priority = "LOW"

            # Calculate confidence score
            confidence = min(
                Decimal("0.3") + (gap_pct / Decimal("20")),  # Gap size component
                Decimal("1.0"),
            )

            # Create alert
            alert = GapDetectionAlert(
                premarket_candle_id=candle.id,
                symbol=candle.symbol,
                gap_percentage=candle.gap_percentage,
                gap_type=candle.gap_type,
                gap_strength=candle.gap_strength,
                trigger_price=candle.close_price,
                previous_close=candle.previous_close,
                alert_priority=priority,
                confidence_score=confidence,
                volume_at_alert=candle.total_volume,
                volume_ratio=candle.volume_ratio,
                expires_at=datetime.combine(candle.candle_date, self.market_open),
            )

            db.add(alert)
            db.commit()

            self.alerts_generated_today += 1

            # Broadcast alert
            await self._broadcast_gap_alert(alert)

            logger.info(
                f"🚨 GAP ALERT: {candle.symbol} {candle.gap_type} "
                f"{candle.gap_percentage}% (Priority: {priority})"
            )

        except Exception as e:
            logger.error(f"❌ Error generating gap alert: {e}")

    async def _broadcast_gap_alert(self, alert: GapDetectionAlert):
        """Broadcast gap alert via WebSocket"""
        try:
            if DEPENDENCIES_AVAILABLE and unified_manager:
                alert_data = {
                    "type": "gap_alert",
                    "symbol": alert.symbol,
                    "gap_type": alert.gap_type,
                    "gap_percentage": float(alert.gap_percentage),
                    "gap_strength": alert.gap_strength,
                    "priority": alert.alert_priority,
                    "confidence": float(alert.confidence_score),
                    "trigger_price": float(alert.trigger_price),
                    "previous_close": float(alert.previous_close),
                    "timestamp": alert.alert_time.isoformat(),
                }

                unified_manager.emit_event(
                    "premarket_gap_alert", alert_data, priority=2  # High priority
                )

        except Exception as e:
            logger.error(f"❌ Error broadcasting gap alert: {e}")

    async def cleanup_old_data(self):
        """Remove data older than 2 days"""
        try:
            cutoff_date = date.today() - timedelta(days=2)

            db = next(get_db())
            try:
                # Delete old candles (cascades to alerts)
                deleted_candles = (
                    db.query(PremarketCandle)
                    .filter(PremarketCandle.candle_date < cutoff_date)
                    .delete()
                )

                db.commit()

                if deleted_candles > 0:
                    logger.info(
                        f"🧹 Cleaned up {deleted_candles} old premarket candles"
                    )

            finally:
                try:
                    db.close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

    async def finalize_session(self):
        """Finalize premarket session and cleanup - ONLY at end of 8-minute window"""
        try:
            if not self.is_premarket_active:
                return

            # Double-check we're at the end of premarket window
            current_time = datetime.now().time()
            if current_time < self.premarket_end:
                logger.warning(
                    f"⚠️ Session finalization called early at {current_time} - waiting until {self.premarket_end}"
                )
                return

            logger.info("⏰ PREMARKET 8-MINUTE WINDOW ENDED - Finalizing all candles")

            # Finalize all remaining builders
            finalization_tasks = []
            for builder in self.active_builders.values():
                if builder.symbol not in self.processed_symbols:
                    finalization_tasks.append(self._finalize_candle(builder))

            # Process all finalizations concurrently for speed
            if finalization_tasks:
                await asyncio.gather(*finalization_tasks, return_exceptions=True)

            # Log session statistics
            logger.info(
                f"📊 Premarket 8-Minute Session Complete: "
                f"Ticks: {self.ticks_processed_today}, "
                f"Candles: {self.candles_built_today}, "
                f"Gaps: {self.gaps_detected_today}, "
                f"Alerts: {self.alerts_generated_today}"
            )

            # Cleanup old data
            await self.cleanup_old_data()

            # Clear session state
            self.active_builders.clear()
            self.is_premarket_active = False

            # Unregister WebSocket callback until next day
            await self._unregister_websocket_callback()

            logger.info(
                "✅ Premarket session finalized - service inactive until next trading day"
            )

        except Exception as e:
            logger.error(f"❌ Error finalizing premarket session: {e}")

    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics"""
        return {
            "is_premarket_active": self.is_premarket_active,
            "session_date": self.current_session_date.isoformat(),
            "ticks_processed": self.ticks_processed_today,
            "candles_built": self.candles_built_today,
            "gaps_detected": self.gaps_detected_today,
            "alerts_generated": self.alerts_generated_today,
            "active_builders": len(self.active_builders),
            "processed_symbols": len(self.processed_symbols),
            "previous_closes_loaded": len(self.previous_closes),
        }

    async def start_monitoring(self):
        """Start premarket monitoring - ONLY active during 8-minute window"""
        logger.info(
            "🕘 Starting premarket candle builder monitoring (8-minute window only)..."
        )

        while True:
            try:
                current_time = datetime.now().time()

                # STRICT: Only operate during 8:55 AM - 9:15 AM window
                monitoring_start = time(8, 55)  # 5 minutes before for preparation
                monitoring_end = time(9, 15)  # 7 minutes after for cleanup

                if not (monitoring_start <= current_time <= monitoring_end):
                    # Outside monitoring window - sleep longer and unregister callbacks
                    if self.direct_ws_subscribed:
                        await self._unregister_websocket_callback()

                    # Calculate sleep time until next monitoring window
                    next_check = datetime.combine(
                        datetime.now().date(), monitoring_start
                    )
                    if current_time > monitoring_end:
                        # Move to next day
                        next_check += timedelta(days=1)

                    sleep_seconds = (next_check - datetime.now()).total_seconds()
                    logger.info(
                        f"⏰ Outside premarket monitoring window - sleeping {sleep_seconds/3600:.1f} hours"
                    )
                    await asyncio.sleep(min(sleep_seconds, 3600))  # Max 1 hour sleep
                    continue

                # Setup WebSocket integration if we're in monitoring window but not registered
                if not self.direct_ws_subscribed:
                    await self.setup_direct_ws_integration()

                # Check if premarket session should start (9:00 AM exactly)
                if self.is_premarket_hours() and not self.is_premarket_active:
                    await self._start_premarket_session()

                # Check if session should end (9:08 AM exactly)
                elif current_time >= self.premarket_end and self.is_premarket_active:
                    await self.finalize_session()

                # During monitoring window, check every 5 seconds for precision
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"❌ Premarket monitoring error: {e}")
                await asyncio.sleep(30)

    async def _start_premarket_session(self):
        """Start premarket session ONLY at exactly 9:00 AM"""
        try:
            # STRICT: Double-check we're at exactly 9:00 AM
            current_time = datetime.now().time()
            if not self.is_premarket_hours():
                logger.error(
                    f"❌ Cannot start premarket session outside 8-minute window (current: {current_time})"
                )
                return False

            # Additional check: Must be at or very close to 9:00 AM
            seconds_from_start = (
                datetime.combine(datetime.now().date(), current_time)
                - datetime.combine(datetime.now().date(), self.premarket_start)
            ).total_seconds()

            if abs(seconds_from_start) > 30:  # Allow 30-second tolerance from 9:00 AM
                logger.warning(
                    f"⚠️ Starting premarket session {seconds_from_start}s from 9:00 AM"
                )

            logger.info(
                "🕘 Starting 8-minute premarket candle building session (9:00-9:08 AM)"
            )
            self.is_premarket_active = True

            # Reset session state for clean start
            self.active_builders.clear()
            self.processed_symbols.clear()
            self.ticks_processed_today = 0
            self.candles_built_today = 0
            self.gaps_detected_today = 0
            self.alerts_generated_today = 0

            # Load previous day close prices for gap calculation
            await self._load_previous_closes()

            # Ensure direct WebSocket integration is active
            if not self.direct_ws_subscribed:
                await self.setup_direct_ws_integration()

            logger.info(
                "✅ 8-minute premarket session started - Processing ALL market instruments"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error starting premarket session: {e}")
            self.is_premarket_active = False
            return False

    async def _load_previous_closes(self):
        """Load previous day closing prices for gap calculation"""
        try:
            # This would typically fetch from database or external API
            # For now, we'll rely on the live data providing prev_close
            logger.info("📊 Previous close prices will be loaded from live data")

        except Exception as e:
            logger.error(f"❌ Error loading previous closes: {e}")


# Singleton instance
premarket_candle_service = PremarketCandleBuilderService()


def get_premarket_candle_service() -> PremarketCandleBuilderService:
    """Get singleton premarket candle builder service"""
    return premarket_candle_service


async def start_premarket_monitoring():
    """Start premarket monitoring task"""
    await premarket_candle_service.start_monitoring()


# Utility functions for integration
async def get_todays_gaps(
    gap_type: str = None, min_strength: str = None
) -> List[Dict[str, Any]]:
    """Get today's gap detection results"""
    try:
        db = next(get_db())

        query = db.query(PremarketCandle).filter(
            and_(
                PremarketCandle.candle_date == date.today(),
                PremarketCandle.is_significant_gap == True,
            )
        )

        if gap_type:
            query = query.filter(PremarketCandle.gap_type == gap_type)

        if min_strength:
            strength_order = ["WEAK", "MODERATE", "STRONG", "VERY_STRONG"]
            min_index = (
                strength_order.index(min_strength)
                if min_strength in strength_order
                else 0
            )
            valid_strengths = strength_order[min_index:]
            query = query.filter(PremarketCandle.gap_strength.in_(valid_strengths))

        candles = query.order_by(desc(func.abs(PremarketCandle.gap_percentage))).all()

        results = []
        for candle in candles:
            results.append(
                {
                    "symbol": candle.symbol,
                    "gap_type": candle.gap_type,
                    "gap_percentage": float(candle.gap_percentage or 0),
                    "gap_strength": candle.gap_strength,
                    "open_price": float(candle.open_price),
                    "close_price": float(candle.close_price),
                    "previous_close": float(candle.previous_close or 0),
                    "volume": candle.total_volume,
                    "volume_ratio": float(candle.volume_ratio or 1),
                    "data_quality": float(candle.data_quality_score or 0),
                    "sector": candle.sector,
                    "timestamp": candle.created_at.isoformat(),
                }
            )

        return results

    except Exception as e:
        logger.error(f"❌ Error getting today's gaps: {e}")
        return []
    finally:
        try:
            db.close()
        except Exception:
            pass


async def get_active_alerts() -> List[Dict[str, Any]]:
    """Get active gap detection alerts"""
    try:
        db = next(get_db())

        alerts = (
            db.query(GapDetectionAlert)
            .filter(
                and_(
                    GapDetectionAlert.alert_status == "ACTIVE",
                    GapDetectionAlert.expires_at > datetime.now(),
                )
            )
            .order_by(desc(GapDetectionAlert.confidence_score))
            .all()
        )

        results = []
        for alert in alerts:
            results.append(
                {
                    "symbol": alert.symbol,
                    "gap_type": alert.gap_type,
                    "gap_percentage": float(alert.gap_percentage),
                    "priority": alert.alert_priority,
                    "confidence": float(alert.confidence_score),
                    "trigger_price": float(alert.trigger_price),
                    "expires_at": alert.expires_at.isoformat(),
                    "timestamp": alert.alert_time.isoformat(),
                }
            )

        return results

    except Exception as e:
        logger.error(f"❌ Error getting active alerts: {e}")
        return []
    finally:
        try:
            db.close()
        except Exception:
            pass
