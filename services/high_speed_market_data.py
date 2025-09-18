# """
# High-Speed Market Data Access Layer
# ==================================

# Optimized for ultra-low latency trading strategies with numpy/pandas integration.
# Provides zero-copy data access, vectorized operations, and sub-millisecond response times.

# Key Features:
# - Zero-copy numpy arrays for tick data
# - Vectorized pandas operations for OHLCV generation
# - Ring buffer for memory-efficient storage
# - Lock-free access patterns for strategies
# - Pre-computed technical indicators
# - Batch processing for multiple instruments
# """

# import asyncio
# import logging
# import numpy as np
# import pandas as pd
# import numba
# from collections import deque
# from datetime import datetime, timedelta
# from typing import Dict, List, Optional, Callable, Any, Union, Tuple
# from dataclasses import dataclass
# import threading
# import time
# import pytz
# from concurrent.futures import ThreadPoolExecutor

# logger = logging.getLogger(__name__)
# IST = pytz.timezone('Asia/Kolkata')

# # Pre-compile numba functions for maximum speed
# @numba.jit(nopython=True, cache=True)
# def calculate_sma(prices: np.ndarray, period: int) -> np.ndarray:
#     """Ultra-fast Simple Moving Average calculation"""
#     if len(prices) < period:
#         return np.full_like(prices, np.nan)

#     result = np.empty_like(prices)
#     result[:period-1] = np.nan

#     for i in range(period-1, len(prices)):
#         result[i] = np.mean(prices[i-period+1:i+1])

#     return result

# @numba.jit(nopython=True, cache=True)
# def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
#     """Ultra-fast Exponential Moving Average calculation"""
#     if len(prices) == 0:
#         return np.array([])

#     alpha = 2.0 / (period + 1.0)
#     result = np.empty_like(prices)
#     result[0] = prices[0]

#     for i in range(1, len(prices)):
#         result[i] = alpha * prices[i] + (1 - alpha) * result[i-1]

#     return result

# @numba.jit(nopython=True, cache=True)
# def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
#     """Ultra-fast RSI calculation"""
#     if len(prices) < period + 1:
#         return np.full_like(prices, np.nan)

#     deltas = np.diff(prices)
#     gains = np.where(deltas > 0, deltas, 0.0)
#     losses = np.where(deltas < 0, -deltas, 0.0)

#     avg_gains = calculate_ema(gains, period)
#     avg_losses = calculate_ema(losses, period)

#     rs = avg_gains / np.maximum(avg_losses, 1e-10)
#     rsi = 100 - (100 / (1 + rs))

#     # Prepend NaN for the first price (no delta)
#     return np.concatenate([np.array([np.nan]), rsi])

# @numba.jit(nopython=True, cache=True)
# def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
#     """Ultra-fast Bollinger Bands calculation"""
#     sma = calculate_sma(prices, period)

#     if len(prices) < period:
#         return sma, sma, sma

#     upper = np.empty_like(prices)
#     lower = np.empty_like(prices)
#     upper[:period-1] = np.nan
#     lower[:period-1] = np.nan

#     for i in range(period-1, len(prices)):
#         window = prices[i-period+1:i+1]
#         std = np.std(window)
#         upper[i] = sma[i] + (std_dev * std)
#         lower[i] = sma[i] - (std_dev * std)

#     return upper, sma, lower

# @dataclass
# class TickRecord:
#     """Memory-efficient tick record for ring buffer"""
#     timestamp: float  # Unix timestamp for speed
#     ltp: float
#     volume: int
#     change: float
#     change_percent: float
#     high: float
#     low: float
#     open: float

# class RingBuffer:
#     """Lock-free ring buffer optimized for tick data"""

#     def __init__(self, size: int):
#         self.size = size
#         self.buffer = np.zeros(size, dtype=[
#             ('timestamp', 'f8'),
#             ('ltp', 'f4'),
#             ('volume', 'i4'),
#             ('change', 'f4'),
#             ('change_percent', 'f4'),
#             ('high', 'f4'),
#             ('low', 'f4'),
#             ('open', 'f4')
#         ])
#         self.head = 0
#         self.count = 0
#         self.lock = threading.RLock()  # Only for write operations

