"""
Enhanced Base Calculator with NumPy/Pandas Optimization

Production-grade base class for feature calculators with:
- Vectorized NumPy operations for performance
- Pandas DataFrame processing
- Memory efficient calculations
- Error handling and validation
- Performance monitoring

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np
import pandas as pd
from decimal import Decimal

from ..partition_strategy import ServiceType

logger = logging.getLogger(__name__)


class CalculationType(Enum):
    """Types of calculations supported"""
    STREAMING = "streaming"    # Real-time streaming calculations
    BATCH = "batch"           # Batch processing calculations
    HISTORICAL = "historical" # Historical data analysis


@dataclass
class CalculationConfig:
    """Configuration for feature calculations"""
    calculation_type: CalculationType
    window_size: int = 20
    min_data_points: int = 5
    precision: int = 4
    memory_limit_mb: int = 100
    enable_caching: bool = True
    cache_ttl_seconds: int = 300


class EnhancedBaseCalculator(ABC):
    """
    Enhanced base calculator with NumPy/Pandas optimization
    
    Features:
    - Vectorized operations using NumPy
    - Efficient DataFrame processing with Pandas
    - Memory management and optimization
    - Performance monitoring
    - Error handling and validation
    """
    
    def __init__(self, config: CalculationConfig):
        self.config = config
        self.calculation_cache: Dict[str, Any] = {}
        self.last_calculation_time: Dict[str, datetime] = {}
        
        # Performance tracking
        self.performance_stats = {
            'calculations_performed': 0,
            'total_calculation_time_ns': 0,
            'avg_calculation_time_ns': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0
        }
        
        # Memory management
        self.memory_usage_mb = 0.0
        self.max_memory_usage_mb = 0.0
        
        logger.info(f"Initialized {self.get_feature_name()} calculator")
    
    @abstractmethod
    def get_feature_name(self) -> str:
        """Get the name of the feature this calculator computes"""
        pass
    
    @abstractmethod
    def get_service_type(self) -> ServiceType:
        """Get the service type this calculator belongs to"""
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Get list of required DataFrame fields for calculation"""
        pass
    
    async def calculate_vectorized(
        self,
        df: pd.DataFrame,
        price_arrays: Dict[str, np.ndarray],
        volume_arrays: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """
        Calculate feature using vectorized operations
        
        Args:
            df: DataFrame with market data
            price_arrays: NumPy arrays with price history
            volume_arrays: NumPy arrays with volume history
            
        Returns:
            List of calculation results
        """
        start_time = time.perf_counter_ns()
        
        try:
            # Validate input data
            self._validate_input_data(df)
            
            # Check cache if enabled
            if self.config.enable_caching:
                cached_results = self._check_cache(df)
                if cached_results:
                    self.performance_stats['cache_hits'] += 1
                    return cached_results
                self.performance_stats['cache_misses'] += 1
            
            # Perform vectorized calculation
            results = await self._calculate_vectorized_impl(df, price_arrays, volume_arrays)
            
            # Cache results if enabled
            if self.config.enable_caching:
                self._cache_results(df, results)
            
            # Update performance stats
            calculation_time = time.perf_counter_ns() - start_time
            self._update_performance_stats(calculation_time)
            
            return results
            
        except Exception as e:
            self.performance_stats['errors'] += 1
            logger.error(f"Error in vectorized calculation for {self.get_feature_name()}: {e}")
            return []
    
    async def calculate_batch(
        self,
        df: pd.DataFrame,
        price_arrays: Dict[str, np.ndarray],
        volume_arrays: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """
        Calculate feature using batch processing
        
        Args:
            df: DataFrame with historical market data
            price_arrays: NumPy arrays with price history
            volume_arrays: NumPy arrays with volume history
            
        Returns:
            List of calculation results
        """
        start_time = time.perf_counter_ns()
        
        try:
            # Validate input data
            self._validate_input_data(df)
            
            # Perform batch calculation with memory optimization
            results = await self._calculate_batch_impl(df, price_arrays, volume_arrays)
            
            # Update performance stats
            calculation_time = time.perf_counter_ns() - start_time
            self._update_performance_stats(calculation_time)
            
            return results
            
        except Exception as e:
            self.performance_stats['errors'] += 1
            logger.error(f"Error in batch calculation for {self.get_feature_name()}: {e}")
            return []
    
    @abstractmethod
    async def _calculate_vectorized_impl(
        self,
        df: pd.DataFrame,
        price_arrays: Dict[str, np.ndarray],
        volume_arrays: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """Implementation of vectorized calculation"""
        pass
    
    @abstractmethod
    async def _calculate_batch_impl(
        self,
        df: pd.DataFrame,
        price_arrays: Dict[str, np.ndarray],
        volume_arrays: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """Implementation of batch calculation"""
        pass
    
    def _validate_input_data(self, df: pd.DataFrame) -> None:
        """Validate input DataFrame"""
        
        if df.empty:
            raise ValueError("Input DataFrame is empty")
        
        required_fields = self.get_required_fields()
        missing_fields = set(required_fields) - set(df.columns)
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Check for sufficient data points
        if len(df) < self.config.min_data_points:
            raise ValueError(f"Insufficient data points: {len(df)} < {self.config.min_data_points}")
        
        # Check for NaN values in critical fields
        critical_fields = ['ltp', 'volume', 'timestamp']
        for field in critical_fields:
            if field in df.columns and df[field].isna().any():
                logger.warning(f"Found NaN values in {field}")
    
    def _check_cache(self, df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
        """Check if calculation results are cached"""
        
        if not self.config.enable_caching:
            return None
        
        # Create cache key based on data characteristics
        cache_key = self._create_cache_key(df)
        
        if cache_key in self.calculation_cache:
            cached_time = self.last_calculation_time.get(cache_key)
            if cached_time and (datetime.now() - cached_time).seconds < self.config.cache_ttl_seconds:
                return self.calculation_cache[cache_key]
        
        return None
    
    def _cache_results(self, df: pd.DataFrame, results: List[Dict[str, Any]]) -> None:
        """Cache calculation results"""
        
        cache_key = self._create_cache_key(df)
        self.calculation_cache[cache_key] = results
        self.last_calculation_time[cache_key] = datetime.now()
        
        # Clean old cache entries if memory limit exceeded
        if self.memory_usage_mb > self.config.memory_limit_mb:
            self._cleanup_cache()
    
    def _create_cache_key(self, df: pd.DataFrame) -> str:
        """Create cache key from DataFrame characteristics"""
        
        # Use hash of data characteristics for cache key
        key_components = [
            str(len(df)),
            str(df['ltp'].sum() if 'ltp' in df.columns else 0),
            str(df['volume'].sum() if 'volume' in df.columns else 0),
            str(df['timestamp'].max() if 'timestamp' in df.columns else 0)
        ]
        
        return "_".join(key_components)
    
    def _cleanup_cache(self) -> None:
        """Clean up old cache entries to free memory"""
        
        current_time = datetime.now()
        expired_keys = []
        
        for cache_key, cached_time in self.last_calculation_time.items():
            if (current_time - cached_time).seconds > self.config.cache_ttl_seconds:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            self.calculation_cache.pop(key, None)
            self.last_calculation_time.pop(key, None)
        
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _update_performance_stats(self, calculation_time_ns: int) -> None:
        """Update performance statistics"""
        
        self.performance_stats['calculations_performed'] += 1
        self.performance_stats['total_calculation_time_ns'] += calculation_time_ns
        
        # Update average using exponential moving average
        if self.performance_stats['avg_calculation_time_ns'] == 0:
            self.performance_stats['avg_calculation_time_ns'] = float(calculation_time_ns)
        else:
            alpha = 0.1
            current_avg = self.performance_stats['avg_calculation_time_ns']
            self.performance_stats['avg_calculation_time_ns'] = (
                (1 - alpha) * current_avg + alpha * calculation_time_ns
            )
    
    def calculate_moving_average(self, prices: np.ndarray, window: int) -> np.ndarray:
        """Calculate moving average using NumPy for performance"""
        
        if len(prices) < window:
            return np.full(len(prices), np.nan)
        
        # Use convolution for efficient moving average calculation
        kernel = np.ones(window) / window
        ma = np.convolve(prices, kernel, mode='valid')
        
        # Pad with NaN for consistent length
        return np.concatenate([np.full(window - 1, np.nan), ma])
    
    def calculate_standard_deviation(self, prices: np.ndarray, window: int) -> np.ndarray:
        """Calculate rolling standard deviation using NumPy"""
        
        if len(prices) < window:
            return np.full(len(prices), np.nan)
        
        # Calculate rolling standard deviation
        std_values = []
        for i in range(len(prices)):
            if i < window - 1:
                std_values.append(np.nan)
            else:
                window_data = prices[i - window + 1:i + 1]
                std_values.append(np.std(window_data))
        
        return np.array(std_values)
    
    def calculate_rsi(self, prices: np.ndarray, window: int = 14) -> np.ndarray:
        """Calculate RSI using vectorized NumPy operations"""
        
        if len(prices) < window + 1:
            return np.full(len(prices), np.nan)
        
        # Calculate price changes
        deltas = np.diff(prices)
        
        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate initial averages
        avg_gains = np.zeros(len(gains))
        avg_losses = np.zeros(len(losses))
        
        # First RSI calculation
        avg_gains[window - 1] = np.mean(gains[:window])
        avg_losses[window - 1] = np.mean(losses[:window])
        
        # Calculate smoothed averages
        for i in range(window, len(gains)):
            avg_gains[i] = (avg_gains[i - 1] * (window - 1) + gains[i]) / window
            avg_losses[i] = (avg_losses[i - 1] * (window - 1) + losses[i]) / window
        
        # Calculate RSI
        rs = np.divide(avg_gains, avg_losses, out=np.zeros_like(avg_gains), where=avg_losses != 0)
        rsi = 100 - (100 / (1 + rs))
        
        # Pad with NaN for consistent length
        return np.concatenate([np.full(1, np.nan), rsi])
    
    def calculate_bollinger_bands(
        self, 
        prices: np.ndarray, 
        window: int = 20, 
        num_std: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands using NumPy"""
        
        ma = self.calculate_moving_average(prices, window)
        std = self.calculate_standard_deviation(prices, window)
        
        upper_band = ma + (std * num_std)
        lower_band = ma - (std * num_std)
        
        return upper_band, ma, lower_band
    
    def calculate_volume_weighted_price(self, prices: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate volume weighted average price"""
        
        if len(prices) != len(volumes) or len(prices) == 0:
            return np.nan
        
        # Filter out zero volumes
        valid_mask = volumes > 0
        if not np.any(valid_mask):
            return np.nan
        
        valid_prices = prices[valid_mask]
        valid_volumes = volumes[valid_mask]
        
        return np.sum(valid_prices * valid_volumes) / np.sum(valid_volumes)
    
    def detect_price_breakouts(
        self, 
        prices: np.ndarray, 
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        volumes: np.ndarray,
        lookback_periods: int = 20,
        volume_threshold: float = 1.5
    ) -> List[Dict[str, Any]]:
        """Detect price breakouts using vectorized operations"""
        
        if len(prices) < lookback_periods:
            return []
        
        breakouts = []
        
        for i in range(lookback_periods, len(prices)):
            # Get historical data window
            hist_high = high_prices[i - lookback_periods:i]
            hist_low = low_prices[i - lookback_periods:i]
            hist_volume = volumes[i - lookback_periods:i]
            
            current_price = prices[i]
            current_volume = volumes[i]
            
            # Calculate resistance and support levels
            resistance = np.max(hist_high)
            support = np.min(hist_low)
            avg_volume = np.mean(hist_volume)
            
            # Check for breakout conditions
            volume_spike = current_volume > (avg_volume * volume_threshold)
            
            if current_price > resistance and volume_spike:
                breakouts.append({
                    'type': 'resistance_breakout',
                    'price': current_price,
                    'resistance_level': resistance,
                    'volume': current_volume,
                    'volume_ratio': current_volume / avg_volume,
                    'index': i
                })
            elif current_price < support and volume_spike:
                breakouts.append({
                    'type': 'support_breakdown',
                    'price': current_price,
                    'support_level': support,
                    'volume': current_volume,
                    'volume_ratio': current_volume / avg_volume,
                    'index': i
                })
        
        return breakouts
    
    def calculate_sector_momentum(
        self, 
        sector_df: pd.DataFrame,
        price_column: str = 'ltp',
        volume_column: str = 'volume'
    ) -> Dict[str, float]:
        """Calculate sector momentum using pandas operations"""
        
        if sector_df.empty:
            return {}
        
        # Calculate weighted momentum for sector
        prices = sector_df[price_column].values
        volumes = sector_df[volume_column].values
        changes = sector_df['change_percent'].values if 'change_percent' in sector_df.columns else np.zeros(len(prices))
        
        # Volume-weighted momentum
        total_volume = np.sum(volumes)
        if total_volume > 0:
            momentum = np.sum(changes * volumes) / total_volume
        else:
            momentum = np.mean(changes)
        
        # Calculate additional metrics
        advancing_count = np.sum(changes > 0)
        declining_count = np.sum(changes < 0)
        unchanged_count = len(changes) - advancing_count - declining_count
        
        return {
            'momentum': round(momentum, 4),
            'advancing_count': int(advancing_count),
            'declining_count': int(declining_count),
            'unchanged_count': int(unchanged_count),
            'advance_decline_ratio': float(advancing_count / declining_count) if declining_count > 0 else float('inf'),
            'total_instruments': len(sector_df)
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        
        avg_time_ms = self.performance_stats['avg_calculation_time_ns'] / 1_000_000
        
        return {
            **self.performance_stats,
            'avg_calculation_time_ms': round(avg_time_ms, 4),
            'feature_name': self.get_feature_name(),
            'service_type': self.get_service_type().value,
            'cache_hit_ratio': (
                self.performance_stats['cache_hits'] / 
                max(1, self.performance_stats['cache_hits'] + self.performance_stats['cache_misses'])
            ),
            'memory_usage_mb': self.memory_usage_mb,
            'max_memory_usage_mb': self.max_memory_usage_mb
        }
    
    def reset_performance_stats(self) -> None:
        """Reset performance statistics"""
        
        self.performance_stats = {
            'calculations_performed': 0,
            'total_calculation_time_ns': 0,
            'avg_calculation_time_ns': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0
        }
        
        logger.info(f"Reset performance stats for {self.get_feature_name()}")


# Export main classes
__all__ = [
    "CalculationType",
    "CalculationConfig", 
    "EnhancedBaseCalculator"
]