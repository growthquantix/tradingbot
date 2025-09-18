"""
Enhanced Breakout Detection Calculator for Live Feed Data

Provides comprehensive breakout detection using live feed data format,
integrating with existing breakout engine and adding real-time analysis.

Breakout Types Detected:
- Resistance Breakouts (price > recent high)
- Support Breakdowns (price < recent low)  
- Volume Breakouts (volume > avg volume)
- Momentum Breakouts (strong price acceleration)
- Pattern Breakouts (triangles, flags, channels)

Author: Trading System
Created: 2025-01-11
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import numpy as np

from .base_calculator import BaseFeatureCalculator, calculate_moving_average, calculate_volatility

logger = logging.getLogger(__name__)


class BreakoutType(Enum):
    """Types of breakouts detected"""
    RESISTANCE_BREAKOUT = "resistance_breakout"
    SUPPORT_BREAKDOWN = "support_breakdown"
    VOLUME_BREAKOUT = "volume_breakout"
    MOMENTUM_BREAKOUT = "momentum_breakout"
    HIGH_BREAKOUT = "high_breakout"
    LOW_BREAKDOWN = "low_breakdown"
    VOLATILITY_EXPANSION = "volatility_expansion"
    TRIANGULAR_BREAKOUT = "triangular_breakout"
    CHANNEL_BREAKOUT = "channel_breakout"
    FLAG_BREAKOUT = "flag_breakout"


class BreakoutStrength(Enum):
    """Breakout strength classification"""
    WEAK = "WEAK"                    # 1-3% move
    MODERATE = "MODERATE"            # 3-5% move
    STRONG = "STRONG"                # 5-8% move
    VERY_STRONG = "VERY_STRONG"      # > 8% move


class BreakoutDirection(Enum):
    """Breakout direction"""
    BULLISH = "BULLISH"              # Upward breakout
    BEARISH = "BEARISH"              # Downward breakout
    NEUTRAL = "NEUTRAL"              # Sideways breakout


@dataclass
class BreakoutSignal:
    """Comprehensive breakout detection signal"""
    symbol: str
    instrument_key: str
    breakout_type: BreakoutType
    breakout_direction: BreakoutDirection
    breakout_strength: BreakoutStrength
    
    # Price data
    current_price: float
    breakout_level: float
    trigger_price: float
    percentage_move: float
    
    # Volume analysis
    volume: int
    avg_volume: float
    volume_ratio: float
    has_volume_confirmation: bool
    
    # Technical levels
    resistance_level: Optional[float] = None
    support_level: Optional[float] = None
    previous_high: Optional[float] = None
    previous_low: Optional[float] = None
    
    # Pattern analysis
    pattern_duration_bars: int = 0
    pattern_reliability: float = 0.0
    consolidation_range: float = 0.0
    
    # Signal quality
    confidence_score: float = 0.0
    strength_score: float = 0.0  # 1-10 scale
    is_significant: bool = False
    
    # Market context
    sector: str = "OTHER"
    market_cap_category: str = "UNKNOWN"
    volatility_score: float = 0.0
    
    # Trading context
    expected_target: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward_ratio: float = 0.0
    
    # Timing
    detection_time: datetime = field(default_factory=datetime.now)
    market_phase: str = "UNKNOWN"
    
    # Confirmation signals
    confirmation_signals: List[str] = field(default_factory=list)


@dataclass
class BreakoutSummary:
    """Summary of breakout analysis results"""
    total_breakouts: int
    bullish_breakouts: int
    bearish_breakouts: int
    significant_breakouts: int
    
    # By type
    breakout_type_distribution: Dict[str, int]
    
    # By strength  
    strength_distribution: Dict[str, int]
    
    # By sector
    sector_breakouts: Dict[str, int]
    
    # Top breakouts
    top_bullish_breakouts: List[BreakoutSignal]
    top_bearish_breakouts: List[BreakoutSignal]
    strongest_breakouts: List[BreakoutSignal]
    
    # Market analysis
    avg_breakout_strength: float
    volume_confirmed_breakouts: int
    pattern_breakouts: int
    
    calculation_timestamp: datetime


class BreakoutDetectionCalculator(BaseFeatureCalculator):
    """
    Enhanced Breakout Detection Calculator for Live Feed Data
    
    Features:
    - Multiple breakout type detection
    - Volume confirmation analysis
    - Pattern recognition (triangles, flags, channels)
    - Support/resistance level tracking
    - Real-time momentum analysis
    - Integration with existing breakout engine
    - Comprehensive signal validation
    """
    
    def __init__(
        self,
        lookback_periods: int = 20,              # Periods to look back for levels
        min_breakout_percentage: float = 1.0,    # Minimum 1% for breakout
        significant_threshold: float = 3.0,      # 3% for significant breakout
        volume_confirmation_ratio: float = 1.5,  # 1.5x volume for confirmation
        calculation_interval_ms: int = 3000      # Update every 3 seconds
    ):
        super().__init__(
            calculator_name="breakout_detection",
            calculation_interval_ms=calculation_interval_ms
        )
        
        # Breakout parameters
        self.lookback_periods = lookback_periods
        self.min_breakout_percentage = min_breakout_percentage
        self.significant_threshold = significant_threshold
        self.volume_confirmation_ratio = volume_confirmation_ratio
        
        # Technical analysis parameters
        self.resistance_touch_threshold = 0.5   # 0.5% from resistance to count as touch
        self.support_touch_threshold = 0.5      # 0.5% from support to count as touch
        self.consolidation_min_bars = 10        # Minimum bars for consolidation pattern
        
        # Price history storage for each instrument
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.lookback_periods * 2))
        self._volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.lookback_periods))
        self._high_low_tracker: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Detected breakouts storage
        self._detected_breakouts: Dict[str, List[BreakoutSignal]] = defaultdict(list)
        self._recent_breakouts: Dict[str, BreakoutSignal] = {}
        
        # Support/resistance levels
        self._support_levels: Dict[str, List[float]] = defaultdict(list)
        self._resistance_levels: Dict[str, List[float]] = defaultdict(list)
        
        logger.info(f"BreakoutDetectionCalculator initialized with {lookback_periods} period lookback")
    
    def _initialize_required_fields(self) -> None:
        """Initialize required fields for breakout detection"""
        self._required_fields = {
            'ltp', 'volume', 'high', 'low', 'open', 'instrument_key'
        }
    
    async def _calculate_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate breakout detection features from live feed data"""
        try:
            feeds = data.get('feeds', {})
            
            # Update price history and detect breakouts
            breakout_signals = []
            for instrument_key, feed_data in feeds.items():
                # Update historical data
                await self._update_price_history(instrument_key, feed_data)
                
                # Detect breakouts
                breakout_signal = await self._detect_breakouts_for_instrument(instrument_key, feed_data)
                if breakout_signal:
                    breakout_signals.append(breakout_signal)
                    self._recent_breakouts[instrument_key] = breakout_signal
                    self._detected_breakouts[instrument_key].append(breakout_signal)
            
            # Generate breakout summary
            breakout_summary = self._generate_breakout_summary(breakout_signals)
            
            return {
                'breakout_signals': [self._breakout_signal_to_dict(signal) for signal in breakout_signals],
                'breakout_summary': self._breakout_summary_to_dict(breakout_summary),
                'breakouts_by_type': self._categorize_breakouts_by_type(breakout_signals),
                'breakouts_by_direction': self._categorize_breakouts_by_direction(breakout_signals),
                'volume_analysis': self._analyze_volume_breakouts(breakout_signals),
                'pattern_analysis': self._analyze_pattern_breakouts(breakout_signals),
                'sector_analysis': self._analyze_breakouts_by_sector(breakout_signals),
                'trading_opportunities': self._identify_breakout_opportunities(breakout_signals),
                'total_breakouts': len(breakout_signals),
                'significant_breakouts': len([b for b in breakout_signals if b.is_significant])
            }
            
        except Exception as e:
            logger.error(f"Breakout detection calculation error: {e}")
            return self._get_empty_breakout_result()
    
    async def _update_price_history(self, instrument_key: str, feed_data: Dict[str, Any]) -> None:
        """Update price and volume history for instrument"""
        try:
            # Extract price data
            price_data = self._extract_price_data_from_feed(feed_data)
            if not price_data:
                return
            
            current_price = price_data['ltp']
            volume = price_data['volume']
            high = price_data.get('high', current_price)
            low = price_data.get('low', current_price)
            
            # Update price history
            price_point = {
                'price': current_price,
                'high': high,
                'low': low,
                'volume': volume,
                'timestamp': datetime.now()
            }
            
            self._price_history[instrument_key].append(price_point)
            self._volume_history[instrument_key].append(volume)
            
            # Update high/low tracker
            self._update_high_low_tracker(instrument_key, high, low)
            
            # Update support/resistance levels
            await self._update_support_resistance_levels(instrument_key)
            
        except Exception as e:
            logger.error(f"Price history update error for {instrument_key}: {e}")
    
    def _extract_price_data_from_feed(self, feed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract price data from live feed"""
        try:
            # Check normalized format first
            if 'ltp' in feed_data:
                return {
                    'ltp': float(feed_data.get('ltp', 0)),
                    'volume': int(feed_data.get('volume', 0)),
                    'high': float(feed_data.get('high', feed_data.get('ltp', 0))),
                    'low': float(feed_data.get('low', feed_data.get('ltp', 0))),
                    'open': float(feed_data.get('open', feed_data.get('ltp', 0)))
                }
            
            # Extract from raw Upstox format
            full_feed = feed_data.get('fullFeed', {})
            market_data = full_feed.get('marketFF') or full_feed.get('indexFF')
            
            if not market_data:
                return None
            
            # Extract LTPC
            ltpc = market_data.get('ltpc', {})
            ltp = float(ltpc.get('ltp', 0))
            
            # Extract OHLC
            ohlc_data = market_data.get('marketOHLC', {}).get('ohlc', [])
            high = low = open_price = ltp
            
            for ohlc in ohlc_data:
                if ohlc.get('interval') == '1d':
                    high = float(ohlc.get('high', ltp))
                    low = float(ohlc.get('low', ltp))
                    open_price = float(ohlc.get('open', ltp))
                    break
            
            # Extract volume
            volume = int(market_data.get('vtt', 0))
            
            return {
                'ltp': ltp,
                'volume': volume,
                'high': high,
                'low': low,
                'open': open_price
            }
            
        except Exception as e:
            logger.error(f"Price data extraction error: {e}")
            return None
    
    def _update_high_low_tracker(self, instrument_key: str, high: float, low: float) -> None:
        """Update running high/low tracker"""
        tracker = self._high_low_tracker[instrument_key]
        
        # Update period highs/lows
        if 'period_high' not in tracker or high > tracker['period_high']:
            tracker['period_high'] = high
            tracker['period_high_time'] = datetime.now()
        
        if 'period_low' not in tracker or low < tracker['period_low']:
            tracker['period_low'] = low
            tracker['period_low_time'] = datetime.now()
    
    async def _update_support_resistance_levels(self, instrument_key: str) -> None:
        """Update support and resistance levels based on price history"""
        try:
            price_history = list(self._price_history[instrument_key])
            if len(price_history) < self.lookback_periods:
                return
            
            # Extract highs and lows
            highs = [p['high'] for p in price_history]
            lows = [p['low'] for p in price_history]
            
            # Find resistance levels (local maxima)
            resistance_levels = self._find_resistance_levels(highs)
            self._resistance_levels[instrument_key] = resistance_levels
            
            # Find support levels (local minima)
            support_levels = self._find_support_levels(lows)
            self._support_levels[instrument_key] = support_levels
            
        except Exception as e:
            logger.error(f"Support/resistance update error for {instrument_key}: {e}")
    
    def _find_resistance_levels(self, highs: List[float]) -> List[float]:
        """Find resistance levels from price highs"""
        if len(highs) < 5:
            return []
        
        resistance_levels = []
        
        # Find local maxima
        for i in range(2, len(highs) - 2):
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                resistance_levels.append(highs[i])
        
        # Remove levels too close to each other (within 1%)
        filtered_levels = []
        for level in sorted(resistance_levels, reverse=True):
            is_unique = True
            for existing in filtered_levels:
                if abs(level - existing) / existing < 0.01:  # Within 1%
                    is_unique = False
                    break
            if is_unique:
                filtered_levels.append(level)
        
        return filtered_levels[:5]  # Top 5 resistance levels
    
    def _find_support_levels(self, lows: List[float]) -> List[float]:
        """Find support levels from price lows"""
        if len(lows) < 5:
            return []
        
        support_levels = []
        
        # Find local minima
        for i in range(2, len(lows) - 2):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                support_levels.append(lows[i])
        
        # Remove levels too close to each other
        filtered_levels = []
        for level in sorted(support_levels):
            is_unique = True
            for existing in filtered_levels:
                if abs(level - existing) / existing < 0.01:
                    is_unique = False
                    break
            if is_unique:
                filtered_levels.append(level)
        
        return filtered_levels[:5]  # Top 5 support levels
    
    async def _detect_breakouts_for_instrument(
        self, 
        instrument_key: str, 
        feed_data: Dict[str, Any]
    ) -> Optional[BreakoutSignal]:
        """Detect breakouts for a single instrument"""
        try:
            price_data = self._extract_price_data_from_feed(feed_data)
            if not price_data:
                return None
            
            current_price = price_data['ltp']
            volume = price_data['volume']
            high = price_data['high']
            low = price_data['low']
            
            symbol = self._extract_symbol_from_key(instrument_key)
            
            # Check for various breakout types
            breakout_signals = []
            
            # 1. Resistance breakout
            resistance_breakout = self._check_resistance_breakout(instrument_key, current_price, volume)
            if resistance_breakout:
                breakout_signals.append(resistance_breakout)
            
            # 2. Support breakdown
            support_breakdown = self._check_support_breakdown(instrument_key, current_price, volume)
            if support_breakdown:
                breakout_signals.append(support_breakdown)
            
            # 3. Volume breakout
            volume_breakout = self._check_volume_breakout(instrument_key, current_price, volume)
            if volume_breakout:
                breakout_signals.append(volume_breakout)
            
            # 4. Momentum breakout
            momentum_breakout = self._check_momentum_breakout(instrument_key, current_price, volume)
            if momentum_breakout:
                breakout_signals.append(momentum_breakout)
            
            # 5. High/Low breakout
            high_low_breakout = self._check_high_low_breakout(instrument_key, current_price, high, low, volume)
            if high_low_breakout:
                breakout_signals.append(high_low_breakout)
            
            # Return the strongest breakout signal
            if breakout_signals:
                strongest_breakout = max(breakout_signals, key=lambda x: x.strength_score)
                return strongest_breakout
            
            return None
            
        except Exception as e:
            logger.error(f"Breakout detection error for {instrument_key}: {e}")
            return None
    
    def _check_resistance_breakout(
        self, 
        instrument_key: str, 
        current_price: float, 
        volume: int
    ) -> Optional[BreakoutSignal]:
        """Check for resistance level breakout"""
        try:
            resistance_levels = self._resistance_levels.get(instrument_key, [])
            if not resistance_levels:
                return None
            
            # Find the nearest resistance level above current price
            nearest_resistance = None
            for level in resistance_levels:
                if level > current_price * 0.95:  # Within 5% below resistance
                    if nearest_resistance is None or level < nearest_resistance:
                        nearest_resistance = level
            
            if not nearest_resistance:
                return None
            
            # Check if price broke above resistance
            breakout_threshold = nearest_resistance * 1.005  # 0.5% above resistance
            if current_price > breakout_threshold:
                percentage_move = ((current_price - nearest_resistance) / nearest_resistance) * 100
                
                if percentage_move >= self.min_breakout_percentage:
                    # Calculate volume confirmation
                    avg_volume = self._calculate_average_volume(instrument_key)
                    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
                    has_volume_confirmation = volume_ratio >= self.volume_confirmation_ratio
                    
                    return self._create_breakout_signal(
                        instrument_key=instrument_key,
                        breakout_type=BreakoutType.RESISTANCE_BREAKOUT,
                        current_price=current_price,
                        breakout_level=nearest_resistance,
                        percentage_move=percentage_move,
                        volume=volume,
                        volume_ratio=volume_ratio,
                        has_volume_confirmation=has_volume_confirmation,
                        direction=BreakoutDirection.BULLISH
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Resistance breakout check error: {e}")
            return None
    
    def _check_support_breakdown(
        self, 
        instrument_key: str, 
        current_price: float, 
        volume: int
    ) -> Optional[BreakoutSignal]:
        """Check for support level breakdown"""
        try:
            support_levels = self._support_levels.get(instrument_key, [])
            if not support_levels:
                return None
            
            # Find the nearest support level below current price
            nearest_support = None
            for level in support_levels:
                if level < current_price * 1.05:  # Within 5% above support
                    if nearest_support is None or level > nearest_support:
                        nearest_support = level
            
            if not nearest_support:
                return None
            
            # Check if price broke below support
            breakdown_threshold = nearest_support * 0.995  # 0.5% below support
            if current_price < breakdown_threshold:
                percentage_move = ((nearest_support - current_price) / nearest_support) * 100
                
                if percentage_move >= self.min_breakout_percentage:
                    avg_volume = self._calculate_average_volume(instrument_key)
                    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
                    has_volume_confirmation = volume_ratio >= self.volume_confirmation_ratio
                    
                    return self._create_breakout_signal(
                        instrument_key=instrument_key,
                        breakout_type=BreakoutType.SUPPORT_BREAKDOWN,
                        current_price=current_price,
                        breakout_level=nearest_support,
                        percentage_move=percentage_move,
                        volume=volume,
                        volume_ratio=volume_ratio,
                        has_volume_confirmation=has_volume_confirmation,
                        direction=BreakoutDirection.BEARISH
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Support breakdown check error: {e}")
            return None
    
    def _check_volume_breakout(
        self, 
        instrument_key: str, 
        current_price: float, 
        volume: int
    ) -> Optional[BreakoutSignal]:
        """Check for volume breakout"""
        try:
            avg_volume = self._calculate_average_volume(instrument_key)
            if avg_volume <= 0:
                return None
            
            volume_ratio = volume / avg_volume
            
            # Volume breakout threshold (3x average volume)
            if volume_ratio >= 3.0:
                # Also check for price movement
                price_history = list(self._price_history[instrument_key])
                if len(price_history) < 2:
                    return None
                
                previous_price = price_history[-2]['price']
                percentage_move = ((current_price - previous_price) / previous_price) * 100
                
                if abs(percentage_move) >= 1.0:  # At least 1% price movement
                    direction = BreakoutDirection.BULLISH if percentage_move > 0 else BreakoutDirection.BEARISH
                    
                    return self._create_breakout_signal(
                        instrument_key=instrument_key,
                        breakout_type=BreakoutType.VOLUME_BREAKOUT,
                        current_price=current_price,
                        breakout_level=previous_price,
                        percentage_move=abs(percentage_move),
                        volume=volume,
                        volume_ratio=volume_ratio,
                        has_volume_confirmation=True,
                        direction=direction
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Volume breakout check error: {e}")
            return None
    
    def _check_momentum_breakout(
        self, 
        instrument_key: str, 
        current_price: float, 
        volume: int
    ) -> Optional[BreakoutSignal]:
        """Check for momentum breakout"""
        try:
            price_history = list(self._price_history[instrument_key])
            if len(price_history) < 5:
                return None
            
            # Calculate recent price changes
            recent_prices = [p['price'] for p in price_history[-5:]]
            price_changes = []
            
            for i in range(1, len(recent_prices)):
                change = ((recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]) * 100
                price_changes.append(change)
            
            # Check for accelerating momentum
            if len(price_changes) >= 3:
                # Check if momentum is accelerating
                is_accelerating = (
                    abs(price_changes[-1]) > abs(price_changes[-2]) and
                    abs(price_changes[-2]) > abs(price_changes[-3])
                )
                
                latest_change = price_changes[-1]
                if is_accelerating and abs(latest_change) >= 2.0:  # Strong momentum
                    avg_volume = self._calculate_average_volume(instrument_key)
                    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
                    
                    direction = BreakoutDirection.BULLISH if latest_change > 0 else BreakoutDirection.BEARISH
                    
                    return self._create_breakout_signal(
                        instrument_key=instrument_key,
                        breakout_type=BreakoutType.MOMENTUM_BREAKOUT,
                        current_price=current_price,
                        breakout_level=recent_prices[-2],
                        percentage_move=abs(latest_change),
                        volume=volume,
                        volume_ratio=volume_ratio,
                        has_volume_confirmation=volume_ratio >= self.volume_confirmation_ratio,
                        direction=direction
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Momentum breakout check error: {e}")
            return None
    
    def _check_high_low_breakout(
        self, 
        instrument_key: str, 
        current_price: float,
        high: float,
        low: float, 
        volume: int
    ) -> Optional[BreakoutSignal]:
        """Check for period high/low breakout"""
        try:
            tracker = self._high_low_tracker.get(instrument_key, {})
            if 'period_high' not in tracker or 'period_low' not in tracker:
                return None
            
            period_high = tracker['period_high']
            period_low = tracker['period_low']
            
            avg_volume = self._calculate_average_volume(instrument_key)
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
            
            # Check for new high breakout
            if high > period_high:
                percentage_move = ((high - period_high) / period_high) * 100
                if percentage_move >= self.min_breakout_percentage:
                    return self._create_breakout_signal(
                        instrument_key=instrument_key,
                        breakout_type=BreakoutType.HIGH_BREAKOUT,
                        current_price=current_price,
                        breakout_level=period_high,
                        percentage_move=percentage_move,
                        volume=volume,
                        volume_ratio=volume_ratio,
                        has_volume_confirmation=volume_ratio >= self.volume_confirmation_ratio,
                        direction=BreakoutDirection.BULLISH
                    )
            
            # Check for new low breakdown
            elif low < period_low:
                percentage_move = ((period_low - low) / period_low) * 100
                if percentage_move >= self.min_breakout_percentage:
                    return self._create_breakout_signal(
                        instrument_key=instrument_key,
                        breakout_type=BreakoutType.LOW_BREAKDOWN,
                        current_price=current_price,
                        breakout_level=period_low,
                        percentage_move=percentage_move,
                        volume=volume,
                        volume_ratio=volume_ratio,
                        has_volume_confirmation=volume_ratio >= self.volume_confirmation_ratio,
                        direction=BreakoutDirection.BEARISH
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"High/low breakout check error: {e}")
            return None
    
    def _calculate_average_volume(self, instrument_key: str) -> float:
        """Calculate average volume for instrument"""
        volume_history = list(self._volume_history[instrument_key])
        if not volume_history:
            return 0.0
        
        return sum(volume_history) / len(volume_history)
    
    def _create_breakout_signal(
        self,
        instrument_key: str,
        breakout_type: BreakoutType,
        current_price: float,
        breakout_level: float,
        percentage_move: float,
        volume: int,
        volume_ratio: float,
        has_volume_confirmation: bool,
        direction: BreakoutDirection
    ) -> BreakoutSignal:
        """Create a standardized breakout signal"""
        
        symbol = self._extract_symbol_from_key(instrument_key)
        
        # Determine breakout strength
        breakout_strength = self._determine_breakout_strength(percentage_move)
        
        # Calculate confidence and strength scores
        confidence_score = self._calculate_breakout_confidence(
            percentage_move, volume_ratio, has_volume_confirmation
        )
        strength_score = min(percentage_move, 10.0)  # Cap at 10
        
        # Determine significance
        is_significant = percentage_move >= self.significant_threshold
        
        # Calculate targets and stops
        expected_target, stop_loss = self._calculate_target_and_stop(
            current_price, breakout_level, direction, percentage_move
        )
        
        # Calculate risk-reward ratio
        risk_reward_ratio = self._calculate_risk_reward(
            current_price, expected_target, stop_loss
        )
        
        return BreakoutSignal(
            symbol=symbol,
            instrument_key=instrument_key,
            breakout_type=breakout_type,
            breakout_direction=direction,
            breakout_strength=breakout_strength,
            current_price=current_price,
            breakout_level=breakout_level,
            trigger_price=current_price,
            percentage_move=round(percentage_move, 2),
            volume=volume,
            avg_volume=self._calculate_average_volume(instrument_key),
            volume_ratio=round(volume_ratio, 2),
            has_volume_confirmation=has_volume_confirmation,
            confidence_score=round(confidence_score, 2),
            strength_score=round(strength_score, 1),
            is_significant=is_significant,
            expected_target=expected_target,
            stop_loss=stop_loss,
            risk_reward_ratio=round(risk_reward_ratio, 2),
            sector=self._get_sector_for_symbol(symbol),
            market_cap_category=self._estimate_market_cap_category(current_price)
        )
    
    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        return instrument_key.replace('|', '_').replace('NSE_EQ|', '').replace('NSE_INDEX|', '')
    
    def _determine_breakout_strength(self, percentage_move: float) -> BreakoutStrength:
        """Determine breakout strength from percentage move"""
        abs_move = abs(percentage_move)
        if abs_move >= 8.0:
            return BreakoutStrength.VERY_STRONG
        elif abs_move >= 5.0:
            return BreakoutStrength.STRONG
        elif abs_move >= 3.0:
            return BreakoutStrength.MODERATE
        else:
            return BreakoutStrength.WEAK
    
    def _calculate_breakout_confidence(
        self, 
        percentage_move: float, 
        volume_ratio: float,
        has_volume_confirmation: bool
    ) -> float:
        """Calculate confidence score for breakout"""
        confidence = 0.5  # Base confidence
        
        # Percentage move factor
        if abs(percentage_move) >= 5.0:
            confidence += 0.3
        elif abs(percentage_move) >= 3.0:
            confidence += 0.2
        elif abs(percentage_move) >= 1.5:
            confidence += 0.1
        
        # Volume factor
        if has_volume_confirmation:
            confidence += 0.2
        elif volume_ratio >= 1.2:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_target_and_stop(
        self, 
        current_price: float, 
        breakout_level: float,
        direction: BreakoutDirection,
        percentage_move: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate target and stop loss levels"""
        try:
            if direction == BreakoutDirection.BULLISH:
                # Target: Current price + breakout move
                target = current_price + (current_price - breakout_level)
                # Stop: Just below breakout level
                stop = breakout_level * 0.98  # 2% below breakout level
            else:
                # Target: Current price - breakout move  
                target = current_price - (breakout_level - current_price)
                # Stop: Just above breakout level
                stop = breakout_level * 1.02  # 2% above breakout level
            
            return target, stop
            
        except Exception:
            return None, None
    
    def _calculate_risk_reward(
        self, 
        current_price: float,
        target: Optional[float], 
        stop: Optional[float]
    ) -> float:
        """Calculate risk-reward ratio"""
        if not target or not stop:
            return 0.0
        
        try:
            reward = abs(target - current_price)
            risk = abs(current_price - stop)
            
            if risk > 0:
                return reward / risk
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    def _get_sector_for_symbol(self, symbol: str) -> str:
        """Get sector for symbol"""
        return "OTHER"  # Would integrate with instrument registry
    
    def _estimate_market_cap_category(self, price: float) -> str:
        """Estimate market cap category"""
        if price > 1000:
            return "LARGE_CAP"
        elif price > 100:
            return "MID_CAP"
        else:
            return "SMALL_CAP"
    
    # Summary and analysis methods
    def _generate_breakout_summary(self, breakout_signals: List[BreakoutSignal]) -> BreakoutSummary:
        """Generate comprehensive breakout summary"""
        if not breakout_signals:
            return self._get_empty_breakout_summary()
        
        bullish_breakouts = [b for b in breakout_signals if b.breakout_direction == BreakoutDirection.BULLISH]
        bearish_breakouts = [b for b in breakout_signals if b.breakout_direction == BreakoutDirection.BEARISH]
        significant_breakouts = [b for b in breakout_signals if b.is_significant]
        
        # Type distribution
        type_dist = defaultdict(int)
        for breakout in breakout_signals:
            type_dist[breakout.breakout_type.value] += 1
        
        # Strength distribution
        strength_dist = defaultdict(int)
        for breakout in breakout_signals:
            strength_dist[breakout.breakout_strength.value] += 1
        
        # Sector distribution
        sector_dist = defaultdict(int)
        for breakout in breakout_signals:
            sector_dist[breakout.sector] += 1
        
        # Top breakouts
        top_bullish = sorted(bullish_breakouts, key=lambda x: x.strength_score, reverse=True)[:5]
        top_bearish = sorted(bearish_breakouts, key=lambda x: x.strength_score, reverse=True)[:5]
        strongest = sorted(breakout_signals, key=lambda x: x.strength_score, reverse=True)[:10]
        
        # Statistics
        avg_strength = sum(b.percentage_move for b in breakout_signals) / len(breakout_signals)
        volume_confirmed = len([b for b in breakout_signals if b.has_volume_confirmation])
        pattern_breakouts = len([b for b in breakout_signals if 'pattern' in b.breakout_type.value.lower()])
        
        return BreakoutSummary(
            total_breakouts=len(breakout_signals),
            bullish_breakouts=len(bullish_breakouts),
            bearish_breakouts=len(bearish_breakouts),
            significant_breakouts=len(significant_breakouts),
            breakout_type_distribution=dict(type_dist),
            strength_distribution=dict(strength_dist),
            sector_breakouts=dict(sector_dist),
            top_bullish_breakouts=top_bullish,
            top_bearish_breakouts=top_bearish,
            strongest_breakouts=strongest,
            avg_breakout_strength=round(avg_strength, 2),
            volume_confirmed_breakouts=volume_confirmed,
            pattern_breakouts=pattern_breakouts,
            calculation_timestamp=datetime.now()
        )
    
    def _categorize_breakouts_by_type(self, breakouts: List[BreakoutSignal]) -> Dict[str, int]:
        """Categorize breakouts by type"""
        type_counts = defaultdict(int)
        for breakout in breakouts:
            type_counts[breakout.breakout_type.value] += 1
        return dict(type_counts)
    
    def _categorize_breakouts_by_direction(self, breakouts: List[BreakoutSignal]) -> Dict[str, int]:
        """Categorize breakouts by direction"""
        return {
            'BULLISH': len([b for b in breakouts if b.breakout_direction == BreakoutDirection.BULLISH]),
            'BEARISH': len([b for b in breakouts if b.breakout_direction == BreakoutDirection.BEARISH])
        }
    
    def _analyze_volume_breakouts(self, breakouts: List[BreakoutSignal]) -> Dict[str, Any]:
        """Analyze volume-related breakouts"""
        volume_breakouts = [b for b in breakouts if b.breakout_type == BreakoutType.VOLUME_BREAKOUT]
        volume_confirmed = [b for b in breakouts if b.has_volume_confirmation]
        
        return {
            'volume_breakouts_count': len(volume_breakouts),
            'volume_confirmed_count': len(volume_confirmed),
            'avg_volume_ratio': round(
                sum(b.volume_ratio for b in breakouts) / len(breakouts) if breakouts else 0, 2
            )
        }
    
    def _analyze_pattern_breakouts(self, breakouts: List[BreakoutSignal]) -> Dict[str, Any]:
        """Analyze pattern-based breakouts"""
        pattern_types = [BreakoutType.TRIANGULAR_BREAKOUT, BreakoutType.CHANNEL_BREAKOUT, BreakoutType.FLAG_BREAKOUT]
        pattern_breakouts = [b for b in breakouts if b.breakout_type in pattern_types]
        
        return {
            'pattern_breakouts_count': len(pattern_breakouts),
            'pattern_types_detected': list(set(b.breakout_type.value for b in pattern_breakouts))
        }
    
    def _analyze_breakouts_by_sector(self, breakouts: List[BreakoutSignal]) -> Dict[str, Any]:
        """Analyze breakouts by sector"""
        sector_analysis = defaultdict(lambda: {'bullish': 0, 'bearish': 0, 'total': 0})
        
        for breakout in breakouts:
            sector = breakout.sector
            sector_analysis[sector]['total'] += 1
            if breakout.breakout_direction == BreakoutDirection.BULLISH:
                sector_analysis[sector]['bullish'] += 1
            else:
                sector_analysis[sector]['bearish'] += 1
        
        return dict(sector_analysis)
    
    def _identify_breakout_opportunities(self, breakouts: List[BreakoutSignal]) -> List[Dict[str, Any]]:
        """Identify high-probability breakout trading opportunities"""
        opportunities = []
        
        for breakout in breakouts:
            if (breakout.is_significant and 
                breakout.confidence_score > 0.7 and
                breakout.has_volume_confirmation and
                breakout.risk_reward_ratio > 1.5):
                
                opportunities.append({
                    'symbol': breakout.symbol,
                    'breakout_type': breakout.breakout_type.value,
                    'direction': breakout.breakout_direction.value,
                    'strength': breakout.breakout_strength.value,
                    'percentage_move': breakout.percentage_move,
                    'confidence': breakout.confidence_score,
                    'risk_reward': breakout.risk_reward_ratio,
                    'target': breakout.expected_target,
                    'stop_loss': breakout.stop_loss
                })
        
        return sorted(opportunities, key=lambda x: x['confidence'], reverse=True)[:15]
    
    def _breakout_signal_to_dict(self, signal: BreakoutSignal) -> Dict[str, Any]:
        """Convert BreakoutSignal to dictionary"""
        return {
            'symbol': signal.symbol,
            'instrument_key': signal.instrument_key,
            'breakout_type': signal.breakout_type.value,
            'direction': signal.breakout_direction.value,
            'strength': signal.breakout_strength.value,
            'current_price': signal.current_price,
            'breakout_level': signal.breakout_level,
            'percentage_move': signal.percentage_move,
            'volume': signal.volume,
            'volume_ratio': signal.volume_ratio,
            'has_volume_confirmation': signal.has_volume_confirmation,
            'confidence_score': signal.confidence_score,
            'strength_score': signal.strength_score,
            'is_significant': signal.is_significant,
            'expected_target': signal.expected_target,
            'stop_loss': signal.stop_loss,
            'risk_reward_ratio': signal.risk_reward_ratio,
            'sector': signal.sector,
            'detection_time': signal.detection_time.isoformat()
        }
    
    def _breakout_summary_to_dict(self, summary: BreakoutSummary) -> Dict[str, Any]:
        """Convert BreakoutSummary to dictionary"""
        return {
            'total_breakouts': summary.total_breakouts,
            'bullish_breakouts': summary.bullish_breakouts,
            'bearish_breakouts': summary.bearish_breakouts,
            'significant_breakouts': summary.significant_breakouts,
            'type_distribution': summary.breakout_type_distribution,
            'strength_distribution': summary.strength_distribution,
            'sector_distribution': summary.sector_breakouts,
            'statistics': {
                'avg_breakout_strength': summary.avg_breakout_strength,
                'volume_confirmed_breakouts': summary.volume_confirmed_breakouts,
                'pattern_breakouts': summary.pattern_breakouts
            },
            'top_bullish': [self._breakout_signal_to_dict(b) for b in summary.top_bullish_breakouts],
            'top_bearish': [self._breakout_signal_to_dict(b) for b in summary.top_bearish_breakouts],
            'strongest': [self._breakout_signal_to_dict(b) for b in summary.strongest_breakouts],
            'calculation_timestamp': summary.calculation_timestamp.isoformat()
        }
    
    def _get_empty_breakout_result(self) -> Dict[str, Any]:
        """Get empty breakout result"""
        return {
            'breakout_signals': [],
            'breakout_summary': self._breakout_summary_to_dict(self._get_empty_breakout_summary()),
            'breakouts_by_type': {},
            'breakouts_by_direction': {'BULLISH': 0, 'BEARISH': 0},
            'volume_analysis': {'volume_breakouts_count': 0, 'volume_confirmed_count': 0},
            'pattern_analysis': {'pattern_breakouts_count': 0, 'pattern_types_detected': []},
            'sector_analysis': {},
            'trading_opportunities': [],
            'total_breakouts': 0,
            'significant_breakouts': 0
        }
    
    def _get_empty_breakout_summary(self) -> BreakoutSummary:
        """Get empty breakout summary"""
        return BreakoutSummary(
            total_breakouts=0,
            bullish_breakouts=0,
            bearish_breakouts=0,
            significant_breakouts=0,
            breakout_type_distribution={},
            strength_distribution={},
            sector_breakouts={},
            top_bullish_breakouts=[],
            top_bearish_breakouts=[],
            strongest_breakouts=[],
            avg_breakout_strength=0.0,
            volume_confirmed_breakouts=0,
            pattern_breakouts=0,
            calculation_timestamp=datetime.now()
        )


# Singleton instance
_breakout_detection_calculator: Optional[BreakoutDetectionCalculator] = None


def get_breakout_detection_calculator() -> BreakoutDetectionCalculator:
    """Get singleton breakout detection calculator instance"""
    global _breakout_detection_calculator
    if _breakout_detection_calculator is None:
        _breakout_detection_calculator = BreakoutDetectionCalculator()
    return _breakout_detection_calculator


# Export main classes
__all__ = [
    "BreakoutDetectionCalculator",
    "BreakoutSignal",
    "BreakoutSummary",
    "BreakoutType",
    "BreakoutStrength", 
    "BreakoutDirection",
    "get_breakout_detection_calculator"
]