#     def add(self, tick: TickRecord):
#         """Add tick data - thread-safe write"""
#         with self.lock:
#             self.buffer[self.head] = (
#                 tick.timestamp, tick.ltp, tick.volume,
#                 tick.change, tick.change_percent,
#                 tick.high, tick.low, tick.open
#             )
#             self.head = (self.head + 1) % self.size
#             self.count = min(self.count + 1, self.size)

#     def get_latest_n(self, n: int) -> np.ndarray:
#         """Get latest N records - lock-free read for speed"""
#         if self.count == 0:
#             return np.array([], dtype=self.buffer.dtype)

#         n = min(n, self.count)

#         if self.count < self.size:
#             # Buffer not full, simple slice
#             return self.buffer[:self.count][-n:]
#         else:
#             # Buffer is full, need to handle wrap-around
#             start = (self.head - n) % self.size
#             if start + n <= self.size:
#                 return self.buffer[start:start + n]
#             else:
#                 # Wrap around case
#                 part1 = self.buffer[start:]
#                 part2 = self.buffer[:start + n - self.size]
#                 return np.concatenate([part1, part2])

#     def get_prices_array(self, n: int) -> np.ndarray:
#         """Get price array for vectorized calculations"""
#         data = self.get_latest_n(n)
#         return data['ltp'] if len(data) > 0 else np.array([])

#     def get_volume_array(self, n: int) -> np.ndarray:
#         """Get volume array for analysis"""
#         data = self.get_latest_n(n)
#         return data['volume'] if len(data) > 0 else np.array([])

# class HighSpeedMarketData:
#     """
#     Ultra-fast market data access optimized for trading strategies.

#     Uses numpy arrays, ring buffers, and pre-computed indicators
#     for sub-millisecond data access.

#     Special focus on selected stocks for auto trading strategies.
#     """

#     def __init__(self, max_ticks_per_instrument: int = 5000):
#         # High-speed data storage
#         self.tick_buffers: Dict[str, RingBuffer] = {}
#         self.latest_prices: Dict[str, float] = {}  # Hot cache for latest prices
#         self.latest_volumes: Dict[str, int] = {}   # Hot cache for volumes
#         self.latest_changes: Dict[str, float] = {} # Hot cache for changes

#         # Pre-computed indicators cache
#         self.indicators_cache: Dict[str, Dict[str, np.ndarray]] = {}
#         self.indicators_timestamps: Dict[str, float] = {}

#         # Strategy callbacks - optimized for speed
#         self.strategy_callbacks: Dict[str, Callable] = {}
#         self.hot_instruments: set = set()  # Frequently accessed instruments

#         # 🎯 NEW: Selected stocks tracking for auto trading
#         self.selected_stocks: set = set()  # Currently selected stocks
#         self.selected_stock_data: Dict[str, Dict] = {}  # Enhanced data for selected stocks
#         self.option_chains: Dict[str, Dict] = {}  # Option chain data for selected stocks
#         self.auto_trading_instruments: set = set()  # Instruments needed for auto trading

#         # Configuration
#         self.max_ticks = max_ticks_per_instrument
#         self.indicator_cache_ttl = 1.0  # 1 second cache for indicators

#         # Thread pool for parallel processing
#         self.thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="MarketData")

#         # Performance metrics
#         self.access_counts: Dict[str, int] = {}
#         self.last_performance_report = time.time()

#         # Integration with existing services
#         self._setup_integration()

#         logger.info("🚀 High-Speed Market Data initialized with selected stocks tracking")

#     def _setup_integration(self):
#         """Set up integration with existing live adapter"""
#         try:
#             from services.live_adapter import live_feed_adapter

#             # Register ourselves as a high-priority callback
#             live_feed_adapter.register_tick_callback(
#                 name="high_speed_processor",
#                 instruments=[],  # Will be updated dynamically
#                 callback=self._process_tick_update
#             )

#             logger.info("✅ Integrated with live feed adapter")

#         except ImportError as e:
#             logger.warning(f"⚠️ Could not integrate with live adapter: {e}")

#     def _process_tick_update(self, instrument_key: str, price_data: Dict[str, Any]):
#         """Process incoming tick updates - optimized for speed"""
#         try:
#             # Convert to high-speed record
#             tick = TickRecord(
#                 timestamp=time.time(),
#                 ltp=float(price_data.get('ltp', 0.0)),
#                 volume=int(price_data.get('volume', 0)),
#                 change=float(price_data.get('change', 0.0)),
#                 change_percent=float(price_data.get('change_percent', 0.0)),
#                 high=float(price_data.get('high', price_data.get('ltp', 0.0))),
#                 low=float(price_data.get('low', price_data.get('ltp', 0.0))),
#                 open=float(price_data.get('open', price_data.get('ltp', 0.0)))
#             )

