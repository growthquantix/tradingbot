"""
HFT Subscription-Based Data Management Module

Manages instrument subscriptions with Kafka partition-based routing
for efficient live feed processing and real-time calculations.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import hashlib

import numpy as np
from decimal import Decimal

from .config import get_hft_kafka_config, get_topic_manager, ServicePriority

logger = logging.getLogger(__name__)


class SubscriptionType(Enum):
    """Types of data subscriptions"""
    PRICE_UPDATES = "price_updates"
    VOLUME_ANALYSIS = "volume_analysis"
    ADVANCE_DECLINE = "advance_decline"
    SECTOR_PERFORMANCE = "sector_performance"
    MARKET_BREADTH = "market_breadth"
    TECHNICAL_INDICATORS = "technical_indicators"


class MarketSegment(Enum):
    """Market segments for classification"""
    NIFTY_50 = "nifty_50"
    NIFTY_100 = "nifty_100"
    NIFTY_500 = "nifty_500"
    MIDCAP = "midcap"
    SMALLCAP = "smallcap"
    BANKING = "banking"
    IT = "it"
    AUTO = "auto"
    PHARMA = "pharma"
    FMCG = "fmcg"


@dataclass
class InstrumentSubscription:
    """Instrument subscription configuration"""
    instrument_key: str
    symbol: str
    sector: Optional[str] = None
    market_segment: Optional[MarketSegment] = None
    subscription_types: Set[SubscriptionType] = field(default_factory=set)
    partition_key: Optional[str] = None
    last_price: Optional[float] = None
    previous_close: Optional[float] = None
    is_active: bool = True
    
    def __post_init__(self):
        """Generate partition key based on instrument characteristics"""
        if not self.partition_key:
            # Create hash-based partition key for even distribution
            hash_input = f"{self.instrument_key}_{self.market_segment.value if self.market_segment else 'unknown'}"
            self.partition_key = hashlib.md5(hash_input.encode()).hexdigest()[:8]


@dataclass
class LiveFeedMetrics:
    """Real-time calculated metrics for instruments"""
    instrument_key: str
    ltp: float
    volume: int
    change: float
    change_percent: float
    previous_close: float
    open_price: float
    high_price: float
    low_price: float
    value_traded: float
    bid_price: float
    ask_price: float
    timestamp_ns: int
    
    def is_advancing(self) -> bool:
        """Check if instrument is advancing (price up)"""
        return self.change_percent > 0
    
    def is_declining(self) -> bool:
        """Check if instrument is declining (price down)"""
        return self.change_percent < 0
    
    def is_unchanged(self) -> bool:
        """Check if instrument is unchanged"""
        return abs(self.change_percent) < 0.01  # Within 0.01%


class HFTSubscriptionManager:
    """
    HFT Subscription Manager with Kafka Partition-Based Routing
    
    Features:
    - Subscription-based data filtering
    - Partition routing for scalability
    - Real-time metric calculations
    - Market segment classification
    - Advanced analytics support
    """
    
    def __init__(self):
        self._config = get_hft_kafka_config()
        
        # Subscription management
        self._subscriptions: Dict[str, InstrumentSubscription] = {}
        self._subscription_callbacks: Dict[SubscriptionType, List[Callable]] = defaultdict(list)
        self._active_instruments: Set[str] = set()
        
        # Partition management
        self._partition_assignments: Dict[str, Set[str]] = defaultdict(set)  # partition -> instruments
        self._instrument_partitions: Dict[str, str] = {}  # instrument -> partition
        
        # Market data cache for calculations
        self._live_metrics: Dict[str, LiveFeedMetrics] = {}
        self._metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Performance tracking
        self._processing_stats = {
            "subscriptions_processed": 0,
            "metrics_calculated": 0,
            "avg_processing_time_ns": 0,
            "last_update_time": 0
        }
        
        logger.info("HFT Subscription Manager initialized")
    
    def subscribe_instruments(
        self,
        instruments: List[Dict[str, Any]],
        subscription_types: Set[SubscriptionType]
    ) -> bool:
        """
        Subscribe to multiple instruments with specified data types
        
        Args:
            instruments: List of instrument dictionaries with keys: instrument_key, symbol, sector, market_segment
            subscription_types: Types of data to subscribe to
            
        Returns:
            True if subscription successful
        """
        try:
            for instrument_data in instruments:
                subscription = InstrumentSubscription(
                    instrument_key=instrument_data["instrument_key"],
                    symbol=instrument_data["symbol"],
                    sector=instrument_data.get("sector"),
                    market_segment=MarketSegment(instrument_data.get("market_segment", "nifty_500")),
                    subscription_types=subscription_types
                )
                
                self._subscriptions[subscription.instrument_key] = subscription
                self._active_instruments.add(subscription.instrument_key)
                
                # Assign to partition
                self._assign_to_partition(subscription)
            
            logger.info(f"✅ Subscribed to {len(instruments)} instruments for {len(subscription_types)} data types")
            return True
            
        except Exception as e:
            logger.error(f"❌ Subscription failed: {e}")
            return False
    
    def subscribe_market_segment(
        self,
        market_segment: MarketSegment,
        subscription_types: Set[SubscriptionType]
    ) -> bool:
        """
        Subscribe to all instruments in a market segment
        
        Args:
            market_segment: Market segment to subscribe to
            subscription_types: Types of data to subscribe to
            
        Returns:
            True if subscription successful
        """
        try:
            # Get instruments for market segment (would integrate with your instrument service)
            instruments = self._get_instruments_for_segment(market_segment)
            return self.subscribe_instruments(instruments, subscription_types)
            
        except Exception as e:
            logger.error(f"❌ Market segment subscription failed: {e}")
            return False
    
    def _get_instruments_for_segment(self, market_segment: MarketSegment) -> List[Dict[str, Any]]:
        """Get instruments for a specific market segment"""
        # This would integrate with your instrument registry
        # For now, return sample data structure
        segment_mappings = {
            MarketSegment.NIFTY_50: [
                {"instrument_key": "NSE_EQ|INE002A01018", "symbol": "RELIANCE", "sector": "ENERGY"},
                {"instrument_key": "NSE_EQ|INE467B01029", "symbol": "TCS", "sector": "IT"},
                # ... more instruments
            ],
            MarketSegment.BANKING: [
                {"instrument_key": "NSE_EQ|INE238A01034", "symbol": "AXISBANK", "sector": "BANKING"},
                {"instrument_key": "NSE_EQ|INE040A01034", "symbol": "HDFC", "sector": "BANKING"},
                # ... more banking stocks
            ]
        }
        
        instruments = segment_mappings.get(market_segment, [])
        for instrument in instruments:
            instrument["market_segment"] = market_segment.value
        
        return instruments
    
    def _assign_to_partition(self, subscription: InstrumentSubscription) -> None:
        """Assign instrument to Kafka partition for balanced load distribution"""
        partition_key = subscription.partition_key
        
        # Add to partition assignments
        self._partition_assignments[partition_key].add(subscription.instrument_key)
        self._instrument_partitions[subscription.instrument_key] = partition_key
        
        logger.debug(f"Assigned {subscription.instrument_key} to partition {partition_key}")
    
    async def process_live_feed_data(self, raw_feed_data: Dict[str, Any]) -> None:
        """
        Process live feed data for subscribed instruments only
        
        Args:
            raw_feed_data: Raw feed data from WebSocket
        """
        try:
            start_time_ns = time.perf_counter_ns()
            
            feeds = raw_feed_data.get("feeds", {})
            processed_count = 0
            
            for instrument_key, feed_data in feeds.items():
                # Only process subscribed instruments
                if instrument_key not in self._active_instruments:
                    continue
                
                # Calculate live metrics
                metrics = await self._calculate_live_metrics(instrument_key, feed_data)
                if metrics:
                    self._live_metrics[instrument_key] = metrics
                    self._metric_history[instrument_key].append(metrics)
                    processed_count += 1
                    
                    # Trigger subscription callbacks
                    await self._trigger_subscription_callbacks(metrics)
            
            # Update performance stats
            processing_time_ns = time.perf_counter_ns() - start_time_ns
            self._processing_stats["subscriptions_processed"] += processed_count
            self._processing_stats["metrics_calculated"] += processed_count
            self._processing_stats["last_update_time"] = time.time()
            
            # Update average processing time
            if self._processing_stats["avg_processing_time_ns"] == 0:
                self._processing_stats["avg_processing_time_ns"] = processing_time_ns
            else:
                self._processing_stats["avg_processing_time_ns"] = (
                    (self._processing_stats["avg_processing_time_ns"] * 0.9) + 
                    (processing_time_ns * 0.1)
                )
            
        except Exception as e:
            logger.error(f"❌ Live feed processing error: {e}")
    
    async def _calculate_live_metrics(
        self,
        instrument_key: str,
        feed_data: Dict[str, Any]
    ) -> Optional[LiveFeedMetrics]:
        """
        Calculate real-time metrics from live feed data
        
        Args:
            instrument_key: Instrument identifier
            feed_data: Feed data from WebSocket
            
        Returns:
            LiveFeedMetrics object or None if invalid data
        """
        try:
            # Extract data from Upstox feed structure
            full_feed = feed_data.get("fullFeed", {})
            market_data = full_feed.get("marketFF") or full_feed.get("indexFF") or {}
            
            if not market_data:
                return None
            
            # Extract LTPC (Last Traded Price and Close)
            ltpc = market_data.get("ltpc", {})
            ltp = float(ltpc.get("ltp", 0))
            previous_close = float(ltpc.get("cp", 0))
            
            if ltp <= 0 or previous_close <= 0:
                return None
            
            # Calculate change and change percentage
            change = ltp - previous_close
            change_percent = (change / previous_close) * 100
            
            # Extract OHLC data
            ohlc_data = market_data.get("marketOHLC", {}).get("ohlc", [])
            daily_ohlc = {}
            if ohlc_data:
                for ohlc in ohlc_data:
                    if ohlc.get("interval") == "1d":
                        daily_ohlc = ohlc
                        break
            
            # Extract volume and value traded
            volume = int(market_data.get("vtt", 0))
            value_traded = volume * ltp if volume > 0 else 0
            
            # Extract bid/ask data
            bid_ask = market_data.get("marketLevel", {}).get("bidAskQuote", [])
            bid_price = 0.0
            ask_price = 0.0
            if bid_ask:
                best_quote = bid_ask[0]
                bid_price = float(best_quote.get("bidP", 0))
                ask_price = float(best_quote.get("askP", 0))
            
            return LiveFeedMetrics(
                instrument_key=instrument_key,
                ltp=ltp,
                volume=volume,
                change=change,
                change_percent=change_percent,
                previous_close=previous_close,
                open_price=float(daily_ohlc.get("open", 0)),
                high_price=float(daily_ohlc.get("high", 0)),
                low_price=float(daily_ohlc.get("low", 0)),
                value_traded=value_traded,
                bid_price=bid_price,
                ask_price=ask_price,
                timestamp_ns=time.perf_counter_ns()
            )
            
        except Exception as e:
            logger.error(f"❌ Metrics calculation error for {instrument_key}: {e}")
            return None
    
    async def _trigger_subscription_callbacks(self, metrics: LiveFeedMetrics) -> None:
        """Trigger callbacks for subscribed data types"""
        try:
            subscription = self._subscriptions.get(metrics.instrument_key)
            if not subscription:
                return
            
            # Trigger callbacks for each subscription type
            for sub_type in subscription.subscription_types:
                callbacks = self._subscription_callbacks.get(sub_type, [])
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(metrics)
                        else:
                            callback(metrics)
                    except Exception as e:
                        logger.error(f"❌ Callback error for {sub_type}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Subscription callback error: {e}")
    
    def register_callback(
        self,
        subscription_type: SubscriptionType,
        callback: Callable[[LiveFeedMetrics], None]
    ) -> None:
        """Register callback for subscription type"""
        self._subscription_callbacks[subscription_type].append(callback)
        logger.debug(f"Registered callback for {subscription_type}")
    
    def get_live_metrics(self, instrument_key: str) -> Optional[LiveFeedMetrics]:
        """Get current live metrics for instrument"""
        return self._live_metrics.get(instrument_key)
    
    def get_all_live_metrics(self) -> Dict[str, LiveFeedMetrics]:
        """Get all current live metrics"""
        return self._live_metrics.copy()
    
    def get_instruments_by_segment(self, market_segment: MarketSegment) -> List[str]:
        """Get all subscribed instruments for a market segment"""
        return [
            instrument_key for instrument_key, subscription in self._subscriptions.items()
            if subscription.market_segment == market_segment and subscription.is_active
        ]
    
    def get_partition_assignments(self) -> Dict[str, Set[str]]:
        """Get current partition assignments"""
        return dict(self._partition_assignments)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get subscription manager performance statistics"""
        return {
            "total_subscriptions": len(self._subscriptions),
            "active_instruments": len(self._active_instruments),
            "partitions_used": len(self._partition_assignments),
            "metrics_in_cache": len(self._live_metrics),
            **self._processing_stats,
            "avg_processing_time_ms": self._processing_stats["avg_processing_time_ns"] / 1_000_000
        }
    
    async def unsubscribe_instrument(self, instrument_key: str) -> bool:
        """Unsubscribe from specific instrument"""
        try:
            if instrument_key in self._subscriptions:
                subscription = self._subscriptions[instrument_key]
                subscription.is_active = False
                self._active_instruments.discard(instrument_key)
                
                # Remove from partition
                partition_key = subscription.partition_key
                self._partition_assignments[partition_key].discard(instrument_key)
                
                # Clean up data
                self._live_metrics.pop(instrument_key, None)
                self._metric_history.pop(instrument_key, None)
                
                logger.info(f"✅ Unsubscribed from {instrument_key}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Unsubscribe error for {instrument_key}: {e}")
            return False


# Singleton instance
_subscription_manager: Optional[HFTSubscriptionManager] = None


def get_subscription_manager() -> HFTSubscriptionManager:
    """Get singleton subscription manager instance"""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = HFTSubscriptionManager()
    return _subscription_manager


# Export main classes and functions
__all__ = [
    "SubscriptionType",
    "MarketSegment",
    "InstrumentSubscription",
    "LiveFeedMetrics",
    "HFTSubscriptionManager",
    "get_subscription_manager"
]