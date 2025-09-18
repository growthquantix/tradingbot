# """
# Live Feed Access Adapter - Single shared access point for live market data

# This adapter wraps the existing instrument_registry and centralized_ws_manager
# to provide a unified interface for strategies, backtester, and execution engine.
# It maintains backward compatibility while providing standardized access patterns.

# Key Features:
# - Real-time tick callbacks for strategies
# - Historical DataFrame generation (1m, 5m intervals)
# - Option contract monitoring
# - Fallback safety when underlying services are unavailable
# """

# import asyncio
# import logging
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# from typing import Dict, List, Optional, Callable, Any, Union
# from dataclasses import dataclass
# import pytz

# logger = logging.getLogger(__name__)

# # Define timezone for Indian markets
# IST = pytz.timezone('Asia/Kolkata')

# @dataclass
# class TickData:
#     """Standardized tick data structure"""
#     instrument_key: str
#     ltp: float
#     change: float
#     change_percent: float
#     volume: int
#     high: float
#     low: float
#     open: float
#     timestamp: datetime

# class LiveFeedAdapter:
#     """
#     Single shared access point for live market data.

#     Integrates with existing instrument_registry and centralized_ws_manager
#     while providing a clean, standardized interface for trading strategies.
#     """

#     def __init__(self):
#         self.callbacks = {}  # name -> {instruments: set, callback: callable}
#         self.option_callbacks = {}  # instrument_key -> list of callbacks
#         self.price_history = {}  # instrument_key -> list of ticks for DataFrame generation
#         self.is_initialized = False

#         # Try to connect to existing services
#         self._init_services()

#     def _init_services(self):
#         """Initialize connections to existing services with graceful fallbacks"""
#         try:
#             # Connect to instrument registry
#             from services.instrument_registry import instrument_registry
#             self.instrument_registry = instrument_registry

#             # Register ourselves as a callback subscriber
#             self._register_with_registry()
#             logger.info("✅ Connected to instrument registry")

#         except ImportError as e:
#             logger.warning(f"⚠️ Instrument registry not available: {e}")
#             self.instrument_registry = None

#         try:
#             # Connect to centralized WebSocket manager
#             from services.centralized_ws_manager import centralized_manager
#             self.centralized_manager = centralized_manager

#             # Register for DIRECT real-time data (zero-delay)
#             if hasattr(centralized_manager, 'register_direct_callback'):
#                 centralized_manager.register_direct_callback(self._handle_direct_market_data)
#                 logger.info("✅ Registered DIRECT callback with centralized WebSocket manager")
#             else:
#                 logger.warning("⚠️ Direct callback registration not available - using legacy method")

#             logger.info("✅ Connected to centralized WebSocket manager")

#         except ImportError as e:
#             logger.warning(f"⚠️ Centralized WebSocket manager not available: {e}")
#             self.centralized_manager = None

#         try:
#             # Connect to unified WebSocket manager for events
#             from services.unified_websocket_manager import unified_manager
#             self.unified_manager = unified_manager
#             logger.info("✅ Connected to unified WebSocket manager")

#         except ImportError as e:
#             logger.warning(f"⚠️ Unified WebSocket manager not available: {e}")
#             self.unified_manager = None

#         self.is_initialized = True

#     def _register_with_registry(self):
#         """Register as a callback subscriber with the instrument registry"""
#         if not self.instrument_registry:
#             logger.warning("⚠️ Instrument registry not available for callback registration")
#             return

#         # Register our callback to receive all price updates
#         try:
#             # Check if the registry has the callback system
#             if hasattr(self.instrument_registry, '_instrument_subscribers'):
#                 # Register a generic callback that handles all updates
#                 self.registry_callback_id = f"live_adapter_{id(self)}"

#                 # This callback will be called for every price update
#                 def price_update_handler(instrument_key: str, price_data: Dict[str, Any]):
#                     try:
#                         self._handle_price_update(instrument_key, price_data)
#                     except Exception as e:
#                         logger.error(f"❌ Error in price update handler: {e}")

#                 # Store the handler for potential cleanup
#                 self._price_update_handler = price_update_handler

#                 logger.info("✅ Registered callback with instrument registry")
#             else:
#                 logger.warning("⚠️ Instrument registry doesn't support callback system")

#         except Exception as e:
#             logger.error(f"❌ Failed to register with instrument registry: {e}")

#     def _handle_price_update(self, instrument_key: str, price_data: Dict[str, Any]):
#         """Handle price updates from the registry and distribute to callbacks"""
#         try:
#             # Convert to standardized tick data
#             tick = self._convert_to_tick_data(instrument_key, price_data)

