"""
HFT Kafka Configuration Module

This module provides ultra-low latency Kafka configuration optimized for
High-Frequency Trading systems with sub-millisecond performance targets.

Author: Trading System
Created: 2025-01-11
"""

import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ServicePriority(Enum):
    """Service priority levels for HFT processing"""
    CRITICAL = 0    # < 0.1ms - Trading execution, shared memory
    HIGH = 1        # < 1ms - Analytics, breakout detection
    NORMAL = 2      # < 10ms - UI updates, notifications
    LOW = 3         # < 100ms - Logging, auditing


class TopicType(Enum):
    """Kafka topic types for different data flows"""
    RAW_MARKET_DATA = "raw_market_data"
    SHARED_MEMORY_FEED = "shared_memory_feed"
    ANALYTICS_FEED = "analytics_feed"
    STRATEGY_FEED = "strategy_feed"
    EXECUTION_FEED = "execution_feed"
    UI_FEED = "ui_feed"
    SPECIALIZED_FEED = "specialized_feed"


@dataclass
class TopicConfig:
    """Configuration for individual Kafka topics"""
    name: str
    partitions: int
    replication_factor: int
    retention_ms: int
    segment_ms: int
    cleanup_policy: str = "delete"
    min_in_sync_replicas: int = 1
    compression_type: Optional[str] = None
    consumer_groups: List[str] = field(default_factory=list)
    priority: ServicePriority = ServicePriority.NORMAL
    description: str = ""


@dataclass
class HFTKafkaConfig:
    """Complete HFT Kafka configuration"""
    # Connection settings
    bootstrap_servers: str = "localhost:9092"
    client_id: str = "hft_trading_system"
    
    # Ultra-low latency producer settings
    producer_config: Dict[str, Any] = field(default_factory=lambda: {
        "linger_ms": 0,                    # Send immediately
        "max_batch_size": 1,               # Single message batches
        "acks": 1,                         # Leader acknowledgment only
        "compression_type": None,          # No compression overhead
        "request_timeout_ms": 100,         # 100ms timeout
    })
    
    # Ultra-low latency consumer settings
    consumer_config: Dict[str, Any] = field(default_factory=lambda: {
        "fetch_min_bytes": 1,              # Fetch immediately
        "fetch_max_wait_ms": 1,            # 1ms wait max
        "max_poll_records": 1000,          # Batch processing
        "session_timeout_ms": 10000,       # 10s session
        "heartbeat_interval_ms": 3000,     # 3s heartbeat
        "auto_offset_reset": "latest",     # Start from latest
        "enable_auto_commit": True,        # Auto commit for speed
        "auto_commit_interval_ms": 1000,   # 1s commit interval
    })
    
    # Performance monitoring settings
    monitoring_config: Dict[str, Any] = field(default_factory=lambda: {
        "enable_metrics": True,
        "metrics_interval_ms": 1000,       # 1s metrics collection
        "latency_warning_threshold_ms": 1.0,  # Warn if > 1ms
        "latency_critical_threshold_ms": 5.0, # Critical if > 5ms
        "memory_warning_threshold_mb": 512,    # Warn if > 512MB
    })


