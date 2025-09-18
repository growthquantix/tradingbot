"""
HFT Memory-Mapped Kafka Bridge Module

Ultra-high performance bridge between Kafka streams and HFT shared memory
with sub-millisecond latency targets and vectorized batch processing.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import deque, defaultdict
import mmap
import struct
from decimal import Decimal

import numpy as np
import aiokafka
from aiokafka.errors import KafkaError

from .config import get_hft_kafka_config, get_topic_manager, ServicePriority

logger = logging.getLogger(__name__)


@dataclass
class MemoryBridgeStats:
    """Memory bridge performance statistics"""
    messages_processed: int = 0
    messages_failed: int = 0
    batch_writes_completed: int = 0
    total_processing_time_ns: int = 0
    avg_processing_time_ns: float = 0.0
    memory_writes_per_second: float = 0.0
    queue_utilization: float = 0.0
    last_batch_size: int = 0
    memory_utilization_mb: float = 0.0
    
    def update_processing_time(self, processing_time_ns: int) -> None:
        """Update processing time with exponential moving average"""
        self.total_processing_time_ns += processing_time_ns
        
        # Exponential moving average (95% old, 5% new)
        if self.avg_processing_time_ns == 0.0:
            self.avg_processing_time_ns = float(processing_time_ns)
        else:
            self.avg_processing_time_ns = (
                (self.avg_processing_time_ns * 0.95) + 
                (processing_time_ns * 0.05)
            )


@dataclass
class InstrumentUpdate:
    """Optimized instrument update for batch processing"""
    instrument_key: str
    timestamp_ns: int
    ltp: float
    volume: int
    bid_price: float = 0.0
    ask_price: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    previous_close: float = 0.0
    change_percent: float = 0.0


class HFTMemoryBridge:
    """
    HFT Memory-Mapped Kafka Bridge
    
    Features:
    - Sub-millisecond memory writes
    - Vectorized batch processing
    - Lock-free queue operations
    - Memory-mapped file optimization
    - Performance monitoring
    """
    
    def __init__(self, hft_data_hub=None):
        self.hft_data_hub = hft_data_hub
        self._config = get_hft_kafka_config()
        self._stats = MemoryBridgeStats()
        
        # High-performance processing queue
        self.processing_queue = asyncio.Queue(maxsize=10000)
        self.batch_processing_enabled = True
        self.max_batch_size = 100
        self.batch_timeout_ms = 1  # 1ms batch timeout
        
        # Memory optimization
        self._instrument_cache: Dict[str, int] = {}  # instrument_key -> index
        self._last_updates: Dict[str, InstrumentUpdate] = {}
        self._batch_buffer: List[InstrumentUpdate] = []
        
        # Performance tracking
        self._is_running = False
        self._last_performance_log = 0
        self._consumer_tasks: Set[asyncio.Task] = set()
        
        logger.info("HFT Memory Bridge initialized")
    
    async def initialize(self, hft_data_hub=None) -> None:
        """Initialize the memory bridge with HFT data hub"""
        if hft_data_hub:
            self.hft_data_hub = hft_data_hub
        
        if not self.hft_data_hub:
            try:
                # Try to get HFT data hub instance
                from services.hft_data_hub import get_hft_data_hub
                self.hft_data_hub = get_hft_data_hub()
                await self.hft_data_hub.initialize()
            except ImportError:
                logger.error("❌ HFT Data Hub not available - cannot initialize memory bridge")
                raise
        
        self._is_running = True
        logger.info("✅ HFT Memory Bridge initialized successfully")
    
    async def start_bridge(self) -> None:
        """Start the Kafka to memory bridge"""
        if not self._is_running:
            await self.initialize()
        
        try:
            # Start consumer for raw market data
            consumer_task = asyncio.create_task(self._start_raw_data_consumer())
            self._consumer_tasks.add(consumer_task)
            
            # Start batch processor
            processor_task = asyncio.create_task(self._start_batch_processor())
            self._consumer_tasks.add(processor_task)
            
            # Start performance monitor
            monitor_task = asyncio.create_task(self._start_performance_monitor())
            self._consumer_tasks.add(monitor_task)
            
            logger.info("✅ HFT Memory Bridge started successfully")
            
            # Wait for all tasks
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Failed to start HFT Memory Bridge: {e}")
            raise
    
    async def stop_bridge(self) -> None:
        """Stop the memory bridge gracefully"""
        self._is_running = False
        
        # Cancel all consumer tasks
        for task in self._consumer_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for graceful shutdown
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        
        self._consumer_tasks.clear()
        logger.info("✅ HFT Memory Bridge stopped")
    
    async def _start_raw_data_consumer(self) -> None:
        """Start consuming raw market data from Kafka"""
        consumer = aiokafka.AIOKafkaConsumer(
            "hft.raw.market_data",
            bootstrap_servers=self._config.bootstrap_servers,
            group_id="hft_memory_bridge",
            client_id=f"{self._config.client_id}_memory_bridge",
            value_deserializer=lambda x: json.loads(x.decode()),
            **self._config.consumer_config
        )
        
        try:
            await consumer.start()
            logger.info("✅ HFT Memory Bridge consumer started")
            
            async for message in consumer:
                if not self._is_running:
                    break
                
                await self._process_kafka_message(message.value)
                
        except Exception as e:
            logger.error(f"❌ Raw data consumer error: {e}")
        finally:
            await consumer.stop()
    
    async def _process_kafka_message(self, message_data: Dict[str, Any]) -> None:
        """
        Process Kafka message and queue for batch processing
        
        Args:
            message_data: Kafka message data
        """
        try:
            start_time_ns = time.perf_counter_ns()
            
            # Extract feeds from message
            feeds = message_data.get("d", {}).get("feeds", {})
            if not feeds:
                return
            
            # Process each instrument in the message
            for instrument_key, feed_data in feeds.items():
                update = self._extract_instrument_update(
                    instrument_key, 
                    feed_data, 
                    message_data.get("t", start_time_ns)
                )
                
                if update:
                    # Add to processing queue (non-blocking)
                    try:
                        self.processing_queue.put_nowait(update)
                    except asyncio.QueueFull:
                        # Drop oldest messages if queue is full
                        try:
                            self.processing_queue.get_nowait()
                            self.processing_queue.put_nowait(update)
                        except asyncio.QueueEmpty:
                            pass
            
            # Update statistics
            processing_time_ns = time.perf_counter_ns() - start_time_ns
            self._stats.messages_processed += 1
            self._stats.update_processing_time(processing_time_ns)
            
        except Exception as e:
            self._stats.messages_failed += 1
            logger.error(f"❌ Error processing Kafka message: {e}")
    
    def _extract_instrument_update(
        self, 
        instrument_key: str, 
        feed_data: Dict[str, Any],
        timestamp_ns: int
    ) -> Optional[InstrumentUpdate]:
        """
        Extract instrument update from feed data
        
        Args:
            instrument_key: Instrument identifier
            feed_data: Feed data from Kafka message
            timestamp_ns: Message timestamp
            
        Returns:
            InstrumentUpdate object or None if invalid
        """
        try:
            # Handle both equity and index data structures
            full_feed = feed_data.get("fullFeed", {})
            
            # Try marketFF first (equity), then indexFF (index)
            market_data = (
                full_feed.get("marketFF") or 
                full_feed.get("indexFF") or 
                {}
            )
            
            if not market_data:
                return None
            
            # Extract LTPC (Last Traded Price and Close)
            ltpc = market_data.get("ltpc", {})
            ltp = float(ltpc.get("ltp", 0))
            previous_close = float(ltpc.get("cp", 0))
            
            if ltp <= 0:
                return None
            
            # Calculate change percentage
            change_percent = 0.0
            if previous_close > 0:
                change_percent = ((ltp - previous_close) / previous_close) * 100
            
            # Extract OHLC data
            ohlc_data = market_data.get("marketOHLC", {}).get("ohlc", [])
            daily_ohlc = {}
            if ohlc_data:
                # Find daily interval OHLC
                for ohlc in ohlc_data:
                    if ohlc.get("interval") == "1d":
                        daily_ohlc = ohlc
                        break
            
            # Extract bid/ask data
            bid_ask = market_data.get("marketLevel", {}).get("bidAskQuote", [])
            bid_price = 0.0
            ask_price = 0.0
            if bid_ask:
                best_quote = bid_ask[0]
                bid_price = float(best_quote.get("bidP", 0))
                ask_price = float(best_quote.get("askP", 0))
            
            # Create instrument update
            return InstrumentUpdate(
                instrument_key=instrument_key,
                timestamp_ns=timestamp_ns,
                ltp=ltp,
                volume=int(market_data.get("vtt", 0)),
                bid_price=bid_price,
                ask_price=ask_price,
                open_price=float(daily_ohlc.get("open", 0)),
                high_price=float(daily_ohlc.get("high", 0)),
                low_price=float(daily_ohlc.get("low", 0)),
                previous_close=previous_close,
                change_percent=change_percent
            )
            
        except Exception as e:
            logger.error(f"❌ Error extracting instrument update for {instrument_key}: {e}")
            return None
    
    async def _start_batch_processor(self) -> None:
        """Start batch processor for memory writes"""
        while self._is_running:
            try:
                batch_updates = await self._collect_batch_updates()
                
                if batch_updates:
                    await self._process_batch_updates(batch_updates)
                
            except Exception as e:
                logger.error(f"❌ Batch processor error: {e}")
                await asyncio.sleep(0.001)  # 1ms delay on error
    
    async def _collect_batch_updates(self) -> List[InstrumentUpdate]:
        """
        Collect batch of updates for processing
        
        Returns:
            List of instrument updates
        """
        batch_updates = []
        batch_start_time = time.perf_counter()
        
        try:
            # Get first update (blocking with timeout)
            first_update = await asyncio.wait_for(
                self.processing_queue.get(),
                timeout=self.batch_timeout_ms / 1000.0
            )
            batch_updates.append(first_update)
            
            # Collect additional updates (non-blocking)
            for _ in range(self.max_batch_size - 1):
                try:
                    update = self.processing_queue.get_nowait()
                    batch_updates.append(update)
                except asyncio.QueueEmpty:
                    break
                
                # Break if batch timeout exceeded
                if (time.perf_counter() - batch_start_time) > (self.batch_timeout_ms / 1000.0):
                    break
            
        except asyncio.TimeoutError:
            # No updates within timeout - continue
            pass
        
        return batch_updates
    
    async def _process_batch_updates(self, batch_updates: List[InstrumentUpdate]) -> None:
        """
        Process batch of updates with vectorized operations
        
        Args:
            batch_updates: List of instrument updates to process
        """
        try:
            start_time_ns = time.perf_counter_ns()
            
            # Group updates by instrument (keep latest for each)
            latest_updates = {}
            for update in batch_updates:
                latest_updates[update.instrument_key] = update
            
            # Vectorized memory writes
            if self.hft_data_hub and hasattr(self.hft_data_hub, 'batch_update_instruments'):
                await self.hft_data_hub.batch_update_instruments(
                    list(latest_updates.values())
                )
            else:
                # Fallback to individual updates
                for update in latest_updates.values():
                    await self._write_to_memory(update)
            
            # Update statistics
            processing_time_ns = time.perf_counter_ns() - start_time_ns
            self._stats.batch_writes_completed += 1
            self._stats.last_batch_size = len(latest_updates)
            
            # Calculate throughput
            if processing_time_ns > 0:
                writes_per_second = (len(latest_updates) * 1_000_000_000) / processing_time_ns
                self._stats.memory_writes_per_second = (
                    (self._stats.memory_writes_per_second * 0.9) + 
                    (writes_per_second * 0.1)
                )
            
            # Performance warning if batch takes > 5ms
            if processing_time_ns > 5_000_000:
                logger.warning(
                    f"⚠️ Slow batch processing: {processing_time_ns / 1_000_000:.2f}ms "
                    f"for {len(latest_updates)} instruments"
                )
            
        except Exception as e:
            self._stats.messages_failed += len(batch_updates)
            logger.error(f"❌ Batch processing error: {e}")
    
    async def _write_to_memory(self, update: InstrumentUpdate) -> None:
        """
        Write individual update to shared memory
        
        Args:
            update: Instrument update to write
        """
        try:
            if not self.hft_data_hub:
                return
            
            # Convert to HFT data hub format
            instrument_data = {
                "ltp": update.ltp,
                "volume": update.volume,
                "bid_price": update.bid_price,
                "ask_price": update.ask_price,
                "open": update.open_price,
                "high": update.high_price,
                "low": update.low_price,
                "previous_close": update.previous_close,
                "change_percent": update.change_percent,
                "timestamp": update.timestamp_ns
            }
            
            # Write to shared memory
            await self.hft_data_hub.update_instrument_data(
                update.instrument_key,
                instrument_data
            )
            
        except Exception as e:
            logger.error(f"❌ Memory write error for {update.instrument_key}: {e}")
    
    async def _start_performance_monitor(self) -> None:
        """Start performance monitoring task"""
        while self._is_running:
            try:
                await asyncio.sleep(10.0)  # Monitor every 10 seconds
                await self._log_performance_metrics()
            except Exception as e:
                logger.error(f"❌ Performance monitor error: {e}")
    
    async def _log_performance_metrics(self) -> None:
        """Log performance metrics"""
        try:
            # Calculate queue utilization
            queue_size = self.processing_queue.qsize()
            queue_utilization = (queue_size / self.processing_queue.maxsize) * 100
            self._stats.queue_utilization = queue_utilization
            
            # Log metrics if significant activity
            if self._stats.messages_processed > 0:
                logger.info(
                    f"📊 HFT Memory Bridge Stats: "
                    f"Processed: {self._stats.messages_processed}, "
                    f"Failed: {self._stats.messages_failed}, "
                    f"Avg Latency: {self._stats.avg_processing_time_ns / 1_000_000:.2f}ms, "
                    f"Writes/sec: {self._stats.memory_writes_per_second:.0f}, "
                    f"Queue: {queue_utilization:.1f}%, "
                    f"Last Batch: {self._stats.last_batch_size}"
                )
                
                # Reset counters for next period
                self._stats.messages_processed = 0
                self._stats.messages_failed = 0
        
        except Exception as e:
            logger.error(f"❌ Performance metrics error: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            "messages_processed": self._stats.messages_processed,
            "messages_failed": self._stats.messages_failed,
            "batch_writes_completed": self._stats.batch_writes_completed,
            "avg_processing_time_ms": self._stats.avg_processing_time_ns / 1_000_000,
            "memory_writes_per_second": self._stats.memory_writes_per_second,
            "queue_utilization_percent": self._stats.queue_utilization,
            "last_batch_size": self._stats.last_batch_size,
            "queue_size": self.processing_queue.qsize(),
            "queue_max_size": self.processing_queue.maxsize,
            "is_running": self._is_running
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on memory bridge"""
        try:
            if not self._is_running:
                return {
                    "status": "unhealthy",
                    "reason": "Bridge not running"
                }
            
            # Check queue health
            queue_utilization = (
                self.processing_queue.qsize() / self.processing_queue.maxsize
            ) * 100
            
            if queue_utilization > 90:
                return {
                    "status": "warning",
                    "reason": f"High queue utilization: {queue_utilization:.1f}%",
                    "queue_size": self.processing_queue.qsize()
                }
            
            # Check processing health
            if self._stats.avg_processing_time_ns > 10_000_000:  # > 10ms
                return {
                    "status": "warning",
                    "reason": f"High processing latency: {self._stats.avg_processing_time_ns / 1_000_000:.2f}ms"
                }
            
            return {
                "status": "healthy",
                "performance": self.get_performance_stats()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "reason": f"Health check failed: {e}"
            }


# Singleton instance
_hft_memory_bridge: Optional[HFTMemoryBridge] = None


async def get_hft_memory_bridge(hft_data_hub=None) -> HFTMemoryBridge:
    """Get singleton HFT Memory Bridge instance"""
    global _hft_memory_bridge
    if _hft_memory_bridge is None:
        _hft_memory_bridge = HFTMemoryBridge(hft_data_hub)
        await _hft_memory_bridge.initialize(hft_data_hub)
    return _hft_memory_bridge


async def cleanup_hft_memory_bridge() -> None:
    """Cleanup HFT Memory Bridge resources"""
    global _hft_memory_bridge
    if _hft_memory_bridge:
        await _hft_memory_bridge.stop_bridge()
        _hft_memory_bridge = None


# Export main classes and functions
__all__ = [
    "MemoryBridgeStats",
    "InstrumentUpdate",
    "HFTMemoryBridge",
    "get_hft_memory_bridge",
    "cleanup_hft_memory_bridge"
]