#             # Initialize buffer if needed
#             if instrument_key not in self.tick_buffers:
#                 self.tick_buffers[instrument_key] = RingBuffer(self.max_ticks)

#             # Store in ring buffer
#             self.tick_buffers[instrument_key].add(tick)

#             # Update hot caches for instant access
#             self.latest_prices[instrument_key] = tick.ltp
#             self.latest_volumes[instrument_key] = tick.volume
#             self.latest_changes[instrument_key] = tick.change

#             # Track access patterns
#             self.access_counts[instrument_key] = self.access_counts.get(instrument_key, 0) + 1

#             # Invalidate indicator cache for this instrument
#             if instrument_key in self.indicators_cache:
#                 del self.indicators_cache[instrument_key]
#                 del self.indicators_timestamps[instrument_key]

#             # Notify strategy callbacks asynchronously
#             if instrument_key in self.hot_instruments:
#                 self._notify_strategy_callbacks(instrument_key, tick)

#         except Exception as e:
#             logger.error(f"❌ Error processing tick for {instrument_key}: {e}")

#     def _notify_strategy_callbacks(self, instrument_key: str, tick: TickRecord):
#         """Notify strategy callbacks - non-blocking"""
#         for callback_name, callback in self.strategy_callbacks.items():
#             try:
#                 # Run callback in thread pool to avoid blocking
#                 self.thread_pool.submit(callback, instrument_key, {
#                     'ltp': tick.ltp,
#                     'volume': tick.volume,
#                     'change': tick.change,
#                     'timestamp': tick.timestamp
#                 })
#             except Exception as e:
#                 logger.error(f"❌ Error in strategy callback {callback_name}: {e}")

#     # === ULTRA-FAST ACCESS METHODS ===

#     def get_latest_price(self, instrument_key: str) -> Optional[float]:
#         """Get latest price - sub-microsecond access from hot cache"""
#         return self.latest_prices.get(instrument_key)

#     def get_latest_prices_batch(self, instrument_keys: List[str]) -> Dict[str, Optional[float]]:
#         """Get multiple latest prices in one call - vectorized access"""
#         return {key: self.latest_prices.get(key) for key in instrument_keys}

#     def get_price_array(self, instrument_key: str, count: int = 100) -> np.ndarray:
#         """Get price array for vectorized calculations"""
#         if instrument_key not in self.tick_buffers:
#             return np.array([])

#         self._mark_hot_instrument(instrument_key)
#         return self.tick_buffers[instrument_key].get_prices_array(count)

#     def get_volume_array(self, instrument_key: str, count: int = 100) -> np.ndarray:
#         """Get volume array for analysis"""
#         if instrument_key not in self.tick_buffers:
#             return np.array([])

#         return self.tick_buffers[instrument_key].get_volume_array(count)

#     def get_ohlcv_fast(self, instrument_key: str, timeframe: str = '1T', count: int = 100) -> pd.DataFrame:
#         """
#         Generate OHLCV DataFrame using optimized pandas operations.

#         Args:
#             instrument_key: Instrument to get data for
#             timeframe: '1T' for 1-minute, '5T' for 5-minute, etc.
#             count: Number of bars to return

#         Returns:
#             DataFrame with OHLCV data
#         """
#         if instrument_key not in self.tick_buffers:
#             return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#         try:
#             # Get raw tick data
#             buffer = self.tick_buffers[instrument_key]
#             raw_data = buffer.get_latest_n(count * 60)  # Get more ticks for proper resampling

#             if len(raw_data) == 0:
#                 return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#             # Convert to DataFrame using vectorized operations
#             df = pd.DataFrame({
#                 'timestamp': pd.to_datetime(raw_data['timestamp'], unit='s'),
#                 'price': raw_data['ltp'],
#                 'volume': raw_data['volume']
#             })

#             df.set_index('timestamp', inplace=True)

#             # Use pandas resample for fast OHLCV generation
#             ohlcv = df.resample(timeframe).agg({
#                 'price': ['first', 'max', 'min', 'last'],
#                 'volume': 'sum'
#             }).dropna()

#             # Flatten column names
#             ohlcv.columns = ['open', 'high', 'low', 'close', 'volume']
#             ohlcv.reset_index(inplace=True)

