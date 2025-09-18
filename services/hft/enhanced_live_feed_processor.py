"""
Enhanced Live Feed Processor with Kafka Integration

Production-grade live feed processing system with:
- Kafka partition-based routing for all features
- NumPy/Pandas optimized calculations
- Market session awareness (premarket, trading hours, post-market)
- Modular feature calculation pipeline
- Load distribution and performance monitoring

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
import time
from typing import Dict, List, Set, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, time as time_obj
from enum import Enum
from collections import defaultdict, deque
import json

import numpy as np
import pandas as pd
from decimal import Decimal

from .config import get_hft_kafka_config
from .producer import get_hft_producer
from .partition_strategy import get_enhanced_partition_manager, ServiceType
from .feature_calculators.base_calculator import BaseCalculator

logger = logging.getLogger(__name__)


class MarketSession(Enum):
    """Market session types"""
    PRE_MARKET = "pre_market"       # 9:00-9:15 AM
    OPENING = "opening"             # 9:15-9:30 AM
    REGULAR_HOURS = "regular_hours" # 9:30 AM-3:30 PM
    CLOSING = "closing"             # 3:30-4:00 PM
    POST_MARKET = "post_market"     # After 4:00 PM
    CLOSED = "closed"               # Market closed


class ProcessingMode(Enum):
    """Processing modes for different sessions"""
    BATCH = "batch"                 # Batch processing for heavy calculations
    STREAM = "stream"               # Real-time streaming for active trading
    REDUCED = "reduced"             # Reduced processing for closed hours


@dataclass
class SessionConfig:
    """Configuration for market session processing"""
    session: MarketSession
    processing_mode: ProcessingMode
    batch_size: int
    processing_interval_ms: int
    enabled_features: Set[str]
    priority_level: int


@dataclass 
class LiveFeedData:
    """Standardized live feed data structure"""
    instrument_key: str
    symbol: str
    timestamp_ns: int
    
    # Price data
    ltp: float
    previous_close: float
    open_price: float
    high_price: float
    low_price: float
    
    # Volume data
    volume: int
    value: float
    
    # Bid/Ask data
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_qty: int = 0
    ask_qty: int = 0
    
    # Calculated fields
    change: float = 0.0
    change_percent: float = 0.0
    
    def __post_init__(self):
        """Calculate derived values"""
        if self.previous_close > 0:
            self.change = self.ltp - self.previous_close
            self.change_percent = (self.change / self.previous_close) * 100


@dataclass
class FeatureCalculationResult:
    """Result of feature calculation"""
    feature_name: str
    instrument_key: str
    value: Any
    metadata: Dict[str, Any]
    calculation_time_ns: int
    timestamp: datetime


class EnhancedLiveFeedProcessor:
    """
    Enhanced live feed processor with Kafka integration
    
    Features:
    - Market session-aware processing
    - Kafka partition routing for all calculations
    - NumPy/Pandas optimized feature calculation
    - Load balancing and performance monitoring
    - Modular feature pipeline
    """
    
    def __init__(self):
        self.config = get_hft_kafka_config()
        self.producer = get_hft_producer()
        self.partition_manager = get_enhanced_partition_manager()
        
        # Processing state
        self.current_session = MarketSession.CLOSED
        self.processing_active = False
        self.session_configs = self._initialize_session_configs()
        
        # Data buffers for batch processing
        self.feed_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.calculation_results: Dict[str, Dict] = {}
        
        # Feature calculators registry
        self.feature_calculators: Dict[str, BaseCalculator] = {}
        self.feature_dependencies: Dict[str, Set[str]] = {}
        
        # Performance tracking
        self.processing_stats = {
            'messages_processed': 0,
            'calculations_performed': 0,
            'avg_processing_time_ns': 0,
            'last_batch_size': 0,
            'error_count': 0
        }
        
        # NumPy arrays for optimized calculations
        self.price_arrays: Dict[str, np.ndarray] = {}
        self.volume_arrays: Dict[str, np.ndarray] = {}
        self.timestamp_arrays: Dict[str, np.ndarray] = {}
        
        logger.info("Enhanced Live Feed Processor initialized")
    
    def _initialize_session_configs(self) -> Dict[MarketSession, SessionConfig]:
        """Initialize processing configurations for each market session"""
        return {
            MarketSession.PRE_MARKET: SessionConfig(
                session=MarketSession.PRE_MARKET,
                processing_mode=ProcessingMode.STREAM,
                batch_size=100,
                processing_interval_ms=1000,
                enabled_features={
                    'gap_detection', 'volume_analysis', 'sector_momentum',
                    'advance_decline_ratio', 'market_sentiment'
                },
                priority_level=1
            ),
            
            MarketSession.OPENING: SessionConfig(
                session=MarketSession.OPENING,
                processing_mode=ProcessingMode.STREAM,
                batch_size=50,
                processing_interval_ms=500,
                enabled_features={
                    'breakout_detection', 'volume_spike_detection', 'top_movers',
                    'opening_range_analysis', 'gap_confirmation'
                },
                priority_level=1
            ),
            
            MarketSession.REGULAR_HOURS: SessionConfig(
                session=MarketSession.REGULAR_HOURS,
                processing_mode=ProcessingMode.STREAM,
                batch_size=200,
                processing_interval_ms=250,
                enabled_features={
                    'breakout_detection', 'support_resistance', 'trend_analysis',
                    'volume_profile', 'momentum_indicators', 'sector_performance',
                    'advance_decline_ratio', 'market_breadth', 'volatility_analysis'
                },
                priority_level=1
            ),
            
            MarketSession.CLOSING: SessionConfig(
                session=MarketSession.CLOSING,
                processing_mode=ProcessingMode.STREAM,
                batch_size=300,
                processing_interval_ms=1000,
                enabled_features={
                    'closing_range_analysis', 'day_performance_summary',
                    'volume_weighted_analysis', 'sector_summary'
                },
                priority_level=2
            ),
            
            MarketSession.POST_MARKET: SessionConfig(
                session=MarketSession.POST_MARKET,
                processing_mode=ProcessingMode.BATCH,
                batch_size=1000,
                processing_interval_ms=5000,
                enabled_features={
                    'daily_performance_calculation', 'historical_data_update',
                    'performance_metrics', 'risk_assessment'
                },
                priority_level=3
            ),
            
            MarketSession.CLOSED: SessionConfig(
                session=MarketSession.CLOSED,
                processing_mode=ProcessingMode.REDUCED,
                batch_size=500,
                processing_interval_ms=10000,
                enabled_features={
                    'historical_analysis', 'backtesting_data_prep'
                },
                priority_level=4
            )
        }
    
    def determine_market_session(self) -> MarketSession:
        """Determine current market session based on time"""
        now = datetime.now().time()
        
        # Market session times (IST)
        if time_obj(9, 0) <= now < time_obj(9, 15):
            return MarketSession.PRE_MARKET
        elif time_obj(9, 15) <= now < time_obj(9, 30):
            return MarketSession.OPENING
        elif time_obj(9, 30) <= now < time_obj(15, 30):
            return MarketSession.REGULAR_HOURS
        elif time_obj(15, 30) <= now < time_obj(16, 0):
            return MarketSession.CLOSING
        elif time_obj(16, 0) <= now < time_obj(18, 0):
            return MarketSession.POST_MARKET
        else:
            return MarketSession.CLOSED
    
    def register_feature_calculator(
        self, 
        calculator: BaseCalculator,
        dependencies: Optional[Set[str]] = None
    ):
        """Register a feature calculator with optional dependencies"""
        feature_name = calculator.get_feature_name()
        self.feature_calculators[feature_name] = calculator
        self.feature_dependencies[feature_name] = dependencies or set()
        
        logger.info(f"Registered feature calculator: {feature_name}")
    
    async def process_live_feed_data(self, raw_feed_data: Dict[str, Any]) -> None:
        """
        Process live feed data with session-aware routing
        
        Args:
            raw_feed_data: Raw WebSocket feed data from broker
        """
        start_time = time.perf_counter_ns()
        
        try:
            # Update current session
            self.current_session = self.determine_market_session()
            session_config = self.session_configs[self.current_session]
            
            # Parse and standardize feed data
            standardized_data = await self._parse_live_feed_data(raw_feed_data)
            
            if not standardized_data:
                return
            
            # Route data to appropriate Kafka partitions
            routing_info = self.partition_manager.get_partition_routing_info(raw_feed_data)
            
            # Process data based on session configuration
            if session_config.processing_mode == ProcessingMode.STREAM:
                await self._process_streaming_data(standardized_data, routing_info, session_config)
            elif session_config.processing_mode == ProcessingMode.BATCH:
                await self._process_batch_data(standardized_data, routing_info, session_config)
            else:  # REDUCED
                await self._process_reduced_data(standardized_data, routing_info, session_config)
            
            # Update performance stats
            processing_time = time.perf_counter_ns() - start_time
            self._update_processing_stats(processing_time, len(standardized_data))
            
        except Exception as e:
            logger.error(f"Error processing live feed data: {e}")
            self.processing_stats['error_count'] += 1
    
    async def _parse_live_feed_data(self, raw_data: Dict[str, Any]) -> List[LiveFeedData]:
        """Parse raw feed data into standardized format"""
        standardized_data = []
        
        feeds = raw_data.get("feeds", {})
        
        for instrument_key, feed_data in feeds.items():
            try:
                # Extract data based on feed structure
                full_feed = feed_data.get("fullFeed", {})
                
                # Handle equity data
                if "marketFF" in full_feed:
                    market_ff = full_feed["marketFF"]
                    ltpc = market_ff.get("ltpc", {})
                    ohlc_data = market_ff.get("marketOHLC", {}).get("ohlc", [])
                    
                    # Get daily OHLC
                    daily_ohlc = next((ohlc for ohlc in ohlc_data if ohlc.get("interval") == "1d"), {})
                    
                    data = LiveFeedData(
                        instrument_key=instrument_key,
                        symbol=self._extract_symbol_from_key(instrument_key),
                        timestamp_ns=int(ltpc.get("ltt", 0)),
                        ltp=float(ltpc.get("ltp", 0)),
                        previous_close=float(ltpc.get("cp", 0)),
                        open_price=float(daily_ohlc.get("open", 0)),
                        high_price=float(daily_ohlc.get("high", 0)),
                        low_price=float(daily_ohlc.get("low", 0)),
                        volume=int(daily_ohlc.get("vol", 0)),
                        value=float(market_ff.get("vtt", 0)) * float(ltpc.get("ltp", 0)),
                        bid_price=self._extract_bid_price(market_ff),
                        ask_price=self._extract_ask_price(market_ff)
                    )
                    
                # Handle index data
                elif "indexFF" in full_feed:
                    index_ff = full_feed["indexFF"]
                    ltpc = index_ff.get("ltpc", {})
                    ohlc_data = index_ff.get("marketOHLC", {}).get("ohlc", [])
                    
                    daily_ohlc = next((ohlc for ohlc in ohlc_data if ohlc.get("interval") == "1d"), {})
                    
                    data = LiveFeedData(
                        instrument_key=instrument_key,
                        symbol=self._extract_symbol_from_key(instrument_key),
                        timestamp_ns=int(ltpc.get("ltt", 0)),
                        ltp=float(ltpc.get("ltp", 0)),
                        previous_close=float(ltpc.get("cp", 0)),
                        open_price=float(daily_ohlc.get("open", 0)),
                        high_price=float(daily_ohlc.get("high", 0)),
                        low_price=float(daily_ohlc.get("low", 0)),
                        volume=0,  # Indices don't have volume
                        value=0
                    )
                else:
                    continue
                
                standardized_data.append(data)
                
            except Exception as e:
                logger.error(f"Error parsing data for {instrument_key}: {e}")
                continue
        
        return standardized_data
    
    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract trading symbol from instrument key"""
        if "|" in instrument_key:
            return instrument_key.split("|")[-1]
        return instrument_key
    
    def _extract_bid_price(self, market_ff: Dict[str, Any]) -> float:
        """Extract best bid price from market data"""
        bid_ask_quotes = market_ff.get("marketLevel", {}).get("bidAskQuote", [])
        if bid_ask_quotes and len(bid_ask_quotes) > 0:
            return float(bid_ask_quotes[0].get("bidP", 0))
        return 0.0
    
    def _extract_ask_price(self, market_ff: Dict[str, Any]) -> float:
        """Extract best ask price from market data"""
        bid_ask_quotes = market_ff.get("marketLevel", {}).get("bidAskQuote", [])
        if bid_ask_quotes and len(bid_ask_quotes) > 0:
            return float(bid_ask_quotes[0].get("askP", 0))
        return 0.0
    
    async def _process_streaming_data(
        self,
        data: List[LiveFeedData],
        routing_info: Dict[ServiceType, Dict[int, List[str]]],
        config: SessionConfig
    ) -> None:
        """Process data in streaming mode for real-time features"""
        
        # Update NumPy arrays for vectorized calculations
        await self._update_numpy_arrays(data)
        
        # Calculate enabled features for current session
        calculation_tasks = []
        
        for feature_name in config.enabled_features:
            calculator = self.feature_calculators.get(feature_name)
            if calculator:
                task = self._calculate_feature_streaming(calculator, data, routing_info)
                calculation_tasks.append(task)
        
        # Execute all calculations concurrently
        if calculation_tasks:
            await asyncio.gather(*calculation_tasks, return_exceptions=True)
    
    async def _process_batch_data(
        self,
        data: List[LiveFeedData],
        routing_info: Dict[ServiceType, Dict[int, List[str]]],
        config: SessionConfig
    ) -> None:
        """Process data in batch mode for heavy calculations"""
        
        # Add data to buffers
        for item in data:
            self.feed_buffer[item.instrument_key].append(item)
        
        # Check if batch size reached
        total_buffered = sum(len(buffer) for buffer in self.feed_buffer.values())
        
        if total_buffered >= config.batch_size:
            await self._execute_batch_calculations(config, routing_info)
    
    async def _process_reduced_data(
        self,
        data: List[LiveFeedData],
        routing_info: Dict[ServiceType, Dict[int, List[str]]],
        config: SessionConfig
    ) -> None:
        """Process data in reduced mode for off-hours"""
        
        # Only process essential calculations
        essential_features = config.enabled_features & {'historical_analysis', 'risk_assessment'}
        
        for feature_name in essential_features:
            calculator = self.feature_calculators.get(feature_name)
            if calculator:
                await self._calculate_feature_batch(calculator, data, routing_info)
    
    async def _update_numpy_arrays(self, data: List[LiveFeedData]) -> None:
        """Update NumPy arrays for vectorized calculations"""
        
        for item in data:
            instrument_key = item.instrument_key
            
            # Initialize arrays if needed
            if instrument_key not in self.price_arrays:
                self.price_arrays[instrument_key] = np.zeros(1000, dtype=np.float64)
                self.volume_arrays[instrument_key] = np.zeros(1000, dtype=np.int64)
                self.timestamp_arrays[instrument_key] = np.zeros(1000, dtype=np.int64)
            
            # Shift arrays and add new data
            self.price_arrays[instrument_key][:-1] = self.price_arrays[instrument_key][1:]
            self.price_arrays[instrument_key][-1] = item.ltp
            
            self.volume_arrays[instrument_key][:-1] = self.volume_arrays[instrument_key][1:]
            self.volume_arrays[instrument_key][-1] = item.volume
            
            self.timestamp_arrays[instrument_key][:-1] = self.timestamp_arrays[instrument_key][1:]
            self.timestamp_arrays[instrument_key][-1] = item.timestamp_ns
    
    async def _calculate_feature_streaming(
        self,
        calculator: BaseCalculator,
        data: List[LiveFeedData],
        routing_info: Dict[ServiceType, Dict[int, List[str]]]
    ) -> None:
        """Calculate feature in streaming mode"""
        
        try:
            start_time = time.perf_counter_ns()
            
            # Convert data to pandas DataFrame for efficient processing
            df = self._convert_to_dataframe(data)
            
            # Calculate feature using vectorized operations
            results = await calculator.calculate_vectorized(df, self.price_arrays, self.volume_arrays)
            
            # Route results to appropriate Kafka partitions
            await self._route_results_to_kafka(results, routing_info, calculator.get_service_type())
            
            calculation_time = time.perf_counter_ns() - start_time
            self.processing_stats['calculations_performed'] += 1
            
            logger.debug(f"Calculated {calculator.get_feature_name()} in {calculation_time/1_000_000:.2f}ms")
            
        except Exception as e:
            logger.error(f"Error calculating {calculator.get_feature_name()}: {e}")
    
    async def _calculate_feature_batch(
        self,
        calculator: BaseCalculator,
        data: List[LiveFeedData],
        routing_info: Dict[ServiceType, Dict[int, List[str]]]
    ) -> None:
        """Calculate feature in batch mode"""
        
        try:
            # Collect all buffered data for this calculator
            all_data = []
            for buffer in self.feed_buffer.values():
                all_data.extend(list(buffer))
            
            if not all_data:
                return
            
            # Convert to DataFrame and calculate
            df = self._convert_to_dataframe(all_data)
            results = await calculator.calculate_batch(df, self.price_arrays, self.volume_arrays)
            
            # Route results to Kafka
            await self._route_results_to_kafka(results, routing_info, calculator.get_service_type())
            
            self.processing_stats['calculations_performed'] += 1
            
        except Exception as e:
            logger.error(f"Error in batch calculation for {calculator.get_feature_name()}: {e}")
    
    def _convert_to_dataframe(self, data: List[LiveFeedData]) -> pd.DataFrame:
        """Convert LiveFeedData list to pandas DataFrame for efficient processing"""
        
        records = []
        for item in data:
            records.append({
                'instrument_key': item.instrument_key,
                'symbol': item.symbol,
                'timestamp': pd.to_datetime(item.timestamp_ns, unit='ns'),
                'ltp': item.ltp,
                'previous_close': item.previous_close,
                'open': item.open_price,
                'high': item.high_price,
                'low': item.low_price,
                'volume': item.volume,
                'value': item.value,
                'change': item.change,
                'change_percent': item.change_percent,
                'bid_price': item.bid_price,
                'ask_price': item.ask_price
            })
        
        df = pd.DataFrame(records)
        
        # Set proper data types for efficient processing
        numeric_columns = ['ltp', 'previous_close', 'open', 'high', 'low', 'volume', 
                          'value', 'change', 'change_percent', 'bid_price', 'ask_price']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    async def _route_results_to_kafka(
        self,
        results: List[FeatureCalculationResult],
        routing_info: Dict[ServiceType, Dict[int, List[str]]],
        service_type: ServiceType
    ) -> None:
        """Route calculation results to appropriate Kafka partitions"""
        
        try:
            # Group results by partition
            partition_results = defaultdict(list)
            
            for result in results:
                # Get partition for this instrument and service
                partition_id = self.partition_manager.get_partition_for_service(
                    result.instrument_key, service_type
                )
                
                if partition_id is not None:
                    partition_results[partition_id].append(result)
            
            # Send to each partition
            send_tasks = []
            for partition_id, partition_data in partition_results.items():
                topic_name = self.partition_manager.get_kafka_topic_name(service_type, partition_id)
                
                message_data = {
                    'service_type': service_type.value,
                    'partition_id': partition_id,
                    'results': [
                        {
                            'feature_name': r.feature_name,
                            'instrument_key': r.instrument_key,
                            'value': r.value,
                            'metadata': r.metadata,
                            'timestamp': r.timestamp.isoformat(),
                            'calculation_time_ns': r.calculation_time_ns
                        }
                        for r in partition_data
                    ],
                    'timestamp': datetime.now().isoformat()
                }
                
                task = self.producer.send_to_topic(topic_name, message_data, partition_id)
                send_tasks.append(task)
            
            # Wait for all sends to complete
            if send_tasks:
                await asyncio.gather(*send_tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Error routing results to Kafka: {e}")
    
    async def _execute_batch_calculations(
        self,
        config: SessionConfig,
        routing_info: Dict[ServiceType, Dict[int, List[str]]]
    ) -> None:
        """Execute batch calculations and clear buffers"""
        
        try:
            # Collect all buffered data
            all_data = []
            for buffer in self.feed_buffer.values():
                all_data.extend(list(buffer))
            
            # Execute batch calculations
            calculation_tasks = []
            for feature_name in config.enabled_features:
                calculator = self.feature_calculators.get(feature_name)
                if calculator:
                    task = self._calculate_feature_batch(calculator, all_data, routing_info)
                    calculation_tasks.append(task)
            
            if calculation_tasks:
                await asyncio.gather(*calculation_tasks, return_exceptions=True)
            
            # Clear buffers
            for buffer in self.feed_buffer.values():
                buffer.clear()
            
            self.processing_stats['last_batch_size'] = len(all_data)
            
        except Exception as e:
            logger.error(f"Error executing batch calculations: {e}")
    
    def _update_processing_stats(self, processing_time_ns: int, data_count: int) -> None:
        """Update processing performance statistics"""
        
        self.processing_stats['messages_processed'] += data_count
        
        # Update average processing time using exponential moving average
        if self.processing_stats['avg_processing_time_ns'] == 0:
            self.processing_stats['avg_processing_time_ns'] = processing_time_ns
        else:
            alpha = 0.1  # Smoothing factor
            self.processing_stats['avg_processing_time_ns'] = (
                (1 - alpha) * self.processing_stats['avg_processing_time_ns'] + 
                alpha * processing_time_ns
            )
    
    async def start_processing(self) -> None:
        """Start the live feed processing system"""
        
        self.processing_active = True
        logger.info(f"Started live feed processing in {self.current_session.value} mode")
        
        # Start background tasks
        asyncio.create_task(self._session_monitor_task())
        asyncio.create_task(self._performance_monitor_task())
    
    async def stop_processing(self) -> None:
        """Stop the live feed processing system"""
        
        self.processing_active = False
        
        # Process any remaining buffered data
        for config in self.session_configs.values():
            routing_info = {}  # Empty routing info for cleanup
            await self._execute_batch_calculations(config, routing_info)
        
        logger.info("Stopped live feed processing")
    
    async def _session_monitor_task(self) -> None:
        """Background task to monitor session changes"""
        
        while self.processing_active:
            try:
                new_session = self.determine_market_session()
                
                if new_session != self.current_session:
                    logger.info(f"Market session changed: {self.current_session.value} -> {new_session.value}")
                    self.current_session = new_session
                    
                    # Adjust processing parameters for new session
                    await self._adjust_processing_for_session(new_session)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in session monitor: {e}")
                await asyncio.sleep(60)
    
    async def _performance_monitor_task(self) -> None:
        """Background task to monitor processing performance"""
        
        while self.processing_active:
            try:
                stats = self.get_processing_stats()
                
                # Log performance metrics
                if stats['messages_processed'] > 0:
                    avg_time_ms = stats['avg_processing_time_ns'] / 1_000_000
                    logger.info(
                        f"Processing stats - Messages: {stats['messages_processed']}, "
                        f"Calculations: {stats['calculations_performed']}, "
                        f"Avg time: {avg_time_ms:.2f}ms, "
                        f"Errors: {stats['error_count']}"
                    )
                
                await asyncio.sleep(300)  # Report every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")
                await asyncio.sleep(300)
    
    async def _adjust_processing_for_session(self, session: MarketSession) -> None:
        """Adjust processing parameters for new session"""
        
        config = self.session_configs[session]
        
        # Clear buffers if switching to different processing mode
        if config.processing_mode != self.session_configs[self.current_session].processing_mode:
            for buffer in self.feed_buffer.values():
                buffer.clear()
        
        logger.info(f"Adjusted processing for {session.value} - Mode: {config.processing_mode.value}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        
        return {
            **self.processing_stats,
            'current_session': self.current_session.value,
            'processing_active': self.processing_active,
            'registered_calculators': list(self.feature_calculators.keys()),
            'buffer_sizes': {k: len(v) for k, v in self.feed_buffer.items()},
            'numpy_array_count': len(self.price_arrays)
        }


# Singleton instance
_enhanced_processor: Optional[EnhancedLiveFeedProcessor] = None


def get_enhanced_live_feed_processor() -> EnhancedLiveFeedProcessor:
    """Get singleton enhanced live feed processor instance"""
    global _enhanced_processor
    if _enhanced_processor is None:
        _enhanced_processor = EnhancedLiveFeedProcessor()
    return _enhanced_processor


async def initialize_live_feed_processing() -> bool:
    """Initialize the enhanced live feed processing system"""
    try:
        processor = get_enhanced_live_feed_processor()
        await processor.start_processing()
        logger.info("Enhanced live feed processing system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize live feed processing: {e}")
        return False


async def cleanup_live_feed_processing() -> None:
    """Cleanup the live feed processing system"""
    try:
        global _enhanced_processor
        if _enhanced_processor:
            await _enhanced_processor.stop_processing()
            _enhanced_processor = None
        logger.info("Live feed processing system cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up live feed processing: {e}")