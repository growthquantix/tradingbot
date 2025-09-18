"""
Integration Module

Orchestration and integration services for the trading system.
Coordinates between different modules following clean architecture principles.

Author: Trading System
Created: 2025-01-11
"""

from .kafka_analytics_orchestrator import (
    KafkaAnalyticsOrchestrator,
    get_kafka_analytics_orchestrator,
    start_kafka_analytics_system,
    stop_kafka_analytics_system,
    get_system_status
)

__all__ = [
    "KafkaAnalyticsOrchestrator",
    "get_kafka_analytics_orchestrator", 
    "start_kafka_analytics_system",
    "stop_kafka_analytics_system",
    "get_system_status"
]