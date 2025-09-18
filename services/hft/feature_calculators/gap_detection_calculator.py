"""
Enhanced Gap Detection Calculator for Live Feed Data

Provides accurate gap up/down detection based on live feed data format,
focusing on premarket analysis and real-time gap identification.

Gap Detection Logic:
- Gap Up: open_price > previous_close (positive gap)
- Gap Down: open_price < previous_close (negative gap)
- Uses live feed OHLC data and previous close from ltpc.cp

Author: Trading System
Created: 2025-01-11
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time as dt_time
from enum import Enum
from collections import defaultdict

from .base_calculator import BaseFeatureCalculator, calculate_percentage_change, safe_divide

logger = logging.getLogger(__name__)


class GapType(Enum):
    """Gap types for classification"""
    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    NO_GAP = "NO_GAP"


class GapStrength(Enum):
    """Gap strength classification"""
    WEAK = "WEAK"                    # 0.5% - 2.5%
    MODERATE = "MODERATE"            # 2.5% - 5.0%
    STRONG = "STRONG"                # 5.0% - 8.0%
    VERY_STRONG = "VERY_STRONG"      # > 8.0%


class GapTiming(Enum):
    """Gap timing classification"""
    PREMARKET = "PREMARKET"          # 9:00-9:08 AM
    MARKET_OPEN = "MARKET_OPEN"      # 9:15 AM onwards
    INTRADAY = "INTRADAY"            # During market hours


@dataclass
class GapSignal:
    """Comprehensive gap detection signal"""
    symbol: str
    instrument_key: str
    gap_type: GapType
    gap_percentage: float
    gap_strength: GapStrength
    gap_timing: GapTiming
    
    # Price data
    current_price: float
    open_price: float
    previous_close: float
    gap_amount: float
    
    # Volume analysis
    volume: int
    volume_ratio: float
    has_volume_confirmation: bool
    
    # Technical analysis
    is_significant: bool
    confidence_score: float
    fill_probability: float
    
    # Market context
    sector: str
    market_cap_category: str
    market_sentiment_alignment: bool
    
    # Timing
    detection_time: datetime
    market_phase: str
    
    # Additional metadata
    resistance_levels: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)
    trading_strategy: str = "HOLD"
    risk_reward_ratio: float = 0.0


@dataclass
class GapSummary:
    """Summary of gap analysis results"""
    total_gaps_detected: int
    gap_up_count: int
    gap_down_count: int
    significant_gaps: int
    
    # By strength
    weak_gaps: int
    moderate_gaps: int
    strong_gaps: int
    very_strong_gaps: int
    
    # By sector
    sector_gap_distribution: Dict[str, int]
    
    # Top gaps
    top_gap_ups: List[GapSignal]
    top_gap_downs: List[GapSignal]
    
    # Market statistics
    avg_gap_percentage: float
    max_gap_percentage: float
    min_gap_percentage: float
    
    calculation_timestamp: datetime


class GapDetectionCalculator(BaseFeatureCalculator):
    """
    Enhanced Gap Detection Calculator for Live Feed Data
    
    Features:
    - Accurate gap detection using live feed OHLC data
    - Previous close extraction from ltpc.cp field
    - Premarket gap analysis (9:00-9:08 AM)
    - Real-time gap monitoring during market hours
    - Volume confirmation analysis
    - Gap strength classification
    - Gap fill probability estimation
    - Trading strategy recommendations
    """
    
    def __init__(
        self,
        min_gap_threshold: float = 0.5,          # Minimum 0.5% for gap detection
        significant_gap_threshold: float = 2.0,   # 2.0% for significant gaps
        calculation_interval_ms: int = 2000       # Update every 2 seconds
    ):
        super().__init__(
            calculator_name="gap_detection",
            calculation_interval_ms=calculation_interval_ms
        )
        
        # Gap detection parameters
        self.min_gap_threshold = min_gap_threshold
        self.significant_gap_threshold = significant_gap_threshold
        
        # Gap strength thresholds
        self.weak_threshold = 2.5
        self.moderate_threshold = 5.0
        self.strong_threshold = 8.0
        
        # Volume confirmation parameters
        self.min_volume_ratio = 1.5  # 1.5x average volume for confirmation
        self.high_volume_ratio = 3.0  # 3x for strong confirmation
        
        # Storage for gap analysis
        self._detected_gaps: Dict[str, GapSignal] = {}
        self._gap_history: Dict[str, List[GapSignal]] = defaultdict(list)
        self._previous_closes: Dict[str, float] = {}
        self._average_volumes: Dict[str, float] = {}
        
        # Market timing
        self._market_open_time = dt_time(9, 15)  # 9:15 AM IST
        self._premarket_start = dt_time(9, 0)    # 9:00 AM IST
        self._premarket_end = dt_time(9, 8)      # 9:08 AM IST
        
        logger.info(f"GapDetectionCalculator initialized with {min_gap_threshold}% threshold")
    
    def _initialize_required_fields(self) -> None:
        """Initialize required fields for gap detection"""
        self._required_fields = {
            'ltp', 'previous_close', 'open', 'volume', 'instrument_key'
        }
    
    async def _calculate_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate gap detection features from live feed data"""
        try:
            feeds = data.get('feeds', {})
            
            # Analyze gaps for each instrument
            gap_signals = []
            for instrument_key, feed_data in feeds.items():
                gap_signal = await self._analyze_gap_for_instrument(instrument_key, feed_data)
                if gap_signal:
                    gap_signals.append(gap_signal)
                    self._detected_gaps[instrument_key] = gap_signal
                    self._gap_history[instrument_key].append(gap_signal)
            
            # Generate gap summary
            gap_summary = self._generate_gap_summary(gap_signals)
            
            # Determine market phase
            market_phase = self._get_current_market_phase()
            
            return {
                'gap_signals': [self._gap_signal_to_dict(signal) for signal in gap_signals],
                'gap_summary': self._gap_summary_to_dict(gap_summary),
                'market_phase': market_phase,
                'gaps_by_type': self._categorize_gaps_by_type(gap_signals),
                'gaps_by_strength': self._categorize_gaps_by_strength(gap_signals),
                'sector_analysis': self._analyze_gaps_by_sector(gap_signals),
                'trading_opportunities': self._identify_trading_opportunities(gap_signals),
                'total_gaps_detected': len(gap_signals),
                'significant_gaps_count': len([g for g in gap_signals if g.is_significant])
            }
            
        except Exception as e:
            logger.error(f"Gap detection calculation error: {e}")
            return self._get_empty_gap_result()
    
    async def _analyze_gap_for_instrument(
        self, 
        instrument_key: str, 
        feed_data: Dict[str, Any]
    ) -> Optional[GapSignal]:
        """Analyze gap for a single instrument using live feed data"""
        try:
            # Extract price data from live feed format
            price_data = self._extract_price_data_from_live_feed(instrument_key, feed_data)
            if not price_data:
                return None
            
            current_price = price_data['ltp']
            previous_close = price_data['previous_close']
            open_price = price_data['open']
            volume = price_data['volume']
            symbol = price_data['symbol']
            
            # Validate price data
            if previous_close <= 0 or open_price <= 0:
                return None
            
            # Calculate gap percentage: (open - previous_close) / previous_close * 100
            gap_amount = open_price - previous_close
            gap_percentage = (gap_amount / previous_close) * 100
            
            # Check if gap meets minimum threshold
            if abs(gap_percentage) < self.min_gap_threshold:
                return None  # No significant gap
            
            # Determine gap type
            gap_type = self._determine_gap_type(gap_percentage)
            if gap_type == GapType.NO_GAP:
                return None
            
            # Determine gap strength
            gap_strength = self._determine_gap_strength(abs(gap_percentage))
            
            # Determine market timing
            gap_timing = self._determine_gap_timing()
            
            # Volume analysis
            volume_ratio = self._calculate_volume_ratio(symbol, volume)
            has_volume_confirmation = self._check_volume_confirmation(volume, volume_ratio)
            
            # Calculate significance and confidence
            is_significant = abs(gap_percentage) >= self.significant_gap_threshold
            confidence_score = self._calculate_confidence_score(
                gap_percentage, volume, volume_ratio, gap_timing
            )
            
            # Calculate gap fill probability
            fill_probability = self._calculate_gap_fill_probability(
                gap_percentage, volume_ratio, gap_timing
            )
            
            # Get market context
            sector = self._get_sector_for_symbol(symbol)
            market_cap_category = self._estimate_market_cap_category(current_price)
            market_sentiment_alignment = self._check_market_sentiment_alignment(gap_type)
            
            # Determine trading strategy
            trading_strategy = self._determine_trading_strategy(
                gap_type, gap_strength, fill_probability, volume_ratio
            )
            
            # Calculate risk-reward ratio
            risk_reward_ratio = self._calculate_risk_reward_ratio(
                current_price, gap_percentage, gap_type
            )
            
            return GapSignal(
                symbol=symbol,
                instrument_key=instrument_key,
                gap_type=gap_type,
                gap_percentage=round(gap_percentage, 2),
                gap_strength=gap_strength,
                gap_timing=gap_timing,
                current_price=current_price,
                open_price=open_price,
                previous_close=previous_close,
                gap_amount=gap_amount,
                volume=volume,
                volume_ratio=volume_ratio,
                has_volume_confirmation=has_volume_confirmation,
                is_significant=is_significant,
                confidence_score=confidence_score,
                fill_probability=fill_probability,
                sector=sector,
                market_cap_category=market_cap_category,
                market_sentiment_alignment=market_sentiment_alignment,
                detection_time=datetime.now(),
                market_phase=gap_timing.value,
                trading_strategy=trading_strategy,
                risk_reward_ratio=risk_reward_ratio
            )
            
        except Exception as e:
            logger.error(f"Gap analysis error for {instrument_key}: {e}")
            return None
    
    def _extract_price_data_from_live_feed(
        self, 
        instrument_key: str, 
        feed_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract price data from live feed using the documented format
        
        Live Feed Format:
        {
          "feeds": {
            "NSE_EQ|INE318A01026": {
              "fullFeed": {
                "marketFF": {
                  "ltpc": {
                    "ltp": 3097.7,          // Last traded price
                    "cp": 3095.1            // Previous close price
                  },
                  "marketOHLC": {
                    "ohlc": [
                      {
                        "interval": "1d",
                        "open": 3094.0,       // Open price
                        "high": 3115.4,
                        "low": 3081.0,
                        "close": 3097.7,
                        "vol": "31929"        // Volume
                      }
                    ]
                  },
                  "vtt": "31929"            // Total volume traded
                }
              }
            }
          }
        }
        """
        try:
            # Check if data is already normalized
            if 'ltp' in feed_data and 'previous_close' in feed_data:
                # Already normalized format
                return {
                    'symbol': self._extract_symbol_from_key(instrument_key),
                    'ltp': float(feed_data.get('ltp', 0)),
                    'previous_close': float(feed_data.get('previous_close', 0)),
                    'open': float(feed_data.get('open', 0)),
                    'volume': int(feed_data.get('volume', 0))
                }
            
            # Extract from raw Upstox format
            full_feed = feed_data.get('fullFeed', {})
            market_data = full_feed.get('marketFF') or full_feed.get('indexFF')
            
            if not market_data:
                return None
            
            # Extract LTPC (Last Traded Price & Close)
            ltpc = market_data.get('ltpc', {})
            if not ltpc:
                return None
            
            ltp = float(ltpc.get('ltp', 0))
            previous_close = float(ltpc.get('cp', 0))  # cp = close price (previous close)
            
            if ltp <= 0 or previous_close <= 0:
                return None
            
            # Extract OHLC data
            ohlc_data = market_data.get('marketOHLC', {}).get('ohlc', [])
            open_price = ltp  # Default to LTP if no OHLC
            
            # Find daily OHLC data
            for ohlc in ohlc_data:
                if ohlc.get('interval') == '1d':
                    open_price = float(ohlc.get('open', ltp))
                    break
            
            # Extract volume
            volume = int(market_data.get('vtt', 0))  # vtt = volume total traded
            
            symbol = self._extract_symbol_from_key(instrument_key)
            
            return {
                'symbol': symbol,
                'ltp': ltp,
                'previous_close': previous_close,
                'open': open_price,
                'volume': volume
            }
            
        except Exception as e:
            logger.error(f"Price data extraction error for {instrument_key}: {e}")
            return None
    
    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract trading symbol from instrument key"""
        # This would need integration with instrument registry for proper symbol mapping
        # For now, return simplified representation
        return instrument_key.replace('|', '_').replace('NSE_EQ|', '').replace('NSE_INDEX|', '')
    
    def _determine_gap_type(self, gap_percentage: float) -> GapType:
        """Determine gap type based on percentage"""
        if gap_percentage > self.min_gap_threshold:
            return GapType.GAP_UP
        elif gap_percentage < -self.min_gap_threshold:
            return GapType.GAP_DOWN
        else:
            return GapType.NO_GAP
    
    def _determine_gap_strength(self, abs_gap_percentage: float) -> GapStrength:
        """Determine gap strength based on absolute percentage"""
        if abs_gap_percentage >= self.strong_threshold:
            return GapStrength.VERY_STRONG
        elif abs_gap_percentage >= self.moderate_threshold:
            return GapStrength.STRONG
        elif abs_gap_percentage >= self.weak_threshold:
            return GapStrength.MODERATE
        else:
            return GapStrength.WEAK
    
    def _determine_gap_timing(self) -> GapTiming:
        """Determine gap timing based on current time"""
        current_time = datetime.now().time()
        
        if self._premarket_start <= current_time <= self._premarket_end:
            return GapTiming.PREMARKET
        elif current_time >= self._market_open_time:
            return GapTiming.MARKET_OPEN
        else:
            return GapTiming.INTRADAY
    
    def _calculate_volume_ratio(self, symbol: str, current_volume: int) -> float:
        """Calculate volume ratio compared to average"""
        avg_volume = self._average_volumes.get(symbol, current_volume)
        if avg_volume > 0:
            return current_volume / avg_volume
        return 1.0
    
    def _check_volume_confirmation(self, volume: int, volume_ratio: float) -> bool:
        """Check if volume confirms the gap"""
        return volume_ratio >= self.min_volume_ratio and volume > 10000
    
    def _calculate_confidence_score(
        self, 
        gap_percentage: float, 
        volume: int, 
        volume_ratio: float,
        gap_timing: GapTiming
    ) -> float:
        """Calculate confidence score for gap signal"""
        score = 0.5  # Base score
        
        # Gap size factor
        if abs(gap_percentage) >= 5.0:
            score += 0.3
        elif abs(gap_percentage) >= 2.5:
            score += 0.2
        elif abs(gap_percentage) >= 1.0:
            score += 0.1
        
        # Volume factor
        if volume_ratio >= 3.0:
            score += 0.2
        elif volume_ratio >= 1.5:
            score += 0.1
        
        # Timing factor
        if gap_timing == GapTiming.PREMARKET:
            score += 0.1  # Premarket gaps are more reliable
        
        return min(score, 1.0)
    
    def _calculate_gap_fill_probability(
        self, 
        gap_percentage: float, 
        volume_ratio: float,
        gap_timing: GapTiming
    ) -> float:
        """Calculate probability that gap will be filled"""
        # Base probability (80% of gaps are filled eventually)
        fill_prob = 0.8
        
        # Larger gaps are less likely to be filled quickly
        if abs(gap_percentage) > 5.0:
            fill_prob -= 0.3
        elif abs(gap_percentage) > 2.5:
            fill_prob -= 0.2
        
        # High volume gaps are more likely to sustain
        if volume_ratio > 3.0:
            fill_prob -= 0.2
        
        # Premarket gaps are more likely to be filled
        if gap_timing == GapTiming.PREMARKET:
            fill_prob += 0.1
        
        return max(0.1, min(fill_prob, 0.95))
    
    def _get_sector_for_symbol(self, symbol: str) -> str:
        """Get sector for symbol (would integrate with instrument registry)"""
        # Simplified sector mapping
        return "OTHER"  # Would be retrieved from instrument registry
    
    def _estimate_market_cap_category(self, current_price: float) -> str:
        """Estimate market cap category based on price (simplified)"""
        if current_price > 1000:
            return "LARGE_CAP"
        elif current_price > 100:
            return "MID_CAP"
        else:
            return "SMALL_CAP"
    
    def _check_market_sentiment_alignment(self, gap_type: GapType) -> bool:
        """Check if gap aligns with overall market sentiment"""
        # Would integrate with market sentiment analysis
        return True  # Simplified
    
    def _determine_trading_strategy(
        self, 
        gap_type: GapType, 
        gap_strength: GapStrength,
        fill_probability: float,
        volume_ratio: float
    ) -> str:
        """Determine recommended trading strategy"""
        if gap_type == GapType.GAP_UP:
            if gap_strength in [GapStrength.STRONG, GapStrength.VERY_STRONG] and volume_ratio > 2.0:
                return "MOMENTUM_LONG"
            elif fill_probability > 0.7:
                return "FADE_GAP"
            else:
                return "WAIT_AND_WATCH"
        
        elif gap_type == GapType.GAP_DOWN:
            if gap_strength in [GapStrength.STRONG, GapStrength.VERY_STRONG] and volume_ratio > 2.0:
                return "MOMENTUM_SHORT"
            elif fill_probability > 0.7:
                return "BUY_DIP"
            else:
                return "WAIT_AND_WATCH"
        
        return "HOLD"
    
    def _calculate_risk_reward_ratio(
        self, 
        current_price: float, 
        gap_percentage: float,
        gap_type: GapType
    ) -> float:
        """Calculate risk-reward ratio for gap trade"""
        if gap_type == GapType.GAP_UP:
            # For gap up: target = gap continuation, stop = gap fill
            target = abs(gap_percentage) * 0.5  # 50% of gap size as target
            stop = abs(gap_percentage) * 1.0    # Full gap as stop
        else:
            # For gap down: target = bounce, stop = further decline
            target = abs(gap_percentage) * 0.3
            stop = abs(gap_percentage) * 0.7
        
        return safe_divide(target, stop, 0.5)
    
    def _generate_gap_summary(self, gap_signals: List[GapSignal]) -> GapSummary:
        """Generate summary of gap analysis"""
        if not gap_signals:
            return self._get_empty_gap_summary()
        
        gap_up_signals = [g for g in gap_signals if g.gap_type == GapType.GAP_UP]
        gap_down_signals = [g for g in gap_signals if g.gap_type == GapType.GAP_DOWN]
        significant_gaps = [g for g in gap_signals if g.is_significant]
        
        # Count by strength
        weak_gaps = len([g for g in gap_signals if g.gap_strength == GapStrength.WEAK])
        moderate_gaps = len([g for g in gap_signals if g.gap_strength == GapStrength.MODERATE])
        strong_gaps = len([g for g in gap_signals if g.gap_strength == GapStrength.STRONG])
        very_strong_gaps = len([g for g in gap_signals if g.gap_strength == GapStrength.VERY_STRONG])
        
        # Sector distribution
        sector_distribution = defaultdict(int)
        for gap in gap_signals:
            sector_distribution[gap.sector] += 1
        
        # Top gaps
        top_gap_ups = sorted(gap_up_signals, key=lambda x: x.gap_percentage, reverse=True)[:5]
        top_gap_downs = sorted(gap_down_signals, key=lambda x: abs(x.gap_percentage), reverse=True)[:5]
        
        # Statistics
        all_percentages = [g.gap_percentage for g in gap_signals]
        avg_gap = sum(all_percentages) / len(all_percentages)
        max_gap = max(all_percentages)
        min_gap = min(all_percentages)
        
        return GapSummary(
            total_gaps_detected=len(gap_signals),
            gap_up_count=len(gap_up_signals),
            gap_down_count=len(gap_down_signals),
            significant_gaps=len(significant_gaps),
            weak_gaps=weak_gaps,
            moderate_gaps=moderate_gaps,
            strong_gaps=strong_gaps,
            very_strong_gaps=very_strong_gaps,
            sector_gap_distribution=dict(sector_distribution),
            top_gap_ups=top_gap_ups,
            top_gap_downs=top_gap_downs,
            avg_gap_percentage=round(avg_gap, 2),
            max_gap_percentage=round(max_gap, 2),
            min_gap_percentage=round(min_gap, 2),
            calculation_timestamp=datetime.now()
        )
    
    def _get_current_market_phase(self) -> str:
        """Get current market phase"""
        current_time = datetime.now().time()
        
        if self._premarket_start <= current_time <= self._premarket_end:
            return "PREMARKET"
        elif current_time >= self._market_open_time:
            return "MARKET_HOURS"
        else:
            return "PRE_PREMARKET"
    
    def _categorize_gaps_by_type(self, gap_signals: List[GapSignal]) -> Dict[str, int]:
        """Categorize gaps by type"""
        return {
            'GAP_UP': len([g for g in gap_signals if g.gap_type == GapType.GAP_UP]),
            'GAP_DOWN': len([g for g in gap_signals if g.gap_type == GapType.GAP_DOWN])
        }
    
    def _categorize_gaps_by_strength(self, gap_signals: List[GapSignal]) -> Dict[str, int]:
        """Categorize gaps by strength"""
        return {
            'WEAK': len([g for g in gap_signals if g.gap_strength == GapStrength.WEAK]),
            'MODERATE': len([g for g in gap_signals if g.gap_strength == GapStrength.MODERATE]),
            'STRONG': len([g for g in gap_signals if g.gap_strength == GapStrength.STRONG]),
            'VERY_STRONG': len([g for g in gap_signals if g.gap_strength == GapStrength.VERY_STRONG])
        }
    
    def _analyze_gaps_by_sector(self, gap_signals: List[GapSignal]) -> Dict[str, Any]:
        """Analyze gaps by sector"""
        sector_analysis = defaultdict(lambda: {'gap_up': 0, 'gap_down': 0, 'avg_gap': 0})
        
        for gap in gap_signals:
            sector = gap.sector
            if gap.gap_type == GapType.GAP_UP:
                sector_analysis[sector]['gap_up'] += 1
            else:
                sector_analysis[sector]['gap_down'] += 1
        
        return dict(sector_analysis)
    
    def _identify_trading_opportunities(self, gap_signals: List[GapSignal]) -> List[Dict[str, Any]]:
        """Identify high-probability trading opportunities"""
        opportunities = []
        
        for gap in gap_signals:
            if (gap.is_significant and 
                gap.confidence_score > 0.7 and 
                gap.has_volume_confirmation and
                gap.trading_strategy != "HOLD"):
                
                opportunities.append({
                    'symbol': gap.symbol,
                    'gap_type': gap.gap_type.value,
                    'gap_percentage': gap.gap_percentage,
                    'strategy': gap.trading_strategy,
                    'confidence': gap.confidence_score,
                    'risk_reward': gap.risk_reward_ratio
                })
        
        return sorted(opportunities, key=lambda x: x['confidence'], reverse=True)[:10]
    
    def _gap_signal_to_dict(self, gap_signal: GapSignal) -> Dict[str, Any]:
        """Convert GapSignal to dictionary"""
        return {
            'symbol': gap_signal.symbol,
            'instrument_key': gap_signal.instrument_key,
            'gap_type': gap_signal.gap_type.value,
            'gap_percentage': gap_signal.gap_percentage,
            'gap_strength': gap_signal.gap_strength.value,
            'gap_timing': gap_signal.gap_timing.value,
            'current_price': gap_signal.current_price,
            'open_price': gap_signal.open_price,
            'previous_close': gap_signal.previous_close,
            'gap_amount': gap_signal.gap_amount,
            'volume': gap_signal.volume,
            'volume_ratio': round(gap_signal.volume_ratio, 2),
            'has_volume_confirmation': gap_signal.has_volume_confirmation,
            'is_significant': gap_signal.is_significant,
            'confidence_score': round(gap_signal.confidence_score, 2),
            'fill_probability': round(gap_signal.fill_probability, 2),
            'sector': gap_signal.sector,
            'market_cap_category': gap_signal.market_cap_category,
            'trading_strategy': gap_signal.trading_strategy,
            'risk_reward_ratio': round(gap_signal.risk_reward_ratio, 2),
            'detection_time': gap_signal.detection_time.isoformat()
        }
    
    def _gap_summary_to_dict(self, gap_summary: GapSummary) -> Dict[str, Any]:
        """Convert GapSummary to dictionary"""
        return {
            'total_gaps_detected': gap_summary.total_gaps_detected,
            'gap_up_count': gap_summary.gap_up_count,
            'gap_down_count': gap_summary.gap_down_count,
            'significant_gaps': gap_summary.significant_gaps,
            'strength_distribution': {
                'weak': gap_summary.weak_gaps,
                'moderate': gap_summary.moderate_gaps,
                'strong': gap_summary.strong_gaps,
                'very_strong': gap_summary.very_strong_gaps
            },
            'sector_distribution': gap_summary.sector_gap_distribution,
            'statistics': {
                'avg_gap_percentage': gap_summary.avg_gap_percentage,
                'max_gap_percentage': gap_summary.max_gap_percentage,
                'min_gap_percentage': gap_summary.min_gap_percentage
            },
            'top_gap_ups': [self._gap_signal_to_dict(g) for g in gap_summary.top_gap_ups],
            'top_gap_downs': [self._gap_signal_to_dict(g) for g in gap_summary.top_gap_downs],
            'calculation_timestamp': gap_summary.calculation_timestamp.isoformat()
        }
    
    def _get_empty_gap_result(self) -> Dict[str, Any]:
        """Get empty gap detection result"""
        return {
            'gap_signals': [],
            'gap_summary': self._gap_summary_to_dict(self._get_empty_gap_summary()),
            'market_phase': self._get_current_market_phase(),
            'gaps_by_type': {'GAP_UP': 0, 'GAP_DOWN': 0},
            'gaps_by_strength': {'WEAK': 0, 'MODERATE': 0, 'STRONG': 0, 'VERY_STRONG': 0},
            'sector_analysis': {},
            'trading_opportunities': [],
            'total_gaps_detected': 0,
            'significant_gaps_count': 0
        }
    
    def _get_empty_gap_summary(self) -> GapSummary:
        """Get empty gap summary"""
        return GapSummary(
            total_gaps_detected=0,
            gap_up_count=0,
            gap_down_count=0,
            significant_gaps=0,
            weak_gaps=0,
            moderate_gaps=0,
            strong_gaps=0,
            very_strong_gaps=0,
            sector_gap_distribution={},
            top_gap_ups=[],
            top_gap_downs=[],
            avg_gap_percentage=0.0,
            max_gap_percentage=0.0,
            min_gap_percentage=0.0,
            calculation_timestamp=datetime.now()
        )


# Singleton instance
_gap_detection_calculator: Optional[GapDetectionCalculator] = None


def get_gap_detection_calculator() -> GapDetectionCalculator:
    """Get singleton gap detection calculator instance"""
    global _gap_detection_calculator
    if _gap_detection_calculator is None:
        _gap_detection_calculator = GapDetectionCalculator()
    return _gap_detection_calculator


# Export main classes
__all__ = [
    "GapDetectionCalculator",
    "GapSignal",
    "GapSummary", 
    "GapType",
    "GapStrength",
    "GapTiming",
    "get_gap_detection_calculator"
]