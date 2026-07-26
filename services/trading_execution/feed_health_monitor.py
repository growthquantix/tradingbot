"""
Feed Health Monitoring & Staleness Protection Service
Tracks websocket feed age and latency to prevent trading on stale market data.
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FeedHealthStatus(Enum):
    """Feed Health Status Types"""
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    CRITICAL = "CRITICAL"


class FeedHealthMonitor:
    """
    Monitors tick staleness across subscribed instruments.
    """

    def __init__(self, stale_threshold_ms: int = 5000, critical_threshold_ms: int = 15000):
        self.stale_threshold_ms = stale_threshold_ms
        self.critical_threshold_ms = critical_threshold_ms
        self.last_tick_timestamps: Dict[str, datetime] = {}

    def record_tick(self, instrument_key: str):
        """Record live tick timestamp."""
        self.last_tick_timestamps[instrument_key] = datetime.now()

    def get_feed_age_ms(self, instrument_key: str) -> float:
        """Calculate feed age in milliseconds for an instrument."""
        last_time = self.last_tick_timestamps.get(instrument_key)
        if not last_time:
            return 999999.0
        return (datetime.now() - last_time).total_seconds() * 1000.0

    def evaluate_feed_health(self, instrument_key: str) -> FeedHealthStatus:
        """Evaluate feed health status."""
        age_ms = self.get_feed_age_ms(instrument_key)
        if age_ms <= self.stale_threshold_ms:
            return FeedHealthStatus.HEALTHY
        elif age_ms <= self.critical_threshold_ms:
            logger.warning(f"⚠️ Feed STALE for {instrument_key}: {age_ms:.1f}ms age")
            return FeedHealthStatus.STALE
        else:
            logger.error(f"❌ Feed CRITICAL for {instrument_key}: {age_ms:.1f}ms age")
            return FeedHealthStatus.CRITICAL


# Singleton instance
feed_health_monitor = FeedHealthMonitor()