#             # Store for historical DataFrame generation
#             self._store_tick_for_history(tick)

#             # Distribute to registered callbacks
#             self._distribute_to_callbacks(tick)

#         except Exception as e:
#             logger.error(f"❌ Error handling price update for {instrument_key}: {e}")

#     def _convert_to_tick_data(self, instrument_key: str, price_data: Dict[str, Any]) -> TickData:
#         """Convert registry price data to standardized TickData"""
#         return TickData(
#             instrument_key=instrument_key,
#             ltp=price_data.get('ltp', 0.0),
#             change=price_data.get('change', 0.0),
#             change_percent=price_data.get('change_percent', 0.0),
#             volume=price_data.get('volume', 0),
#             high=price_data.get('high', 0.0),
#             low=price_data.get('low', 0.0),
#             open=price_data.get('open', 0.0),
#             timestamp=datetime.now(IST)
#         )

#     def _store_tick_for_history(self, tick: TickData):
#         """Store tick data for historical DataFrame generation"""
#         if tick.instrument_key not in self.price_history:
#             self.price_history[tick.instrument_key] = []

#         # Keep last 500 ticks (approximately 8+ hours of 1-minute data)
#         history = self.price_history[tick.instrument_key]
#         history.append(tick)

#         # Trim to prevent memory issues
#         if len(history) > 500:
#             self.price_history[tick.instrument_key] = history[-500:]

#     def _distribute_to_callbacks(self, tick: TickData):
#         """Distribute tick data to registered callbacks"""
#         for name, callback_info in self.callbacks.items():
#             try:
#                 if tick.instrument_key in callback_info['instruments']:
#                     # Call the strategy callback
#                     callback = callback_info['callback']
#                     callback(tick.instrument_key, {
#                         'ltp': tick.ltp,
#                         'change': tick.change,
#                         'change_percent': tick.change_percent,
#                         'volume': tick.volume,
#                         'timestamp': tick.timestamp.isoformat()
#                     })
#             except Exception as e:
#                 logger.error(f"❌ Error in callback {name}: {e}")

#     def _handle_direct_market_data(self, data: Dict[str, Any]):
#         """
#         🚀 ZERO-DELAY: Handle market data directly from centralized manager.
#         This receives raw data IMMEDIATELY without any background processing delays.

#         Args:
#             data: Raw market data from WebSocket (feeds format)
#         """
#         try:
#             # Extract feeds directly from WebSocket data
#             feeds = data.get('feeds', {}) if 'feeds' in data else data.get('data', {})

#             if not feeds:
#                 # Handle direct instrument format (key-value pairs)
#                 feeds = {k: v for k, v in data.items() if isinstance(v, dict) and '|' in k}

#             if not feeds:
#                 return  # No market data to process

#             timestamp = datetime.now(IST).isoformat()

#             logger.debug(f"🚀 DIRECT market data: {len(feeds)} instruments (ZERO-DELAY)")

#             # Process each instrument IMMEDIATELY
#             for instrument_key, price_info in feeds.items():
#                 try:
#                     # Convert to standardized format (optimized for speed)
#                     tick_data = TickData(
#                         instrument_key=instrument_key,
#                         ltp=float(price_info.get('ltp', price_info.get('c', 0.0))),
#                         open_price=float(price_info.get('open', price_info.get('o', 0.0))),
#                         high_price=float(price_info.get('high', price_info.get('h', 0.0))),
#                         low_price=float(price_info.get('low', price_info.get('l', 0.0))),
#                         close_price=float(price_info.get('close', price_info.get('c', 0.0))),
#                         volume=int(price_info.get('volume', price_info.get('v', 0))),
#                         timestamp=timestamp,
#                         change=float(price_info.get('change', price_info.get('chg', 0.0))),
#                         change_percent=float(price_info.get('change_percent', price_info.get('chgp', 0.0)))
#                     )

#                     # IMMEDIATE distribution to auto-trading services
#                     self._distribute_to_callbacks(tick_data)

#                     # Store for history (non-blocking)
#                     self._store_tick_for_history(tick_data)

#                 except Exception as tick_error:
#                     logger.debug(f"Error processing tick for {instrument_key}: {tick_error}")

#         except Exception as e:
#             logger.error(f"❌ Error handling DIRECT market data: {e}")

#     def register_tick_callback(self, name: str, instruments: List[str], callback: Callable[[str, Dict], None]):
#         """
#         Register a callback function for specific instruments.

