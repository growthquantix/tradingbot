"""
HFT Kafka Architecture Module

Ultra-low latency High-Frequency Trading Kafka integration for trading system
with sub-millisecond performance targets and comprehensive monitoring.

Author: Trading System
Created: 2025-01-11
"""

from .config import (
    ServicePriority,
    TopicType,
    TopicConfig,
    HFTKafkaConfig,
    HFTTopicManager,
    get_hft_kafka_config,
    get_topic_manager
)

from .producer import (
    HFTMessage,
    ProducerStats,
    HFTKafkaProducer,
    get_hft_producer,
    cleanup_hft_producer
)

from .memory_bridge import (
    MemoryBridgeStats,
    InstrumentUpdate,
    HFTMemoryBridge,
    get_hft_memory_bridge,
    cleanup_hft_memory_bridge
)

from .consumers import (
    BaseHFTConsumer,
    HFTInstrumentRegistryConsumer,
    HFTBreakoutEngineConsumer,
    HFTPremarketConsumer,
    HFTMarketAnalyticsConsumer,
    ConsumerStats
)

from .monitor import (
    PerformanceMetrics,
    PerformanceThresholds,
    AlertConfig,
    HFTPerformanceMonitor,
    get_hft_monitor,
    start_hft_monitoring,
    stop_hft_monitoring
)

from .integration import (
    HFTSystemIntegration,
    get_hft_system,
    initialize_hft_system,
    cleanup_hft_system
)

# Development mode support
try:
    from .development_mode import DevelopmentHFTSystem, is_development_mode
except ImportError:
    DevelopmentHFTSystem = None
    is_development_mode = lambda: False

__version__ = "1.0.0"
__author__ = "Trading System"

__all__ = [
    # Configuration
    "ServicePriority",
    "TopicType", 
    "TopicConfig",
    "HFTKafkaConfig",
    "HFTTopicManager",
    "get_hft_kafka_config",
    "get_topic_manager",
    
    # Producer
    "HFTMessage",
    "ProducerStats",
    "HFTKafkaProducer", 
    "get_hft_producer",
    "cleanup_hft_producer",
    
    # Memory Bridge
    "MemoryBridgeStats",
    "InstrumentUpdate",
    "HFTMemoryBridge",
    "get_hft_memory_bridge",
    "cleanup_hft_memory_bridge",
    
    # Consumers
    "BaseHFTConsumer",
    "HFTInstrumentRegistryConsumer",
    "HFTBreakoutEngineConsumer", 
    "HFTPremarketConsumer",
    "HFTMarketAnalyticsConsumer",
    "ConsumerStats",
    
    # Monitoring
    "PerformanceMetrics",
    "PerformanceThresholds",
    "AlertConfig", 
    "HFTPerformanceMonitor",
    "get_hft_monitor",
    "start_hft_monitoring",
    "stop_hft_monitoring",
    
    # Integration
    "HFTSystemIntegration",
    "get_hft_system",
    "initialize_hft_system", 
    "cleanup_hft_system"
]