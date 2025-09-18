"""
Auto Trading Data Service - High-Speed Real-Time Processing for Fibonacci + EMA Strategy

This service handles ultra-fast data processing for HFT-grade auto-trading with:
- Sub-millisecond tick processing using NumPy optimizations
- Real-time Fibonacci retracement calculations 
- EMA calculations with optimized rolling windows
- F&O stocks priority queue processing
- Memory-efficient circular buffers
- Database logging with async operations
- Emergency circuit breaker patterns

Key Performance Targets:
- Tick processing: < 2ms
- Fibonacci calculations: < 3ms
- Database logging: < 5ms (async)
- Total signal generation: < 10ms
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from dataclasses import dataclass
from collections import deque
import pytz
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Import services
from services.live_adapter import live_feed_adapter, TickData
from services.database.trading_db_service import TradingDatabaseService
from services.centralized_ws_manager import centralized_manager

logger = logging.getLogger(__name__)
IST = pytz.timezone('Asia/Kolkata')

@dataclass
class FibonacciSignal:
    """Standardized Fibonacci trading signal"""
    instrument_key: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    signal_strength: float  # 0.0 to 1.0
    entry_price: float
    fibonacci_level: str  # e.g., 'fib_61_8'
    fibonacci_value: float
    ema_alignment: str  # 'bullish', 'bearish', 'sideways'
    stop_loss: float
    target_1: float
    target_2: float
    confidence_score: float
    processing_time_ms: float
    timestamp: datetime
    market_structure: str
    option_type: str  # 'CE' or 'PE' for options trading

@dataclass
class ProcessingMetrics:
    """Performance metrics for HFT monitoring"""
    total_ticks_processed: int = 0
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    signals_generated: int = 0
    fibonacci_calculations: int = 0
    database_writes: int = 0
    errors_count: int = 0
    circuit_breaker_triggers: int = 0

class CircularBuffer:
    """Memory-efficient circular buffer for tick data storage"""
    
    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self.data = np.zeros((maxsize, 6))  # [timestamp, open, high, low, close, volume]
        self.current_idx = 0
        self.is_full = False
        self.lock = threading.Lock()
    
    def add(self, tick_data: Tuple[float, float, float, float, float, float]):
        """Add tick data: (timestamp, open, high, low, close, volume)"""
        with self.lock:
            self.data[self.current_idx] = tick_data
            self.current_idx = (self.current_idx + 1) % self.maxsize
            if self.current_idx == 0:
                self.is_full = True
    
    def get_recent_data(self, n_points: int = 100) -> np.ndarray:
        """Get recent n data points as NumPy array"""
        with self.lock:
            if not self.is_full:
                return self.data[:self.current_idx][-n_points:]
            else:
                # Handle circular buffer wraparound
                if n_points >= self.maxsize:
                    if self.current_idx == 0:
                        return self.data
                    else:
                        return np.concatenate([
                            self.data[self.current_idx:],
                            self.data[:self.current_idx]
                        ])
                else:
                    end_idx = self.current_idx
                    start_idx = (end_idx - n_points) % self.maxsize
                    
                    if start_idx < end_idx:
                        return self.data[start_idx:end_idx]
                    else:
                        return np.concatenate([
                            self.data[start_idx:],
                            self.data[:end_idx]
                        ])
    
    def get_size(self) -> int:
        """Get current buffer size"""
        return self.maxsize if self.is_full else self.current_idx

class AutoTradingDataService:
    """
    High-Speed Real-Time Data Processing Service for Auto-Trading
    
    Handles ultra-fast processing of market data for Fibonacci + EMA strategy
    with HFT-grade performance requirements.
    """
    
    def __init__(self, max_instruments: int = 200):
        self.max_instruments = max_instruments
        self.is_running = False
        self.processing_metrics = ProcessingMetrics()
        
        # Data storage: instrument_key -> CircularBuffer
        self.tick_buffers: Dict[str, CircularBuffer] = {}
        
        # Fibonacci calculation caches (for performance)
        self.fib_cache: Dict[str, Dict] = {}
        self.ema_cache: Dict[str, np.ndarray] = {}  # EMA 9, 21, 50
        
        # Active instruments for processing
        self.active_instruments: set = set()
        self.priority_instruments: set = set()  # High-frequency processing
        
        # Signal callbacks
        self.signal_callbacks: List[Callable[[FibonacciSignal], None]] = []
        
        # Database service
        self.db_service = TradingDatabaseService()
        
        # Threading for high-performance processing
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AutoTrading")
        self.processing_queue = deque()
        self.processing_lock = threading.Lock()
        
        # Circuit breaker for error handling
        self.circuit_breaker_active = False
        self.error_threshold = 10  # Errors in 1 minute before circuit breaker
        self.error_count_window = deque()
        
        # Performance monitoring
        self.last_performance_log = time.time()
        
        logger.info("✅ AutoTradingDataService initialized")
    
    async def initialize(self) -> bool:
        """Initialize the auto-trading data service - called by AutoTradingCoordinator"""
        try:
            logger.info("🔄 Initializing AutoTradingDataService...")
            
            # Initialize database service (if it has initialize method)
            if hasattr(self.db_service, 'initialize'):
                await self.db_service.initialize()
            else:
                logger.info("✅ Database service ready (no initialization method needed)")
            
            # Connect to live feed adapter for real-time data
            self.live_feed_adapter = live_feed_adapter
            
            logger.info("✅ AutoTradingDataService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize auto-trading data service: {e}")
            return False
    
    async def start_service(self) -> bool:
        """Start the auto-trading data service"""
        try:
            if self.is_running:
                logger.warning("⚠️ Service already running")
                return True
            
            # Ensure initialization first
            if not hasattr(self, 'live_feed_adapter') or not self.live_feed_adapter:
                await self.initialize()
            
            # Register with live feed adapter
            live_feed_adapter.register_fibonacci_strategy_callback(
                strategy_name="auto_trading_main",
                instruments=[],  # Will be populated dynamically
                callback=self._process_tick_callback,
                priority_level=1  # Highest priority
            )
            
            # Start processing thread
            self.is_running = True
            asyncio.create_task(self._processing_loop())
            
            # Setup integration callbacks for live data pipeline
            self.setup_integration_callbacks()
            
            logger.info("🚀 Auto-trading data service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start auto-trading service: {e}")
            return False
    
    async def stop_service(self):
        """Stop the auto-trading data service"""
        self.is_running = False
        self.executor.shutdown(wait=True)
        logger.info("⏹️ Auto-trading data service stopped")
    
    def add_instruments(self, instruments: List[str], priority: bool = False):
        """Add instruments for processing"""
        for instrument_key in instruments:
            if len(self.active_instruments) >= self.max_instruments:
                logger.warning(f"⚠️ Max instruments limit reached ({self.max_instruments})")
                break
                
            self.active_instruments.add(instrument_key)
            self.tick_buffers[instrument_key] = CircularBuffer(maxsize=1000)
            
            if priority:
                self.priority_instruments.add(instrument_key)
                logger.info(f"✅ Added priority instrument: {instrument_key}")
            else:
                logger.info(f"✅ Added instrument: {instrument_key}")
    
    def remove_instruments(self, instruments: List[str]):
        """Remove instruments from processing"""
        for instrument_key in instruments:
            self.active_instruments.discard(instrument_key)
            self.priority_instruments.discard(instrument_key)
            
            # Clear caches
            self.tick_buffers.pop(instrument_key, None)
            self.fib_cache.pop(instrument_key, None)
            self.ema_cache.pop(instrument_key, None)
            
            logger.info(f"✅ Removed instrument: {instrument_key}")
    
    def register_signal_callback(self, callback: Callable[[FibonacciSignal], None]):
        """Register callback for trading signals"""
        self.signal_callbacks.append(callback)
        logger.info(f"✅ Registered signal callback: {callback.__name__}")
    
    def _process_tick_callback(self, instrument_key: str, enhanced_data: Dict):
        """Callback for processing enhanced tick data from live adapter"""
        if not self.is_running or self.circuit_breaker_active:
            return
        
        if instrument_key not in self.active_instruments:
            return
        
        start_time = time.time()
        
        try:
            # Add to processing queue for high-speed processing
            with self.processing_lock:
                self.processing_queue.append({
                    'instrument_key': instrument_key,
                    'enhanced_data': enhanced_data,
                    'processing_start': start_time
                })
            
        except Exception as e:
            self._handle_processing_error(f"Tick callback error: {e}")
    
    async def _processing_loop(self):
        """Main processing loop for high-speed data processing"""
        while self.is_running:
            try:
                # Process queue items
                while self.processing_queue:
                    with self.processing_lock:
                        if not self.processing_queue:
                            break
                        item = self.processing_queue.popleft()
                    
                    # Process in thread pool for parallel processing
                    future = self.executor.submit(self._process_tick_data, item)
                    
                    # Don't wait for completion to maintain high throughput
                
                # Performance monitoring
                current_time = time.time()
                if current_time - self.last_performance_log > 30:  # Log every 30 seconds
                    self._log_performance_metrics()
                    self.last_performance_log = current_time
                
                # Small sleep to prevent CPU overload
                await asyncio.sleep(0.001)  # 1ms
                
            except Exception as e:
                self._handle_processing_error(f"Processing loop error: {e}")
                await asyncio.sleep(0.01)  # 10ms backoff on error
    
    def _process_tick_data(self, item: Dict):
        """Process individual tick data with high-speed calculations"""
        instrument_key = item['instrument_key']
        enhanced_data = item['enhanced_data']
        processing_start = item['processing_start']
        
        try:
            # Step 1: Update tick buffer (< 0.5ms)
            tick_timestamp = time.time()
            ltp = enhanced_data.get('ltp', 0.0)
            volume = enhanced_data.get('volume', 0)
            
            # Add to circular buffer
            buffer = self.tick_buffers[instrument_key]
            buffer.add((tick_timestamp, ltp, ltp, ltp, ltp, volume))  # Using LTP for OHLC for now
            
            # Step 2: Fast Fibonacci calculations (< 2ms)
            fibonacci_signal = self._calculate_fibonacci_signal_fast(
                instrument_key, enhanced_data, buffer
            )
            
            # Step 3: Generate trading signal if strong enough (< 1ms)
            if fibonacci_signal and fibonacci_signal.confidence_score > 0.7:
                # Broadcast signal to callbacks
                for callback in self.signal_callbacks:
                    try:
                        callback(fibonacci_signal)
                    except Exception as e:
                        logger.error(f"❌ Signal callback error: {e}")
                
                # Async database logging (non-blocking)
                asyncio.create_task(self._log_signal_to_database(fibonacci_signal))
                
                # Update live position prices for real-time P&L tracking
                asyncio.create_task(self._update_live_positions(instrument_key, enhanced_data.get('ltp', 0.0)))
                
                self.processing_metrics.signals_generated += 1
            
            # Step 4: Update performance metrics
            processing_time = (time.time() - processing_start) * 1000  # Convert to milliseconds
            self._update_processing_metrics(processing_time)
            
            self.processing_metrics.total_ticks_processed += 1
            
        except Exception as e:
            self._handle_processing_error(f"Tick processing error for {instrument_key}: {e}")
    
    def _calculate_fibonacci_signal_fast(self, instrument_key: str, enhanced_data: Dict, 
                                       buffer: CircularBuffer) -> Optional[FibonacciSignal]:
        """Ultra-fast Fibonacci signal calculation using NumPy optimizations"""
        try:
            start_time = time.time()
            
            # Get recent price data (last 60 data points)
            recent_data = buffer.get_recent_data(60)
            if len(recent_data) < 10:
                return None
            
            # Extract price data using NumPy (vectorized operations)
            prices = recent_data[:, 4]  # Close prices (LTP in our case)
            current_price = prices[-1]
            
            # Fast high/low calculation using NumPy
            recent_high = np.max(prices[-30:])  # Last 30 points for swing high
            recent_low = np.min(prices[-30:])   # Last 30 points for swing low
            
            # Skip if range is too small (< 0.5%)
            price_range = recent_high - recent_low
            if price_range / current_price < 0.005:
                return None
            
            # Calculate Fibonacci levels using vectorized operations
            fib_levels = self._calculate_fibonacci_levels_fast(recent_high, recent_low)
            
            # Fast EMA calculations using cached values
            ema_values = self._calculate_emas_fast(instrument_key, prices)
            
            # Determine signal type and strength
            signal_data = self._analyze_fibonacci_signal(
                current_price, fib_levels, ema_values, enhanced_data
            )
            
            if not signal_data:
                return None
            
            # Create signal object
            processing_time_ms = (time.time() - start_time) * 1000
            
            fibonacci_signal = FibonacciSignal(
                instrument_key=instrument_key,
                signal_type=signal_data['signal_type'],
                signal_strength=signal_data['strength'],
                entry_price=current_price,
                fibonacci_level=signal_data['fib_level'],
                fibonacci_value=signal_data['fib_value'],
                ema_alignment=signal_data['ema_alignment'],
                stop_loss=signal_data['stop_loss'],
                target_1=signal_data['target_1'],
                target_2=signal_data['target_2'],
                confidence_score=signal_data['confidence'],
                processing_time_ms=processing_time_ms,
                timestamp=datetime.now(IST),
                market_structure=signal_data['market_structure'],
                option_type=signal_data['option_type']
            )
            
            self.processing_metrics.fibonacci_calculations += 1
            return fibonacci_signal
            
        except Exception as e:
            logger.error(f"❌ Fibonacci calculation error: {e}")
            return None
    
    def _calculate_fibonacci_levels_fast(self, high: float, low: float) -> Dict[str, float]:
        """Fast Fibonacci level calculations using NumPy"""
        diff = high - low
        
        # Vectorized Fibonacci calculations
        fib_ratios = np.array([0.236, 0.382, 0.500, 0.618, 0.786])
        fib_values = high - (diff * fib_ratios)
        
        return {
            'high': high,
            'low': low,
            'fib_23_6': fib_values[0],
            'fib_38_2': fib_values[1],
            'fib_50_0': fib_values[2],
            'fib_61_8': fib_values[3],
            'fib_78_6': fib_values[4]
        }
    
    def _calculate_emas_fast(self, instrument_key: str, prices: np.ndarray) -> Dict[str, float]:
        """Fast EMA calculations with caching"""
        if len(prices) < 2:
            return {'ema_9': 0.0, 'ema_21': 0.0, 'ema_50': 0.0}
        
        try:
            # Use cached EMAs for incremental updates (much faster)
            if instrument_key in self.ema_cache:
                cached_emas = self.ema_cache[instrument_key]
                current_price = prices[-1]
                
                # Incremental EMA update: EMA = α * current + (1-α) * prev_EMA
                alpha_9 = 2.0 / (9 + 1)
                alpha_21 = 2.0 / (21 + 1) 
                alpha_50 = 2.0 / (50 + 1)
                
                new_ema_9 = alpha_9 * current_price + (1 - alpha_9) * cached_emas[0]
                new_ema_21 = alpha_21 * current_price + (1 - alpha_21) * cached_emas[1]
                new_ema_50 = alpha_50 * current_price + (1 - alpha_50) * cached_emas[2]
                
                # Update cache
                self.ema_cache[instrument_key] = np.array([new_ema_9, new_ema_21, new_ema_50])
                
                return {
                    'ema_9': new_ema_9,
                    'ema_21': new_ema_21,
                    'ema_50': new_ema_50
                }
            else:
                # Initial EMA calculation using pandas (slower but necessary for first time)
                df = pd.DataFrame({'close': prices})
                
                ema_9 = df['close'].ewm(span=9).mean().iloc[-1] if len(prices) >= 9 else prices.mean()
                ema_21 = df['close'].ewm(span=21).mean().iloc[-1] if len(prices) >= 21 else prices.mean()
                ema_50 = df['close'].ewm(span=50).mean().iloc[-1] if len(prices) >= 50 else prices.mean()
                
                # Cache for future incremental updates
                self.ema_cache[instrument_key] = np.array([ema_9, ema_21, ema_50])
                
                return {
                    'ema_9': ema_9,
                    'ema_21': ema_21,
                    'ema_50': ema_50
                }
                
        except Exception as e:
            logger.error(f"❌ EMA calculation error: {e}")
            return {'ema_9': 0.0, 'ema_21': 0.0, 'ema_50': 0.0}
    
    def _analyze_fibonacci_signal(self, current_price: float, fib_levels: Dict, 
                                 ema_values: Dict, enhanced_data: Dict) -> Optional[Dict]:
        """Analyze and generate trading signal based on Fibonacci + EMA alignment"""
        try:
            # Determine market structure
            ema_9, ema_21, ema_50 = ema_values['ema_9'], ema_values['ema_21'], ema_values['ema_50']
            
            if current_price > ema_9 > ema_21 > ema_50:
                market_structure = "strong_bullish"
                ema_alignment = "bullish"
            elif current_price < ema_9 < ema_21 < ema_50:
                market_structure = "strong_bearish" 
                ema_alignment = "bearish"
            elif current_price > ema_21:
                market_structure = "bullish"
                ema_alignment = "bullish"
            elif current_price < ema_21:
                market_structure = "bearish"
                ema_alignment = "bearish"
            else:
                market_structure = "sideways"
                ema_alignment = "sideways"
            
            # Find nearest Fibonacci level
            nearest_fib = None
            min_distance = float('inf')
            
            key_fib_levels = ['fib_38_2', 'fib_50_0', 'fib_61_8']
            for fib_name in key_fib_levels:
                fib_value = fib_levels[fib_name]
                distance = abs(current_price - fib_value) / current_price
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_fib = {
                        'name': fib_name,
                        'value': fib_value,
                        'distance_percent': distance * 100
                    }
            
            # Generate signal only if price is near key Fibonacci level (< 0.2%)
            if not nearest_fib or nearest_fib['distance_percent'] > 0.2:
                return None
            
            # Determine signal type based on market structure and Fibonacci level
            signal_type = "HOLD"
            confidence = 0.0
            strength = 0.0
            
            if ema_alignment == "bullish" and current_price > nearest_fib['value']:
                # Bullish breakout above Fibonacci resistance
                signal_type = "BUY"
                confidence = 0.8 if market_structure == "strong_bullish" else 0.65
                strength = 0.9
            elif ema_alignment == "bearish" and current_price < nearest_fib['value']:
                # Bearish breakdown below Fibonacci support  
                signal_type = "SELL"
                confidence = 0.8 if market_structure == "strong_bearish" else 0.65
                strength = 0.9
            elif ema_alignment == "bullish" and abs(current_price - nearest_fib['value']) / current_price < 0.001:
                # Bullish bounce from Fibonacci support
                signal_type = "BUY"
                confidence = 0.75
                strength = 0.8
            elif ema_alignment == "bearish" and abs(current_price - nearest_fib['value']) / current_price < 0.001:
                # Bearish rejection at Fibonacci resistance
                signal_type = "SELL" 
                confidence = 0.75
                strength = 0.8
            
            if signal_type == "HOLD":
                return None
            
            # Calculate stop loss and targets
            price_range = fib_levels['high'] - fib_levels['low']
            
            if signal_type == "BUY":
                stop_loss = current_price - (price_range * 0.02)  # 2% of recent range
                target_1 = current_price + (price_range * 0.05)   # 5% of recent range
                target_2 = current_price + (price_range * 0.1)    # 10% of recent range
                option_type = "CE"  # Call option for bullish signals
            else:  # SELL
                stop_loss = current_price + (price_range * 0.02)  # 2% of recent range
                target_1 = current_price - (price_range * 0.05)   # 5% of recent range
                target_2 = current_price - (price_range * 0.1)    # 10% of recent range
                option_type = "PE"  # Put option for bearish signals
            
            return {
                'signal_type': signal_type,
                'strength': strength,
                'fib_level': nearest_fib['name'],
                'fib_value': nearest_fib['value'],
                'ema_alignment': ema_alignment,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'confidence': confidence,
                'market_structure': market_structure,
                'option_type': option_type
            }
            
        except Exception as e:
            logger.error(f"❌ Signal analysis error: {e}")
            return None
    
    async def _log_signal_to_database(self, signal: FibonacciSignal):
        """Asynchronously log trading signal to database"""
        try:
            signal_data = {
                'instrument_key': signal.instrument_key,
                'signal_type': signal.signal_type,
                'signal_strength': signal.signal_strength,
                'entry_price': signal.entry_price,
                'fibonacci_level': signal.fibonacci_level,
                'fibonacci_value': signal.fibonacci_value,
                'ema_alignment': signal.ema_alignment,
                'stop_loss': signal.stop_loss,
                'target_1': signal.target_1,
                'target_2': signal.target_2,
                'confidence_score': signal.confidence_score,
                'processing_time_ms': signal.processing_time_ms,
                'timestamp': signal.timestamp,
                'market_structure': signal.market_structure,
                'option_type': signal.option_type
            }
            
            trade_id = await self.db_service.log_fibonacci_signal(signal_data, user_id=1)
            if trade_id:
                self.processing_metrics.database_writes += 1
                logger.debug(f"✅ Logged Fibonacci signal to database: {trade_id}")
                
        except Exception as e:
            logger.error(f"❌ Database logging error: {e}")
            self._handle_processing_error("Database logging failed")
    
    async def _update_live_positions(self, instrument_key: str, current_price: float):
        """Update live positions with current price for real-time P&L"""
        try:
            updated = await self.db_service.update_live_position_price(
                instrument_key=instrument_key,
                current_price=current_price,
                user_id=1  # Default user for auto-trading
            )
            
            if updated:
                logger.debug(f"✅ Updated live positions for {instrument_key} @ {current_price}")
            
        except Exception as e:
            logger.debug(f"Position update failed for {instrument_key}: {e}")
    
    async def log_performance_metrics_to_db(self):
        """Log performance metrics to database for monitoring"""
        try:
            metrics_data = self.get_performance_stats()['metrics']
            
            success = await self.db_service.log_tick_processing_metrics(metrics_data)
            if success:
                logger.debug("✅ Performance metrics logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log performance metrics to database: {e}")
    
    async def get_live_dashboard_data(self, user_id: int = 1) -> Dict[str, Any]:
        """Get comprehensive live trading dashboard data"""
        try:
            # Get dashboard data from database service
            dashboard_data = await self.db_service.get_live_trading_dashboard_data(user_id)
            
            # Add auto-trading service specific metrics
            service_stats = self.get_performance_stats()
            dashboard_data['auto_trading_service'] = service_stats
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get live dashboard data: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(IST).isoformat()
            }
    
    async def bulk_process_price_updates(self, price_updates: List[Dict[str, Any]]):
        """Bulk process multiple price updates for performance"""
        try:
            if not price_updates:
                return
            
            # Update database positions in bulk
            updated_count = await self.db_service.bulk_update_positions_from_live_data(price_updates)
            
            if updated_count > 0:
                logger.debug(f"✅ Bulk processed {len(price_updates)} price updates, updated {updated_count} positions")
                
        except Exception as e:
            logger.error(f"❌ Bulk price update processing failed: {e}")
    
    def setup_integration_callbacks(self):
        """Setup integration callbacks with live feed adapter and database"""
        try:
            # Register for bulk price updates every 5 seconds
            async def bulk_update_callback():
                while self.is_running:
                    try:
                        # Collect recent price updates
                        price_updates = []
                        current_time = time.time()
                        
                        for instrument_key in self.active_instruments:
                            if instrument_key in self.tick_buffers:
                                buffer = self.tick_buffers[instrument_key]
                                recent_data = buffer.get_recent_data(1)  # Get latest tick
                                
                                if len(recent_data) > 0:
                                    latest_tick = recent_data[-1]
                                    price_updates.append({
                                        'instrument_key': instrument_key,
                                        'current_price': latest_tick[4],  # Close price (LTP)
                                        'timestamp': current_time
                                    })
                        
                        # Bulk update positions
                        if price_updates:
                            await self.bulk_process_price_updates(price_updates)
                        
                        # Log performance metrics every minute
                        if int(current_time) % 60 == 0:
                            await self.log_performance_metrics_to_db()
                        
                    except Exception as e:
                        logger.error(f"❌ Bulk update callback error: {e}")
                    
                    await asyncio.sleep(5)  # 5-second intervals
            
            # Start the bulk update task
            if self.is_running:
                asyncio.create_task(bulk_update_callback())
            
            logger.info("✅ Integration callbacks setup completed")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup integration callbacks: {e}")
    
    def _update_processing_metrics(self, processing_time_ms: float):
        """Update processing performance metrics"""
        # Update average processing time
        total_processed = self.processing_metrics.total_ticks_processed
        current_avg = self.processing_metrics.avg_processing_time_ms
        
        new_avg = ((current_avg * total_processed) + processing_time_ms) / (total_processed + 1)
        self.processing_metrics.avg_processing_time_ms = new_avg
        
        # Update max processing time
        if processing_time_ms > self.processing_metrics.max_processing_time_ms:
            self.processing_metrics.max_processing_time_ms = processing_time_ms
    
    def _handle_processing_error(self, error_msg: str):
        """Handle processing errors with circuit breaker pattern"""
        self.processing_metrics.errors_count += 1
        current_time = time.time()
        
        # Add to error window (last 60 seconds)
        self.error_count_window.append(current_time)
        
        # Remove old errors (> 60 seconds)
        while self.error_count_window and (current_time - self.error_count_window[0]) > 60:
            self.error_count_window.popleft()
        
        # Check if circuit breaker should be activated
        if len(self.error_count_window) >= self.error_threshold:
            self.circuit_breaker_active = True
            self.processing_metrics.circuit_breaker_triggers += 1
            logger.error(f"🚨 CIRCUIT BREAKER ACTIVATED: {error_msg}")
            
            # Auto-reset after 30 seconds
            async def reset_circuit_breaker():
                await asyncio.sleep(30)
                self.circuit_breaker_active = False
                self.error_count_window.clear()
                logger.info("✅ Circuit breaker reset")
            
            asyncio.create_task(reset_circuit_breaker())
        else:
            logger.error(f"❌ Processing error: {error_msg}")
    
    def _log_performance_metrics(self):
        """Log performance metrics for monitoring"""
        metrics = self.processing_metrics
        
        logger.info(f"📊 Performance Metrics - "
                   f"Processed: {metrics.total_ticks_processed}, "
                   f"Avg Time: {metrics.avg_processing_time_ms:.2f}ms, "
                   f"Max Time: {metrics.max_processing_time_ms:.2f}ms, "
                   f"Signals: {metrics.signals_generated}, "
                   f"DB Writes: {metrics.database_writes}, "
                   f"Errors: {metrics.errors_count}")
    
    async def get_current_price(self, instrument_key: str) -> Optional[Dict[str, Any]]:
        """
        Get current price for an instrument - CRITICAL METHOD called by AutoTradingCoordinator
        
        Args:
            instrument_key: Instrument identifier
            
        Returns:
            Dict with current price data or None if not available
        """
        try:
            # Method 1: Try live feed adapter first (fastest)
            if hasattr(self, 'live_feed_adapter') and self.live_feed_adapter:
                price_data = self.live_feed_adapter.get_latest_price(instrument_key)
                if price_data:
                    logger.debug(f"✅ Got current price from live adapter: {instrument_key} @ {price_data.get('ltp', 0)}")
                    return price_data
            
            # Method 2: Try circular buffer (internal storage)
            if instrument_key in self.tick_buffers:
                buffer = self.tick_buffers[instrument_key]
                recent_data = buffer.get_recent_data(1)  # Get latest tick
                
                if len(recent_data) > 0:
                    latest_tick = recent_data[-1]
                    current_price = latest_tick[4]  # Close price (LTP)
                    
                    logger.debug(f"✅ Got current price from buffer: {instrument_key} @ {current_price}")
                    return {
                        'ltp': current_price,
                        'last_price': current_price,
                        'change': 0.0,  # We'll calculate if needed
                        'change_percent': 0.0,
                        'volume': int(latest_tick[5]),
                        'timestamp': datetime.now(IST).isoformat()
                    }
            
            # Method 3: Try centralized WebSocket manager
            try:
                from services.centralized_ws_manager import centralized_manager
                if hasattr(centralized_manager, '_live_prices'):
                    live_prices = centralized_manager._live_prices
                    if instrument_key in live_prices:
                        price_data = live_prices[instrument_key]
                        logger.debug(f"✅ Got current price from centralized manager: {instrument_key} @ {price_data.get('ltp', 0)}")
                        return price_data
            except ImportError:
                pass
            
            # Method 4: Try instrument registry as fallback
            try:
                from services.instrument_registry import instrument_registry
                symbol = instrument_key.split('|')[-1] if '|' in instrument_key else instrument_key
                price_data = instrument_registry.get_spot_price(symbol)
                if price_data:
                    logger.debug(f"✅ Got current price from instrument registry: {instrument_key} @ {price_data.get('last_price', 0)}")
                    return {
                        'ltp': price_data.get('last_price', 0.0),
                        'last_price': price_data.get('last_price', 0.0),
                        'change': price_data.get('change', 0.0),
                        'change_percent': price_data.get('change_percent', 0.0),
                        'volume': price_data.get('volume', 0),
                        'timestamp': datetime.now(IST).isoformat()
                    }
            except ImportError:
                pass
            
            logger.warning(f"⚠️ No current price available for {instrument_key}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting current price for {instrument_key}: {e}")
            return None
    
    async def get_ohlc_data(self, instrument_key: str, timeframe: str = '1m', periods: int = 100) -> pd.DataFrame:
        """
        Get OHLC data for an instrument - CRITICAL METHOD called by AutoTradingCoordinator
        
        Args:
            instrument_key: Instrument identifier
            timeframe: Time frame ('1m', '5m', '15m', '1h', etc.)
            periods: Number of periods to return
            
        Returns:
            DataFrame with OHLC data
        """
        try:
            # Method 1: Try live feed adapter first (preferred)
            if hasattr(self, 'live_feed_adapter') and self.live_feed_adapter:
                if timeframe == '1m':
                    df = self.live_feed_adapter.get_1m_df(instrument_key, periods)
                    if not df.empty:
                        logger.debug(f"✅ Got {timeframe} OHLC from live adapter: {instrument_key} ({len(df)} bars)")
                        return df
                elif timeframe == '5m':
                    df = self.live_feed_adapter.get_5m_df(instrument_key, periods * 5)  # 5m needs more minutes
                    if not df.empty:
                        logger.debug(f"✅ Got {timeframe} OHLC from live adapter: {instrument_key} ({len(df)} bars)")
                        return df
            
            # Method 2: Generate from circular buffer data
            if instrument_key in self.tick_buffers:
                buffer = self.tick_buffers[instrument_key]
                recent_data = buffer.get_recent_data(periods * 2)  # Get more data for better OHLC
                
                if len(recent_data) >= 5:  # Minimum data required
                    df = self._convert_buffer_to_ohlc(recent_data, timeframe, periods)
                    if not df.empty:
                        logger.debug(f"✅ Got {timeframe} OHLC from buffer: {instrument_key} ({len(df)} bars)")
                        return df
            
            # Method 3: Try dashboard OHLC service fallback
            try:
                from services.dashboard_ohlc_service import dashboard_ohlc_service
                df = await dashboard_ohlc_service.get_ohlc_data(instrument_key, timeframe, periods)
                if not df.empty:
                    logger.debug(f"✅ Got {timeframe} OHLC from dashboard service: {instrument_key} ({len(df)} bars)")
                    return df
            except ImportError:
                pass
            
            logger.warning(f"⚠️ No OHLC data available for {instrument_key} ({timeframe}, {periods} periods)")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
        except Exception as e:
            logger.error(f"❌ Error getting OHLC data for {instrument_key}: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def _convert_buffer_to_ohlc(self, buffer_data: np.ndarray, timeframe: str, periods: int) -> pd.DataFrame:
        """Convert circular buffer data to OHLC DataFrame"""
        try:
            if len(buffer_data) == 0:
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Convert to DataFrame
            df = pd.DataFrame(buffer_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
            df.set_index('timestamp', inplace=True)
            
            # Resample based on timeframe
            if timeframe == '1m':
                freq = '1T'
            elif timeframe == '5m':
                freq = '5T'
            elif timeframe == '15m':
                freq = '15T'
            elif timeframe == '1h':
                freq = '1H'
            else:
                freq = '1T'  # Default to 1 minute
            
            # Resample to OHLCV
            ohlcv = df.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min', 
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            ohlcv.reset_index(inplace=True)
            
            # Limit to requested periods
            if len(ohlcv) > periods:
                ohlcv = ohlcv.tail(periods)
            
            return ohlcv
            
        except Exception as e:
            logger.error(f"❌ Error converting buffer to OHLC: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    async def process_market_data_batch(self):
        """Process batch of market data - called by AutoTradingCoordinator"""
        try:
            # Process any queued items
            processed_count = 0
            max_batch_size = 10  # Limit batch size for performance
            
            while self.processing_queue and processed_count < max_batch_size:
                with self.processing_lock:
                    if not self.processing_queue:
                        break
                    item = self.processing_queue.popleft()
                
                # Process in current thread for immediate processing
                self._process_tick_data(item)
                processed_count += 1
            
            if processed_count > 0:
                logger.debug(f"✅ Processed {processed_count} market data items in batch")
            
        except Exception as e:
            logger.error(f"❌ Error processing market data batch: {e}")
    
    async def register_fibonacci_callback(self, strategy_name: str, callback: Callable):
        """Register callback for Fibonacci signals - called by AutoTradingCoordinator"""
        try:
            self.signal_callbacks.append(callback)
            logger.info(f"✅ Registered Fibonacci callback for strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error registering Fibonacci callback: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the auto-trading data service"""
        try:
            await self.stop_service()
            
            # Cleanup resources
            self.tick_buffers.clear()
            self.fib_cache.clear()
            self.ema_cache.clear()
            self.signal_callbacks.clear()
            
            logger.info("✅ AutoTradingDataService shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            'is_running': self.is_running,
            'circuit_breaker_active': self.circuit_breaker_active,
            'active_instruments': len(self.active_instruments),
            'priority_instruments': len(self.priority_instruments),
            'queue_size': len(self.processing_queue),
            'metrics': {
                'total_ticks_processed': self.processing_metrics.total_ticks_processed,
                'avg_processing_time_ms': self.processing_metrics.avg_processing_time_ms,
                'max_processing_time_ms': self.processing_metrics.max_processing_time_ms,
                'signals_generated': self.processing_metrics.signals_generated,
                'fibonacci_calculations': self.processing_metrics.fibonacci_calculations,
                'database_writes': self.processing_metrics.database_writes,
                'errors_count': self.processing_metrics.errors_count,
                'circuit_breaker_triggers': self.processing_metrics.circuit_breaker_triggers
            }
        }

# Global instance
auto_trading_data_service = AutoTradingDataService()