#         Args:
#             name: Unique name for this callback registration
#             instruments: List of instrument keys to monitor
#             callback: Function called with (instrument_key, price_data) for each tick
#         """
#         self.callbacks[name] = {
#             'instruments': set(instruments),
#             'callback': callback
#         }

#         logger.info(f"✅ Registered callback '{name}' for {len(instruments)} instruments")

#         # If we have existing data, immediately call callback for current prices
#         self._send_initial_data_to_callback(name, instruments, callback)

#     def _send_initial_data_to_callback(self, name: str, instruments: List[str], callback: Callable):
#         """Send current prices to newly registered callback"""
#         if not self.instrument_registry:
#             return

#         try:
#             for instrument_key in instruments:
#                 # Try to get latest price from registry
#                 if hasattr(self.instrument_registry, '_live_prices'):
#                     live_prices = self.instrument_registry._live_prices
#                     if instrument_key in live_prices:
#                         price_data = live_prices[instrument_key]
#                         callback(instrument_key, {
#                             'ltp': price_data.get('ltp', 0.0),
#                             'change': price_data.get('change', 0.0),
#                             'change_percent': price_data.get('change_percent', 0.0),
#                             'volume': price_data.get('volume', 0),
#                             'timestamp': datetime.now(IST).isoformat()
#                         })
#         except Exception as e:
#             logger.debug(f"Could not send initial data to {name}: {e}")

#     def get_latest_price(self, instrument_key: str) -> Optional[Dict[str, Any]]:
#         """
#         Get the latest price for an instrument with multiple fallback options.

#         Returns:
#             Dict with ltp, change, volume, timestamp or None if not available
#         """
#         try:
#             # Method 1: Try stored price history first (fastest for active instruments)
#             if instrument_key in self.price_history and self.price_history[instrument_key]:
#                 latest_tick = self.price_history[instrument_key][-1]
#                 return {
#                     'ltp': latest_tick.ltp,
#                     'change': latest_tick.change,
#                     'change_percent': latest_tick.change_percent,
#                     'volume': latest_tick.volume,
#                     'timestamp': latest_tick.timestamp.isoformat()
#                 }

#             # Method 2: Try instrument registry
#             if self.instrument_registry:
#                 try:
#                     # Try direct registry access
#                     if hasattr(self.instrument_registry, 'get_spot_price'):
#                         symbol = instrument_key.split('|')[-1] if '|' in instrument_key else instrument_key
#                         price_data = self.instrument_registry.get_spot_price(symbol)

#                         if price_data:
#                             return {
#                                 'ltp': price_data.get('last_price', 0.0),
#                                 'change': price_data.get('change', 0.0),
#                                 'change_percent': price_data.get('change_percent', 0.0),
#                                 'volume': price_data.get('volume', 0),
#                                 'timestamp': datetime.now(IST).isoformat()
#                             }

#                     # Fallback to direct live prices access
#                     if hasattr(self.instrument_registry, '_live_prices'):
#                         live_prices = self.instrument_registry._live_prices
#                         if instrument_key in live_prices:
#                             price_data = live_prices[instrument_key]
#                             return {
#                                 'ltp': price_data.get('ltp', 0.0),
#                                 'change': price_data.get('change', 0.0),
#                                 'change_percent': price_data.get('change_percent', 0.0),
#                                 'volume': price_data.get('volume', 0),
#                                 'timestamp': datetime.now(IST).isoformat()
#                             }

#                 except Exception as e:
#                     logger.debug(f"Error accessing instrument registry for {instrument_key}: {e}")

#             # Method 3: Try centralized WebSocket manager
#             try:
#                 if self.centralized_manager and hasattr(self.centralized_manager, '_live_prices'):
#                     live_prices = self.centralized_manager._live_prices
#                     if instrument_key in live_prices:
#                         price_data = live_prices[instrument_key]
#                         return {
#                             'ltp': price_data.get('ltp', 0.0),
#                             'change': price_data.get('change', 0.0),
#                             'change_percent': price_data.get('change_percent', 0.0),
#                             'volume': price_data.get('volume', 0),
#                             'timestamp': datetime.now(IST).isoformat()
#                         }
#             except Exception as e:
#                 logger.debug(f"Error accessing centralized manager for {instrument_key}: {e}")

#             logger.debug(f"⚠️ No price data available for {instrument_key}")
#             return None

#         except Exception as e:
#             logger.error(f"❌ Error getting latest price for {instrument_key}: {e}")
#             return None

