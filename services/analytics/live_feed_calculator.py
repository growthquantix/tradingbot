"""
Live Feed Calculator Service

Processes raw live feed data and calculates real-time features.
Implements clean separation between data ingestion and feature calculation.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from collections import deque, defaultdict

from .interfaces import IFeatureCalculator, MarketTick, CalculatedFeatures

logger = logging.getLogger(__name__)


class LiveFeedCalculator(IFeatureCalculator):
    """
    Calculates real-time features from live market feed data.
    
    Features:
    - Price change and percentage calculations
    - Volume ratio analysis
    - Momentum scoring
    - Volatility measurements
    - Moving averages
    """
    
    def __init__(self, history_window_size: int = 100):
        self._history_window_size = history_window_size
        
        # Price history for each symbol
        self._price_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=history_window_size)
        )
        
        # Volume history for each symbol
        self._volume_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=50)
        )
        
        # Sector mapping (should be loaded from config)
        self._sector_mapping = self._load_sector_mapping()
        
        logger.info(f"✅ LiveFeedCalculator initialized with window size {history_window_size}")
    
    async def calculate_features(self, tick: MarketTick) -> CalculatedFeatures:
        """Calculate features for a single market tick"""
        try:
            # Update price history
            self._update_price_history(tick)
            
            # Calculate basic price features
            price_change = tick.change or Decimal('0')
            price_change_percent = tick.change_percent or Decimal('0')
            
            # Calculate advanced features
            momentum_score = self._calculate_momentum(tick.symbol)
            volatility_score = self._calculate_volatility(tick.symbol)
            volume_ratio = self._calculate_volume_ratio(tick)
            
            # Get sector information
            sector = self._sector_mapping.get(tick.symbol, 'Unknown')
            market_cap_category = self._determine_market_cap_category(tick.last_price)
            
            return CalculatedFeatures(
                symbol=tick.symbol,
                timestamp=tick.timestamp,
                price_change=price_change,
                price_change_percent=price_change_percent,
                momentum_score=momentum_score,
                volatility_score=volatility_score,
                volume_ratio=volume_ratio,
                sector=sector,
                market_cap_category=market_cap_category
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating features for {tick.symbol}: {e}")
            # Return minimal features on error
            return CalculatedFeatures(
                symbol=tick.symbol,
                timestamp=tick.timestamp,
                price_change=tick.change or Decimal('0'),
                price_change_percent=tick.change_percent or Decimal('0')
            )
    
    async def calculate_batch_features(self, ticks: List[MarketTick]) -> List[CalculatedFeatures]:
        """Calculate features for a batch of ticks"""
        try:
            # Process all ticks in parallel for better performance
            tasks = [self.calculate_features(tick) for tick in ticks]
            features_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and return valid features
            valid_features = [
                features for features in features_list 
                if isinstance(features, CalculatedFeatures)
            ]
            
            logger.debug(f"📊 Calculated features for {len(valid_features)}/{len(ticks)} ticks")
            return valid_features
            
        except Exception as e:
            logger.error(f"❌ Error in batch feature calculation: {e}")
            return []
    
    def _update_price_history(self, tick: MarketTick) -> None:
        """Update price and volume history for the symbol"""
        try:
            symbol = tick.symbol
            
            # Add to price history
            price_data = {
                'price': tick.last_price,
                'volume': tick.volume,
                'timestamp': tick.timestamp
            }
            self._price_history[symbol].append(price_data)
            
            # Add to volume history (separate for volume-specific calculations)
            self._volume_history[symbol].append(tick.volume)
            
        except Exception as e:
            logger.error(f"❌ Error updating history for {tick.symbol}: {e}")
    
    def _calculate_momentum(self, symbol: str) -> Optional[Decimal]:
        """Calculate momentum score based on recent price movements"""
        try:
            history = self._price_history.get(symbol)
            if not history or len(history) < 10:
                return None
            
            # Get recent prices
            recent_prices = [float(data['price']) for data in list(history)[-10:]]
            if len(recent_prices) < 5:
                return None
            
            # Calculate momentum as rate of change
            recent_avg = sum(recent_prices[-5:]) / 5
            older_avg = sum(recent_prices[-10:-5]) / 5
            
            if older_avg == 0:
                return None
            
            momentum = ((recent_avg - older_avg) / older_avg) * 100
            return Decimal(str(round(momentum, 4)))
            
        except Exception as e:
            logger.error(f"❌ Error calculating momentum for {symbol}: {e}")
            return None
    
    def _calculate_volatility(self, symbol: str) -> Optional[Decimal]:
        """Calculate volatility score based on price standard deviation"""
        try:
            history = self._price_history.get(symbol)
            if not history or len(history) < 20:
                return None
            
            # Get recent prices for volatility calculation
            recent_prices = [float(data['price']) for data in list(history)[-20:]]
            if len(recent_prices) < 10:
                return None
            
            # Calculate standard deviation
            mean_price = sum(recent_prices) / len(recent_prices)
            variance = sum((price - mean_price) ** 2 for price in recent_prices) / len(recent_prices)
            std_dev = variance ** 0.5
            
            # Convert to percentage volatility
            if mean_price == 0:
                return None
            
            volatility_percent = (std_dev / mean_price) * 100
            return Decimal(str(round(volatility_percent, 4)))
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility for {symbol}: {e}")
            return None
    
    def _calculate_volume_ratio(self, tick: MarketTick) -> Optional[Decimal]:
        """Calculate volume ratio compared to recent average"""
        try:
            symbol = tick.symbol
            volume_history = self._volume_history.get(symbol)
            
            if not volume_history or len(volume_history) < 5:
                return None
            
            # Calculate average volume (excluding current)
            recent_volumes = list(volume_history)[:-1] if len(volume_history) > 1 else list(volume_history)
            if not recent_volumes or tick.volume == 0:
                return None
            
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            if avg_volume == 0:
                return None
            
            volume_ratio = tick.volume / avg_volume
            return Decimal(str(round(volume_ratio, 4)))
            
        except Exception as e:
            logger.error(f"❌ Error calculating volume ratio for {symbol}: {e}")
            return None
    
    def _load_sector_mapping(self) -> Dict[str, str]:
        """Load sector mapping for stocks"""
        # This should be loaded from config/sector_mapping.json in production
        return {
            'RELIANCE': 'Oil & Gas',
            'TCS': 'IT Services',
            'HDFCBANK': 'Banking', 
            'INFY': 'IT Services',
            'HINDUNILVR': 'FMCG',
            'ICICIBANK': 'Banking',
            'SBIN': 'Banking',
            'BAJFINANCE': 'Financial Services',
            'BHARTIARTL': 'Telecommunications',
            'ITC': 'FMCG',
            'MARUTI': 'Automobiles',
            'WIPRO': 'IT Services',
            'AXISBANK': 'Banking',
            'LT': 'Construction',
            'ASIANPAINT': 'Paints'
        }
    
    def _determine_market_cap_category(self, price: Decimal) -> str:
        """Determine market cap category (simplified based on price)"""
        # This is a simplified approach - should use actual market cap data
        try:
            price_float = float(price)
            if price_float >= 2000:
                return 'large_cap'
            elif price_float >= 500:
                return 'mid_cap'
            else:
                return 'small_cap'
        except Exception:
            return 'unknown'
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get calculator statistics"""
        return {
            'symbols_tracked': len(self._price_history),
            'total_price_points': sum(len(history) for history in self._price_history.values()),
            'total_volume_points': sum(len(history) for history in self._volume_history.values()),
            'history_window_size': self._history_window_size
        }
    
    def clear_history_for_symbol(self, symbol: str) -> None:
        """Clear history for a specific symbol"""
        if symbol in self._price_history:
            self._price_history[symbol].clear()
        if symbol in self._volume_history:
            self._volume_history[symbol].clear()
    
    def clear_all_history(self) -> None:
        """Clear all historical data"""
        self._price_history.clear()
        self._volume_history.clear()
        logger.info("🧹 Cleared all calculator history")