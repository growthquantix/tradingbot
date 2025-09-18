"""
HFT Market Breadth Analytics Engine

Comprehensive real-time market breadth analysis with advanced indicators
and trend analysis for trading decision support.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats

from .advance_decline_service import (
    get_advance_decline_service,
    MarketBreadthSnapshot,
    AdvanceDeclineData
)
from .subscription_manager import MarketSegment, LiveFeedMetrics

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Market trend directions"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class MarketPhase(Enum):
    """Market phases based on breadth analysis"""
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    SIDEWAYS = "sideways"


@dataclass
class BreadthIndicators:
    """Comprehensive breadth indicators"""
    advance_decline_line: float = 0.0
    mcclellan_oscillator: float = 0.0
    mcclellan_summation: float = 0.0
    breadth_thrust: float = 0.0
    high_low_index: float = 0.0
    percentage_above_ma: float = 0.0
    up_down_volume_ratio: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketSentiment:
    """Market sentiment analysis"""
    sentiment_score: float = 0.0  # -100 to +100
    trend_direction: TrendDirection = TrendDirection.NEUTRAL
    market_phase: MarketPhase = MarketPhase.SIDEWAYS
    confidence_level: float = 0.0  # 0 to 100
    key_indicators: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AdvancedBreadthAnalysis:
    """Advanced breadth analysis results"""
    market_segment: MarketSegment
    breadth_indicators: BreadthIndicators
    market_sentiment: MarketSentiment
    participation_rate: float = 0.0
    momentum_score: float = 0.0
    divergence_alerts: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class HFTMarketBreadthAnalytics:
    """
    HFT Market Breadth Analytics Engine
    
    Features:
    - Advanced breadth indicators (McClellan, Breadth Thrust)
    - Market sentiment analysis
    - Trend detection and divergence analysis
    - Real-time market phase identification
    - Performance optimized calculations
    """
    
    def __init__(self):
        self._adr_service = get_advance_decline_service()
        
        # Analytics state
        self._breadth_analytics: Dict[MarketSegment, AdvancedBreadthAnalysis] = {}
        self._analytics_history: Dict[MarketSegment, deque] = defaultdict(
            lambda: deque(maxlen=500)  # Keep 500 analytics snapshots
        )
        
        # McClellan Oscillator calculation state
        self._mcclellan_ema19: Dict[MarketSegment, float] = {}
        self._mcclellan_ema39: Dict[MarketSegment, float] = {}
        self._mcclellan_summation: Dict[MarketSegment, float] = {}
        
        # Advance-Decline Line calculation
        self._ad_line: Dict[MarketSegment, float] = {}
        
        # Breadth indicators state
        self._breadth_thrust_readings: Dict[MarketSegment, deque] = defaultdict(
            lambda: deque(maxlen=10)  # 10-day breadth thrust
        )
        
        # Performance tracking
        self._last_calculation_time: Dict[MarketSegment, float] = {}
        self._calculation_interval = 5.0  # Calculate every 5 seconds
        
        self._performance_stats = {
            "analytics_calculated": 0,
            "segments_analyzed": 0,
            "avg_calculation_time_ns": 0,
            "alerts_generated": 0
        }
        
        logger.info("HFT Market Breadth Analytics Engine initialized")
    
    async def initialize_analytics(self, market_segments: List[MarketSegment]) -> bool:
        """
        Initialize analytics for market segments
        
        Args:
            market_segments: List of market segments to analyze
            
        Returns:
            True if initialization successful
        """
        try:
            for segment in market_segments:
                # Initialize analytics state
                self._breadth_analytics[segment] = AdvancedBreadthAnalysis(
                    market_segment=segment,
                    breadth_indicators=BreadthIndicators(),
                    market_sentiment=MarketSentiment()
                )
                
                # Initialize calculation state
                self._mcclellan_ema19[segment] = 0.0
                self._mcclellan_ema39[segment] = 0.0
                self._mcclellan_summation[segment] = 0.0
                self._ad_line[segment] = 0.0
                self._last_calculation_time[segment] = 0.0
                
                logger.info(f"✅ Analytics initialized for {segment.value}")
            
            # Start analytics calculation loop
            asyncio.create_task(self._analytics_calculation_loop())
            
            logger.info(f"✅ Market breadth analytics initialized for {len(market_segments)} segments")
            return True
            
        except Exception as e:
            logger.error(f"❌ Analytics initialization failed: {e}")
            return False
    
    async def _analytics_calculation_loop(self) -> None:
        """Main analytics calculation loop"""
        while True:
            try:
                current_time = time.time()
                
                for segment in self._breadth_analytics.keys():
                    last_calc_time = self._last_calculation_time.get(segment, 0)
                    
                    if current_time - last_calc_time >= self._calculation_interval:
                        await self._calculate_advanced_analytics(segment)
                        self._last_calculation_time[segment] = current_time
                
                await asyncio.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"❌ Analytics calculation loop error: {e}")
                await asyncio.sleep(1.0)
    
    async def _calculate_advanced_analytics(self, segment: MarketSegment) -> None:
        """
        Calculate advanced breadth analytics for market segment
        
        Args:
            segment: Market segment to analyze
        """
        try:
            start_time_ns = time.perf_counter_ns()
            
            # Get current market breadth snapshot
            breadth_snapshot = self._adr_service.get_market_breadth_snapshot(segment)
            if not breadth_snapshot:
                return
            
            # Calculate advanced indicators
            breadth_indicators = await self._calculate_breadth_indicators(segment, breadth_snapshot)
            
            # Analyze market sentiment
            market_sentiment = await self._analyze_market_sentiment(segment, breadth_indicators)
            
            # Calculate participation and momentum
            participation_rate = await self._calculate_participation_rate(segment, breadth_snapshot)
            momentum_score = await self._calculate_momentum_score(segment)
            
            # Detect divergences
            divergence_alerts = await self._detect_divergences(segment, breadth_indicators)
            
            # Create advanced analysis
            advanced_analysis = AdvancedBreadthAnalysis(
                market_segment=segment,
                breadth_indicators=breadth_indicators,
                market_sentiment=market_sentiment,
                participation_rate=participation_rate,
                momentum_score=momentum_score,
                divergence_alerts=divergence_alerts,
                timestamp=datetime.now()
            )
            
            # Store results
            self._breadth_analytics[segment] = advanced_analysis
            self._analytics_history[segment].append(advanced_analysis)
            
            # Update performance stats
            calculation_time_ns = time.perf_counter_ns() - start_time_ns
            self._performance_stats["analytics_calculated"] += 1
            self._performance_stats["segments_analyzed"] += 1
            
            if self._performance_stats["avg_calculation_time_ns"] == 0:
                self._performance_stats["avg_calculation_time_ns"] = calculation_time_ns
            else:
                self._performance_stats["avg_calculation_time_ns"] = (
                    (self._performance_stats["avg_calculation_time_ns"] * 0.9) + 
                    (calculation_time_ns * 0.1)
                )
            
            # Log significant analytics
            await self._log_significant_analytics(segment, advanced_analysis)
            
        except Exception as e:
            logger.error(f"❌ Advanced analytics calculation error for {segment}: {e}")
    
    async def _calculate_breadth_indicators(
        self,
        segment: MarketSegment,
        breadth_snapshot: MarketBreadthSnapshot
    ) -> BreadthIndicators:
        """Calculate comprehensive breadth indicators"""
        try:
            indicators = BreadthIndicators()
            adr_data = breadth_snapshot.advance_decline
            
            # 1. Advance-Decline Line
            net_advances = adr_data.advance_decline_difference
            self._ad_line[segment] = self._ad_line.get(segment, 0) + net_advances
            indicators.advance_decline_line = self._ad_line[segment]
            
            # 2. McClellan Oscillator
            indicators.mcclellan_oscillator = await self._calculate_mcclellan_oscillator(
                segment, net_advances
            )
            
            # 3. McClellan Summation Index
            self._mcclellan_summation[segment] = (
                self._mcclellan_summation.get(segment, 0) + indicators.mcclellan_oscillator
            )
            indicators.mcclellan_summation = self._mcclellan_summation[segment]
            
            # 4. Breadth Thrust
            indicators.breadth_thrust = await self._calculate_breadth_thrust(segment, adr_data)
            
            # 5. High-Low Index
            if breadth_snapshot.new_highs + breadth_snapshot.new_lows > 0:
                indicators.high_low_index = (
                    breadth_snapshot.new_highs / 
                    (breadth_snapshot.new_highs + breadth_snapshot.new_lows) * 100
                )
            
            # 6. Up/Down Volume Ratio
            if adr_data.declining_volume > 0:
                indicators.up_down_volume_ratio = adr_data.advancing_volume / adr_data.declining_volume
            elif adr_data.advancing_volume > 0:
                indicators.up_down_volume_ratio = float('inf')
            
            indicators.timestamp = datetime.now()
            return indicators
            
        except Exception as e:
            logger.error(f"❌ Breadth indicators calculation error: {e}")
            return BreadthIndicators()
    
    async def _calculate_mcclellan_oscillator(
        self,
        segment: MarketSegment,
        net_advances: int
    ) -> float:
        """Calculate McClellan Oscillator"""
        try:
            # Initialize EMAs if not present
            if segment not in self._mcclellan_ema19:
                self._mcclellan_ema19[segment] = float(net_advances)
                self._mcclellan_ema39[segment] = float(net_advances)
                return 0.0
            
            # Calculate 19-day EMA
            multiplier_19 = 2.0 / 20.0  # 19-day EMA multiplier
            self._mcclellan_ema19[segment] = (
                (net_advances * multiplier_19) + 
                (self._mcclellan_ema19[segment] * (1 - multiplier_19))
            )
            
            # Calculate 39-day EMA
            multiplier_39 = 2.0 / 40.0  # 39-day EMA multiplier
            self._mcclellan_ema39[segment] = (
                (net_advances * multiplier_39) + 
                (self._mcclellan_ema39[segment] * (1 - multiplier_39))
            )
            
            # McClellan Oscillator = 19-day EMA - 39-day EMA
            oscillator = self._mcclellan_ema19[segment] - self._mcclellan_ema39[segment]
            return oscillator
            
        except Exception as e:
            logger.error(f"❌ McClellan oscillator calculation error: {e}")
            return 0.0
    
    async def _calculate_breadth_thrust(
        self,
        segment: MarketSegment,
        adr_data: AdvanceDeclineData
    ) -> float:
        """Calculate Breadth Thrust indicator"""
        try:
            # Breadth Thrust = Advancing Issues / (Advancing + Declining Issues)
            total_directional = adr_data.advancing_count + adr_data.declining_count
            
            if total_directional > 0:
                thrust_reading = adr_data.advancing_count / total_directional
                
                # Store reading
                self._breadth_thrust_readings[segment].append(thrust_reading)
                
                # Calculate 10-day average
                readings = list(self._breadth_thrust_readings[segment])
                if len(readings) >= 10:
                    return np.mean(readings[-10:]) * 100  # Convert to percentage
                else:
                    return np.mean(readings) * 100
            
            return 50.0  # Neutral
            
        except Exception as e:
            logger.error(f"❌ Breadth thrust calculation error: {e}")
            return 50.0
    
    async def _analyze_market_sentiment(
        self,
        segment: MarketSegment,
        indicators: BreadthIndicators
    ) -> MarketSentiment:
        """Analyze market sentiment based on breadth indicators"""
        try:
            sentiment = MarketSentiment()
            sentiment_scores = []
            key_indicators = []
            
            # 1. Advance-Decline Line analysis
            if indicators.advance_decline_line > 0:
                sentiment_scores.append(20)
                key_indicators.append("AD Line positive")
            elif indicators.advance_decline_line < 0:
                sentiment_scores.append(-20)
                key_indicators.append("AD Line negative")
            
            # 2. McClellan Oscillator analysis
            if indicators.mcclellan_oscillator > 50:
                sentiment_scores.append(25)
                key_indicators.append("McClellan bullish")
            elif indicators.mcclellan_oscillator < -50:
                sentiment_scores.append(-25)
                key_indicators.append("McClellan bearish")
            
            # 3. Breadth Thrust analysis
            if indicators.breadth_thrust > 70:
                sentiment_scores.append(30)
                key_indicators.append("Strong breadth thrust")
            elif indicators.breadth_thrust < 30:
                sentiment_scores.append(-30)
                key_indicators.append("Weak breadth")
            
            # 4. High-Low Index analysis
            if indicators.high_low_index > 70:
                sentiment_scores.append(15)
                key_indicators.append("New highs dominating")
            elif indicators.high_low_index < 30:
                sentiment_scores.append(-15)
                key_indicators.append("New lows concerning")
            
            # 5. Volume analysis
            if indicators.up_down_volume_ratio > 2.0:
                sentiment_scores.append(10)
                key_indicators.append("Strong up volume")
            elif indicators.up_down_volume_ratio < 0.5:
                sentiment_scores.append(-10)
                key_indicators.append("Heavy down volume")
            
            # Calculate overall sentiment score
            if sentiment_scores:
                sentiment.sentiment_score = np.mean(sentiment_scores)
                sentiment.confidence_level = min(len(sentiment_scores) * 20, 100)
            
            # Determine trend direction
            if sentiment.sentiment_score > 40:
                sentiment.trend_direction = TrendDirection.STRONG_BULLISH
            elif sentiment.sentiment_score > 15:
                sentiment.trend_direction = TrendDirection.BULLISH
            elif sentiment.sentiment_score < -40:
                sentiment.trend_direction = TrendDirection.STRONG_BEARISH
            elif sentiment.sentiment_score < -15:
                sentiment.trend_direction = TrendDirection.BEARISH
            else:
                sentiment.trend_direction = TrendDirection.NEUTRAL
            
            # Determine market phase
            sentiment.market_phase = await self._determine_market_phase(segment, indicators)
            
            sentiment.key_indicators = key_indicators
            sentiment.timestamp = datetime.now()
            
            return sentiment
            
        except Exception as e:
            logger.error(f"❌ Market sentiment analysis error: {e}")
            return MarketSentiment()
    
    async def _determine_market_phase(
        self,
        segment: MarketSegment,
        indicators: BreadthIndicators
    ) -> MarketPhase:
        """Determine current market phase"""
        try:
            # Get historical data for trend analysis
            history = self._analytics_history.get(segment, deque())
            if len(history) < 10:
                return MarketPhase.SIDEWAYS
            
            # Analyze trends in key indicators
            recent_ad_line = [h.breadth_indicators.advance_decline_line for h in list(history)[-10:]]
            recent_mcclellan = [h.breadth_indicators.mcclellan_oscillator for h in list(history)[-10:]]
            
            # Calculate trends
            ad_trend = np.polyfit(range(len(recent_ad_line)), recent_ad_line, 1)[0]
            mcclellan_trend = np.polyfit(range(len(recent_mcclellan)), recent_mcclellan, 1)[0]
            
            # Determine phase based on trends and current levels
            if (ad_trend > 0 and mcclellan_trend > 0 and 
                indicators.mcclellan_oscillator > 0 and 
                indicators.breadth_thrust > 60):
                return MarketPhase.MARKUP
            
            elif (ad_trend < 0 and mcclellan_trend < 0 and 
                  indicators.mcclellan_oscillator < 0 and 
                  indicators.breadth_thrust < 40):
                return MarketPhase.MARKDOWN
            
            elif (indicators.mcclellan_oscillator > 0 and 
                  indicators.breadth_thrust < 50 and 
                  ad_trend < 0):
                return MarketPhase.DISTRIBUTION
            
            elif (indicators.mcclellan_oscillator < 0 and 
                  indicators.breadth_thrust > 50 and 
                  ad_trend > 0):
                return MarketPhase.ACCUMULATION
            
            else:
                return MarketPhase.SIDEWAYS
            
        except Exception as e:
            logger.error(f"❌ Market phase determination error: {e}")
            return MarketPhase.SIDEWAYS
    
    async def _calculate_participation_rate(
        self,
        segment: MarketSegment,
        breadth_snapshot: MarketBreadthSnapshot
    ) -> float:
        """Calculate market participation rate"""
        try:
            adr_data = breadth_snapshot.advance_decline
            total_active = adr_data.advancing_count + adr_data.declining_count
            
            if adr_data.total_count > 0:
                return (total_active / adr_data.total_count) * 100
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Participation rate calculation error: {e}")
            return 0.0
    
    async def _calculate_momentum_score(self, segment: MarketSegment) -> float:
        """Calculate momentum score based on recent performance"""
        try:
            history = self._analytics_history.get(segment, deque())
            if len(history) < 5:
                return 0.0
            
            # Get recent sentiment scores
            recent_sentiment = [h.market_sentiment.sentiment_score for h in list(history)[-5:]]
            
            # Calculate momentum as rate of change
            if len(recent_sentiment) >= 2:
                momentum = recent_sentiment[-1] - recent_sentiment[0]
                return momentum
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Momentum score calculation error: {e}")
            return 0.0
    
    async def _detect_divergences(
        self,
        segment: MarketSegment,
        indicators: BreadthIndicators
    ) -> List[str]:
        """Detect divergences between price and breadth indicators"""
        try:
            divergences = []
            
            # This would integrate with price index data
            # For now, check internal divergences between indicators
            
            # Check McClellan vs AD Line divergence
            history = self._analytics_history.get(segment, deque())
            if len(history) >= 5:
                recent_history = list(history)[-5:]
                
                ad_line_trend = np.polyfit(
                    range(5), 
                    [h.breadth_indicators.advance_decline_line for h in recent_history], 
                    1
                )[0]
                
                mcclellan_trend = np.polyfit(
                    range(5), 
                    [h.breadth_indicators.mcclellan_oscillator for h in recent_history], 
                    1
                )[0]
                
                # Check for divergence
                if ad_line_trend > 0 and mcclellan_trend < 0:
                    divergences.append("Bearish divergence: AD Line up, McClellan down")
                elif ad_line_trend < 0 and mcclellan_trend > 0:
                    divergences.append("Bullish divergence: AD Line down, McClellan up")
            
            return divergences
            
        except Exception as e:
            logger.error(f"❌ Divergence detection error: {e}")
            return []
    
    async def _log_significant_analytics(
        self,
        segment: MarketSegment,
        analysis: AdvancedBreadthAnalysis
    ) -> None:
        """Log significant analytics events"""
        try:
            # Log trend changes
            history = self._analytics_history.get(segment, deque())
            if len(history) >= 2:
                previous_trend = history[-2].market_sentiment.trend_direction
                current_trend = analysis.market_sentiment.trend_direction
                
                if previous_trend != current_trend:
                    logger.info(
                        f"📊 Trend change in {segment.value}: "
                        f"{previous_trend.value} → {current_trend.value}"
                    )
            
            # Log extreme readings
            if analysis.breadth_indicators.mcclellan_oscillator > 100:
                logger.info(
                    f"🟢 Extreme bullish McClellan in {segment.value}: "
                    f"{analysis.breadth_indicators.mcclellan_oscillator:.1f}"
                )
            elif analysis.breadth_indicators.mcclellan_oscillator < -100:
                logger.info(
                    f"🔴 Extreme bearish McClellan in {segment.value}: "
                    f"{analysis.breadth_indicators.mcclellan_oscillator:.1f}"
                )
            
            # Log divergence alerts
            if analysis.divergence_alerts:
                for alert in analysis.divergence_alerts:
                    logger.warning(f"⚠️ {segment.value}: {alert}")
                    self._performance_stats["alerts_generated"] += 1
            
        except Exception as e:
            logger.error(f"❌ Significant analytics logging error: {e}")
    
    def get_advanced_analysis(self, segment: MarketSegment) -> Optional[AdvancedBreadthAnalysis]:
        """Get current advanced analysis for segment"""
        return self._breadth_analytics.get(segment)
    
    def get_all_analyses(self) -> Dict[MarketSegment, AdvancedBreadthAnalysis]:
        """Get all current advanced analyses"""
        return self._breadth_analytics.copy()
    
    def get_market_sentiment_summary(self) -> Dict[str, Any]:
        """Get comprehensive market sentiment summary"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "segments": {},
            "overall_market": {
                "sentiment_score": 0.0,
                "trend_direction": TrendDirection.NEUTRAL.value,
                "confidence_level": 0.0
            }
        }
        
        sentiment_scores = []
        
        for segment, analysis in self._breadth_analytics.items():
            sentiment = analysis.market_sentiment
            
            summary["segments"][segment.value] = {
                "sentiment_score": sentiment.sentiment_score,
                "trend_direction": sentiment.trend_direction.value,
                "market_phase": sentiment.market_phase.value,
                "confidence_level": sentiment.confidence_level,
                "key_indicators": sentiment.key_indicators,
                "participation_rate": analysis.participation_rate,
                "momentum_score": analysis.momentum_score,
                "divergence_alerts": analysis.divergence_alerts
            }
            
            sentiment_scores.append(sentiment.sentiment_score)
        
        # Calculate overall market sentiment
        if sentiment_scores:
            overall_sentiment = np.mean(sentiment_scores)
            summary["overall_market"]["sentiment_score"] = overall_sentiment
            summary["overall_market"]["confidence_level"] = np.mean([
                a.market_sentiment.confidence_level for a in self._breadth_analytics.values()
            ])
            
            # Determine overall trend
            if overall_sentiment > 40:
                summary["overall_market"]["trend_direction"] = TrendDirection.STRONG_BULLISH.value
            elif overall_sentiment > 15:
                summary["overall_market"]["trend_direction"] = TrendDirection.BULLISH.value
            elif overall_sentiment < -40:
                summary["overall_market"]["trend_direction"] = TrendDirection.STRONG_BEARISH.value
            elif overall_sentiment < -15:
                summary["overall_market"]["trend_direction"] = TrendDirection.BEARISH.value
        
        return summary
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get analytics performance statistics"""
        return {
            **self._performance_stats,
            "avg_calculation_time_ms": self._performance_stats["avg_calculation_time_ns"] / 1_000_000,
            "segments_tracking": len(self._breadth_analytics),
            "total_history_points": sum(len(h) for h in self._analytics_history.values())
        }


# Singleton instance
_market_breadth_analytics: Optional[HFTMarketBreadthAnalytics] = None


def get_market_breadth_analytics() -> HFTMarketBreadthAnalytics:
    """Get singleton market breadth analytics instance"""
    global _market_breadth_analytics
    if _market_breadth_analytics is None:
        _market_breadth_analytics = HFTMarketBreadthAnalytics()
    return _market_breadth_analytics


# Export main classes and functions
__all__ = [
    "TrendDirection",
    "MarketPhase",
    "BreadthIndicators",
    "MarketSentiment",
    "AdvancedBreadthAnalysis",
    "HFTMarketBreadthAnalytics",
    "get_market_breadth_analytics"
]