"""
HFT Service-Specific Kafka Consumers Module

Ultra-low latency Kafka consumers optimized for specific trading services
with sub-millisecond processing targets and vectorized operations.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional, Set, Callable, Deque
from dataclasses import dataclass, field
from collections import deque, defaultdict
from abc import ABC, abstractmethod
from decimal import Decimal
import hashlib

import numpy as np
import aiokafka
from aiokafka.errors import KafkaError

from .config import get_hft_kafka_config, get_topic_manager, ServicePriority

logger = logging.getLogger(__name__)


@dataclass
class ConsumerStats:
    """Consumer performance statistics"""
    messages_processed: int = 0
    messages_failed: int = 0
    total_processing_time_ns: int = 0
    avg_processing_time_ns: float = 0.0
    last_message_time_ns: int = 0
    throughput_msg_per_sec: float = 0.0
    
    def update_processing_time(self, processing_time_ns: int) -> None:
        """Update processing time statistics"""
        self.total_processing_time_ns += processing_time_ns
        self.last_message_time_ns = time.perf_counter_ns()
        
        # Exponential moving average
        if self.avg_processing_time_ns == 0.0:
            self.avg_processing_time_ns = float(processing_time_ns)
        else:
            self.avg_processing_time_ns = (
                (self.avg_processing_time_ns * 0.9) + 
                (processing_time_ns * 0.1)
            )


class BaseHFTConsumer(ABC):
    """Base class for HFT Kafka consumers with common functionality"""
    
    def __init__(self, service_name: str, topics: List[str], group_id: str):
        self.service_name = service_name
        self.topics = topics
        self.group_id = group_id
        self._config = get_hft_kafka_config()
        self._stats = ConsumerStats()
        self._consumer: Optional[aiokafka.AIOKafkaConsumer] = None
        self._is_running = False
        self._processing_queue = asyncio.Queue(maxsize=1000)
        
        # Performance optimization
        self._batch_processing = True
        self._max_batch_size = 50
        self._batch_timeout_ms = 1
        
        logger.info(f"HFT Consumer initialized: {service_name}")
    
    async def start_consuming(self) -> None:
        """Start consuming from Kafka topics"""
        try:
            self._consumer = aiokafka.AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self._config.bootstrap_servers,
                group_id=self.group_id,
                client_id=f"{self._config.client_id}_{self.service_name}",
                value_deserializer=lambda x: json.loads(x.decode()),
                **self._config.consumer_config
            )
            
            await self._consumer.start()
            self._is_running = True
            
            logger.info(f"✅ HFT Consumer started: {self.service_name}")
            
            # Start processing tasks
            consumer_task = asyncio.create_task(self._consume_messages())
            processor_task = asyncio.create_task(self._process_batch_messages())
            
            await asyncio.gather(consumer_task, processor_task, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Failed to start HFT consumer {self.service_name}: {e}")
            raise
        finally:
            await self.stop_consuming()
    
    async def stop_consuming(self) -> None:
        """Stop consuming and cleanup resources"""
        self._is_running = False
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        logger.info(f"✅ HFT Consumer stopped: {self.service_name}")
    
    async def _consume_messages(self) -> None:
        """Consume messages from Kafka and queue for processing"""
        try:
            async for message in self._consumer:
                if not self._is_running:
                    break
                
                try:
                    # Add to processing queue (non-blocking)
                    self._processing_queue.put_nowait(message.value)
                except asyncio.QueueFull:
                    # Drop oldest message if queue is full
                    try:
                        self._processing_queue.get_nowait()
                        self._processing_queue.put_nowait(message.value)
                    except asyncio.QueueEmpty:
                        pass
                    
        except Exception as e:
            logger.error(f"❌ Consumer error in {self.service_name}: {e}")
    
    async def _process_batch_messages(self) -> None:
        """Process messages in batches for optimal performance"""
        while self._is_running:
            try:
                batch_messages = await self._collect_batch_messages()
                if batch_messages:
                    await self._process_message_batch(batch_messages)
            except Exception as e:
                logger.error(f"❌ Batch processing error in {self.service_name}: {e}")
                await asyncio.sleep(0.001)  # 1ms delay on error
    
    async def _collect_batch_messages(self) -> List[Dict[str, Any]]:
        """Collect batch of messages for processing"""
        batch_messages = []
        
        try:
            # Get first message (blocking with timeout)
            first_message = await asyncio.wait_for(
                self._processing_queue.get(),
                timeout=self._batch_timeout_ms / 1000.0
            )
            batch_messages.append(first_message)
            
            # Collect additional messages (non-blocking)
            for _ in range(self._max_batch_size - 1):
                try:
                    message = self._processing_queue.get_nowait()
                    batch_messages.append(message)
                except asyncio.QueueEmpty:
                    break
                    
        except asyncio.TimeoutError:
            pass
        
        return batch_messages
    
    async def _process_message_batch(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of messages"""
        start_time_ns = time.perf_counter_ns()
        
        try:
            # Process messages using derived class implementation
            await self.process_messages(messages)
            
            # Update statistics
            processing_time_ns = time.perf_counter_ns() - start_time_ns
            self._stats.messages_processed += len(messages)
            self._stats.update_processing_time(processing_time_ns)
            
            # Performance warning if batch takes > 5ms
            if processing_time_ns > 5_000_000:
                logger.warning(
                    f"⚠️ Slow batch processing in {self.service_name}: "
                    f"{processing_time_ns / 1_000_000:.2f}ms for {len(messages)} messages"
                )
            
        except Exception as e:
            self._stats.messages_failed += len(messages)
            logger.error(f"❌ Message processing error in {self.service_name}: {e}")
    
    @abstractmethod
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of messages - implemented by derived classes"""
        pass
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get consumer performance statistics"""
        return {
            "service_name": self.service_name,
            "messages_processed": self._stats.messages_processed,
            "messages_failed": self._stats.messages_failed,
            "avg_processing_time_ms": self._stats.avg_processing_time_ns / 1_000_000,
            "throughput_msg_per_sec": self._stats.throughput_msg_per_sec,
            "queue_size": self._processing_queue.qsize(),
            "is_running": self._is_running
        }


