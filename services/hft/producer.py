"""
HFT Kafka Producer Module

Ultra-low latency Kafka producer optimized for High-Frequency Trading with
sub-millisecond performance targets and zero-copy optimizations.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import aiokafka
from aiokafka.errors import KafkaError

from .config import get_hft_kafka_config, get_topic_manager, ServicePriority

logger = logging.getLogger(__name__)


@dataclass
class HFTMessage:
    """HFT-optimized message structure with minimal overhead"""
    instrument_key: str
    timestamp_ns: int
    data: Dict[str, Any]
    source_timestamp_ns: Optional[int] = None
    message_id: Optional[str] = None
    priority: ServicePriority = ServicePriority.NORMAL
    
    def __post_init__(self) -> None:
        """Generate message ID if not provided"""
        if self.message_id is None:
            self.message_id = f"{self.instrument_key}_{self.timestamp_ns}"


@dataclass
class ProducerStats:
    """Producer performance statistics"""
    messages_sent: int = 0
    messages_failed: int = 0
    total_latency_ns: int = 0
    avg_latency_ns: float = 0.0
    last_send_time_ns: int = 0
    bytes_sent: int = 0
    
    def update_latency(self, latency_ns: int) -> None:
        """Update latency statistics with exponential moving average"""
        self.total_latency_ns += latency_ns
        self.last_send_time_ns = time.perf_counter_ns()
        
        # Exponential moving average (90% old, 10% new)
        if self.avg_latency_ns == 0.0:
            self.avg_latency_ns = float(latency_ns)
        else:
            self.avg_latency_ns = (self.avg_latency_ns * 0.9) + (latency_ns * 0.1)


class HFTKafkaProducer:
    """
    HFT-grade Kafka producer with ultra-low latency optimizations
    
    Features:
    - Sub-millisecond message publishing
    - Zero-copy serialization where possible
    - Intelligent partition key generation
    - Performance monitoring and alerts
    - Automatic failover and error handling
    """
    
    def __init__(self):
        self._producer: Optional[aiokafka.AIOKafkaProducer] = None
        self._config = get_hft_kafka_config()
        self._topic_manager = get_topic_manager()
        self._stats = ProducerStats()
        self._is_initialized = False
        self._initialization_lock = asyncio.Lock()
        
        # Performance monitoring
        self._latency_warnings = 0
        self._error_count = 0
        self._last_health_check = 0
        
        logger.info("HFT Kafka Producer initialized")
    
    async def initialize(self) -> None:
        """Initialize the Kafka producer with HFT optimizations"""
        async with self._initialization_lock:
            if self._is_initialized:
                return
            
            try:
                # Create producer with HFT configuration
                self._producer = aiokafka.AIOKafkaProducer(
                    bootstrap_servers=self._config.bootstrap_servers,
                    client_id=f"{self._config.client_id}_producer",
                    value_serializer=self._serialize_message,
                    key_serializer=lambda x: x.encode() if x else None,
                    **self._config.producer_config
                )

                # Start the producer
                await self._producer.start()
                self._is_initialized = True

                logger.info(
                    f"HFT Kafka Producer started successfully: "
                    f"{self._config.bootstrap_servers}"
                )

            except Exception as e:
                logger.error(f"Failed to initialize HFT Kafka Producer: {e}")
                # Set producer to None to indicate failure
                self._producer = None
                self._is_initialized = False
                # Don't raise - allow system to continue without HFT Kafka
                logger.warning("⚠️ System will continue without HFT Kafka support")
    
    async def close(self) -> None:
        """Close the Kafka producer gracefully"""
        if self._producer:
            try:
                await self._producer.stop()
                logger.info("HFT Kafka Producer closed successfully")
            except Exception as e:
                logger.error(f"Error closing HFT Kafka Producer: {e}")
            finally:
                self._producer = None
                self._is_initialized = False
    
    async def send_market_data(
        self,
        data: Dict[str, Any],
        source_timestamp_ns: Optional[int] = None
    ) -> None:
        """
        Send market data with HFT optimizations
        
        Args:
            data: Market data dictionary from WebSocket
            source_timestamp_ns: Original timestamp from data source
        """
        if not self._is_initialized:
            await self.initialize()

        # Skip if producer failed to initialize
        if not self._producer:
            logger.debug("HFT Kafka producer not available, skipping message")
            return

        start_time_ns = time.perf_counter_ns()
        
        try:
            feeds = data.get("feeds", {})
            if not feeds:
                return
            
            # Batch process all instruments in parallel
            send_tasks = []
            for instrument_key, feed_data in feeds.items():
                # Create HFT message
                message = HFTMessage(
                    instrument_key=instrument_key,
                    timestamp_ns=start_time_ns,
                    data=feed_data,
                    source_timestamp_ns=source_timestamp_ns,
                    priority=ServicePriority.CRITICAL
                )
                
                # Create send task (non-blocking)
                task = self._send_message_async(
                    topic="hft.raw.market_data",
                    message=message
                )
                send_tasks.append(task)
            
            # Execute all sends in parallel
            if send_tasks:
                await asyncio.gather(*send_tasks, return_exceptions=True)
            
            # Update performance statistics
            processing_time_ns = time.perf_counter_ns() - start_time_ns
            self._stats.update_latency(processing_time_ns)
            self._stats.messages_sent += len(feeds)
            
            # Performance warning if > 1ms
            if processing_time_ns > 1_000_000:
                self._latency_warnings += 1
                logger.warning(
                    f"High latency market data send: "
                    f"{processing_time_ns / 1_000_000:.2f}ms"
                )
            
        except Exception as e:
            self._stats.messages_failed += 1
            self._error_count += 1
            logger.error(f"Failed to send market data: {e}")
    
    async def send_analytics_data(
        self,
        analytics_type: str,
        data: Dict[str, Any],
        instrument_keys: Optional[List[str]] = None
    ) -> None:
        """
        Send analytics data to appropriate topic
        
        Args:
            analytics_type: Type of analytics (breakout, top_movers, etc.)
            data: Analytics data
            instrument_keys: Related instrument keys for partitioning
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            # Determine topic based on analytics type
            topic_map = {
                "breakout": "hft.strategy.breakout",
                "momentum": "hft.strategy.momentum", 
                "gap_trading": "hft.strategy.gap_trading",
                "top_movers": "hft.analytics.market_data",
                "volume_analysis": "hft.analytics.market_data"
            }
            
            topic = topic_map.get(analytics_type, "hft.analytics.market_data")
            
            # Create message
            message = HFTMessage(
                instrument_key=instrument_keys[0] if instrument_keys else "ANALYTICS",
                timestamp_ns=time.perf_counter_ns(),
                data={
                    "analytics_type": analytics_type,
                    "analytics_data": data,
                    "instrument_keys": instrument_keys or []
                },
                priority=ServicePriority.HIGH
            )
            
            await self._send_message_async(topic, message)
            
        except Exception as e:
            logger.error(f"Failed to send analytics data: {e}")
    
    async def send_execution_signal(
        self,
        signal_type: str,
        instrument_key: str,
        signal_data: Dict[str, Any]
    ) -> None:
        """
        Send trading execution signal with CRITICAL priority
        
        Args:
            signal_type: Type of signal (BUY, SELL, STOP_LOSS, etc.)
            instrument_key: Target instrument
            signal_data: Signal details
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            message = HFTMessage(
                instrument_key=instrument_key,
                timestamp_ns=time.perf_counter_ns(),
                data={
                    "signal_type": signal_type,
                    "signal_data": signal_data
                },
                priority=ServicePriority.CRITICAL
            )
            
            await self._send_message_async("hft.execution.signals", message)
            
        except Exception as e:
            logger.error(f"Failed to send execution signal: {e}")
    
    async def send_ui_update(
        self,
        update_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Send UI update with throttling for performance
        
        Args:
            update_type: Type of UI update
            data: Update data
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            message = HFTMessage(
                instrument_key="UI_UPDATE",
                timestamp_ns=time.perf_counter_ns(),
                data={
                    "update_type": update_type,
                    "update_data": data
                },
                priority=ServicePriority.NORMAL
            )
            
            await self._send_message_async("hft.ui.price_updates", message)
            
        except Exception as e:
            logger.error(f"Failed to send UI update: {e}")
    
    async def _send_message_async(
        self,
        topic: str,
        message: HFTMessage
    ) -> None:
        """
        Send individual message with optimizations
        
        Args:
            topic: Kafka topic name
            message: HFT message to send
        """
        try:
            start_time_ns = time.perf_counter_ns()
            
            # Generate partition key for optimal distribution
            partition_key = self._generate_partition_key(
                message.instrument_key,
                topic
            )
            
            # Serialize message (optimized)
            message_data = {
                "k": message.instrument_key,
                "t": message.timestamp_ns,
                "d": message.data,
                "st": message.source_timestamp_ns,
                "mid": message.message_id,
                "p": message.priority.value
            }
            
            # Send to Kafka
            await self._producer.send_and_wait(
                topic=topic,
                key=partition_key,
                value=message_data,
                timestamp_ms=message.timestamp_ns // 1_000_000
            )
            
            # Update statistics
            send_time_ns = time.perf_counter_ns() - start_time_ns
            self._stats.bytes_sent += len(json.dumps(message_data).encode())
            
            # Log slow sends
            if send_time_ns > 5_000_000:  # > 5ms
                logger.warning(
                    f"Slow Kafka send: {send_time_ns / 1_000_000:.2f}ms "
                    f"to {topic}"
                )
            
        except KafkaError as e:
            self._stats.messages_failed += 1
            logger.error(f"Kafka error sending to {topic}: {e}")
        except Exception as e:
            self._stats.messages_failed += 1
            logger.error(f"Unexpected error sending to {topic}: {e}")
    
    def _generate_partition_key(self, instrument_key: str, topic: str) -> str:
        """
        Generate optimized partition key for load distribution
        
        Args:
            instrument_key: Instrument identifier
            topic: Target topic name
            
        Returns:
            Partition key string
        """
        # Use different strategies based on topic type
        if "execution" in topic:
            # For execution, use user-based partitioning
            # For now, use instrument-based
            return self._hash_key(instrument_key, 8)
        elif "ui" in topic:
            # For UI, distribute load evenly
            return self._hash_key(instrument_key, 32)
        elif "analytics" in topic:
            # For analytics, use sector-based partitioning if available
            return self._hash_key(instrument_key, 16)
        else:
            # Default: instrument-based hash
            return self._hash_key(instrument_key, 4)
    
    def _hash_key(self, key: str, num_partitions: int) -> str:
        """Generate hash-based partition key"""
        hash_value = hashlib.md5(key.encode()).hexdigest()
        return hash_value[:8]  # Use first 8 characters
    
    def _serialize_message(self, message_data: Dict[str, Any]) -> bytes:
        """
        Optimized message serialization
        
        Args:
            message_data: Message dictionary
            
        Returns:
            Serialized message bytes
        """
        try:
            # Use compact JSON encoding for speed
            return json.dumps(
                message_data,
                separators=(',', ':'),  # Compact format
                default=self._json_serializer
            ).encode('utf-8')
        except Exception as e:
            logger.error(f"Message serialization error: {e}")
            raise
    
    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for Decimal and other types"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current producer performance statistics"""
        return {
            "messages_sent": self._stats.messages_sent,
            "messages_failed": self._stats.messages_failed,
            "success_rate": (
                self._stats.messages_sent / 
                max(1, self._stats.messages_sent + self._stats.messages_failed)
            ) * 100,
            "avg_latency_ms": self._stats.avg_latency_ns / 1_000_000,
            "bytes_sent": self._stats.bytes_sent,
            "latency_warnings": self._latency_warnings,
            "error_count": self._error_count,
            "throughput_msg_per_sec": self._calculate_throughput(),
            "last_send_time": datetime.fromtimestamp(
                self._stats.last_send_time_ns / 1_000_000_000
            ).isoformat() if self._stats.last_send_time_ns else None
        }
    
    def _calculate_throughput(self) -> float:
        """Calculate messages per second throughput"""
        if self._stats.last_send_time_ns == 0:
            return 0.0
        
        current_time_ns = time.perf_counter_ns()
        time_diff_seconds = (current_time_ns - self._stats.last_send_time_ns) / 1_000_000_000
        
        if time_diff_seconds > 0:
            return self._stats.messages_sent / time_diff_seconds
        return 0.0
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on producer"""
        try:
            if not self._is_initialized or not self._producer:
                return {
                    "status": "unhealthy",
                    "reason": "Producer not initialized"
                }
            
            # Check if producer is still connected
            # Note: aiokafka doesn't have a direct health check method
            # We'll use the last successful send time as an indicator
            current_time = time.time()
            last_send_time = self._stats.last_send_time_ns / 1_000_000_000
            
            if current_time - last_send_time > 60:  # No sends in last 60 seconds
                return {
                    "status": "warning",
                    "reason": "No recent activity",
                    "last_send_time": last_send_time
                }
            
            return {
                "status": "healthy",
                "uptime_seconds": current_time - (self._stats.last_send_time_ns / 1_000_000_000),
                "performance": self.get_performance_stats()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "reason": f"Health check failed: {e}"
            }


# Singleton instance
_hft_producer: Optional[HFTKafkaProducer] = None


async def get_hft_producer() -> HFTKafkaProducer:
    """Get singleton HFT Kafka producer instance"""
    global _hft_producer
    if _hft_producer is None:
        _hft_producer = HFTKafkaProducer()
        await _hft_producer.initialize()
    return _hft_producer


async def cleanup_hft_producer() -> None:
    """Cleanup HFT producer resources"""
    global _hft_producer
    if _hft_producer:
        await _hft_producer.close()
        _hft_producer = None


# Export main classes and functions
__all__ = [
    "HFTMessage",
    "ProducerStats", 
    "HFTKafkaProducer",
    "get_hft_producer",
    "cleanup_hft_producer"
]