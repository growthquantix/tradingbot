"""
Enhanced Kafka Partition Strategy for Auto-Trading Services

This module implements intelligent Kafka partitioning based on:
1. Live feed data format analysis
2. Service-specific requirements 
3. Real-time feature calculation needs
4. Auto-trading workflow patterns

Author: Trading System
Created: 2025-01-11
"""

import hashlib
import logging
from typing import Dict, List, Set, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)


class PartitionStrategy(Enum):
    """Kafka partition strategies for different data types"""
    SECTOR_BASED = "sector_based"           # Partition by sector for sector analytics
    MARKET_CAP_BASED = "market_cap_based"   # Partition by market cap (large/mid/small)
    EXCHANGE_BASED = "exchange_based"       # Partition by exchange (NSE/BSE)
    INSTRUMENT_TYPE = "instrument_type"     # Partition by type (EQ/FO/INDEX)
    HASH_BALANCED = "hash_balanced"         # Even distribution via hash
    PRIORITY_BASED = "priority_based"       # Priority-based partitioning
    VOLUME_BASED = "volume_based"           # High/medium/low volume partitions


class ServiceType(Enum):
    """Service types for partition routing"""
    SECTOR_ANALYTICS = "sector_analytics"
    STOCK_SELECTION = "stock_selection"
    BREAKOUT_DETECTION = "breakout_detection"
    TOP_MOVERS = "top_movers"
    HEATMAP_GENERATION = "heatmap_generation"
    GAP_DETECTION = "gap_detection"
    MARKET_SENTIMENT = "market_sentiment"
    ADR_CALCULATION = "adr_calculation"
    REAL_TIME_UI = "real_time_ui"
    AUTO_TRADING = "auto_trading"


@dataclass
class PartitionConfig:
    """Configuration for Kafka partition routing"""
    service_type: ServiceType
    partition_strategy: PartitionStrategy
    partition_count: int
    priority_level: int
    data_retention_hours: int = 24
    compression_type: str = "gzip"
    batch_size: int = 1000
    max_latency_ms: int = 100


@dataclass
class InstrumentPartitionInfo:
    """Partition information for an instrument"""
    instrument_key: str
    symbol: str
    sector: str
    exchange: str
    instrument_type: str
    market_cap_category: str
    volume_category: str
    partition_assignments: Dict[ServiceType, int] = field(default_factory=dict)


