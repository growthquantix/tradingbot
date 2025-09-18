"""
Analytics Module

Modular analytics services for real-time market data processing and calculations.
Follows clean architecture principles with proper separation of concerns.

Author: Trading System
Created: 2025-01-11
"""

from .live_feed_calculator import LiveFeedCalculator
from .real_time_analytics_engine import RealTimeAnalyticsEngine, get_analytics_engine
from .kafka_sse_bridge import KafkaSSEBridge, get_kafka_sse_bridge
from .interfaces import IAnalyticsCalculator, IFeatureCalculator

__all__ = [
    "LiveFeedCalculator",
    "RealTimeAnalyticsEngine",
    "KafkaSSEBridge", 
    "get_analytics_engine",
    "get_kafka_sse_bridge",
    "IAnalyticsCalculator",
    "IFeatureCalculator"
]