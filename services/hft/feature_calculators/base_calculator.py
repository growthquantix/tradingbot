"""
Base Feature Calculator for Real-Time Market Data Processing

Provides the foundation for all real-time feature calculations with
standardized interfaces, error handling, and performance monitoring.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
import numpy as np
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CalculationResult:
    """Standardized result format for feature calculations"""
    feature_type: str
    data: Dict[str, Any]
    timestamp: datetime
    calculation_time_ms: float
    instruments_processed: int
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance tracking for feature calculators"""
    total_calculations: int = 0
    total_processing_time_ms: float = 0.0
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    min_processing_time_ms: float = float('inf')
    error_count: int = 0
    last_calculation_time: Optional[datetime] = None


class BaseFeatureCalculator(ABC):
    """
    Abstract base class for all real-time feature calculators
    
    Features:
    - Standardized calculation interface
    - Performance monitoring
    - Error handling and recovery
    - Data validation
    - Memory management
    - Async processing support
    """
    
    def __init__(
        self,
        calculator_name: str,
        max_history_size: int = 1000,
        calculation_interval_ms: int = 1000
    ):
        self.calculator_name = calculator_name
        self.max_history_size = max_history_size
        self.calculation_interval_ms = calculation_interval_ms
        
        # Performance tracking
        self.performance_metrics = PerformanceMetrics()
        
        # Data storage
        self._data_history: deque = deque(maxlen=max_history_size)
        self._current_data: Dict[str, Any] = {}
        self._calculation_cache: Dict[str, CalculationResult] = {}
        
        # Processing control
        self._is_running = False
        self._last_calculation_time = 0
        self._required_fields: Set[str] = set()
        
        # Initialize required fields
        self._initialize_required_fields()
        
        logger.info(f"Initialized {calculator_name} calculator")
    
    @abstractmethod
    def _initialize_required_fields(self) -> None:
        """Initialize the required fields for this calculator"""
        pass
    
    @abstractmethod
    async def _calculate_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform the actual feature calculation
        
        Args:
            data: Processed live feed data
            
        Returns:
            Calculated features as dictionary
        """
        pass
    
    def get_required_fields(self) -> Set[str]:
        """Get list of required fields for this calculator"""
        return self._required_fields.copy()
    
    async def process_live_feed(self, live_feed_data: Dict[str, Any]) -> Optional[CalculationResult]:
        """
        Process live feed data and calculate features
        
        Args:
            live_feed_data: Raw live feed data from Kafka
            
        Returns:
            CalculationResult or None if processing failed
        """
        try:
            start_time = time.perf_counter()
            
            # Validate input data
            if not self._validate_input_data(live_feed_data):
                logger.warning(f"{self.calculator_name}: Invalid input data")
                return None
            
            # Check calculation interval
            current_time = time.time() * 1000
            if current_time - self._last_calculation_time < self.calculation_interval_ms:
                return None  # Skip calculation if interval not met
            
            # Extract and validate required data
            processed_data = self._extract_required_data(live_feed_data)
            if not processed_data:
                return None
            
            # Store data for history
            self._store_data_point(processed_data)
            
            # Perform calculation
            calculated_features = await self._calculate_features(processed_data)
            
            # Calculate processing time
            processing_time = (time.perf_counter() - start_time) * 1000
            
            # Create result
            result = CalculationResult(
                feature_type=self.calculator_name,
                data=calculated_features,
                timestamp=datetime.now(),
                calculation_time_ms=processing_time,
                instruments_processed=len(processed_data.get('feeds', {})),
                metadata={
                    'data_points_used': len(self._data_history),
                    'calculation_interval_ms': self.calculation_interval_ms
                }
            )
            
            # Update performance metrics
            self._update_performance_metrics(processing_time)
            self._last_calculation_time = current_time
            
            # Cache result
            self._calculation_cache[self.calculator_name] = result
            
            logger.debug(
                f"{self.calculator_name}: Processed {result.instruments_processed} instruments "
                f"in {processing_time:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            self.performance_metrics.error_count += 1
            logger.error(f"{self.calculator_name}: Calculation error: {e}")
            return None
    
    def _validate_input_data(self, data: Dict[str, Any]) -> bool:
        """Validate input data structure"""
        try:
            if not isinstance(data, dict):
                return False
            
            if 'feeds' not in data:
                return False
            
            feeds = data['feeds']
            if not isinstance(feeds, dict) or len(feeds) == 0:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"{self.calculator_name}: Input validation error: {e}")
            return False
    
    def _extract_required_data(self, live_feed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract only the required data fields for this calculator
        
        Args:
            live_feed_data: Raw live feed data
            
        Returns:
            Filtered data containing only required fields
        """
        try:
            feeds = live_feed_data.get('feeds', {})
            extracted_feeds = {}
            
            for instrument_key, feed_data in feeds.items():
                # Extract relevant data based on live feed format
                full_feed = feed_data.get('fullFeed', {})
                
                # Handle both marketFF and indexFF formats
                market_data = full_feed.get('marketFF') or full_feed.get('indexFF')
                if not market_data:
                    continue
                
                # Extract standard fields
                extracted_data = self._extract_standard_fields(instrument_key, market_data)
                if extracted_data:
                    extracted_feeds[instrument_key] = extracted_data
            
            if not extracted_feeds:
                return None
            
            return {
                'feeds': extracted_feeds,
                'timestamp': live_feed_data.get('timestamp', datetime.now().isoformat()),
                'type': live_feed_data.get('type', 'live_feed')
            }
            
        except Exception as e:
            logger.error(f"{self.calculator_name}: Data extraction error: {e}")
            return None
    
    def _extract_standard_fields(
        self, 
        instrument_key: str, 
        market_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract standard fields from market data"""
        try:
            # Extract LTPC (Last Traded Price & Close)
            ltpc = market_data.get('ltpc', {})
            if not ltpc:
                return None
            
            ltp = ltpc.get('ltp')
            cp = ltpc.get('cp')  # Previous close
            
            if ltp is None or cp is None:
                return None
            
            # Calculate basic metrics
            change = float(ltp) - float(cp)
            change_percent = (change / float(cp)) * 100 if cp != 0 else 0
            
            # Extract volume data
            volume = int(market_data.get('vtt', 0))  # Total volume traded
            
            # Extract OHLC data
            ohlc_data = self._extract_ohlc_data(market_data)
            
            # Extract bid/ask data
            bid_ask_data = self._extract_bid_ask_data(market_data)
            
            extracted = {
                'instrument_key': instrument_key,
                'ltp': float(ltp),
                'previous_close': float(cp),
                'change': change,
                'change_percent': change_percent,
                'volume': volume,
                'timestamp': ltpc.get('ltt', str(int(time.time() * 1000))),
                **ohlc_data,
                **bid_ask_data
            }
            
            return extracted
            
        except Exception as e:
            logger.error(f"Field extraction error for {instrument_key}: {e}")
            return None
    
    def _extract_ohlc_data(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract OHLC data from market data"""
        try:
            ohlc_list = market_data.get('marketOHLC', {}).get('ohlc', [])
            
            # Find daily OHLC data
            daily_ohlc = None
            for ohlc in ohlc_list:
                if ohlc.get('interval') == '1d':
                    daily_ohlc = ohlc
                    break
            
            if daily_ohlc:
                return {
                    'open': float(daily_ohlc.get('open', 0)),
                    'high': float(daily_ohlc.get('high', 0)),
                    'low': float(daily_ohlc.get('low', 0)),
                    'close': float(daily_ohlc.get('close', 0))
                }
            
            return {'open': 0, 'high': 0, 'low': 0, 'close': 0}
            
        except Exception:
            return {'open': 0, 'high': 0, 'low': 0, 'close': 0}
    
    def _extract_bid_ask_data(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract bid/ask data from market data"""
        try:
            bid_ask_quotes = market_data.get('marketLevel', {}).get('bidAskQuote', [])
            
            if bid_ask_quotes:
                best_quote = bid_ask_quotes[0]
                return {
                    'bid_price': float(best_quote.get('bidP', 0)),
                    'ask_price': float(best_quote.get('askP', 0)),
                    'bid_qty': int(best_quote.get('bidQ', 0)),
                    'ask_qty': int(best_quote.get('askQ', 0))
                }
            
            return {'bid_price': 0, 'ask_price': 0, 'bid_qty': 0, 'ask_qty': 0}
            
        except Exception:
            return {'bid_price': 0, 'ask_price': 0, 'bid_qty': 0, 'ask_qty': 0}
    
    def _store_data_point(self, data: Dict[str, Any]) -> None:
        """Store data point in history for trend analysis"""
        try:
            timestamp = datetime.now()
            data_point = {
                'timestamp': timestamp,
                'data': data,
                'feeds_count': len(data.get('feeds', {}))
            }
            
            self._data_history.append(data_point)
            self._current_data = data
            
        except Exception as e:
            logger.error(f"{self.calculator_name}: Data storage error: {e}")
    
    def _update_performance_metrics(self, processing_time_ms: float) -> None:
        """Update performance tracking metrics"""
        metrics = self.performance_metrics
        
        metrics.total_calculations += 1
        metrics.total_processing_time_ms += processing_time_ms
        metrics.avg_processing_time_ms = (
            metrics.total_processing_time_ms / metrics.total_calculations
        )
        
        if processing_time_ms > metrics.max_processing_time_ms:
            metrics.max_processing_time_ms = processing_time_ms
        
        if processing_time_ms < metrics.min_processing_time_ms:
            metrics.min_processing_time_ms = processing_time_ms
        
        metrics.last_calculation_time = datetime.now()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this calculator"""
        metrics = self.performance_metrics
        
        return {
            'calculator_name': self.calculator_name,
            'total_calculations': metrics.total_calculations,
            'avg_processing_time_ms': round(metrics.avg_processing_time_ms, 2),
            'max_processing_time_ms': round(metrics.max_processing_time_ms, 2),
            'min_processing_time_ms': round(metrics.min_processing_time_ms, 2),
            'error_count': metrics.error_count,
            'error_rate_percent': round(
                (metrics.error_count / max(metrics.total_calculations, 1)) * 100, 2
            ),
            'last_calculation': metrics.last_calculation_time.isoformat() if metrics.last_calculation_time else None,
            'data_history_size': len(self._data_history),
            'cache_size': len(self._calculation_cache)
        }
    
    def get_latest_result(self) -> Optional[CalculationResult]:
        """Get the latest calculation result"""
        return self._calculation_cache.get(self.calculator_name)
    
    def get_historical_data(
        self, 
        lookback_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get historical data points for trend analysis"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
            
            return [
                data_point for data_point in self._data_history
                if data_point['timestamp'] >= cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"{self.calculator_name}: Historical data retrieval error: {e}")
            return []
    
    def clear_cache(self) -> None:
        """Clear calculation cache to free memory"""
        self._calculation_cache.clear()
        logger.debug(f"{self.calculator_name}: Cache cleared")
    
    def reset_performance_metrics(self) -> None:
        """Reset performance tracking metrics"""
        self.performance_metrics = PerformanceMetrics()
        logger.info(f"{self.calculator_name}: Performance metrics reset")


# Utility functions for common calculations
def calculate_percentage_change(current: float, previous: float) -> float:
    """Calculate percentage change between two values"""
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def calculate_moving_average(values: List[float], period: int) -> Optional[float]:
    """Calculate simple moving average"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def calculate_volatility(values: List[float], period: int = 20) -> Optional[float]:
    """Calculate price volatility using standard deviation"""
    if len(values) < period:
        return None
    
    recent_values = values[-period:]
    mean_value = sum(recent_values) / len(recent_values)
    variance = sum((x - mean_value) ** 2 for x in recent_values) / len(recent_values)
    return variance ** 0.5


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default value for zero denominator"""
    return numerator / denominator if denominator != 0 else default


# Export main classes and functions
__all__ = [
    "BaseFeatureCalculator",
    "CalculationResult", 
    "PerformanceMetrics",
    "calculate_percentage_change",
    "calculate_moving_average",
    "calculate_volatility",
    "safe_divide"
]