#     def get_1m_df(self, instrument_key: str, window_minutes: int = 120) -> pd.DataFrame:
#         """
#         Generate 1-minute OHLCV DataFrame from stored tick data.

#         Args:
#             instrument_key: Instrument to get data for
#             window_minutes: Number of minutes of data to return

#         Returns:
#             DataFrame with columns [timestamp, open, high, low, close, volume]
#         """
#         if instrument_key not in self.price_history:
#             logger.warning(f"⚠️ No price history for {instrument_key}")
#             return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#         try:
#             ticks = self.price_history[instrument_key]

#             # Convert to DataFrame
#             data = []
#             for tick in ticks:
#                 data.append({
#                     'timestamp': tick.timestamp,
#                     'price': tick.ltp,
#                     'volume': tick.volume
#                 })

#             if not data:
#                 return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#             df = pd.DataFrame(data)
#             df['timestamp'] = pd.to_datetime(df['timestamp'])
#             df.set_index('timestamp', inplace=True)

#             # Resample to 1-minute OHLCV
#             ohlcv = df.resample('1T').agg({
#                 'price': ['first', 'max', 'min', 'last'],
#                 'volume': 'sum'
#             }).dropna()

#             # Flatten column names
#             ohlcv.columns = ['open', 'high', 'low', 'close', 'volume']
#             ohlcv.reset_index(inplace=True)

#             # Apply window limit
#             if window_minutes > 0 and len(ohlcv) > window_minutes:
#                 ohlcv = ohlcv.tail(window_minutes)

#             return ohlcv

#         except Exception as e:
#             logger.error(f"❌ Error generating 1m DataFrame for {instrument_key}: {e}")
#             return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#     def get_5m_df(self, instrument_key: str, window_minutes: int = 300) -> pd.DataFrame:
#         """
#         Generate 5-minute OHLCV DataFrame by resampling 1-minute data.

#         Args:
#             instrument_key: Instrument to get data for
#             window_minutes: Number of minutes of data (in 5m intervals)

#         Returns:
#             DataFrame with columns [timestamp, open, high, low, close, volume]
#         """
#         try:
#             # Get 1-minute data (need more data to generate proper 5m bars)
#             df_1m = self.get_1m_df(instrument_key, window_minutes * 5)  # Get 5x more 1m data

#             if df_1m.empty:
#                 return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#             # Set timestamp as index for resampling
#             df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
#             df_1m.set_index('timestamp', inplace=True)

#             # Resample to 5-minute OHLCV
#             df_5m = df_1m.resample('5T').agg({
#                 'open': 'first',
#                 'high': 'max',
#                 'low': 'min',
#                 'close': 'last',
#                 'volume': 'sum'
#             }).dropna()

#             df_5m.reset_index(inplace=True)

#             # Apply window limit (convert minutes to 5-minute bars)
#             window_bars = window_minutes // 5
#             if window_bars > 0 and len(df_5m) > window_bars:
#                 df_5m = df_5m.tail(window_bars)

#             return df_5m

#         except Exception as e:
#             logger.error(f"❌ Error generating 5m DataFrame for {instrument_key}: {e}")
#             return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#     def subscribe_option_ticks(self, instrument_key: str, callback: Callable[[str, Dict], None]):
#         """
#         Subscribe to option contract tick updates.

#         Args:
#             instrument_key: Option contract instrument key
#             callback: Function called with (instrument_key, price_data) for each tick
#         """
#         if instrument_key not in self.option_callbacks:
#             self.option_callbacks[instrument_key] = []

#         self.option_callbacks[instrument_key].append(callback)

#         # Also register with main callback system
#         callback_name = f"option_{instrument_key}_{len(self.option_callbacks[instrument_key])}"
#         self.register_tick_callback(callback_name, [instrument_key], callback)

#         logger.info(f"✅ Subscribed to option ticks for {instrument_key}")

#     def unregister_callback(self, name: str):
#         """Unregister a previously registered callback"""
#         if name in self.callbacks:
#             del self.callbacks[name]
#             logger.info(f"✅ Unregistered callback '{name}'")

#     def get_registered_instruments(self) -> List[str]:
#         """Get list of all instruments being monitored by registered callbacks"""
#         all_instruments = set()
#         for callback_info in self.callbacks.values():
#             all_instruments.update(callback_info['instruments'])
#         return list(all_instruments)