class EnhancedPartitionManager:
    """
    Enhanced Kafka Partition Manager for Auto-Trading Services
    
    Features:
    - Service-specific partition routing
    - Sector-based data distribution
    - Volume-weighted partitioning
    - Real-time feature calculation optimization
    - Auto-trading workflow support
    """
    
    def __init__(self):
        self._service_configs = self._initialize_service_configs()
        self._sector_mappings = self._load_sector_mappings()
        self._instrument_cache: Dict[str, InstrumentPartitionInfo] = {}
        self._partition_loads: Dict[Tuple[ServiceType, int], int] = {}
        
        logger.info("Enhanced Partition Manager initialized for auto-trading services")
    
    def _initialize_service_configs(self) -> Dict[ServiceType, PartitionConfig]:
        """Initialize partition configurations for each service"""
        return {
            # High-priority services with low latency requirements
            ServiceType.REAL_TIME_UI: PartitionConfig(
                service_type=ServiceType.REAL_TIME_UI,
                partition_strategy=PartitionStrategy.HASH_BALANCED,
                partition_count=8,
                priority_level=1,
                max_latency_ms=50,
                batch_size=100
            ),
            
            ServiceType.AUTO_TRADING: PartitionConfig(
                service_type=ServiceType.AUTO_TRADING,
                partition_strategy=PartitionStrategy.PRIORITY_BASED,
                partition_count=4,
                priority_level=1,
                max_latency_ms=25,
                batch_size=10
            ),
            
            ServiceType.BREAKOUT_DETECTION: PartitionConfig(
                service_type=ServiceType.BREAKOUT_DETECTION,
                partition_strategy=PartitionStrategy.VOLUME_BASED,
                partition_count=6,
                priority_level=2,
                max_latency_ms=100,
                batch_size=500
            ),
            
            ServiceType.GAP_DETECTION: PartitionConfig(
                service_type=ServiceType.GAP_DETECTION,
                partition_strategy=PartitionStrategy.EXCHANGE_BASED,
                partition_count=4,
                priority_level=2,
                max_latency_ms=200,
                batch_size=200
            ),
            
            # Analytics services
            ServiceType.SECTOR_ANALYTICS: PartitionConfig(
                service_type=ServiceType.SECTOR_ANALYTICS,
                partition_strategy=PartitionStrategy.SECTOR_BASED,
                partition_count=12,  # One per major sector
                priority_level=3,
                max_latency_ms=500,
                batch_size=1000
            ),
            
            ServiceType.HEATMAP_GENERATION: PartitionConfig(
                service_type=ServiceType.HEATMAP_GENERATION,
                partition_strategy=PartitionStrategy.SECTOR_BASED,
                partition_count=12,
                priority_level=3,
                max_latency_ms=1000,
                batch_size=2000
            ),
            
            ServiceType.TOP_MOVERS: PartitionConfig(
                service_type=ServiceType.TOP_MOVERS,
                partition_strategy=PartitionStrategy.MARKET_CAP_BASED,
                partition_count=3,  # Large/Mid/Small cap
                priority_level=3,
                max_latency_ms=1000,
                batch_size=1500
            ),
            
            ServiceType.STOCK_SELECTION: PartitionConfig(
                service_type=ServiceType.STOCK_SELECTION,
                partition_strategy=PartitionStrategy.SECTOR_BASED,
                partition_count=8,
                priority_level=4,
                max_latency_ms=2000,
                batch_size=5000
            ),
            
            ServiceType.ADR_CALCULATION: PartitionConfig(
                service_type=ServiceType.ADR_CALCULATION,
                partition_strategy=PartitionStrategy.MARKET_CAP_BASED,
                partition_count=3,
                priority_level=3,
                max_latency_ms=1000,
                batch_size=2000
            ),
            
            ServiceType.MARKET_SENTIMENT: PartitionConfig(
                service_type=ServiceType.MARKET_SENTIMENT,
                partition_strategy=PartitionStrategy.HASH_BALANCED,
                partition_count=4,
                priority_level=3,
                max_latency_ms=2000,
                batch_size=3000
            )
        }
    
    def _load_sector_mappings(self) -> Dict[str, str]:
        """Load sector mappings for instruments"""
        return {
            # Major sectors with dedicated partitions
            "BANKING": "banking",
            "IT": "information_technology", 
            "AUTO": "automobile",
            "PHARMA": "pharmaceuticals",
            "FMCG": "consumer_goods",
            "ENERGY": "oil_gas",
            "METALS": "metals_mining",
            "REAL_ESTATE": "real_estate",
            "TELECOM": "telecommunications",
            "INFRASTRUCTURE": "infrastructure",
            "CHEMICALS": "chemicals",
            "TEXTILES": "textiles"
        }
    
    def register_instrument(
        self,
        instrument_key: str,
        symbol: str,
        sector: str,
        exchange: str,
        instrument_type: str,
        market_cap_category: str = "UNKNOWN",
        average_volume: int = 0
    ) -> InstrumentPartitionInfo:
        """
        Register instrument and calculate partition assignments for all services
        
        Args:
            instrument_key: Unique instrument identifier (e.g., NSE_EQ|INE318A01026)
            symbol: Trading symbol (e.g., RELIANCE)
            sector: Sector classification
            exchange: Exchange name (NSE/BSE)
            instrument_type: Type (EQ/FO/INDEX)
            market_cap_category: LARGE_CAP/MID_CAP/SMALL_CAP
            average_volume: Average daily volume
            
        Returns:
            InstrumentPartitionInfo with all service partition assignments
        """
        try:
            # Determine volume category
            volume_category = self._categorize_volume(average_volume)
            
            # Create instrument info
            instrument_info = InstrumentPartitionInfo(
                instrument_key=instrument_key,
                symbol=symbol,
                sector=sector,
                exchange=exchange,
                instrument_type=instrument_type,
                market_cap_category=market_cap_category,
                volume_category=volume_category
            )
            
            # Calculate partition assignments for each service
            for service_type, config in self._service_configs.items():
                partition_id = self._calculate_partition(
                    instrument_info, service_type, config
                )
                instrument_info.partition_assignments[service_type] = partition_id
            
            # Cache the instrument info
            self._instrument_cache[instrument_key] = instrument_info
            
            logger.debug(f"Registered instrument {symbol} with partition assignments")
            return instrument_info
            
        except Exception as e:
            logger.error(f"Failed to register instrument {instrument_key}: {e}")
            raise
    
    def _categorize_volume(self, average_volume: int) -> str:
        """Categorize volume into HIGH/MEDIUM/LOW"""
        if average_volume >= 1000000:  # 10L+
            return "HIGH"
        elif average_volume >= 100000:  # 1L+
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_partition(
        self,
        instrument_info: InstrumentPartitionInfo,
        service_type: ServiceType,
        config: PartitionConfig
    ) -> int:
        """Calculate partition ID for instrument and service combination"""
        try:
            if config.partition_strategy == PartitionStrategy.SECTOR_BASED:
                return self._sector_based_partition(instrument_info, config)
            
            elif config.partition_strategy == PartitionStrategy.MARKET_CAP_BASED:
                return self._market_cap_based_partition(instrument_info, config)
            
            elif config.partition_strategy == PartitionStrategy.EXCHANGE_BASED:
                return self._exchange_based_partition(instrument_info, config)
            
            elif config.partition_strategy == PartitionStrategy.INSTRUMENT_TYPE:
                return self._instrument_type_partition(instrument_info, config)
            
            elif config.partition_strategy == PartitionStrategy.VOLUME_BASED:
                return self._volume_based_partition(instrument_info, config)
            
            elif config.partition_strategy == PartitionStrategy.PRIORITY_BASED:
                return self._priority_based_partition(instrument_info, config)
            
            else:  # HASH_BALANCED
                return self._hash_balanced_partition(instrument_info, config)
                
        except Exception as e:
            logger.error(f"Partition calculation failed for {instrument_info.symbol}: {e}")
            # Fallback to hash-based
            return self._hash_balanced_partition(instrument_info, config)
    
    def _sector_based_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Partition based on sector for sector analytics"""
        sector_normalized = instrument_info.sector.upper()
        sector_mapping = self._sector_mappings.get(sector_normalized, "OTHER")
        
        # Use hash of sector name for consistent partitioning
        sector_hash = hashlib.md5(sector_mapping.encode()).hexdigest()
        return int(sector_hash, 16) % config.partition_count
    
    def _market_cap_based_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Partition based on market cap category"""
        cap_mapping = {
            "LARGE_CAP": 0,
            "MID_CAP": 1,
            "SMALL_CAP": 2
        }
        return cap_mapping.get(instrument_info.market_cap_category, 0) % config.partition_count
    
    def _exchange_based_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Partition based on exchange"""
        exchange_mapping = {
            "NSE": 0,
            "BSE": 1,
            "MCX": 2,
            "NCDEX": 3
        }
        return exchange_mapping.get(instrument_info.exchange, 0) % config.partition_count
    
    def _instrument_type_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Partition based on instrument type"""
        type_mapping = {
            "EQ": 0,      # Equity
            "FO": 1,      # Futures & Options
            "INDEX": 2,   # Indices
            "COMMODITY": 3
        }
        return type_mapping.get(instrument_info.instrument_type, 0) % config.partition_count
    
    def _volume_based_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Partition based on volume category for breakout detection"""
        volume_mapping = {
            "HIGH": 0,    # High volume stocks get priority partition
            "MEDIUM": 1,  # Medium volume
            "LOW": 2      # Low volume
        }
        base_partition = volume_mapping.get(instrument_info.volume_category, 2)
        
        # Distribute within volume category using hash
        if config.partition_count > 3:
            symbol_hash = hashlib.md5(instrument_info.symbol.encode()).hexdigest()
            hash_offset = int(symbol_hash, 16) % (config.partition_count // 3 + 1)
            return (base_partition * (config.partition_count // 3)) + hash_offset
        
        return base_partition % config.partition_count
    
    def _priority_based_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Priority-based partitioning for auto-trading"""
        # Auto-trading gets dedicated partitions based on trading priority
        priority_score = 0
        
        # Higher priority for high volume stocks
        if instrument_info.volume_category == "HIGH":
            priority_score += 2
        elif instrument_info.volume_category == "MEDIUM":
            priority_score += 1
        
        # Higher priority for liquid sectors
        liquid_sectors = {"BANKING", "IT", "AUTO", "PHARMA"}
        if instrument_info.sector.upper() in liquid_sectors:
            priority_score += 1
        
        # Higher priority for large cap
        if instrument_info.market_cap_category == "LARGE_CAP":
            priority_score += 1
        
        return min(priority_score, config.partition_count - 1)
    
    def _hash_balanced_partition(
        self, instrument_info: InstrumentPartitionInfo, config: PartitionConfig
    ) -> int:
        """Hash-based balanced partitioning"""
        hash_input = f"{instrument_info.instrument_key}_{instrument_info.symbol}"
        partition_hash = hashlib.md5(hash_input.encode()).hexdigest()
        return int(partition_hash, 16) % config.partition_count
    
    def get_partition_for_service(
        self, instrument_key: str, service_type: ServiceType
    ) -> Optional[int]:
        """Get partition ID for specific instrument and service"""
        instrument_info = self._instrument_cache.get(instrument_key)
        if not instrument_info:
            logger.warning(f"Instrument {instrument_key} not registered for partitioning")
            return None
        
        return instrument_info.partition_assignments.get(service_type)
    
    def get_kafka_topic_name(self, service_type: ServiceType, partition_id: int) -> str:
        """Generate Kafka topic name for service and partition"""
        service_name = service_type.value
        return f"hft.live_feed.{service_name}.p{partition_id}"
    
    def get_partition_routing_info(
        self, live_feed_data: Dict[str, Any]
    ) -> Dict[ServiceType, Dict[int, List[str]]]:
        """
        Route live feed data to appropriate partitions for each service
        
        Args:
            live_feed_data: Raw live feed data from WebSocket
            
        Returns:
            Dict mapping service_type -> partition_id -> list of instrument_keys
        """
        routing_info: Dict[ServiceType, Dict[int, List[str]]] = {}
        
        feeds = live_feed_data.get("feeds", {})
        
        for instrument_key in feeds.keys():
            instrument_info = self._instrument_cache.get(instrument_key)
            if not instrument_info:
                continue
            
            # Route to each service's appropriate partition
            for service_type, partition_id in instrument_info.partition_assignments.items():
                if service_type not in routing_info:
                    routing_info[service_type] = {}
                if partition_id not in routing_info[service_type]:
                    routing_info[service_type][partition_id] = []
                
                routing_info[service_type][partition_id].append(instrument_key)
        
        return routing_info
    
    def get_service_config(self, service_type: ServiceType) -> Optional[PartitionConfig]:
        """Get partition configuration for service"""
        return self._service_configs.get(service_type)
    
    def get_partition_load_stats(self) -> Dict[str, Any]:
        """Get partition load distribution statistics"""
        stats = {
            "total_instruments": len(self._instrument_cache),
            "service_distributions": {},
            "sector_distributions": {},
            "volume_distributions": {}
        }
        
        # Calculate service-wise distributions
        for service_type in ServiceType:
            partition_counts = {}
            for instrument_info in self._instrument_cache.values():
                partition_id = instrument_info.partition_assignments.get(service_type, -1)
                partition_counts[partition_id] = partition_counts.get(partition_id, 0) + 1
            stats["service_distributions"][service_type.value] = partition_counts
        
        # Calculate sector distributions
        sector_counts = {}
        for instrument_info in self._instrument_cache.values():
            sector = instrument_info.sector
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        stats["sector_distributions"] = sector_counts
        
        # Calculate volume distributions
        volume_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for instrument_info in self._instrument_cache.values():
            volume_category = instrument_info.volume_category
            volume_counts[volume_category] = volume_counts.get(volume_category, 0) + 1
        stats["volume_distributions"] = volume_counts
        
        return stats


# Singleton instance
_partition_manager: Optional[EnhancedPartitionManager] = None


def get_enhanced_partition_manager() -> EnhancedPartitionManager:
    """Get singleton enhanced partition manager instance"""
    global _partition_manager
    if _partition_manager is None:
        _partition_manager = EnhancedPartitionManager()
    return _partition_manager


# Export main classes and functions
__all__ = [
    "PartitionStrategy",
    "ServiceType", 
    "PartitionConfig",
    "InstrumentPartitionInfo",
    "EnhancedPartitionManager",
    "get_enhanced_partition_manager"
]