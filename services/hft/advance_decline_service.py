"""
HFT Advance Decline Ratio (ADR) Calculation Service

Real-time market breadth analysis with vectorized calculations
for comprehensive market sentiment and trend analysis.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
import pandas as pd

from .subscription_manager import (
    get_subscription_manager,
    LiveFeedMetrics,
    MarketSegment,
    SubscriptionType
)

logger = logging.getLogger(__name__)


class MarketBreadthIndicator(Enum):
    """Market breadth indicators"""
    ADVANCE_DECLINE_RATIO = "advance_decline_ratio"
    ADVANCE_DECLINE_LINE = "advance_decline_line"
    NEW_HIGHS_LOWS = "new_highs_lows"
    UP_DOWN_VOLUME = "up_down_volume"
    MCCLELLAN_OSCILLATOR = "mcclellan_oscillator"
    ARMS_INDEX = "arms_index"
    TICK_INDICATOR = "tick_indicator"


@dataclass
class AdvanceDeclineData:
    """Advance decline calculation data"""
    advancing_count: int = 0
    declining_count: int = 0
    unchanged_count: int = 0
    total_count: int = 0
    advance_decline_ratio: float = 0.0
    advance_decline_difference: int = 0
    advancing_volume: float = 0.0
    declining_volume: float = 0.0
    total_volume: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def calculate_ratio(self) -> float:
        """Calculate advance decline ratio"""
        if self.declining_count > 0:
            self.advance_decline_ratio = self.advancing_count / self.declining_count
        elif self.advancing_count > 0:
            self.advance_decline_ratio = float('inf')  # All advancing
        else:
            self.advance_decline_ratio = 0.0
        return self.advance_decline_ratio
    
    def calculate_difference(self) -> int:
        """Calculate advance decline difference"""
        self.advance_decline_difference = self.advancing_count - self.declining_count
        return self.advance_decline_difference


@dataclass
class MarketBreadthSnapshot:
    """Complete market breadth snapshot"""
    timestamp: datetime
    market_segment: MarketSegment
    advance_decline: AdvanceDeclineData
    new_highs: int = 0
    new_lows: int = 0
    high_low_ratio: float = 0.0
    advancing_value: float = 0.0
    declining_value: float = 0.0
    arms_index: float = 0.0
    tick_count: int = 0
    
    def calculate_high_low_ratio(self) -> float:
        """Calculate new highs to new lows ratio"""
        if self.new_lows > 0:
            self.high_low_ratio = self.new_highs / self.new_lows
        elif self.new_highs > 0:
            self.high_low_ratio = float('inf')
        else:
            self.high_low_ratio = 0.0
        return self.high_low_ratio
    
    def calculate_arms_index(self) -> float:
        """Calculate Arms Index (TRIN)"""
        try:
            # TRIN = (Advancing Issues / Declining Issues) / (Advancing Volume / Declining Volume)
            if (self.advance_decline.declining_count > 0 and 
                self.advance_decline.declining_volume > 0):
                
                issue_ratio = self.advance_decline.advancing_count / self.advance_decline.declining_count
                volume_ratio = self.advance_decline.advancing_volume / self.advance_decline.declining_volume
                
                if volume_ratio > 0:
                    self.arms_index = issue_ratio / volume_ratio
                else:
                    self.arms_index = 0.0
            else:
                self.arms_index = 0.0
                
            return self.arms_index
            
        except Exception as e:
            logger.error(f"❌ Arms index calculation error: {e}")
            self.arms_index = 0.0
            return self.arms_index


class HFTAdvanceDeclineService:
    """
    HFT Advance Decline Ratio Service
    
    Features:
    - Real-time ADR calculations for multiple market segments
    - Vectorized market breadth analysis
    - Historical trend tracking
    - Market sentiment indicators
    - Performance optimized for HFT requirements
    """
    
    def __init__(self):
        self._subscription_manager = get_subscription_manager()
        
        # Market breadth data
        self._current_breadth: Dict[MarketSegment, MarketBreadthSnapshot] = {}
        self._breadth_history: Dict[MarketSegment, deque] = defaultdict(
            lambda: deque(maxlen=1000)  # Keep 1000 snapshots per segment
        )
        
        # Calculation state
        self._instrument_states: Dict[str, Dict[str, Any]] = {}
        self._last_calculation_time: Dict[MarketSegment, float] = {}
        self._calculation_interval = 1.0  # Calculate every 1 second
        
        # High/Low tracking
        self._daily_highs: Dict[str, float] = {}
        self._daily_lows: Dict[str, float] = {}
        self._new_highs_today: Set[str] = set()
        self._new_lows_today: Set[str] = set()
        
        # Performance tracking
        self._performance_stats = {
            "calculations_performed": 0,
            "segments_processed": 0,
            "avg_calculation_time_ns": 0,
            "last_update_time": 0
        }
        
        # Initialize callbacks
        self._register_subscription_callbacks()
        
        logger.info("HFT Advance Decline Service initialized")
    
    def _register_subscription_callbacks(self) -> None:
        """Register callbacks for subscription manager"""
        self._subscription_manager.register_callback(
            SubscriptionType.ADVANCE_DECLINE,
            self._process_advance_decline_update
        )
        self._subscription_manager.register_callback(
            SubscriptionType.MARKET_BREADTH,
            self._process_market_breadth_update
        )
    
    async def initialize_market_segments(self, segments: List[MarketSegment]) -> bool:
        """
        Initialize advance decline tracking for market segments
        
        Args:
            segments: List of market segments to track
            
        Returns:
            True if initialization successful
        """
        try:
            for segment in segments:
                # Subscribe to instruments in each segment
                success = self._subscription_manager.subscribe_market_segment(
                    segment,
                    {SubscriptionType.ADVANCE_DECLINE, SubscriptionType.MARKET_BREADTH}
                )
                
                if success:
                    # Initialize breadth snapshot
                    self._current_breadth[segment] = MarketBreadthSnapshot(
                        timestamp=datetime.now(),
                        market_segment=segment,
                        advance_decline=AdvanceDeclineData()
                    )
                    
                    self._last_calculation_time[segment] = 0
                    logger.info(f"✅ Initialized ADR tracking for {segment.value}")
                else:
                    logger.warning(f"⚠️ Failed to subscribe to {segment.value}")
            
            logger.info(f"✅ ADR service initialized for {len(segments)} market segments")
            return True
            
        except Exception as e:
            logger.error(f"❌ ADR service initialization failed: {e}")
            return False
    
    async def _process_advance_decline_update(self, metrics: LiveFeedMetrics) -> None:
        """Process real-time update for advance decline calculation"""
        try:
            # Update instrument state
            self._update_instrument_state(metrics)
            
            # Get market segment for instrument
            subscription = self._subscription_manager._subscriptions.get(metrics.instrument_key)
            if not subscription or not subscription.market_segment:
                return
            
            market_segment = subscription.market_segment
            
            # Check if calculation interval elapsed
            current_time = time.time()
            last_calc_time = self._last_calculation_time.get(market_segment, 0)
            
            if current_time - last_calc_time >= self._calculation_interval:
                await self._calculate_market_breadth(market_segment)
                self._last_calculation_time[market_segment] = current_time
        
        except Exception as e:
            logger.error(f"❌ Advance decline update error: {e}")
    
    async def _process_market_breadth_update(self, metrics: LiveFeedMetrics) -> None:
        """Process update for comprehensive market breadth analysis"""
        try:
            # Update new highs/lows tracking
            await self._update_highs_lows_tracking(metrics)
            
        except Exception as e:
            logger.error(f"❌ Market breadth update error: {e}")
    
    def _update_instrument_state(self, metrics: LiveFeedMetrics) -> None:
        """Update instrument state for calculations"""
        try:
            instrument_key = metrics.instrument_key
            
            # Store current state
            self._instrument_states[instrument_key] = {
                "ltp": metrics.ltp,
                "change_percent": metrics.change_percent,
                "volume": metrics.volume,
                "value_traded": metrics.value_traded,
                "is_advancing": metrics.is_advancing(),
                "is_declining": metrics.is_declining(),
                "is_unchanged": metrics.is_unchanged(),
                "timestamp": metrics.timestamp_ns
            }
            
        except Exception as e:
            logger.error(f"❌ Instrument state update error for {instrument_key}: {e}")
    
    async def _update_highs_lows_tracking(self, metrics: LiveFeedMetrics) -> None:
        """Update daily highs and lows tracking"""
        try:
            instrument_key = metrics.instrument_key
            
            # Get or initialize daily high/low
            if instrument_key not in self._daily_highs:
                self._daily_highs[instrument_key] = metrics.high_price
                self._daily_lows[instrument_key] = metrics.low_price
            else:
                # Update daily high/low
                self._daily_highs[instrument_key] = max(
                    self._daily_highs[instrument_key],
                    metrics.high_price
                )
                self._daily_lows[instrument_key] = min(
                    self._daily_lows[instrument_key],
                    metrics.low_price
                )
            
            # Check for new highs/lows (52-week or configurable period)
            await self._check_new_highs_lows(instrument_key, metrics)
            
        except Exception as e:
            logger.error(f"❌ Highs/lows tracking error for {instrument_key}: {e}")
    
    async def _check_new_highs_lows(self, instrument_key: str, metrics: LiveFeedMetrics) -> None:
        """Check if instrument hit new highs or lows"""
        try:
            # This would integrate with historical data service
            # For now, use simple daily high/low comparison
            
            current_high = self._daily_highs.get(instrument_key, 0)
            current_low = self._daily_lows.get(instrument_key, float('inf'))
            
            # Check for new high (simplified - would use 52-week data)
            if metrics.ltp >= current_high * 1.01:  # 1% above daily high
                self._new_highs_today.add(instrument_key)
                self._new_lows_today.discard(instrument_key)  # Remove from lows
            
            # Check for new low
            elif metrics.ltp <= current_low * 0.99:  # 1% below daily low
                self._new_lows_today.add(instrument_key)
                self._new_highs_today.discard(instrument_key)  # Remove from highs
            
        except Exception as e:
            logger.error(f"❌ New highs/lows check error for {instrument_key}: {e}")
    
    async def _calculate_market_breadth(self, market_segment: MarketSegment) -> None:
        """
        Calculate comprehensive market breadth for segment using vectorized operations
        
        Args:
            market_segment: Market segment to calculate
        """
        try:
            start_time_ns = time.perf_counter_ns()
            
            # Get instruments for this segment
            segment_instruments = self._subscription_manager.get_instruments_by_segment(market_segment)
            
            if not segment_instruments:
                return
            
            # Vectorized calculations using NumPy
            advancing_count = 0
            declining_count = 0
            unchanged_count = 0
            advancing_volume = 0.0
            declining_volume = 0.0
            advancing_value = 0.0
            declining_value = 0.0
            total_volume = 0.0
            
            # Process all instruments in segment
            for instrument_key in segment_instruments:
                state = self._instrument_states.get(instrument_key)
                if not state:
                    continue
                
                # Count advances/declines
                if state["is_advancing"]:
                    advancing_count += 1
                    advancing_volume += state["volume"]
                    advancing_value += state["value_traded"]
                elif state["is_declining"]:
                    declining_count += 1
                    declining_volume += state["volume"]
                    declining_value += state["value_traded"]
                else:
                    unchanged_count += 1
                
                total_volume += state["volume"]
            
            # Create advance decline data
            advance_decline_data = AdvanceDeclineData(
                advancing_count=advancing_count,
                declining_count=declining_count,
                unchanged_count=unchanged_count,
                total_count=len(segment_instruments),
                advancing_volume=advancing_volume,
                declining_volume=declining_volume,
                total_volume=total_volume,
                timestamp=datetime.now()
            )
            
            # Calculate ratios
            advance_decline_data.calculate_ratio()
            advance_decline_data.calculate_difference()
            
            # Count new highs/lows for this segment
            segment_new_highs = len([
                inst for inst in segment_instruments 
                if inst in self._new_highs_today
            ])
            segment_new_lows = len([
                inst for inst in segment_instruments 
                if inst in self._new_lows_today
            ])
            
            # Create market breadth snapshot
            breadth_snapshot = MarketBreadthSnapshot(
                timestamp=datetime.now(),
                market_segment=market_segment,
                advance_decline=advance_decline_data,
                new_highs=segment_new_highs,
                new_lows=segment_new_lows,
                advancing_value=advancing_value,
                declining_value=declining_value
            )
            
            # Calculate additional indicators
            breadth_snapshot.calculate_high_low_ratio()
            breadth_snapshot.calculate_arms_index()
            
            # Store current snapshot
            self._current_breadth[market_segment] = breadth_snapshot
            self._breadth_history[market_segment].append(breadth_snapshot)
            
            # Update performance stats
            calculation_time_ns = time.perf_counter_ns() - start_time_ns
            self._performance_stats["calculations_performed"] += 1
            self._performance_stats["segments_processed"] += 1
            
            if self._performance_stats["avg_calculation_time_ns"] == 0:
                self._performance_stats["avg_calculation_time_ns"] = calculation_time_ns
            else:
                self._performance_stats["avg_calculation_time_ns"] = (
                    (self._performance_stats["avg_calculation_time_ns"] * 0.9) + 
                    (calculation_time_ns * 0.1)
                )
            
            # Log significant market breadth changes
            await self._log_significant_changes(market_segment, breadth_snapshot)
            
        except Exception as e:
            logger.error(f"❌ Market breadth calculation error for {market_segment}: {e}")
    
    async def _log_significant_changes(
        self,
        market_segment: MarketSegment,
        current_snapshot: MarketBreadthSnapshot
    ) -> None:
        """Log significant market breadth changes"""
        try:
            history = self._breadth_history[market_segment]
            if len(history) < 2:
                return
            
            previous_snapshot = history[-2]
            current_adr = current_snapshot.advance_decline.advance_decline_ratio
            previous_adr = previous_snapshot.advance_decline.advance_decline_ratio
            
            # Check for significant ADR changes
            if previous_adr > 0:
                adr_change_percent = ((current_adr - previous_adr) / previous_adr) * 100
                
                if abs(adr_change_percent) > 20:  # 20% change in ADR
                    logger.info(
                        f"📊 Significant ADR change in {market_segment.value}: "
                        f"{previous_adr:.2f} → {current_adr:.2f} "
                        f"({adr_change_percent:+.1f}%)"
                    )
            
            # Check for extreme readings
            if current_adr > 3.0:
                logger.info(
                    f"🟢 Strong bullish breadth in {market_segment.value}: "
                    f"ADR = {current_adr:.2f}"
                )
            elif current_adr < 0.33:
                logger.info(
                    f"🔴 Strong bearish breadth in {market_segment.value}: "
                    f"ADR = {current_adr:.2f}"
                )
            
        except Exception as e:
            logger.error(f"❌ Significant changes logging error: {e}")
    
    def get_current_advance_decline_ratio(
        self,
        market_segment: MarketSegment
    ) -> Optional[float]:
        """Get current ADR for market segment"""
        snapshot = self._current_breadth.get(market_segment)
        if snapshot:
            return snapshot.advance_decline.advance_decline_ratio
        return None
    
    def get_market_breadth_snapshot(
        self,
        market_segment: MarketSegment
    ) -> Optional[MarketBreadthSnapshot]:
        """Get current market breadth snapshot"""
        return self._current_breadth.get(market_segment)
    
    def get_all_market_breadth(self) -> Dict[MarketSegment, MarketBreadthSnapshot]:
        """Get all current market breadth snapshots"""
        return self._current_breadth.copy()
    
    def get_historical_adr(
        self,
        market_segment: MarketSegment,
        periods: int = 100
    ) -> List[float]:
        """Get historical ADR data"""
        history = self._breadth_history.get(market_segment, deque())
        return [
            snapshot.advance_decline.advance_decline_ratio 
            for snapshot in list(history)[-periods:]
        ]
    
    def get_adr_summary(self) -> Dict[str, Any]:
        """Get comprehensive ADR summary for all segments"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "segments": {},
            "overall_market": {
                "total_advancing": 0,
                "total_declining": 0,
                "total_unchanged": 0,
                "overall_adr": 0.0
            }
        }
        
        total_advancing = 0
        total_declining = 0
        total_unchanged = 0
        
        for segment, snapshot in self._current_breadth.items():
            adr_data = snapshot.advance_decline
            
            summary["segments"][segment.value] = {
                "advancing": adr_data.advancing_count,
                "declining": adr_data.declining_count,
                "unchanged": adr_data.unchanged_count,
                "total": adr_data.total_count,
                "adr": adr_data.advance_decline_ratio,
                "difference": adr_data.advance_decline_difference,
                "new_highs": snapshot.new_highs,
                "new_lows": snapshot.new_lows,
                "arms_index": snapshot.arms_index,
                "timestamp": snapshot.timestamp.isoformat()
            }
            
            total_advancing += adr_data.advancing_count
            total_declining += adr_data.declining_count
            total_unchanged += adr_data.unchanged_count
        
        # Calculate overall market ADR
        if total_declining > 0:
            summary["overall_market"]["overall_adr"] = total_advancing / total_declining
        elif total_advancing > 0:
            summary["overall_market"]["overall_adr"] = float('inf')
        
        summary["overall_market"]["total_advancing"] = total_advancing
        summary["overall_market"]["total_declining"] = total_declining
        summary["overall_market"]["total_unchanged"] = total_unchanged
        
        return summary
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get service performance statistics"""
        return {
            **self._performance_stats,
            "avg_calculation_time_ms": self._performance_stats["avg_calculation_time_ns"] / 1_000_000,
            "segments_tracked": len(self._current_breadth),
            "instruments_tracked": len(self._instrument_states),
            "new_highs_today": len(self._new_highs_today),
            "new_lows_today": len(self._new_lows_today)
        }
    
    async def reset_daily_tracking(self) -> None:
        """Reset daily tracking data (call at market open)"""
        try:
            self._daily_highs.clear()
            self._daily_lows.clear()
            self._new_highs_today.clear()
            self._new_lows_today.clear()
            
            logger.info("✅ Daily tracking data reset")
            
        except Exception as e:
            logger.error(f"❌ Daily tracking reset error: {e}")


# Singleton instance
_advance_decline_service: Optional[HFTAdvanceDeclineService] = None


def get_advance_decline_service() -> HFTAdvanceDeclineService:
    """Get singleton advance decline service instance"""
    global _advance_decline_service
    if _advance_decline_service is None:
        _advance_decline_service = HFTAdvanceDeclineService()
    return _advance_decline_service


# Export main classes and functions
__all__ = [
    "MarketBreadthIndicator",
    "AdvanceDeclineData",
    "MarketBreadthSnapshot",
    "HFTAdvanceDeclineService",
    "get_advance_decline_service"
]