#     def get_callback_stats(self) -> Dict[str, Any]:
#         """Get statistics about registered callbacks"""
#         return {
#             'total_callbacks': len(self.callbacks),
#             'total_instruments': len(self.get_registered_instruments()),
#             'option_subscriptions': len(self.option_callbacks),
#             'price_history_instruments': len(self.price_history),
#             'services_available': {
#                 'instrument_registry': self.instrument_registry is not None,
#                 'centralized_manager': self.centralized_manager is not None,
#                 'unified_manager': self.unified_manager is not None
#             }
#         }

#     def register_fibonacci_strategy_callback(self, strategy_name: str, instruments: List[str],
#                                            callback: Callable[[str, Dict], None],
#                                            priority_level: int = 1) -> bool:
#         """
#         Register a Fibonacci strategy callback with priority processing.

#         Args:
#             strategy_name: Unique name for the Fibonacci strategy
#             instruments: List of F&O instrument keys to monitor
#             callback: Function called with (instrument_key, enhanced_data) for each tick
#             priority_level: 1=highest (sub-5ms), 2=normal (sub-10ms), 3=low priority

#         Returns:
#             bool: True if registered successfully, False otherwise
#         """
#         try:
#             # Validate F&O instruments
#             validated_instruments = []
#             for instrument_key in instruments:
#                 if self.validate_fno_stock(instrument_key):
#                     validated_instruments.append(instrument_key)
#                 else:
#                     logger.warning(f"⚠️ {instrument_key} is not a valid F&O stock, skipping")

#             if not validated_instruments:
#                 logger.error(f"❌ No valid F&O instruments for strategy {strategy_name}")
#                 return False

#             # Register with enhanced callback wrapper
#             def fibonacci_enhanced_callback(instrument_key: str, price_data: Dict):
#                 try:
#                     # Enhance data with Fibonacci-specific information
#                     enhanced_data = self._enhance_data_for_fibonacci(instrument_key, price_data)

#                     # Call the original callback
#                     callback(instrument_key, enhanced_data)

#                 except Exception as e:
#                     logger.error(f"❌ Error in Fibonacci callback for {instrument_key}: {e}")

#             # Store with priority information
#             callback_id = f"fib_{strategy_name}_{priority_level}"
#             self.callbacks[callback_id] = {
#                 'instruments': set(validated_instruments),
#                 'callback': fibonacci_enhanced_callback,
#                 'strategy_type': 'fibonacci',
#                 'priority_level': priority_level,
#                 'created_at': datetime.now(IST)
#             }

#             # Register with centralized manager for priority processing if available
#             if self.centralized_manager and hasattr(self.centralized_manager, 'priority_subscription'):
#                 self.centralized_manager.priority_subscription([
#                     {'instrument_key': key, 'priority': priority_level}
#                     for key in validated_instruments
#                 ])

#             logger.info(f"✅ Registered Fibonacci strategy '{strategy_name}' for {len(validated_instruments)} instruments with priority {priority_level}")
#             return True

#         except Exception as e:
#             logger.error(f"❌ Failed to register Fibonacci strategy callback: {e}")
#             return False

#     def _enhance_data_for_fibonacci(self, instrument_key: str, price_data: Dict) -> Dict:
#         """Enhance price data with Fibonacci strategy specific information"""
#         try:
#             enhanced_data = price_data.copy()

#             # Get recent OHLC data for Fibonacci calculations
#             ohlc_1m = self.get_real_time_ohlc(instrument_key, minutes=60)  # Last 60 minutes

#             if not ohlc_1m.empty and len(ohlc_1m) >= 5:
#                 # Calculate recent high and low for Fibonacci levels
#                 recent_high = ohlc_1m['high'].max()
#                 recent_low = ohlc_1m['low'].min()
#                 current_price = price_data.get('ltp', 0.0)

#                 # Calculate Fibonacci retracement levels
#                 fib_diff = recent_high - recent_low
#                 fibonacci_levels = {
#                     'high': recent_high,
#                     'low': recent_low,
#                     'fib_23_6': recent_high - (fib_diff * 0.236),
#                     'fib_38_2': recent_high - (fib_diff * 0.382),
#                     'fib_50_0': recent_high - (fib_diff * 0.500),
#                     'fib_61_8': recent_high - (fib_diff * 0.618),
#                     'fib_78_6': recent_high - (fib_diff * 0.786)
#                 }

#                 # Calculate EMA values (9, 21, 50)
#                 ema_values = self._calculate_emas(ohlc_1m)

#                 # Add to enhanced data
#                 enhanced_data.update({
#                     'fibonacci_levels': fibonacci_levels,
#                     'ema_values': ema_values,
#                     'market_structure': self._determine_market_structure(current_price, fibonacci_levels, ema_values),
#                     'signal_strength': self._calculate_signal_strength(current_price, fibonacci_levels, ema_values),
#                     'processing_timestamp': datetime.now(IST).isoformat()
#                 })