#             # Return latest N bars
#             return ohlcv.tail(count) if len(ohlcv) > count else ohlcv

#         except Exception as e:
#             logger.error(f"❌ Error generating OHLCV for {instrument_key}: {e}")
#             return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#     def get_indicators_fast(self, instrument_key: str, price_count: int = 200) -> Dict[str, np.ndarray]:
#         """
#         Get pre-computed technical indicators using numba-optimized functions.

#         Args:
#             instrument_key: Instrument to analyze
#             price_count: Number of price points for calculation

#         Returns:
#             Dict with indicator names and numpy arrays
#         """
#         # Check cache first
#         cache_key = instrument_key
#         current_time = time.time()

#         if (cache_key in self.indicators_cache and
#             cache_key in self.indicators_timestamps and
#             current_time - self.indicators_timestamps[cache_key] < self.indicator_cache_ttl):
#             return self.indicators_cache[cache_key]

#         # Calculate indicators
#         prices = self.get_price_array(instrument_key, price_count)

#         if len(prices) < 20:  # Need minimum data for meaningful indicators
#             return {}

#         try:
#             # Use numba-optimized functions for speed
#             indicators = {
#                 'sma_20': calculate_sma(prices, 20),
#                 'sma_50': calculate_sma(prices, 50),
#                 'ema_12': calculate_ema(prices, 12),
#                 'ema_26': calculate_ema(prices, 26),
#                 'rsi_14': calculate_rsi(prices, 14),
#             }

#             # Bollinger Bands
#             bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices, 20, 2.0)
#             indicators.update({
#                 'bb_upper': bb_upper,
#                 'bb_middle': bb_middle,
#                 'bb_lower': bb_lower
#             })

#             # MACD
#             if len(indicators['ema_12']) > 0 and len(indicators['ema_26']) > 0:
#                 macd_line = indicators['ema_12'] - indicators['ema_26']
#                 signal_line = calculate_ema(macd_line[~np.isnan(macd_line)], 9)

#                 # Pad signal line to match MACD length
#                 if len(signal_line) > 0:
#                     padded_signal = np.full_like(macd_line, np.nan)
#                     padded_signal[-len(signal_line):] = signal_line
#                     indicators['macd'] = macd_line
#                     indicators['macd_signal'] = padded_signal
#                     indicators['macd_histogram'] = macd_line - padded_signal

#             # Cache results
#             self.indicators_cache[cache_key] = indicators
#             self.indicators_timestamps[cache_key] = current_time

#             return indicators

#         except Exception as e:
#             logger.error(f"❌ Error calculating indicators for {instrument_key}: {e}")
#             return {}

#     def register_strategy_callback(self, strategy_name: str, instruments: List[str], callback: Callable):
#         """Register a high-speed callback for trading strategies"""
#         self.strategy_callbacks[strategy_name] = callback

#         # Mark instruments as hot for prioritized processing
#         for instrument in instruments:
#             self.hot_instruments.add(instrument)
#             self._mark_hot_instrument(instrument)

#         logger.info(f"✅ Registered high-speed callback for strategy: {strategy_name}")

#     def _mark_hot_instrument(self, instrument_key: str):
#         """Mark instrument as frequently accessed for optimization"""
#         self.access_counts[instrument_key] = self.access_counts.get(instrument_key, 0) + 1

#         # Auto-promote to hot if accessed frequently
#         if self.access_counts[instrument_key] > 10:
#             self.hot_instruments.add(instrument_key)

#     def get_performance_stats(self) -> Dict[str, Any]:
#         """Get performance statistics for monitoring"""
#         current_time = time.time()

#         # Performance report every 60 seconds
#         if current_time - self.last_performance_report > 60:
#             top_instruments = sorted(
#                 self.access_counts.items(),
#                 key=lambda x: x[1],
#                 reverse=True
#             )[:10]

#             logger.info(f"📊 Top 10 accessed instruments: {top_instruments}")
#             self.last_performance_report = current_time

#         return {
#             'total_instruments': len(self.tick_buffers),
#             'hot_instruments': len(self.hot_instruments),
#             'strategy_callbacks': len(self.strategy_callbacks),
#             'indicators_cached': len(self.indicators_cache),
#             'top_accessed': dict(sorted(
#                 self.access_counts.items(),
#                 key=lambda x: x[1],
#                 reverse=True
#             )[:5]),
#             'memory_usage_mb': sum(
#                 buffer.buffer.nbytes for buffer in self.tick_buffers.values()
#             ) / (1024 * 1024)
#         }