class HFTInstrumentRegistryConsumer(BaseHFTConsumer):
    """HFT Consumer for Instrument Registry - Priority 1"""
    
    def __init__(self, instrument_registry=None):
        super().__init__(
            service_name="instrument_registry",
            topics=["hft.shared_memory.feed"],
            group_id="instrument_registry_group"
        )
        self.registry = instrument_registry
        self._price_updates = defaultdict(dict)
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process instrument registry updates with vectorized operations"""
        try:
            # Group updates by instrument for deduplication
            latest_updates = {}
            
            for message in messages:
                instrument_key = message.get("k")
                if instrument_key:
                    latest_updates[instrument_key] = message
            
            # Batch update registry
            if self.registry and latest_updates:
                await self._batch_update_registry(latest_updates)
                
        except Exception as e:
            logger.error(f"❌ Instrument registry processing error: {e}")
    
    async def _batch_update_registry(self, updates: Dict[str, Dict[str, Any]]) -> None:
        """Batch update instrument registry"""
        try:
            if not hasattr(self.registry, 'batch_update_prices'):
                # Fallback to individual updates
                for instrument_key, message in updates.items():
                    await self._update_single_instrument(instrument_key, message)
            else:
                # Use vectorized batch update
                await self.registry.batch_update_prices(updates)
                
        except Exception as e:
            logger.error(f"❌ Registry batch update error: {e}")
    
    async def _update_single_instrument(self, instrument_key: str, message: Dict[str, Any]) -> None:
        """Update single instrument in registry"""
        try:
            feed_data = message.get("d", {})
            
            # Extract price data
            price_data = {
                "ltp": feed_data.get("ltp", 0),
                "volume": feed_data.get("volume", 0),
                "timestamp": message.get("t", time.perf_counter_ns())
            }
            
            # Update registry
            if hasattr(self.registry, 'update_live_price'):
                await self.registry.update_live_price(instrument_key, price_data)
            
        except Exception as e:
            logger.error(f"❌ Single instrument update error for {instrument_key}: {e}")


class HFTBreakoutEngineConsumer(BaseHFTConsumer):
    """HFT Consumer for Enhanced Breakout Engine"""
    
    def __init__(self, breakout_engine=None):
        super().__init__(
            service_name="breakout_engine", 
            topics=["hft.strategy.breakout"],
            group_id="breakout_strategy_group"
        )
        self.engine = breakout_engine
        self._price_buffers: Dict[str, Deque] = defaultdict(lambda: deque(maxlen=100))
        self._pattern_cache: Dict[str, Dict] = {}
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process breakout detection with vectorized analysis"""
        try:
            # Group messages by instrument
            instrument_data = defaultdict(list)
            
            for message in messages:
                instrument_key = message.get("k")
                if instrument_key:
                    instrument_data[instrument_key].append(message)
            
            # Process each instrument's data
            breakout_signals = []
            for instrument_key, data_list in instrument_data.items():
                # Use latest data point
                latest_data = data_list[-1]
                signal = await self._detect_breakout(instrument_key, latest_data)
                if signal:
                    breakout_signals.append(signal)
            
            # Publish breakout signals
            if breakout_signals:
                await self._publish_breakout_signals(breakout_signals)
                
        except Exception as e:
            logger.error(f"❌ Breakout engine processing error: {e}")
    
    async def _detect_breakout(self, instrument_key: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect breakout patterns for instrument"""
        try:
            feed_data = message.get("d", {})
            
            # Extract price information
            price_info = {
                "ltp": float(feed_data.get("ltp", 0)),
                "volume": int(feed_data.get("volume", 0)),
                "timestamp": message.get("t", time.perf_counter_ns())
            }
            
            if price_info["ltp"] <= 0:
                return None
            
            # Update price buffer
            self._price_buffers[instrument_key].append(price_info)
            
            # Need sufficient history for breakout detection
            if len(self._price_buffers[instrument_key]) < 20:
                return None
            
            # Calculate support/resistance levels
            recent_prices = list(self._price_buffers[instrument_key])
            prices = [p["ltp"] for p in recent_prices[-20:]]
            volumes = [p["volume"] for p in recent_prices[-20:]]
            
            resistance = np.max(prices)
            support = np.min(prices)
            avg_volume = np.mean(volumes) if volumes else 0
            current_ltp = price_info["ltp"]
            current_volume = price_info["volume"]
            
            # Detect breakout conditions
            breakout_type = None
            if current_ltp > resistance * 1.005:  # 0.5% above resistance
                breakout_type = "RESISTANCE_BREAKOUT"
            elif current_ltp < support * 0.995:  # 0.5% below support
                breakout_type = "SUPPORT_BREAKDOWN"
            
            # Confirm with volume
            if breakout_type and current_volume > avg_volume * 1.5:
                return {
                    "instrument_key": instrument_key,
                    "breakout_type": breakout_type,
                    "ltp": current_ltp,
                    "resistance": float(resistance),
                    "support": float(support),
                    "volume": current_volume,
                    "avg_volume": float(avg_volume),
                    "timestamp": price_info["timestamp"],
                    "confidence": self._calculate_confidence(prices, current_ltp, breakout_type)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Breakout detection error for {instrument_key}: {e}")
            return None
    
    def _calculate_confidence(self, prices: List[float], current_ltp: float, breakout_type: str) -> float:
        """Calculate breakout confidence score"""
        try:
            if not prices:
                return 0.0
            
            price_range = np.max(prices) - np.min(prices)
            if price_range == 0:
                return 0.0
            
            # Calculate breakout magnitude as percentage of recent range
            if breakout_type == "RESISTANCE_BREAKOUT":
                breakout_magnitude = (current_ltp - np.max(prices)) / price_range
            else:  # SUPPORT_BREAKDOWN
                breakout_magnitude = (np.min(prices) - current_ltp) / price_range
            
            # Confidence based on breakout magnitude (0-100%)
            confidence = min(breakout_magnitude * 100, 100.0)
            return max(confidence, 0.0)
            
        except Exception:
            return 0.0
    
    async def _publish_breakout_signals(self, signals: List[Dict[str, Any]]) -> None:
        """Publish breakout signals to execution engine"""
        try:
            # Here you would publish to execution topic or notify trading engine
            logger.info(f"📈 Detected {len(signals)} breakout signals")
            for signal in signals:
                logger.debug(
                    f"🚨 {signal['breakout_type']} for {signal['instrument_key']} "
                    f"at {signal['ltp']} (confidence: {signal['confidence']:.1f}%)"
                )
        except Exception as e:
            logger.error(f"❌ Error publishing breakout signals: {e}")


class HFTPremarketConsumer(BaseHFTConsumer):
    """HFT Consumer for Premarket Candle Building (Time-Window Specific)"""
    
    def __init__(self, candle_builder=None):
        super().__init__(
            service_name="premarket_candle",
            topics=["hft.premarket.candles"],
            group_id="premarket_group"
        )
        self.builder = candle_builder
        self._candle_data: Dict[str, Dict] = defaultdict(dict)
        self._active_window = False
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process premarket candle building (9:00-9:08 AM window only)"""
        try:
            # Check if we're in premarket window
            if not self._is_premarket_window():
                return
            
            # Process tick data for candle building
            for message in messages:
                instrument_key = message.get("k")
                if instrument_key:
                    await self._process_premarket_tick(instrument_key, message)
                    
        except Exception as e:
            logger.error(f"❌ Premarket processing error: {e}")
    
    def _is_premarket_window(self) -> bool:
        """Check if current time is within premarket window (9:00-9:08 AM)"""
        from datetime import datetime
        now = datetime.now()
        start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=9, minute=8, second=0, microsecond=0)
        return start_time <= now <= end_time
    
    async def _process_premarket_tick(self, instrument_key: str, message: Dict[str, Any]) -> None:
        """Process individual tick for premarket candle"""
        try:
            feed_data = message.get("d", {})
            
            tick_data = {
                "price": float(feed_data.get("ltp", 0)),
                "volume": int(feed_data.get("volume", 0)),
                "timestamp": message.get("t", time.perf_counter_ns())
            }
            
            if tick_data["price"] <= 0:
                return
            
            # Update candle data
            if instrument_key not in self._candle_data:
                self._candle_data[instrument_key] = {
                    "open": tick_data["price"],
                    "high": tick_data["price"],
                    "low": tick_data["price"],
                    "close": tick_data["price"],
                    "volume": tick_data["volume"],
                    "start_time": tick_data["timestamp"],
                    "last_update": tick_data["timestamp"]
                }
            else:
                candle = self._candle_data[instrument_key]
                candle["high"] = max(candle["high"], tick_data["price"])
                candle["low"] = min(candle["low"], tick_data["price"])
                candle["close"] = tick_data["price"]
                candle["volume"] = tick_data["volume"]  # Assuming cumulative volume
                candle["last_update"] = tick_data["timestamp"]
            
            # Update candle builder if available
            if self.builder and hasattr(self.builder, 'update_premarket_candle'):
                await self.builder.update_premarket_candle(instrument_key, tick_data)
                
        except Exception as e:
            logger.error(f"❌ Premarket tick processing error for {instrument_key}: {e}")