#             return enhanced_data

#         except Exception as e:
#             logger.error(f"❌ Error enhancing data for {instrument_key}: {e}")
#             return price_data

#     def _calculate_emas(self, df: pd.DataFrame) -> Dict[str, float]:
#         """Calculate EMA 9, 21, 50 from OHLC data"""
#         try:
#             if df.empty or len(df) < 2:
#                 return {'ema_9': 0.0, 'ema_21': 0.0, 'ema_50': 0.0}

#             close_prices = df['close']

#             return {
#                 'ema_9': close_prices.ewm(span=9).mean().iloc[-1] if len(close_prices) >= 9 else close_prices.mean(),
#                 'ema_21': close_prices.ewm(span=21).mean().iloc[-1] if len(close_prices) >= 21 else close_prices.mean(),
#                 'ema_50': close_prices.ewm(span=50).mean().iloc[-1] if len(close_prices) >= 50 else close_prices.mean()
#             }

#         except Exception as e:
#             logger.error(f"❌ Error calculating EMAs: {e}")
#             return {'ema_9': 0.0, 'ema_21': 0.0, 'ema_50': 0.0}

#     def _determine_market_structure(self, current_price: float, fib_levels: Dict, ema_values: Dict) -> str:
#         """Determine market structure: bullish, bearish, or sideways"""
#         try:
#             if current_price > ema_values['ema_9'] > ema_values['ema_21'] > ema_values['ema_50']:
#                 return "strong_bullish"
#             elif current_price < ema_values['ema_9'] < ema_values['ema_21'] < ema_values['ema_50']:
#                 return "strong_bearish"
#             elif current_price > ema_values['ema_21']:
#                 return "bullish"
#             elif current_price < ema_values['ema_21']:
#                 return "bearish"
#             else:
#                 return "sideways"

#         except Exception:
#             return "unknown"

#     def _calculate_signal_strength(self, current_price: float, fib_levels: Dict, ema_values: Dict) -> float:
#         """Calculate signal strength (0.0 to 1.0) based on Fibonacci and EMA alignment"""
#         try:
#             strength = 0.0

#             # EMA alignment strength (0.3 max)
#             ema_9, ema_21, ema_50 = ema_values['ema_9'], ema_values['ema_21'], ema_values['ema_50']
#             if ema_9 > ema_21 > ema_50 or ema_9 < ema_21 < ema_50:
#                 strength += 0.3
#             elif ema_9 > ema_50 or ema_9 < ema_50:
#                 strength += 0.15

#             # Fibonacci level proximity (0.4 max)
#             fib_50 = fib_levels.get('fib_50_0', current_price)
#             fib_618 = fib_levels.get('fib_61_8', current_price)

#             if abs(current_price - fib_618) / current_price < 0.001:  # Within 0.1%
#                 strength += 0.4
#             elif abs(current_price - fib_50) / current_price < 0.001:
#                 strength += 0.3
#             elif abs(current_price - fib_levels.get('fib_38_2', current_price)) / current_price < 0.001:
#                 strength += 0.2

#             # Volume and momentum (0.3 max) - simplified for now
#             strength += 0.2  # Base momentum score

#             return min(strength, 1.0)

#         except Exception:
#             return 0.0

#     def get_real_time_ohlc(self, instrument_key: str, minutes: int = 60) -> pd.DataFrame:
#         """
#         Get real-time OHLC data for Fibonacci calculations with sub-second updates.

#         Args:
#             instrument_key: Instrument to get data for
#             minutes: Number of minutes of 1-minute bars to return

#         Returns:
#             DataFrame with real-time OHLC data optimized for Fibonacci calculations
#         """
#         try:
#             # Get 1-minute OHLC data
#             df_1m = self.get_1m_df(instrument_key, minutes)

#             if df_1m.empty:
#                 return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#             # Add current tick as latest bar if we have recent tick data
#             if instrument_key in self.price_history:
#                 latest_ticks = self.price_history[instrument_key][-10:]  # Last 10 ticks
#                 if latest_ticks:
#                     current_minute = datetime.now(IST).replace(second=0, microsecond=0)