#     def cleanup_old_data(self):
#         """Cleanup old cached data to prevent memory leaks"""
#         current_time = time.time()

#         # Clean indicators cache
#         expired_keys = [
#             key for key, timestamp in self.indicators_timestamps.items()
#             if current_time - timestamp > self.indicator_cache_ttl * 10
#         ]

#         for key in expired_keys:
#             self.indicators_cache.pop(key, None)
#             self.indicators_timestamps.pop(key, None)

#         logger.debug(f"🧹 Cleaned {len(expired_keys)} expired indicator caches")

#     # === SELECTED STOCKS SPECIFIC METHODS ===

#     def update_selected_stocks(self, selected_stocks_data: List[Dict[str, Any]]):
#         """
#         Update the list of selected stocks for auto trading.

#         Args:
#             selected_stocks_data: List of dicts with stock selection data
#                 Each dict should have: symbol, instrument_key, option_type,
#                 atm_strike, expiry_date, etc.
#         """
#         try:
#             # Clear previous selections
#             self.selected_stocks.clear()
#             self.selected_stock_data.clear()
#             self.option_chains.clear()
#             self.auto_trading_instruments.clear()

#             for stock_data in selected_stocks_data:
#                 symbol = stock_data.get('symbol')
#                 instrument_key = stock_data.get('instrument_key')
#                 option_type = stock_data.get('option_type')

#                 if symbol and instrument_key:
#                     self.selected_stocks.add(symbol)
#                     self.selected_stock_data[symbol] = stock_data

#                     # Add underlying stock instrument
#                     self.auto_trading_instruments.add(instrument_key)

#                     # If option trading, add option instrument keys
#                     if option_type and stock_data.get('option_instrument_key'):
#                         option_key = stock_data.get('option_instrument_key')
#                         self.auto_trading_instruments.add(option_key)

#                         # Store option chain data
#                         if symbol not in self.option_chains:
#                             self.option_chains[symbol] = {}

#                         self.option_chains[symbol][option_type] = {
#                             'instrument_key': option_key,
#                             'strike': stock_data.get('atm_strike'),
#                             'expiry': stock_data.get('expiry_date'),
#                             'lot_size': stock_data.get('lot_size', 1)
#                         }

#                     # Mark as hot instrument for prioritized processing
#                     self.hot_instruments.add(instrument_key)
#                     if stock_data.get('option_instrument_key'):
#                         self.hot_instruments.add(stock_data['option_instrument_key'])

#             logger.info(f"✅ Updated {len(self.selected_stocks)} selected stocks for auto trading")
#             logger.info(f"📊 Monitoring {len(self.auto_trading_instruments)} instruments total")

#             # Update live adapter subscription
#             self._update_live_subscriptions()

#         except Exception as e:
#             logger.error(f"❌ Error updating selected stocks: {e}")

#     def _update_live_subscriptions(self):
#         """Update live feed subscriptions to focus on selected stocks"""
#         try:
#             from services.live_adapter import live_feed_adapter

#             # Update instruments list for live adapter
#             instruments_list = list(self.auto_trading_instruments)

#             if instruments_list:
#                 live_feed_adapter.register_tick_callback(
#                     name="selected_stocks_feed",
#                     instruments=instruments_list,
#                     callback=self._process_selected_stock_tick
#                 )

#                 logger.info(f"✅ Subscribed to live feed for {len(instruments_list)} selected instruments")

#         except Exception as e:
#             logger.warning(f"⚠️ Could not update live subscriptions: {e}")

#     def _process_selected_stock_tick(self, instrument_key: str, price_data: Dict[str, Any]):
#         """Special processing for selected stock ticks - highest priority"""
#         # Process with regular tick handler but with priority
#         self._process_tick_update(instrument_key, price_data)

#         # Additional processing for selected stocks
#         symbol = self._get_symbol_from_instrument_key(instrument_key)
#         if symbol and symbol in self.selected_stocks:
#             # Update enhanced data for selected stock
#             if symbol in self.selected_stock_data:
#                 self.selected_stock_data[symbol]['current_price'] = price_data.get('ltp', 0.0)
#                 self.selected_stock_data[symbol]['last_update'] = time.time()