class HFTMarketAnalyticsConsumer(BaseHFTConsumer):
    """HFT Consumer for Enhanced Market Analytics"""
    
    def __init__(self, analytics_service=None):
        super().__init__(
            service_name="market_analytics",
            topics=["hft.analytics.market_data"],
            group_id="enhanced_market_analytics_group"
        )
        self.analytics = analytics_service
        self._market_data_cache: Dict[str, Dict] = {}
        self._calculation_interval = 30  # Calculate analytics every 30 seconds
        self._last_calculation = 0
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process market analytics calculations"""
        try:
            # Update market data cache
            for message in messages:
                instrument_key = message.get("k")
                if instrument_key:
                    self._market_data_cache[instrument_key] = message
            
            # Calculate analytics if interval elapsed
            current_time = time.time()
            if current_time - self._last_calculation >= self._calculation_interval:
                await self._calculate_market_analytics()
                self._last_calculation = current_time
                
        except Exception as e:
            logger.error(f"❌ Market analytics processing error: {e}")
    
    async def _calculate_market_analytics(self) -> None:
        """Calculate comprehensive market analytics"""
        try:
            if not self._market_data_cache:
                return
            
            # Calculate top movers
            top_movers = await self._calculate_top_movers()
            
            # Calculate sector performance
            sector_performance = await self._calculate_sector_performance()
            
            # Calculate volume leaders
            volume_leaders = await self._calculate_volume_leaders()
            
            # Publish analytics results
            analytics_result = {
                "top_movers": top_movers,
                "sector_performance": sector_performance,
                "volume_leaders": volume_leaders,
                "timestamp": time.perf_counter_ns(),
                "total_instruments": len(self._market_data_cache)
            }
            
            if self.analytics and hasattr(self.analytics, 'update_analytics_cache'):
                await self.analytics.update_analytics_cache(analytics_result)
            
            logger.debug(f"📊 Market analytics calculated for {len(self._market_data_cache)} instruments")
            
        except Exception as e:
            logger.error(f"❌ Market analytics calculation error: {e}")
    
    async def _calculate_top_movers(self) -> Dict[str, List[Dict]]:
        """Calculate top gainers and losers"""
        try:
            movers = []
            
            for instrument_key, message in self._market_data_cache.items():
                feed_data = message.get("d", {})
                ltp = float(feed_data.get("ltp", 0))
                previous_close = float(feed_data.get("previous_close", 0))
                
                if ltp > 0 and previous_close > 0:
                    change_percent = ((ltp - previous_close) / previous_close) * 100
                    movers.append({
                        "instrument_key": instrument_key,
                        "ltp": ltp,
                        "change_percent": change_percent,
                        "volume": int(feed_data.get("volume", 0))
                    })
            
            # Sort by change percentage
            movers.sort(key=lambda x: x["change_percent"], reverse=True)
            
            return {
                "top_gainers": movers[:10],
                "top_losers": movers[-10:][::-1]  # Reverse for ascending order
            }
            
        except Exception as e:
            logger.error(f"❌ Top movers calculation error: {e}")
            return {"top_gainers": [], "top_losers": []}
    
    async def _calculate_sector_performance(self) -> Dict[str, float]:
        """Calculate sector-wise performance"""
        try:
            # This would require sector mapping - simplified implementation
            sector_data = defaultdict(list)
            
            for instrument_key, message in self._market_data_cache.items():
                feed_data = message.get("d", {})
                ltp = float(feed_data.get("ltp", 0))
                previous_close = float(feed_data.get("previous_close", 0))
                
                if ltp > 0 and previous_close > 0:
                    change_percent = ((ltp - previous_close) / previous_close) * 100
                    
                    # Extract sector from instrument key (simplified)
                    sector = "UNKNOWN"
                    if "BANK" in instrument_key.upper():
                        sector = "BANKING"
                    elif "IT" in instrument_key.upper():
                        sector = "IT"
                    elif "AUTO" in instrument_key.upper():
                        sector = "AUTO"
                    
                    sector_data[sector].append(change_percent)
            
            # Calculate average performance per sector
            sector_performance = {}
            for sector, changes in sector_data.items():
                if changes:
                    sector_performance[sector] = np.mean(changes)
            
            return sector_performance
            
        except Exception as e:
            logger.error(f"❌ Sector performance calculation error: {e}")
            return {}
    
    async def _calculate_volume_leaders(self) -> List[Dict]:
        """Calculate volume leaders"""
        try:
            volume_data = []
            
            for instrument_key, message in self._market_data_cache.items():
                feed_data = message.get("d", {})
                volume = int(feed_data.get("volume", 0))
                ltp = float(feed_data.get("ltp", 0))
                
                if volume > 0 and ltp > 0:
                    value_traded = volume * ltp
                    volume_data.append({
                        "instrument_key": instrument_key,
                        "volume": volume,
                        "ltp": ltp,
                        "value_traded": value_traded
                    })
            
            # Sort by volume
            volume_data.sort(key=lambda x: x["volume"], reverse=True)
            
            return volume_data[:20]  # Top 20 by volume
            
        except Exception as e:
            logger.error(f"❌ Volume leaders calculation error: {e}")
            return []


# Export main classes
__all__ = [
    "BaseHFTConsumer",
    "HFTInstrumentRegistryConsumer", 
    "HFTBreakoutEngineConsumer",
    "HFTPremarketConsumer",
    "HFTMarketAnalyticsConsumer",
    "ConsumerStats"
]