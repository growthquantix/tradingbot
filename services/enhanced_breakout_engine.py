#!/usr/bin/env python3
"""
Enhanced Breakout Detection Engine - HFT Integration Bridge
LEGACY SYSTEM - Use services/hft_breakout_detection.py for new HFT architecture

This service now acts as a bridge between legacy breakout detection and the new HFT system.
All new breakout detection should use the HFT system for sub-millisecond performance.

Migration Status:
- HFT system provides ultra-fast vectorized processing
- This service maintained for backwards compatibility
- Gradually being phased out in favor of HFT architecture
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import json
import threading
import weakref
from decimal import Decimal

# High-performance libraries
import numpy as np
import pandas as pd
from numba import jit, njit
import psutil

logger = logging.getLogger(__name__)

# Configuration constants for ultra-fast processing
MAX_INSTRUMENTS = 5000  # Support up to 5000 instruments
RING_BUFFER_SIZE = 100  # Keep 100 price points per instrument (last ~2-3 hours)
PRICE_DTYPE = np.float32  # 4 bytes vs 8 for float64
VOLUME_DTYPE = np.uint32  # 4 bytes, supports up to 4B volume
TIMESTAMP_DTYPE = np.float64  # Precise timestamps


class BreakoutType(Enum):
    """Enhanced breakout types - 16 different strategies"""

    # Volume-based breakouts
    VOLUME_BREAKOUT = "volume_breakout"
    VOLUME_SURGE = "volume_surge"
    UNUSUAL_VOLUME = "unusual_volume"

    # Price momentum breakouts
    MOMENTUM_BREAKOUT = "momentum_breakout"
    STRONG_MOMENTUM = "strong_momentum"
    ACCELERATION = "acceleration"

    # Technical level breakouts
    RESISTANCE_BREAKOUT = "resistance_breakout"
    SUPPORT_BREAKDOWN = "support_breakdown"
    HIGH_BREAKOUT = "high_breakout"
    LOW_BREAKDOWN = "low_breakdown"

    # Pattern-based breakouts
    GAP_UP = "gap_up"
    GAP_DOWN = "gap_down"
    VOLATILITY_EXPANSION = "volatility_expansion"
    PRICE_SQUEEZE = "price_squeeze"

    # Advanced patterns
    TRIANGULAR_BREAKOUT = "triangular_breakout"
    CHANNEL_BREAKOUT = "channel_breakout"


@dataclass
class BreakoutSignal:
    """Enhanced breakout signal with comprehensive data"""

    instrument_key: str
    symbol: str
    breakout_type: BreakoutType
    current_price: float
    breakout_price: float
    trigger_price: float  # Price that triggered the breakout
    volume: int
    percentage_move: float
    strength: float  # 1-10 scale
    confidence: float  # 0-100% confidence score
    timestamp: datetime

    # Enhanced metadata
    volume_ratio: float = 0.0
    volatility_score: float = 0.0
    market_cap_category: str = "unknown"
    sector: str = "unknown"
    confirmation_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "instrument_key": self.instrument_key,
            "symbol": self.symbol,
            "breakout_type": self.breakout_type.value,
            "current_price": self.current_price,
            "breakout_price": self.breakout_price,
            "trigger_price": self.trigger_price,
            "volume": self.volume,
            "percentage_move": self.percentage_move,
            "strength": self.strength,
            "confidence": self.confidence,
            "volume_ratio": self.volume_ratio,
            "volatility_score": self.volatility_score,
            "timestamp": self.timestamp.isoformat(),
            "market_cap_category": self.market_cap_category,
            "sector": self.sector,
            "confirmation_signals": self.confirmation_signals,
            "time_ago": self._calculate_time_ago(),
            "epoch_timestamp": int(self.timestamp.timestamp()),
        }

    def _calculate_time_ago(self) -> str:
        """Calculate human readable time ago"""
        now = datetime.now()
        diff = now - self.timestamp
        total_seconds = diff.total_seconds()

        if total_seconds < 10:
            return "just now"
        elif total_seconds < 60:
            return f"{int(total_seconds)}s ago"
        elif total_seconds < 3600:
            return f"{int(total_seconds / 60)}m ago"
        elif total_seconds < 86400:
            hours = int(total_seconds / 3600)
            minutes = int((total_seconds % 3600) / 60)
            return f"{hours}h {minutes}m ago" if minutes > 0 else f"{hours}h ago"
        else:
            return f"{int(total_seconds / 86400)}d ago"


# Numba-compiled ultra-fast detection functions
@njit(cache=True)
def fast_volume_breakout_check(
    current_volume: np.ndarray,
    volume_history: np.ndarray,
    price_change_pct: np.ndarray,
    min_change: float = 0.8,
    volume_multiplier: float = 2.0,
) -> np.ndarray:
    """Ultra-fast volume breakout detection"""
    n_instruments = len(current_volume)
    result = np.zeros(n_instruments, dtype=np.int8)

    for i in range(n_instruments):
        if volume_history.shape[1] < 10:  # Need at least 10 data points
            continue

        # Calculate volume statistics
        vol_hist = volume_history[i, :]
        valid_vols = vol_hist[vol_hist > 0]

        if len(valid_vols) < 5:
            continue

        avg_volume = np.mean(valid_vols)
        if avg_volume <= 0:
            continue

        volume_ratio = current_volume[i] / avg_volume

        # Breakout conditions
        if (
            volume_ratio >= volume_multiplier * 1.5
            and abs(price_change_pct[i]) >= min_change
        ):
            result[i] = 1

    return result


@njit(cache=True)
def fast_momentum_breakout_check(
    current_prices: np.ndarray,
    price_change_pct: np.ndarray,
    base_threshold: float = 1.8,
) -> np.ndarray:
    """Ultra-fast momentum breakout detection with dynamic thresholds"""
    n_instruments = len(current_prices)
    result = np.zeros(n_instruments, dtype=np.int8)

    for i in range(n_instruments):
        price = current_prices[i]
        change_pct = abs(price_change_pct[i])

        # Dynamic threshold based on price
        if price >= 2000:
            threshold = base_threshold * 0.75  # 1.35% for expensive stocks
        elif price >= 1000:
            threshold = base_threshold  # 1.8% for mid-price stocks
        else:
            threshold = base_threshold * 1.25  # 2.25% for cheaper stocks

        if change_pct >= threshold:
            result[i] = 1

    return result


@njit(cache=True)
def fast_resistance_breakout_check(
    current_prices: np.ndarray,
    price_history: np.ndarray,
    min_history: int = 15,
    percentile_threshold: float = 90.0,
    breakout_buffer: float = 0.005,
) -> np.ndarray:
    """Ultra-fast resistance/support breakout detection"""
    n_instruments = len(current_prices)
    result = np.zeros(n_instruments, dtype=np.int8)

    for i in range(n_instruments):
        if price_history.shape[1] < min_history:
            continue

        # Get recent price history
        price_hist = price_history[i, :]
        valid_prices = price_hist[price_hist > 0]

        if len(valid_prices) < min_history:
            continue

        # Use last 20 points for resistance calculation
        recent_prices = valid_prices[-20:] if len(valid_prices) >= 20 else valid_prices

        # Calculate resistance (90th percentile)
        sorted_prices = np.sort(recent_prices)
        resistance_idx = int(len(sorted_prices) * 0.9)
        resistance_level = sorted_prices[resistance_idx]

        # Calculate support (10th percentile)
        support_idx = int(len(sorted_prices) * 0.1)
        support_level = sorted_prices[support_idx]

        current_price = current_prices[i]

        # Check resistance breakout
        if current_price > resistance_level * (1 + breakout_buffer):
            percentage_move = (
                (current_price - resistance_level) / resistance_level
            ) * 100
            if percentage_move >= 0.3:  # At least 0.3% above resistance
                result[i] = 1

        # Check support breakdown
        elif current_price < support_level * (1 - breakout_buffer):
            percentage_move = ((support_level - current_price) / support_level) * 100
            if percentage_move >= 0.3:  # At least 0.3% below support
                result[i] = -1  # Negative for breakdown

    return result


@njit(cache=True)
def fast_volatility_calculation(
    price_history: np.ndarray, window: int = 20
) -> np.ndarray:
    """Ultra-fast volatility calculation for all instruments"""
    n_instruments, n_periods = price_history.shape
    volatility = np.zeros(n_instruments, dtype=np.float32)

    for i in range(n_instruments):
        prices = price_history[i, :]
        valid_prices = prices[prices > 0]

        if len(valid_prices) < window:
            continue

        # Calculate returns
        recent_prices = valid_prices[-window:]
        if len(recent_prices) < 2:
            continue

        returns = np.diff(recent_prices) / recent_prices[:-1]
        volatility[i] = np.std(returns) * np.sqrt(252)  # Annualized

    return volatility


class RingBufferStorage:
    """Memory-efficient ring buffer for storing market data"""

    def __init__(self, max_instruments: int, buffer_size: int):
        self.max_instruments = max_instruments
        self.buffer_size = buffer_size

        # Ring buffers for different data types
        self.prices = np.zeros((max_instruments, buffer_size), dtype=PRICE_DTYPE)
        self.volumes = np.zeros((max_instruments, buffer_size), dtype=VOLUME_DTYPE)
        self.timestamps = np.zeros(
            (max_instruments, buffer_size), dtype=TIMESTAMP_DTYPE
        )

        # Metadata arrays
        self.current_positions = np.zeros(max_instruments, dtype=np.int32)
        self.data_counts = np.zeros(max_instruments, dtype=np.int32)

        # Instrument mapping
        self.instrument_index: Dict[str, int] = {}
        self.index_to_instrument: Dict[int, str] = {}
        self.next_index = 0

        # Current state arrays
        self.current_prices = np.zeros(max_instruments, dtype=PRICE_DTYPE)
        self.current_volumes = np.zeros(max_instruments, dtype=VOLUME_DTYPE)
        self.price_changes_pct = np.zeros(max_instruments, dtype=PRICE_DTYPE)

        # Calculated fields
        self.volatility = np.zeros(max_instruments, dtype=PRICE_DTYPE)
        self.volume_ratios = np.zeros(max_instruments, dtype=PRICE_DTYPE)

        self.lock = threading.RLock()

    def add_instrument(self, instrument_key: str) -> int:
        """Add new instrument and return its index"""
        with self.lock:
            if instrument_key in self.instrument_index:
                return self.instrument_index[instrument_key]

            if self.next_index >= self.max_instruments:
                raise ValueError(
                    f"Maximum instruments ({self.max_instruments}) reached"
                )

            index = self.next_index
            self.instrument_index[instrument_key] = index
            self.index_to_instrument[index] = instrument_key
            self.next_index += 1

            return index

    def update_data(
        self,
        instrument_key: str,
        price: float,
        volume: int,
        change_pct: float,
        timestamp: float,
    ) -> bool:
        """Update data for an instrument"""
        with self.lock:
            if instrument_key not in self.instrument_index:
                if self.next_index >= self.max_instruments:
                    return False  # No space
                self.add_instrument(instrument_key)

            index = self.instrument_index[instrument_key]
            pos = self.current_positions[index]

            # Add to ring buffer
            self.prices[index, pos] = price
            self.volumes[index, pos] = volume
            self.timestamps[index, pos] = timestamp

            # Update current state
            self.current_prices[index] = price
            self.current_volumes[index] = volume
            self.price_changes_pct[index] = change_pct

            # Update position
            self.current_positions[index] = (pos + 1) % self.buffer_size
            self.data_counts[index] = min(self.data_counts[index] + 1, self.buffer_size)

            return True

    def get_price_history(self, instrument_key: str, window: int = 20) -> np.ndarray:
        """Get price history for an instrument"""
        with self.lock:
            if instrument_key not in self.instrument_index:
                return np.array([])

            index = self.instrument_index[instrument_key]
            count = min(self.data_counts[index], window)

            if count == 0:
                return np.array([])

            pos = self.current_positions[index]

            # Extract data from ring buffer
            if pos >= count:
                return self.prices[index, pos - count : pos]
            else:
                # Wrap around
                return np.concatenate(
                    [
                        self.prices[index, self.buffer_size - (count - pos) :],
                        self.prices[index, :pos],
                    ]
                )

    def batch_update_analytics(self):
        """Update analytics for all instruments in batch"""
        with self.lock:
            # Calculate volatility for all instruments
            self.volatility = fast_volatility_calculation(self.prices, window=20)

            # Calculate volume ratios
            for i in range(self.next_index):
                if self.data_counts[i] >= 10:
                    vol_history = self.volumes[i, : min(self.data_counts[i], 10)]
                    valid_vols = vol_history[vol_history > 0]
                    if len(valid_vols) > 0:
                        avg_volume = np.mean(valid_vols)
                        if avg_volume > 0:
                            self.volume_ratios[i] = self.current_volumes[i] / avg_volume

    def get_memory_usage(self) -> float:
        """Get memory usage in MB"""
        total_bytes = (
            self.prices.nbytes
            + self.volumes.nbytes
            + self.timestamps.nbytes
            + self.current_prices.nbytes
            + self.current_volumes.nbytes
            + self.price_changes_pct.nbytes
            + self.volatility.nbytes
            + self.volume_ratios.nbytes
        )
        return total_bytes / (1024 * 1024)


class EnhancedBreakoutEngine:
    """
    🚀 ULTRA-HIGH-PERFORMANCE BREAKOUT DETECTION ENGINE

    Consolidates all existing breakout services with vectorized processing
    """

    def __init__(
        self,
        max_instruments: int = MAX_INSTRUMENTS,
        buffer_size: int = RING_BUFFER_SIZE,
    ):

        # Core storage system
        self.storage = RingBufferStorage(max_instruments, buffer_size)
        self.daily_breakouts: List[BreakoutSignal] = []
        self.active_breakouts: Dict[str, List[BreakoutSignal]] = defaultdict(list)
        self.recent_breakouts: Dict[str, BreakoutSignal] = (
            {}
        )  # Cache for duplicate prevention

        # Configuration (optimized parameters)
        self.config = {
            "min_price": 20.0,
            "max_price": 50000.0,
            "min_volume": 10000,
            "volume_multiplier": 2.0,
            "base_momentum_threshold": 1.8,
            "gap_threshold": 1.5,
            "volatility_threshold": 0.25,
            "confidence_threshold": 70.0,
            "duplicate_prevention_seconds": 300,  # 5 minutes
        }

        # Service connections
        self.market_data_hub = None
        self.unified_manager = None
        self.centralized_manager = None

        # Processing state
        self.is_running = False
        self.is_market_open = False
        self.current_trading_day = datetime.now().date()
        self.last_scan_time = None

        # Performance metrics
        self.metrics = {
            "total_scans": 0,
            "breakouts_detected": 0,
            "avg_processing_time_ms": 0.0,
            "instruments_processed": 0,
            "memory_usage_mb": 0.0,
            "detection_accuracy": 0.0,
        }

        # Threading
        self.data_lock = threading.RLock()
        self.background_tasks: Set[asyncio.Task] = set()

        # Database storage (optional - for persistence)
        self.db_session = None
        self.db_enabled = True

        # Data source tracking
        self.data_sources = {
            "centralized_manager": {
                "active": False,
                "last_data": None,
                "last_update": 0,
            },
        }
        self.last_successful_data = time.time()

        # Initialize connections and database
        self._init_connections()
        self._init_database()

        logger.info(
            f"🚀 Enhanced Breakout Engine initialized for {max_instruments} instruments"
        )

    def _init_connections(self):
        """Initialize connection with HFT Kafka system for optimized data flow"""
        connection_count = 0

        # NEW: Register with HFT Kafka system for optimized data processing
        try:
            from services.hft.integration import get_hft_system
            
            hft_system = get_hft_system()
            
            # The HFT system will automatically register this service with appropriate consumer
            # Data will flow through Kafka topics: hft.shared_memory.feed → breakout processing
            
            self.data_sources["hft_kafka_system"] = {
                "active": True,
                "last_data": None, 
                "last_update": 0,
            }
            
            logger.info("✅ OPTIMIZED: Registered with HFT Kafka system for breakout processing")
            connection_count += 1

        except Exception as e:
            logger.error(f"❌ HFT Kafka system connection failed: {e}")
            
        # FALLBACK: Keep centralized manager as backup (no callbacks, just for emergency data)
        try:
            from services.centralized_ws_manager import centralized_manager
            self.centralized_manager = centralized_manager
            logger.info("✅ FALLBACK: Centralized manager available as backup")
        except Exception as e:
            logger.error(f"❌ FALLBACK: Centralized Manager connection failed: {e}")

        # FALLBACK: Unified WebSocket Manager (minimal setup)
        try:
            from services.unified_websocket_manager import unified_manager

            self.unified_manager = unified_manager
            connection_count += 1
            logger.info("✅ FALLBACK: Connected to Unified WebSocket Manager")
        except Exception as e:
            logger.warning(f"⚠️ Unified Manager connection failed: {e}")

        # CRITICAL CHECK
        if connection_count == 0:
            logger.error(
                "🚨 CRITICAL: NO DATA SOURCES AVAILABLE - BREAKOUT ENGINE CANNOT FUNCTION"
            )
            raise RuntimeError(
                "CRITICAL FAILURE: No data sources available for breakout engine"
            )

        logger.info(
            f"🚀 DATA SOURCES ESTABLISHED: {connection_count} connections active"
        )

    def _init_database(self):
        """Initialize database connection for breakout persistence"""
        try:
            from database.connection import get_db as get_db_session
            from database.models import BreakoutSignal

            # Test database connection
            db_gen = get_db_session()
            self.db_session = next(db_gen)
            logger.info("✅ Database connection established for breakout persistence")

        except ImportError as e:
            logger.warning(f"❌ Database models not available: {e}")
            self.db_enabled = False
        except Exception as e:
            logger.warning(f"❌ Database connection failed: {e}")
            self.db_enabled = False

    async def start(self):
        """Start the enhanced breakout engine"""
        if self.is_running:
            logger.info("🔍 Enhanced Breakout Engine already running")
            return

        self.is_running = True
        self.last_successful_data = time.time()
        logger.info(
            "🚀 Starting Enhanced Breakout Engine with BULLETPROOF redundancy..."
        )

        # Primary data connection is already established in _init_connections()
        logger.info(
            "🚀 Using direct centralized WebSocket manager connection for breakout detection"
        )

        # Start background tasks
        tasks = [
            asyncio.create_task(self._processing_loop()),
            asyncio.create_task(self._analytics_loop()),
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._market_status_loop()),
        ]

        self.background_tasks.update(tasks)
        logger.info("✅ Enhanced Breakout Engine started successfully")

    async def _setup_live_feed_subscription(self):
        """Setup subscription to live feed manager for ultra-fast breakout detection"""
        try:
            from services.live_feed_manager import subscribe_to_live_feed
            from services.auto_stock_selection_service import (
                get_selected_fo_instruments,
                get_index_instruments,
            )

            # Get F&O instruments + indices for breakout detection
            try:
                from services.auto_stock_selection_service import (
                    get_selected_fo_instruments_async,
                    get_index_instruments,
                )

                fo_instruments = await get_selected_fo_instruments_async()
                index_instruments = await get_index_instruments()

                # Combine F&O stocks and indices
                all_instruments = fo_instruments + index_instruments
                instrument_keys = [
                    stock.get("instrument_key")
                    for stock in all_instruments
                    if stock.get("instrument_key")
                ]

                if not instrument_keys:
                    logger.error("❌ No instruments found for breakout detection")
                    return

                # Subscribe with high priority for breakout detection
                success = await subscribe_to_live_feed(
                    service_name="enhanced_breakout_engine",
                    callback=self._process_live_feed_data,
                    instrument_keys=instrument_keys,
                    priority=1,  # Highest priority
                    filter_func=self._filter_breakout_candidates,
                )

                if success:
                    logger.info(
                        f"🔍 Subscribed to {len(instrument_keys)} F&O instruments for breakout detection"
                    )
                else:
                    logger.error("❌ Failed to subscribe to live feed manager")

            except Exception as e:
                logger.error(f"❌ Error getting F&O instruments: {e}")

        except ImportError as e:
            logger.warning(f"❌ Live Feed Manager not available: {e}")

    def _filter_breakout_candidates(self, live_data) -> bool:
        """Filter function to identify potential breakout candidates"""
        try:
            # Only process data during market hours
            if not self.is_market_open:
                return False

            # Filter by minimum volume (avoid illiquid stocks)
            if live_data.volume < 1000:
                return False

            # Filter by minimum price movement (>0.5%)
            if abs(live_data.change_percent) < 0.5:  # Decimal converted to float
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Error in breakout filter: {e}")
            return False

    async def _process_live_feed_data(self, live_data):
        """Process live feed data for ultra-fast breakout detection"""
        try:
            # Convert to internal format and update storage
            price_float = float(live_data.ltp)
            volume_int = live_data.volume
            change_pct = float(live_data.change_percent)
            timestamp = time.time()

            # Update ring buffer storage
            success = self.storage.update_data(
                live_data.instrument_key, price_float, volume_int, change_pct, timestamp
            )

            if not success:
                return  # Storage full

            # Perform real-time breakout analysis
            await self._analyze_real_time_breakout(live_data)

        except Exception as e:
            logger.error(f"❌ Error processing live feed data: {e}")

    async def _analyze_real_time_breakout(self, live_data):
        """Analyze live data for immediate breakout detection"""
        try:
            # Quick momentum check for significant moves
            change_pct = float(live_data.change_percent)
            if abs(change_pct) > 2.0:  # >2% movement
                # Get price history for analysis
                price_history = self.storage.get_price_history(
                    live_data.instrument_key, 20
                )

                if len(price_history) >= 5:  # Need minimum data points
                    # Detect breakout patterns
                    breakout_signals = await self._detect_breakouts_from_history(
                        live_data.instrument_key,
                        live_data.symbol,
                        price_history,
                        float(live_data.ltp),
                        live_data.volume,
                    )

                    # Process any detected breakouts
                    for signal in breakout_signals:
                        await self._process_breakout_signal(signal)

        except Exception as e:
            logger.error(f"❌ Error in real-time breakout analysis: {e}")

    async def _detect_breakouts_from_history(
        self,
        instrument_key: str,
        symbol: str,
        price_history: list,
        current_price: float,
        current_volume: int,
    ) -> List[BreakoutSignal]:
        """Detect breakouts from price history"""
        signals = []

        try:
            if len(price_history) < 5:
                return signals

            # Calculate basic statistics
            recent_high = (
                max(price_history[-10:])
                if len(price_history) >= 10
                else max(price_history)
            )
            recent_low = (
                min(price_history[-10:])
                if len(price_history) >= 10
                else min(price_history)
            )
            avg_price = sum(price_history) / len(price_history)

            # High breakout detection
            if current_price > recent_high * 1.005:  # 0.5% above recent high
                signal = BreakoutSignal(
                    instrument_key=instrument_key,
                    symbol=symbol,
                    breakout_type=BreakoutType.HIGH_BREAKOUT,
                    current_price=current_price,
                    breakout_price=recent_high,
                    trigger_price=current_price,
                    volume=current_volume,
                    percentage_move=((current_price - recent_high) / recent_high) * 100,
                    strength=min(
                        10, abs((current_price - recent_high) / recent_high) * 500
                    ),  # Scale strength
                    confidence=75.0,
                    timestamp=datetime.now(),
                    volume_ratio=(
                        current_volume / max(price_history) if price_history else 1.0
                    ),
                )
                signals.append(signal)

            # Low breakdown detection
            elif current_price < recent_low * 0.995:  # 0.5% below recent low
                signal = BreakoutSignal(
                    instrument_key=instrument_key,
                    symbol=symbol,
                    breakout_type=BreakoutType.LOW_BREAKDOWN,
                    current_price=current_price,
                    breakout_price=recent_low,
                    trigger_price=current_price,
                    volume=current_volume,
                    percentage_move=((current_price - recent_low) / recent_low) * 100,
                    strength=min(
                        10, abs((current_price - recent_low) / recent_low) * 500
                    ),
                    confidence=75.0,
                    timestamp=datetime.now(),
                    volume_ratio=(
                        current_volume / max(price_history) if price_history else 1.0
                    ),
                )
                signals.append(signal)

        except Exception as e:
            logger.error(f"❌ Error detecting breakouts: {e}")

        return signals

    async def _process_breakout_signal(self, signal: BreakoutSignal):
        """Process a detected breakout signal"""
        try:
            # Store the signal
            signal_key = f"{signal.instrument_key}_{signal.breakout_type.value}_{signal.timestamp.strftime('%H%M%S')}"

            # Check for duplicates
            if signal_key in self.recent_breakouts:
                return  # Already processed

            # Add to recent breakouts
            self.recent_breakouts[signal_key] = signal

            # Limit cache size
            if len(self.recent_breakouts) > 1000:
                # Remove oldest entries
                oldest_keys = sorted(self.recent_breakouts.keys())[:100]
                for key in oldest_keys:
                    del self.recent_breakouts[key]

            # Log the breakout
            logger.info(
                f"🔥 BREAKOUT DETECTED: {signal.symbol} - {signal.breakout_type.value} - "
                f"Price: {signal.current_price}, Move: {signal.percentage_move:.2f}%, "
                f"Strength: {signal.strength:.1f}"
            )

            # Persist to database (background task)
            if self.db_enabled:
                asyncio.create_task(self._persist_breakout_to_db(signal))

            # Broadcast to WebSocket clients
            await self._broadcast_breakout_signal(signal)

        except Exception as e:
            logger.error(f"❌ Error processing breakout signal: {e}")

    async def _persist_breakout_to_db(self, signal: BreakoutSignal):
        """Persist breakout signal to database for historical analysis"""
        try:
            if not self.db_enabled or not self.db_session:
                return

            from database.models import BreakoutSignal as DBBreakoutSignal
            from datetime import date

            # Create database record
            db_signal = DBBreakoutSignal(
                instrument_key=signal.instrument_key,
                symbol=signal.symbol,
                breakout_type=signal.breakout_type.value,
                current_price=Decimal(str(signal.current_price)),
                breakout_price=Decimal(str(signal.breakout_price)),
                trigger_price=Decimal(str(signal.trigger_price)),
                percentage_move=signal.percentage_move,
                strength=signal.strength,
                confidence=signal.confidence,
                volume=signal.volume,
                volume_ratio=signal.volume_ratio,
                volatility_score=signal.volatility_score,
                market_cap_category=signal.market_cap_category,
                sector=signal.sector,
                confirmation_signals=signal.confirmation_signals,
                detected_at=signal.timestamp,
                trading_date=signal.timestamp.date(),
                market_hours=self.is_market_open,
                market_status="open" if self.is_market_open else "closed",
            )

            # Save to database
            self.db_session.add(db_signal)
            self.db_session.commit()

            logger.debug(f"💾 Persisted breakout signal to database: {signal.symbol}")

        except Exception as e:
            logger.error(f"❌ Error persisting breakout to database: {e}")
            if self.db_session:
                self.db_session.rollback()

    async def _broadcast_breakout_signal(self, signal: BreakoutSignal):
        """Broadcast breakout signal to WebSocket clients"""
        try:
            broadcast_data = {"type": "breakout_signal", "signal": signal.to_dict()}

            # Broadcast via unified manager if available
            if self.unified_manager:
                try:
                    # *** FIX: Handle priority parameter gracefully ***
                    try:
                        self.unified_manager.emit_event(
                            "breakout_signal", broadcast_data, priority=1
                        )
                    except TypeError:
                        # Fallback without priority if not supported
                        self.unified_manager.emit_event(
                            "breakout_signal", broadcast_data
                        )
                    logger.debug(f"📡 Broadcasted breakout signal via unified manager")
                except Exception as e:
                    logger.debug(f"Unified manager broadcast failed: {e}")

            # Broadcast via centralized manager as fallback
            if self.centralized_manager:
                try:
                    await self.centralized_manager.broadcast_to_clients(broadcast_data)
                    logger.debug(
                        f"📡 Broadcasted breakout signal via centralized manager"
                    )
                except Exception as e:
                    logger.debug(f"Centralized manager broadcast failed: {e}")

        except Exception as e:
            logger.error(f"❌ Error broadcasting breakout signal: {e}")

    async def stop(self):
        """Stop the enhanced breakout engine"""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        self.background_tasks.clear()
        logger.info("🛑 Enhanced Breakout Engine stopped")

    async def _process_market_data_hub(self, data: Dict[str, Any]):
        """Process data from Market Data Hub"""
        try:
            # Process different data types from hub
            if isinstance(data, dict):
                data_type = data.get("type", "unknown")

                if data_type == "price_update":
                    # Handle single price update
                    instrument_key = data.get("instrument_key")
                    price_data = data.get("data", {})

                    if instrument_key and price_data:
                        await self._process_single_update(instrument_key, price_data)

                elif data_type == "batch_update":
                    # Handle batch of price updates
                    updates = data.get("updates", [])
                    await self._process_feed_batch(updates)

                elif data_type == "market_data":
                    # Handle general market data
                    feeds = data.get("feeds", [])
                    if feeds:
                        await self._process_feed_batch(feeds)

                else:
                    # Try to process as direct feed data
                    await self._process_centralized_data(data)

        except Exception as e:
            logger.error(f"❌ Error processing market data hub data: {e}")

    async def _process_single_update(
        self, instrument_key: str, price_data: Dict[str, Any]
    ):
        """Process a single price update efficiently"""
        try:
            # Extract price information
            current_price = float(
                price_data.get("ltp", price_data.get("last_price", 0))
            )
            volume = int(price_data.get("volume", 0))

            # Basic validation
            if current_price <= 0:
                return

            # Update storage
            with self.data_lock:
                success = self.storage.update_instrument_data(
                    instrument_key=instrument_key,
                    price=current_price,
                    volume=volume,
                    timestamp=time.time(),
                )

                if success:
                    logger.debug(f"Updated {instrument_key}: ₹{current_price:.2f}")

        except (ValueError, TypeError) as e:
            logger.debug(f"Data validation error for {instrument_key}: {e}")
        except Exception as e:
            logger.error(f"Error processing single update for {instrument_key}: {e}")

    async def _process_live_market_data(self, raw_data: Dict[str, Any]):
        """Process live market data directly from centralized WebSocket manager"""
        start_time = time.perf_counter()

        try:
            # Update health tracking immediately
            self.last_successful_data = time.time()
            self.data_sources["centralized_manager"]["last_data"] = raw_data
            self.data_sources["centralized_manager"]["last_update"] = time.time()
            self.data_sources["centralized_manager"]["active"] = True

            # Data flow is active

            # Extract feeds data based on Upstox format
            feeds_data = None

            # Handle different data structures from ws_client
            if "feeds" in raw_data:
                # Direct feeds format from Upstox WebSocket
                feeds_data = raw_data["feeds"]
            elif "data" in raw_data and isinstance(raw_data["data"], dict):
                # Wrapped data format
                feeds_data = raw_data["data"]
            elif isinstance(raw_data, dict) and any(
                key for key in raw_data.keys() if "|" in str(key)
            ):
                # Direct instrument key format
                feeds_data = raw_data

            if not feeds_data:
                return

            # Process feeds data for breakout detection
            await self._process_upstox_feeds(feeds_data)

            # Update processing metrics
            processing_time = (time.perf_counter() - start_time) * 1000
            self.metrics["avg_processing_time_ms"] = (
                self.metrics["avg_processing_time_ms"] * 0.9 + processing_time * 0.1
            )
            self.metrics["total_scans"] += 1

        except Exception as e:
            logger.error(f"❌ Error processing live market data: {e}")

    async def _process_upstox_feeds(self, feeds_data: Dict[str, Any]):
        """Process Upstox feeds data format for breakout detection"""
        with self.data_lock:
            updates_processed = 0
            breakouts_found = []
            current_time = time.time()

            # Process each instrument in the feeds
            for instrument_key, feed_data in feeds_data.items():
                try:
                    # Extract data from Upstox feed format
                    full_feed = feed_data.get("fullFeed", {})
                    if not full_feed:
                        continue

                    # Handle both equity and index feeds
                    market_data = full_feed.get("marketFF") or full_feed.get("indexFF")
                    if not market_data:
                        continue

                    # Extract LTPC (Last Traded Price and Quantity)
                    ltpc = market_data.get("ltpc", {})
                    if not ltpc:
                        continue

                    # Get price and volume data
                    current_price = float(ltpc.get("ltp", 0))
                    previous_close = float(ltpc.get("cp", current_price))
                    volume_traded = int(
                        market_data.get("vtt", 0)
                    )  # Total volume traded

                    # Skip if invalid data
                    if current_price <= 0 or previous_close <= 0:
                        continue

                    # Calculate percentage change
                    change_pct = (
                        (current_price - previous_close) / previous_close
                    ) * 100

                    # Apply basic filters for breakout candidates
                    if (
                        current_price < self.config["min_price"]
                        or current_price > self.config["max_price"]
                        or volume_traded < self.config["min_volume"]
                    ):
                        continue

                    # Update ring buffer storage
                    success = self.storage.update_data(
                        instrument_key,
                        current_price,
                        volume_traded,
                        change_pct,
                        current_time,
                    )

                    if success:
                        updates_processed += 1

                        # Quick breakout check for significant moves
                        if abs(change_pct) >= self.config["base_momentum_threshold"]:
                            # Get symbol name
                            symbol = (
                                instrument_key.split("|")[-1]
                                if "|" in instrument_key
                                else instrument_key
                            )

                            # Perform immediate breakout analysis
                            signal = await self._quick_breakout_analysis(
                                instrument_key,
                                symbol,
                                current_price,
                                volume_traded,
                                change_pct,
                                ltpc,
                            )

                            if signal:
                                breakouts_found.append(signal)
                                await self._process_breakout_signal(signal)

                except Exception as e:
                    logger.debug(f"Error processing feed for {instrument_key}: {e}")
                    continue

            # Update metrics
            self.metrics["instruments_processed"] = updates_processed
            if breakouts_found:
                self.metrics["breakouts_detected"] += len(breakouts_found)
                logger.info(
                    f"🔥 Detected {len(breakouts_found)} breakouts from live feed"
                )

            self.last_scan_time = datetime.now()

    async def _quick_breakout_analysis(
        self,
        instrument_key: str,
        symbol: str,
        current_price: float,
        volume: int,
        change_pct: float,
        ltpc_data: Dict[str, Any],
    ) -> Optional[BreakoutSignal]:
        """Perform quick breakout analysis based on live feed data"""
        try:
            # Determine breakout type based on price movement and volume
            breakout_type = None
            strength = 0.0
            confidence = 0.0

            # High momentum breakout (>2% move)
            if abs(change_pct) >= 2.0:
                if change_pct > 0:
                    breakout_type = BreakoutType.MOMENTUM_BREAKOUT
                else:
                    breakout_type = BreakoutType.SUPPORT_BREAKDOWN

                strength = min(10.0, abs(change_pct) * 2)
                confidence = min(95.0, abs(change_pct) * 20 + 50)

            # Volume surge detection (if available)
            elif volume > 50000:  # High volume threshold
                breakout_type = BreakoutType.VOLUME_BREAKOUT
                strength = min(8.0, volume / 10000)
                confidence = min(80.0, volume / 1000 + 40)

            # Gap detection
            elif abs(change_pct) >= 1.5:
                if change_pct > 0:
                    breakout_type = BreakoutType.GAP_UP
                else:
                    breakout_type = BreakoutType.GAP_DOWN

                strength = min(7.0, abs(change_pct) * 1.5)
                confidence = min(75.0, abs(change_pct) * 15 + 45)

            if not breakout_type:
                return None

            # Create breakout signal
            signal = BreakoutSignal(
                instrument_key=instrument_key,
                symbol=symbol,
                breakout_type=breakout_type,
                current_price=current_price,
                breakout_price=current_price,
                trigger_price=current_price,
                volume=volume,
                percentage_move=change_pct,
                strength=strength,
                confidence=confidence,
                timestamp=datetime.now(),
                confirmation_signals=[
                    f"{abs(change_pct):.1f}% move",
                    f"Volume: {volume:,}",
                    f"Strength: {strength:.1f}/10",
                ],
            )

            return signal

        except Exception as e:
            logger.error(f"❌ Error in quick breakout analysis: {e}")
            return None

    async def _processing_loop(self):
        """Main processing loop for breakout detection"""
        while self.is_running:
            try:
                start_time = time.perf_counter()

                # Update analytics in batch
                self.storage.batch_update_analytics()

                # Run vectorized breakout detection
                await self._detect_breakouts_vectorized()

                # Update memory usage metric
                self.metrics["memory_usage_mb"] = self.storage.get_memory_usage()

                # Process at 10Hz for real-time performance
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Error in processing loop: {e}")
                await asyncio.sleep(1.0)

    async def _detect_breakouts_vectorized(self):
        """Ultra-fast vectorized breakout detection"""
        with self.data_lock:
            n_instruments = self.storage.next_index
            if n_instruments == 0:
                return

            new_breakouts = []

            # 1. Volume breakouts (vectorized)
            volume_breakouts = fast_volume_breakout_check(
                self.storage.current_volumes[:n_instruments],
                self.storage.volumes[:n_instruments, :],
                self.storage.price_changes_pct[:n_instruments],
                min_change=0.8,
                volume_multiplier=self.config["volume_multiplier"],
            )

            # 2. Momentum breakouts (vectorized)
            momentum_breakouts = fast_momentum_breakout_check(
                self.storage.current_prices[:n_instruments],
                self.storage.price_changes_pct[:n_instruments],
                base_threshold=self.config["base_momentum_threshold"],
            )

            # 3. Resistance/Support breakouts (vectorized)
            resistance_breakouts = fast_resistance_breakout_check(
                self.storage.current_prices[:n_instruments],
                self.storage.prices[:n_instruments, :],
                min_history=15,
                percentile_threshold=90.0,
                breakout_buffer=0.005,
            )

            # Process results and create breakout signals
            for i in range(n_instruments):
                instrument_key = self.storage.index_to_instrument[i]

                # Check for volume breakout
                if volume_breakouts[i] == 1:
                    signal = self._create_breakout_signal(
                        instrument_key, i, BreakoutType.VOLUME_BREAKOUT
                    )
                    if signal:
                        new_breakouts.append(signal)

                # Check for momentum breakout
                if momentum_breakouts[i] == 1:
                    breakout_type = (
                        BreakoutType.MOMENTUM_BREAKOUT
                        if self.storage.price_changes_pct[i] > 0
                        else BreakoutType.SUPPORT_BREAKDOWN
                    )
                    signal = self._create_breakout_signal(
                        instrument_key, i, breakout_type
                    )
                    if signal:
                        new_breakouts.append(signal)

                # Check for resistance/support breakout
                if resistance_breakouts[i] != 0:
                    breakout_type = (
                        BreakoutType.RESISTANCE_BREAKOUT
                        if resistance_breakouts[i] > 0
                        else BreakoutType.SUPPORT_BREAKDOWN
                    )
                    signal = self._create_breakout_signal(
                        instrument_key, i, breakout_type
                    )
                    if signal:
                        new_breakouts.append(signal)

            # Add to daily breakouts and broadcast
            if new_breakouts:
                self.daily_breakouts.extend(new_breakouts)
                self.metrics["breakouts_detected"] += len(new_breakouts)
                await self._broadcast_breakouts(new_breakouts)

                logger.info(
                    f"🚨 Detected {len(new_breakouts)} breakouts via vectorized processing"
                )

    def _create_breakout_signal(
        self, instrument_key: str, index: int, breakout_type: BreakoutType
    ) -> Optional[BreakoutSignal]:
        """Create a breakout signal with comprehensive data"""
        try:
            symbol = (
                instrument_key.split("|")[-1]
                if "|" in instrument_key
                else instrument_key
            )
            current_price = float(self.storage.current_prices[index])
            volume = int(self.storage.current_volumes[index])
            change_pct = float(self.storage.price_changes_pct[index])
            volume_ratio = float(self.storage.volume_ratios[index])
            volatility = float(self.storage.volatility[index])

            # Calculate strength (1-10 scale)
            strength = min(10.0, max(1.0, abs(change_pct) * 2 + volume_ratio))

            # Calculate confidence (0-100%)
            confidence = min(
                100.0,
                max(0.0, (abs(change_pct) * 10 + volume_ratio * 15 + volatility * 20)),
            )

            # Generate confirmation signals
            confirmations = []
            if volume_ratio > 2.0:
                confirmations.append(f"{volume_ratio:.1f}x volume")
            if abs(change_pct) > 2.0:
                confirmations.append(f"{abs(change_pct):.1f}% move")
            if volatility > 0.3:
                confirmations.append("High volatility")

            return BreakoutSignal(
                instrument_key=instrument_key,
                symbol=symbol,
                breakout_type=breakout_type,
                current_price=current_price,
                breakout_price=current_price,
                trigger_price=current_price,
                volume=volume,
                percentage_move=change_pct,
                strength=strength,
                confidence=confidence,
                volume_ratio=volume_ratio,
                volatility_score=volatility,
                timestamp=datetime.now(),
                confirmation_signals=confirmations,
            )

        except Exception as e:
            logger.debug(f"Error creating breakout signal: {e}")
            return None

    async def _broadcast_breakouts(self, breakouts: List[BreakoutSignal]):
        """Broadcast breakout signals to UI"""
        try:
            if not breakouts:
                return

            # Get complete summary for broadcast
            complete_summary = self.get_breakouts_summary()

            broadcast_data = {
                "type": "breakout_analysis_update",
                "data": complete_summary,
            }

            # Try unified manager first, then centralized manager
            broadcasted = False

            if self.unified_manager:
                try:
                    self.unified_manager.emit_event(
                        "breakout_analysis_update", broadcast_data, priority=1
                    )
                    broadcasted = True
                    logger.info(f"📡 Broadcasted breakout analysis via unified manager")
                except Exception as e:
                    logger.debug(f"Unified manager broadcast failed: {e}")

            if not broadcasted and self.centralized_manager:
                try:
                    await self.centralized_manager.broadcast_to_clients(broadcast_data)
                    broadcasted = True
                    logger.info(
                        f"📡 Broadcasted breakout analysis via centralized manager"
                    )
                except Exception as e:
                    logger.debug(f"Centralized manager broadcast failed: {e}")

            if not broadcasted:
                logger.warning(
                    "❌ No WebSocket managers available for breakout broadcast"
                )

        except Exception as e:
            logger.error(f"❌ Error broadcasting breakouts: {e}")

    async def broadcast_complete_analysis(self):
        """Broadcast complete breakout analysis (can be called manually)"""
        try:
            complete_summary = self.get_breakouts_summary()

            broadcast_data = {
                "type": "breakout_analysis_update",
                "data": complete_summary,
            }

            if self.unified_manager:
                self.unified_manager.emit_event(
                    "breakout_analysis_update", broadcast_data, priority=1
                )
                logger.info("📡 Manual broadcast of complete breakout analysis")

        except Exception as e:
            logger.error(f"❌ Error in manual broadcast: {e}")

    async def inject_test_data(self, count: int = 10):
        """REMOVED: Test data injection - system uses actual market data only"""
        logger.warning(
            "⚠️ Test data injection disabled - system uses actual market data only"
        )
        return False

    async def _analytics_loop(self):
        """Background analytics and optimization loop"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Run every minute

                # Update detection accuracy
                await self._calculate_detection_accuracy()

                # Optimize parameters based on market conditions
                await self._optimize_parameters()

                # Periodic broadcast to frontend (every 5 minutes)
                if hasattr(self, "_last_broadcast_time"):
                    time_since_broadcast = datetime.now() - self._last_broadcast_time
                    if time_since_broadcast.total_seconds() >= 300:  # 5 minutes
                        await self.broadcast_complete_analysis()
                        self._last_broadcast_time = datetime.now()
                else:
                    await self.broadcast_complete_analysis()
                    self._last_broadcast_time = datetime.now()

            except Exception as e:
                logger.error(f"❌ Error in analytics loop: {e}")

    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Clean every 5 minutes

                with self.data_lock:
                    # Clean old breakouts
                    cutoff_time = datetime.now() - timedelta(hours=6)
                    self.daily_breakouts = [
                        b for b in self.daily_breakouts if b.timestamp > cutoff_time
                    ]

                    # Clean active breakouts
                    for breakout_type in self.active_breakouts:
                        self.active_breakouts[breakout_type] = [
                            b
                            for b in self.active_breakouts[breakout_type]
                            if b.timestamp > cutoff_time
                        ]

                logger.debug("🧹 Cleaned up old breakout data")

            except Exception as e:
                logger.error(f"❌ Error in cleanup loop: {e}")

    async def _market_status_loop(self):
        """Track market status and reset for new trading days"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Market hours check (9:15 AM to 3:30 PM IST)
                now = datetime.now()
                market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)

                was_open = self.is_market_open
                self.is_market_open = market_start <= now <= market_end

                if was_open != self.is_market_open:
                    status = "opened" if self.is_market_open else "closed"
                    logger.info(
                        f"📈 Market {status} - Enhanced Breakout Engine adjusted"
                    )

                # Check for new trading day
                today = now.date()
                if today > self.current_trading_day:
                    await self._reset_for_new_day()

            except Exception as e:
                logger.error(f"❌ Error in market status loop: {e}")

    async def _reset_for_new_day(self):
        """Reset for new trading day with database cleanup"""
        with self.data_lock:
            self.current_trading_day = datetime.now().date()

            # Clear in-memory data for new day
            self.daily_breakouts = []
            self.active_breakouts.clear()
            self.recent_breakouts.clear()

            # Reset metrics
            self.metrics["breakouts_detected"] = 0

            logger.info(
                f"🌅 Enhanced Breakout Engine reset for new day: {self.current_trading_day}"
            )

            # Optional: Clean old database records (keep last 30 days)
            if self.db_enabled:
                asyncio.create_task(self._cleanup_old_db_records())

    async def _cleanup_old_db_records(self):
        """Clean up old database records to maintain performance"""
        try:
            if not self.db_enabled or not self.db_session:
                return

            from database.models import BreakoutSignal as DBBreakoutSignal
            from datetime import timedelta

            # Keep last 30 days of records
            cutoff_date = (datetime.now() - timedelta(days=30)).date()

            deleted_count = (
                self.db_session.query(DBBreakoutSignal)
                .filter(DBBreakoutSignal.trading_date < cutoff_date)
                .delete()
            )

            self.db_session.commit()

            if deleted_count > 0:
                logger.info(
                    f"🧹 Cleaned up {deleted_count} old breakout records from database"
                )

        except Exception as e:
            logger.error(f"❌ Error cleaning up database records: {e}")
            if self.db_session:
                self.db_session.rollback()

    def get_historical_breakouts(
        self, days: int = 7, symbol: str = None, breakout_type: str = None
    ):
        """Get historical breakouts from database"""
        try:
            if not self.db_enabled or not self.db_session:
                return []

            from database.models import BreakoutSignal as DBBreakoutSignal
            from datetime import timedelta

            # Base query
            query = self.db_session.query(DBBreakoutSignal)

            # Date filter
            start_date = (datetime.now() - timedelta(days=days)).date()
            query = query.filter(DBBreakoutSignal.trading_date >= start_date)

            # Optional filters
            if symbol:
                query = query.filter(DBBreakoutSignal.symbol == symbol)
            if breakout_type:
                query = query.filter(DBBreakoutSignal.breakout_type == breakout_type)

            # Order by most recent first
            results = (
                query.order_by(DBBreakoutSignal.detected_at.desc()).limit(100).all()
            )

            # Convert to dictionary format
            historical_data = []
            for record in results:
                historical_data.append(
                    {
                        "symbol": record.symbol,
                        "breakout_type": record.breakout_type,
                        "current_price": float(record.current_price),
                        "percentage_move": record.percentage_move,
                        "strength": record.strength,
                        "confidence": record.confidence,
                        "volume": record.volume,
                        "detected_at": record.detected_at.isoformat(),
                        "trading_date": record.trading_date.isoformat(),
                    }
                )

            return historical_data

        except Exception as e:
            logger.error(f"❌ Error fetching historical breakouts: {e}")
            return []

    def get_system_health_status(self) -> Dict[str, Any]:
        """🩺 Get comprehensive system health status for monitoring"""
        current_time = time.time()
        data_gap = current_time - self.last_successful_data

        return {
            "engine_status": "normal",
            "is_running": self.is_running,
            "data_sources": {
                name: {
                    "active": info["active"],
                    "last_update_ago": (
                        current_time - info.get("last_update", 0)
                        if info.get("last_update")
                        else None
                    ),
                }
                for name, info in self.data_sources.items()
            },
            "last_successful_data_ago": data_gap,
            "health_metrics": {
                "instruments_tracked": len(self.storage.price_cache),
                "breakouts_detected_today": self.metrics["breakouts_detected"],
                "avg_processing_time_ms": self.metrics["avg_processing_time_ms"],
                "memory_usage_mb": self.metrics["memory_usage_mb"],
            },
            "alerts": self._get_health_alerts(data_gap),
            "timestamp": current_time,
        }

    def _get_health_alerts(self, data_gap: float) -> List[str]:
        """🚨 Generate health alerts based on current status"""
        alerts = []

        if data_gap > 60:
            alerts.append(f"⚠️ WARNING: No data for {data_gap:.1f}s")

        if data_gap > 30:
            alerts.append("⚠️ WARNING: Data flow delay detected")

        active_sources = sum(1 for info in self.data_sources.values() if info["active"])
        if active_sources < 2:
            alerts.append(f"⚠️ WARNING: Only {active_sources} data sources active")

        if not self.is_running:
            alerts.append("🚨 CRITICAL: Breakout engine not running")

        return alerts

    async def _calculate_detection_accuracy(self):
        """Calculate detection accuracy (placeholder for future ML validation)"""
        # TODO: Implement ML-based validation of breakout signals
        # For now, use a simple heuristic
        if len(self.daily_breakouts) > 0:
            high_confidence_signals = [
                b for b in self.daily_breakouts if b.confidence > 80
            ]
            self.metrics["detection_accuracy"] = (
                len(high_confidence_signals) / len(self.daily_breakouts) * 100
            )

    async def _optimize_parameters(self):
        """Optimize detection parameters based on market conditions"""
        # TODO: Implement dynamic parameter optimization
        # Adjust thresholds based on market volatility, time of day, etc.
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive engine metrics"""
        return {
            **self.metrics,
            "memory_usage_mb": self.storage.get_memory_usage(),
            "instruments_tracked": self.storage.next_index,
            "market_status": "open" if self.is_market_open else "closed",
            "trading_day": self.current_trading_day.isoformat(),
            "last_scan": (
                self.last_scan_time.isoformat() if self.last_scan_time else None
            ),
        }

    def get_breakouts_summary(self) -> Dict[str, Any]:
        """Get comprehensive breakouts summary"""
        with self.data_lock:
            current_time = datetime.now()

            # Group by type
            breakouts_by_type = defaultdict(list)
            for breakout in self.daily_breakouts:
                breakouts_by_type[breakout.breakout_type.value].append(
                    breakout.to_dict()
                )

            # Top breakouts by strength
            top_breakouts = sorted(
                self.daily_breakouts, key=lambda x: x.strength, reverse=True
            )[:20]

            # Recent breakouts
            recent_breakouts = sorted(
                self.daily_breakouts, key=lambda x: x.timestamp, reverse=True
            )[:10]

            # Separate breakouts and breakdowns for frontend compatibility
            breakouts = []
            breakdowns = []

            for breakout in self.daily_breakouts:
                breakout_dict = breakout.to_dict()

                # Classify as breakout (upward) or breakdown (downward) based on type and percentage
                is_breakdown = (
                    breakout.breakout_type
                    in [
                        BreakoutType.SUPPORT_BREAKDOWN,
                        BreakoutType.LOW_BREAKDOWN,
                        BreakoutType.GAP_DOWN,
                    ]
                    or breakout.percentage_move < 0
                )

                if is_breakdown:
                    breakdowns.append(breakout_dict)
                else:
                    breakouts.append(breakout_dict)

            return {
                # Frontend compatibility format
                "breakouts": breakouts,
                "breakdowns": breakdowns,
                "summary": {
                    "total_breakouts": len(breakouts),
                    "total_breakdowns": len(breakdowns),
                    "total_today": len(self.daily_breakouts),
                    "is_trading_hours": self.is_market_open,
                    "detection_active": self.is_running,
                    "last_update": current_time.isoformat(),
                },
                # Enhanced format (additional data)
                "total_breakouts_today": len(self.daily_breakouts),
                "breakouts_by_type": dict(breakouts_by_type),
                "top_breakouts": [b.to_dict() for b in top_breakouts],
                "recent_breakouts": [b.to_dict() for b in recent_breakouts],
                "engine_metrics": self.get_metrics(),
                "timestamp": current_time.isoformat(),
                "generated_at": current_time.strftime("%I:%M:%S %p"),
                "service": "enhanced_breakout_engine",
            }


# Global instance
enhanced_breakout_engine = EnhancedBreakoutEngine()


async def start_enhanced_breakout_engine():
    """Start the enhanced breakout engine"""
    await enhanced_breakout_engine.start()


async def stop_enhanced_breakout_engine():
    """Stop the enhanced breakout engine"""
    await enhanced_breakout_engine.stop()


def get_enhanced_breakouts_data() -> Dict[str, Any]:
    """Get enhanced breakouts data for API"""
    return enhanced_breakout_engine.get_breakouts_summary()


def health_check() -> Dict[str, Any]:
    """Enhanced health check"""
    return {
        "service": "enhanced_breakout_engine",
        "status": "running" if enhanced_breakout_engine.is_running else "stopped",
        "version": "2.0_vectorized",
        "capabilities": [
            "vectorized_processing",
            "16_breakout_types",
            "memory_efficient_storage",
            "real_time_analytics",
        ],
        **enhanced_breakout_engine.get_metrics(),
    }