#                 # Calculate P&L if option position exists
#                 self._calculate_selected_stock_pnl(symbol, price_data)

#     def _get_symbol_from_instrument_key(self, instrument_key: str) -> Optional[str]:
#         """Extract symbol from instrument key"""
#         try:
#             # Instrument keys are typically in format: NSE_EQ|INE123A01234-EQ
#             if '|' in instrument_key:
#                 parts = instrument_key.split('|')
#                 if len(parts) > 1:
#                     symbol_part = parts[1].split('-')[0]
#                     # Extract actual symbol (remove ISIN part if present)
#                     if len(symbol_part) > 12:  # ISIN length
#                         return symbol_part[12:]
#             return None
#         except Exception:
#             return None

#     def _calculate_selected_stock_pnl(self, symbol: str, price_data: Dict[str, Any]):
#         """Calculate P&L for selected stock positions"""
#         if symbol not in self.selected_stock_data:
#             return

#         stock_data = self.selected_stock_data[symbol]
#         current_price = price_data.get('ltp', 0.0)
#         entry_price = stock_data.get('price_at_selection', 0.0)

#         if entry_price > 0:
#             pnl_percent = ((current_price - entry_price) / entry_price) * 100
#             stock_data['current_pnl_percent'] = pnl_percent

#             # Check if it's an option position
#             option_type = stock_data.get('option_type')
#             if option_type:
#                 # For options, P&L calculation is different
#                 lot_size = stock_data.get('lot_size', 1)
#                 pnl_amount = (current_price - entry_price) * lot_size
#                 stock_data['current_pnl_amount'] = pnl_amount

#     def get_selected_stocks_data(self) -> Dict[str, Dict[str, Any]]:
#         """Get current data for all selected stocks"""
#         return self.selected_stock_data.copy()

#     def get_selected_stock_prices(self) -> Dict[str, float]:
#         """Get current prices for all selected stocks - ultra fast"""
#         result = {}
#         for symbol in self.selected_stocks:
#             if symbol in self.selected_stock_data:
#                 # Try to get from hot cache first
#                 instrument_key = self.selected_stock_data[symbol].get('instrument_key')
#                 if instrument_key:
#                     price = self.latest_prices.get(instrument_key)
#                     if price is not None:
#                         result[symbol] = price
#         return result

#     def get_selected_stock_indicators_batch(self) -> Dict[str, Dict[str, np.ndarray]]:
#         """Get indicators for all selected stocks in one batch operation"""
#         result = {}
#         for symbol in self.selected_stocks:
#             if symbol in self.selected_stock_data:
#                 instrument_key = self.selected_stock_data[symbol].get('instrument_key')
#                 if instrument_key:
#                     indicators = self.get_indicators_fast(instrument_key, 200)
#                     if indicators:
#                         result[symbol] = indicators
#         return result

#     def get_option_chain_prices(self, symbol: str) -> Dict[str, float]:
#         """Get current prices for option chain of a selected stock"""
#         if symbol not in self.option_chains:
#             return {}

#         result = {}
#         for option_type, option_data in self.option_chains[symbol].items():
#             instrument_key = option_data.get('instrument_key')
#             if instrument_key:
#                 price = self.latest_prices.get(instrument_key)
#                 if price is not None:
#                     result[option_type] = price

#         return result

#     def is_selected_stock(self, symbol: str) -> bool:
#         """Check if a stock is currently selected for auto trading"""
#         return symbol in self.selected_stocks

#     def get_auto_trading_summary(self) -> Dict[str, Any]:
#         """Get summary of auto trading data access performance"""
#         selected_prices = self.get_selected_stock_prices()

#         return {
#             'selected_stocks_count': len(self.selected_stocks),
#             'instruments_monitored': len(self.auto_trading_instruments),
#             'hot_instruments': len([inst for inst in self.auto_trading_instruments if inst in self.hot_instruments]),
#             'current_prices_available': len(selected_prices),
#             'option_chains_tracked': len(self.option_chains),
#             'selected_stocks': list(self.selected_stocks),
#             'data_freshness_seconds': min([
#                 time.time() - stock_data.get('last_update', time.time())
#                 for stock_data in self.selected_stock_data.values()
#                 if 'last_update' in stock_data
#             ]) if self.selected_stock_data else 0
#         }

# # Global singleton instance
# high_speed_market_data = HighSpeedMarketData()