class HFTTopicManager:
    """Manages HFT Kafka topic configurations"""
    
    def __init__(self):
        self._topics: Dict[str, TopicConfig] = {}
        self._initialize_default_topics()
    
    def _initialize_default_topics(self) -> None:
        """Initialize default HFT topic configurations"""
        
        # Priority 0: Raw Data Ingestion (Single Source of Truth)
        self.add_topic(TopicConfig(
            name="hft.raw.market_data",
            partitions=1,
            replication_factor=3,
            retention_ms=3600000,      # 1 hour
            segment_ms=300000,         # 5 minutes
            min_in_sync_replicas=2,
            consumer_groups=["hft_memory_bridge"],
            priority=ServicePriority.CRITICAL,
            description="Raw market data from WebSocket - single source of truth"
        ))
        
        # Priority 1: HFT Shared Memory Feed (Critical Services)
        self.add_topic(TopicConfig(
            name="hft.shared_memory.feed",
            partitions=8,
            replication_factor=3,
            retention_ms=1800000,      # 30 minutes
            segment_ms=180000,         # 3 minutes
            consumer_groups=[
                "instrument_registry_group",
                "breakout_engine_group",
                "premarket_candle_group"
            ],
            priority=ServicePriority.CRITICAL,
            description="HFT shared memory feed for critical services"
        ))
        
        # Priority 2: Analytics Pipeline
        self.add_topic(TopicConfig(
            name="hft.analytics.market_data",
            partitions=16,
            replication_factor=2,
            retention_ms=7200000,      # 2 hours
            segment_ms=600000,         # 10 minutes
            consumer_groups=[
                "enhanced_market_analytics_group",
                "sector_analytics_group"
            ],
            priority=ServicePriority.HIGH,
            description="Market analytics and calculations feed"
        ))
        
        # Priority 3: Strategy Engine Feeds
        strategy_topics = [
            ("hft.strategy.breakout", "Breakout strategy data feed"),
            ("hft.strategy.momentum", "Momentum strategy data feed"),
            ("hft.strategy.gap_trading", "Gap trading strategy feed"),
            ("hft.strategy.fibonacci", "Fibonacci retracement strategy feed")
        ]
        
        for topic_name, description in strategy_topics:
            self.add_topic(TopicConfig(
                name=topic_name,
                partitions=4,
                replication_factor=2,
                retention_ms=3600000,  # 1 hour
                segment_ms=300000,     # 5 minutes
                consumer_groups=[f"{topic_name.split('.')[-1]}_strategy_group"],
                priority=ServicePriority.HIGH,
                description=description
            ))
        
        # Priority 4: Real-Time Execution
        self.add_topic(TopicConfig(
            name="hft.execution.signals",
            partitions=8,
            replication_factor=3,
            retention_ms=86400000,     # 24 hours
            segment_ms=3600000,        # 1 hour
            min_in_sync_replicas=2,
            consumer_groups=[
                "auto_trade_execution_group",
                "order_management_group",
                "position_monitor_group"
            ],
            priority=ServicePriority.CRITICAL,
            description="Trading execution signals and orders"
        ))
        
        # Priority 5: UI & Broadcasting
        self.add_topic(TopicConfig(
            name="hft.ui.price_updates",
            partitions=32,
            replication_factor=2,
            retention_ms=1800000,      # 30 minutes
            segment_ms=180000,         # 3 minutes
            consumer_groups=[
                "unified_websocket_group",
                "dashboard_group"
            ],
            priority=ServicePriority.NORMAL,
            description="Real-time price updates for UI components"
        ))
        
        # Priority 6: Specialized Services
        self.add_topic(TopicConfig(
            name="hft.premarket.candles",
            partitions=1,
            replication_factor=3,
            retention_ms=86400000,     # 24 hours
            segment_ms=3600000,        # 1 hour
            consumer_groups=["premarket_group"],
            priority=ServicePriority.HIGH,
            description="Premarket candle building (9:00-9:08 AM window)"
        ))
        
        self.add_topic(TopicConfig(
            name="hft.stock_selection.signals",
            partitions=4,
            replication_factor=2,
            retention_ms=86400000,     # 24 hours
            segment_ms=3600000,        # 1 hour
            consumer_groups=["stock_selection_group"],
            priority=ServicePriority.NORMAL,
            description="Stock selection signals (9:00 AM daily)"
        ))
    
    def add_topic(self, topic_config: TopicConfig) -> None:
        """Add a topic configuration"""
        self._topics[topic_config.name] = topic_config
        logger.debug(f"Added topic configuration: {topic_config.name}")
    
    def get_topic(self, name: str) -> Optional[TopicConfig]:
        """Get topic configuration by name"""
        return self._topics.get(name)
    
    def get_topics_by_priority(self, priority: ServicePriority) -> List[TopicConfig]:
        """Get all topics with specified priority"""
        return [
            topic for topic in self._topics.values()
            if topic.priority == priority
        ]
    
    def get_all_topics(self) -> Dict[str, TopicConfig]:
        """Get all topic configurations"""
        return self._topics.copy()
    
    def get_topic_creation_configs(self) -> List[Dict[str, Any]]:
        """Get topic configurations for Kafka admin client"""
        configs = []
        for topic in self._topics.values():
            config = {
                "name": topic.name,
                "num_partitions": topic.partitions,
                "replication_factor": topic.replication_factor,
                "topic_configs": {
                    "retention.ms": str(topic.retention_ms),
                    "segment.ms": str(topic.segment_ms),
                    "cleanup.policy": topic.cleanup_policy,
                    "min.insync.replicas": str(topic.min_in_sync_replicas),
                    "compression.type": topic.compression_type,
                }
            }
            configs.append(config)
        return configs


def get_hft_kafka_config() -> HFTKafkaConfig:
    """Get HFT Kafka configuration with environment overrides"""
    config = HFTKafkaConfig()

    # Override from environment variables - use same variables as simple Kafka system
    if bootstrap_servers := (os.getenv("HFT_KAFKA_BOOTSTRAP_SERVERS") or os.getenv("KAFKA_BOOTSTRAP_SERVERS")):
        config.bootstrap_servers = bootstrap_servers

    if client_id := (os.getenv("HFT_KAFKA_CLIENT_ID") or os.getenv("KAFKA_CLIENT_ID")):
        config.client_id = client_id
    
    # SASL Authentication (for managed services like Upstash)
    if os.getenv("KAFKA_SASL_USERNAME") and os.getenv("KAFKA_SASL_PASSWORD"):
        sasl_config = {
            "security_protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL"),
            "sasl_mechanism": os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256"),
            "sasl_plain_username": os.getenv("KAFKA_SASL_USERNAME"),
            "sasl_plain_password": os.getenv("KAFKA_SASL_PASSWORD"),
        }
        config.producer_config.update(sasl_config)
        config.consumer_config.update(sasl_config)
        logger.info("🔐 SASL authentication configured for Kafka")
    
    # Producer config overrides
    if linger_ms := os.getenv("HFT_KAFKA_PRODUCER_LINGER_MS"):
        config.producer_config["linger_ms"] = int(linger_ms)
    
    if batch_size := os.getenv("HFT_KAFKA_PRODUCER_BATCH_SIZE"):
        config.producer_config["max_batch_size"] = int(batch_size)
    
    # Consumer config overrides
    if fetch_max_wait := os.getenv("HFT_KAFKA_CONSUMER_FETCH_MAX_WAIT_MS"):
        config.consumer_config["fetch_max_wait_ms"] = int(fetch_max_wait)
    
    if max_poll_records := os.getenv("HFT_KAFKA_CONSUMER_MAX_POLL_RECORDS"):
        config.consumer_config["max_poll_records"] = int(max_poll_records)
    
    logger.info(f"HFT Kafka config loaded: {config.bootstrap_servers}")
    return config


def get_topic_manager() -> HFTTopicManager:
    """Get singleton instance of HFT topic manager"""
    if not hasattr(get_topic_manager, "_instance"):
        get_topic_manager._instance = HFTTopicManager()
    return get_topic_manager._instance


# Export main configuration objects
__all__ = [
    "ServicePriority",
    "TopicType", 
    "TopicConfig",
    "HFTKafkaConfig",
    "HFTTopicManager",
    "get_hft_kafka_config",
    "get_topic_manager"
]