#                     # Check if we need to create/update current minute bar
#                     if df_1m.empty or df_1m.iloc[-1]['timestamp'] < current_minute:
#                         # Create new current minute bar from recent ticks
#                         current_prices = [tick.ltp for tick in latest_ticks if tick.timestamp >= current_minute]
#                         if current_prices:
#                             current_bar = {
#                                 'timestamp': current_minute,
#                                 'open': current_prices[0],
#                                 'high': max(current_prices),
#                                 'low': min(current_prices),
#                                 'close': current_prices[-1],
#                                 'volume': sum(tick.volume for tick in latest_ticks if tick.timestamp >= current_minute)
#                             }
#                             df_1m = pd.concat([df_1m, pd.DataFrame([current_bar])], ignore_index=True)
#                     else:
#                         # Update existing current minute bar
#                         current_prices = [tick.ltp for tick in latest_ticks if tick.timestamp >= current_minute]
#                         if current_prices:
#                             df_1m.loc[df_1m.index[-1], 'high'] = max(df_1m.iloc[-1]['high'], max(current_prices))
#                             df_1m.loc[df_1m.index[-1], 'low'] = min(df_1m.iloc[-1]['low'], min(current_prices))
#                             df_1m.loc[df_1m.index[-1], 'close'] = current_prices[-1]

#             return df_1m.tail(minutes) if len(df_1m) > minutes else df_1m

#         except Exception as e:
#             logger.error(f"❌ Error getting real-time OHLC for {instrument_key}: {e}")
#             return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

#     def get_option_greeks_live(self, option_instrument_key: str) -> Optional[Dict[str, float]]:
#         """
#         Get live option Greeks (Delta, Gamma, Theta, Vega) for F&O options.

#         Args:
#             option_instrument_key: Option contract instrument key

#         Returns:
#             Dict with Greeks values or None if not available
#         """
#         try:
#             # Try to get Greeks from centralized manager first
#             if self.centralized_manager and hasattr(self.centralized_manager, 'get_option_greeks'):
#                 greeks = self.centralized_manager.get_option_greeks(option_instrument_key)
#                 if greeks:
#                     return greeks

#             # Try unified manager
#             if self.unified_manager and hasattr(self.unified_manager, 'get_option_data'):
#                 option_data = self.unified_manager.get_option_data(option_instrument_key)
#                 if option_data and 'greeks' in option_data:
#                     return option_data['greeks']

#             # Fallback: Try to get from latest price data
#             price_data = self.get_latest_price(option_instrument_key)
#             if price_data and 'greeks' in price_data:
#                 return price_data['greeks']

#             logger.debug(f"No Greeks data available for {option_instrument_key}")
#             return None

#         except Exception as e:
#             logger.error(f"❌ Error getting option Greeks for {option_instrument_key}: {e}")
#             return None

#     def validate_fno_stock(self, instrument_key: str) -> bool:
#         """
#         Validate if instrument is a valid F&O stock from the 5 supported indices.

#         Args:
#             instrument_key: Instrument key to validate

#         Returns:
#             bool: True if valid F&O stock, False otherwise
#         """
#         try:
#             # FIXED: For auto-trading to work, accept all instruments during stock selection
#             # This allows the system to register callbacks for selected stocks

#             # F&O indices we support
#             fno_indices = {'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX'}

#             # Accept NSE_FO (F&O instruments)
#             if instrument_key.startswith('NSE_FO|'):
#                 return True

#             # Accept NSE_INDEX (index instruments)
#             if instrument_key.startswith('NSE_INDEX|'):
#                 return True

#             # FIXED: Accept equity instruments for options trading - MOVED UP BEFORE F&O CHECK
#             if instrument_key.startswith(('NSE_EQ|', 'BSE_EQ|')):
#                 return True

#             # Parse instrument key to get symbol
#             if '|' in instrument_key:
#                 parts = instrument_key.split('|')
#                 symbol = parts[-1] if parts else instrument_key
#             else:
#                 symbol = instrument_key

#             # Check if it's an index future/option
#             for index_name in fno_indices:
#                 if index_name in symbol.upper():
#                     return True

#             # Check if it's a stock from F&O list (centralized manager has this info)
#             # Only use this as additional validation, not as exclusion criteria
#             if self.centralized_manager and hasattr(self.centralized_manager, 'fno_stocks_keys'):
#                 if instrument_key in self.centralized_manager.fno_stocks_keys:
#                     return True

#             # Basic validation for F&O format
#             symbol_upper = symbol.upper()

#             # Check for common F&O stock patterns
#             fno_indicators = ['FUT', 'CE', 'PE', 'CALL', 'PUT']
#             if any(indicator in symbol_upper for indicator in fno_indicators):
#                 return True

#             # If we can't determine, assume valid for now (better to include than exclude)
#             logger.debug(f"Cannot determine F&O status for {instrument_key}, assuming valid")
#             return True

#         except Exception as e:
#             logger.error(f"❌ Error validating F&O stock {instrument_key}: {e}")
#             return False

#     def get_fibonacci_analysis_summary(self, instrument_key: str) -> Dict[str, Any]:
#         """
#         Get comprehensive Fibonacci analysis summary for an instrument.

#         Args:
#             instrument_key: Instrument to analyze

#         Returns:
#             Dict with comprehensive Fibonacci analysis
#         """
#         try:
#             # Get latest price and OHLC data
#             latest_price = self.get_latest_price(instrument_key)
#             ohlc_data = self.get_real_time_ohlc(instrument_key, minutes=120)  # 2 hours of data

#             if not latest_price or ohlc_data.empty:
#                 return {'error': 'Insufficient data for analysis'}

#             current_ltp = latest_price['ltp']

#             # Calculate Fibonacci levels from recent swing high/low
#             recent_high = ohlc_data['high'].max()
#             recent_low = ohlc_data['low'].min()
#             fib_diff = recent_high - recent_low

#             fibonacci_levels = {
#                 'high': recent_high,
#                 'low': recent_low,
#                 'fib_0': recent_high,
#                 'fib_23_6': recent_high - (fib_diff * 0.236),
#                 'fib_38_2': recent_high - (fib_diff * 0.382),
#                 'fib_50_0': recent_high - (fib_diff * 0.500),
#                 'fib_61_8': recent_high - (fib_diff * 0.618),
#                 'fib_78_6': recent_high - (fib_diff * 0.786),
#                 'fib_100': recent_low
#             }

#             # Calculate EMAs
#             ema_values = self._calculate_emas(ohlc_data)

#             # Determine current position relative to Fibonacci levels
#             fib_position = "unknown"
#             nearest_fib_level = None
#             nearest_fib_distance = float('inf')

#             for level_name, level_value in fibonacci_levels.items():
#                 if level_name not in ['high', 'low']:
#                     distance = abs(current_ltp - level_value)
#                     if distance < nearest_fib_distance:
#                         nearest_fib_distance = distance
#                         nearest_fib_level = {
#                             'name': level_name,
#                             'value': level_value,
#                             'distance_percent': (distance / current_ltp) * 100
#                         }

#             # Market structure analysis
#             market_structure = self._determine_market_structure(current_ltp, fibonacci_levels, ema_values)
#             signal_strength = self._calculate_signal_strength(current_ltp, fibonacci_levels, ema_values)

#             # Generate trading signals
#             signals = []
#             if nearest_fib_level and nearest_fib_level['distance_percent'] < 0.1:  # Within 0.1%
#                 if nearest_fib_level['name'] in ['fib_38_2', 'fib_50_0', 'fib_61_8']:
#                     if market_structure in ['bullish', 'strong_bullish']:
#                         signals.append({
#                             'type': 'BUY',
#                             'reason': f'Price near {nearest_fib_level["name"]} support in bullish trend',
#                             'confidence': signal_strength
#                         })
#                     elif market_structure in ['bearish', 'strong_bearish']:
#                         signals.append({
#                             'type': 'SELL',
#                             'reason': f'Price near {nearest_fib_level["name"]} resistance in bearish trend',
#                             'confidence': signal_strength
#                         })

#             return {
#                 'instrument_key': instrument_key,
#                 'current_price': current_ltp,
#                 'fibonacci_levels': fibonacci_levels,
#                 'ema_values': ema_values,
#                 'market_structure': market_structure,
#                 'signal_strength': signal_strength,
#                 'nearest_fibonacci_level': nearest_fib_level,
#                 'trading_signals': signals,
#                 'analysis_timestamp': datetime.now(IST).isoformat(),
#                 'data_points_used': len(ohlc_data)
#             }

#         except Exception as e:
#             logger.error(f"❌ Error generating Fibonacci analysis for {instrument_key}: {e}")
#             return {'error': str(e)}


# Temporary placeholder to fix import issues
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class TickData:
    """Standardized tick data structure"""
    instrument_key: str
    ltp: float
    change: float
    change_percent: float
    volume: int
    high: float
    low: float
    open: float
    timestamp: datetime

class LiveFeedAdapter:
    """Placeholder live feed adapter"""
    def __init__(self):
        pass
    
    def get_live_price(self, instrument_key: str) -> Optional[float]:
        """Placeholder method"""
        return None

# Global instance
live_feed_adapter = LiveFeedAdapter()

# Export alias for backward compatibility
live_adapter = live_feed_adapter
