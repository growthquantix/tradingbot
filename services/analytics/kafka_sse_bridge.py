"""
Kafka-SSE Integration Bridge

Connects Kafka consumers to SSE broadcasting for real-time UI updates.
Implements clean separation between messaging and UI layers.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from services.hft.consumers import BaseHFTConsumer
from services.sse.sse_manager import get_sse_manager, SSEChannel

logger = logging.getLogger(__name__)


class KafkaSSEBridge(BaseHFTConsumer):
    """
    Bridge service that consumes from UI-specific Kafka topics
    and broadcasts updates to SSE channels for real-time UI updates.
    
    Follows clean architecture by separating:
    - Kafka consumption (messaging layer)
    - SSE broadcasting (presentation layer)
    - Data transformation (business layer)
    """
    
    def __init__(self):
        super().__init__(
            service_name="kafka_sse_bridge",
            topics=["hft.ui.price_updates"],
            group_id="kafka_sse_bridge_group"
        )
        
        self._sse_manager = None
        self._processed_messages = 0
        self._broadcast_count = 0
        self._last_broadcast_time = datetime.now()
        
        # Message throttling to prevent UI overload
        self._throttle_interval = 0.1  # 100ms minimum between broadcasts
        self._last_broadcast_by_type = {}
        
        logger.info("✅ Kafka-SSE Bridge initialized")
    
    async def initialize(self) -> None:
        """Initialize SSE manager dependency"""
        try:
            self._sse_manager = get_sse_manager()
            logger.info("✅ Kafka-SSE Bridge dependencies initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka-SSE Bridge: {e}")
            raise
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of messages from Kafka - required by BaseHFTConsumer"""
        await self._process_message_batch(messages)
    
    async def _process_message_batch(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of messages from Kafka UI topic"""
        try:
            if not messages:
                return
            
            # Group messages by type for efficient processing
            grouped_messages = self._group_messages_by_type(messages)
            
            # Process each message type
            for message_type, message_list in grouped_messages.items():
                await self._process_message_type(message_type, message_list)
            
            self._processed_messages += len(messages)
            logger.debug(f"📡 Processed {len(messages)} messages for SSE broadcast")
            
        except Exception as e:
            logger.error(f"❌ Error processing Kafka messages for SSE: {e}")
    
    def _group_messages_by_type(self, messages: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Group messages by their update type"""
        grouped = {}
        
        for message in messages:
            update_type = message.get('update_type', 'unknown')
            if update_type not in grouped:
                grouped[update_type] = []
            grouped[update_type].append(message)
        
        return grouped
    
    async def _process_message_type(self, message_type: str, messages: List[Dict[str, Any]]) -> None:
        """Process specific message type"""
        try:
            # Check throttling
            if not self._should_broadcast(message_type):
                return
            
            # Route to appropriate handler
            if message_type == 'live_price_updates':
                await self._handle_price_updates(messages)
            elif message_type == 'batch_price_update':
                await self._handle_batch_price_updates(messages)
            elif message_type == 'analytics_update':
                await self._handle_analytics_updates(messages)
            elif message_type == 'trading_signal':
                await self._handle_trading_signals(messages)
            else:
                await self._handle_generic_updates(message_type, messages)
            
            self._last_broadcast_by_type[message_type] = datetime.now()
            self._broadcast_count += 1
            
        except Exception as e:
            logger.error(f"❌ Error processing {message_type} messages: {e}")
    
    async def _handle_price_updates(self, messages: List[Dict[str, Any]]) -> None:
        """Handle live price update messages"""
        try:
            # Combine all price data from messages
            combined_prices = {}
            update_count = 0
            
            for message in messages:
                message_data = message.get('update_data', {})
                prices = message_data.get('prices', {})
                combined_prices.update(prices)
                update_count += message_data.get('count', 0)
            
            if combined_prices:
                # Broadcast to market data channel
                await self._sse_manager.broadcast_to_channel(
                    channel=SSEChannel.MARKET_DATA,
                    event_type='price_update',
                    data={
                        'prices': combined_prices,
                        'count': len(combined_prices),
                        'total_updates': update_count,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'kafka_bridge'
                    },
                    priority=1  # High priority for price updates
                )
                
                logger.debug(f"📊 Broadcast {len(combined_prices)} price updates via SSE")
        
        except Exception as e:
            logger.error(f"❌ Error handling price updates: {e}")
    
    async def _handle_batch_price_updates(self, messages: List[Dict[str, Any]]) -> None:
        """Handle batch price update messages"""
        try:
            # Similar to price updates but may include analytics
            combined_data = {
                'prices': {},
                'top_movers': {},
                'breakout_candidates': [],
                'total_count': 0
            }
            
            for message in messages:
                message_data = message.get('update_data', {})
                
                # Merge price data
                if 'prices' in message_data:
                    combined_data['prices'].update(message_data['prices'])
                
                # Merge top movers
                if 'top_movers' in message_data:
                    combined_data['top_movers'] = message_data['top_movers']
                
                # Merge breakout candidates
                if 'breakout_candidates' in message_data:
                    combined_data['breakout_candidates'].extend(
                        message_data['breakout_candidates']
                    )
                
                combined_data['total_count'] += message_data.get('count', 0)
            
            # Broadcast to multiple channels
            broadcast_tasks = []
            
            # Market data channel for prices
            if combined_data['prices']:
                broadcast_tasks.append(
                    self._sse_manager.broadcast_to_channel(
                        channel=SSEChannel.MARKET_DATA,
                        event_type='batch_price_update',
                        data={
                            'prices': combined_data['prices'],
                            'count': len(combined_data['prices'])
                        },
                        priority=1
                    )
                )
            
            # Top movers channel
            if combined_data['top_movers']:
                broadcast_tasks.append(
                    self._sse_manager.broadcast_to_channel(
                        channel=SSEChannel.TOP_MOVERS,
                        event_type='movers_update',
                        data=combined_data['top_movers'],
                        priority=2
                    )
                )
            
            # Breakouts channel
            if combined_data['breakout_candidates']:
                broadcast_tasks.append(
                    self._sse_manager.broadcast_to_channel(
                        channel=SSEChannel.BREAKOUTS,
                        event_type='breakout_alert',
                        data={'breakouts': combined_data['breakout_candidates']},
                        priority=2
                    )
                )
            
            # Execute all broadcasts in parallel
            if broadcast_tasks:
                await asyncio.gather(*broadcast_tasks, return_exceptions=True)
                
            logger.debug(f"📊 Broadcast batch updates: {combined_data['total_count']} items")
        
        except Exception as e:
            logger.error(f"❌ Error handling batch price updates: {e}")
    
    async def _handle_analytics_updates(self, messages: List[Dict[str, Any]]) -> None:
        """Handle analytics update messages"""
        try:
            for message in messages:
                message_data = message.get('update_data', {})
                analytics_type = message_data.get('analytics_type', 'unknown')
                analytics_data = message_data.get('analytics_data', {})
                
                # Route to appropriate SSE channel based on analytics type
                channel_mapping = {
                    'top_movers': SSEChannel.TOP_MOVERS,
                    'breakout': SSEChannel.BREAKOUTS,
                    'volume_analysis': SSEChannel.VOLUME_ALERTS,
                    'sector_performance': SSEChannel.SECTOR_PERFORMANCE,
                    'market_sentiment': SSEChannel.MARKET_SENTIMENT,
                    'heatmap': SSEChannel.HEATMAP_DATA
                }
                
                channel = channel_mapping.get(analytics_type, SSEChannel.MARKET_DATA)
                
                await self._sse_manager.broadcast_to_channel(
                    channel=channel,
                    event_type=f'{analytics_type}_update',
                    data=analytics_data,
                    priority=2
                )
            
            logger.debug(f"📊 Broadcast {len(messages)} analytics updates via SSE")
        
        except Exception as e:
            logger.error(f"❌ Error handling analytics updates: {e}")
    
    async def _handle_trading_signals(self, messages: List[Dict[str, Any]]) -> None:
        """Handle trading signal messages"""
        try:
            signals = []
            
            for message in messages:
                message_data = message.get('update_data', {})
                if 'signal_data' in message_data:
                    signals.append(message_data['signal_data'])
            
            if signals:
                await self._sse_manager.broadcast_to_channel(
                    channel=SSEChannel.TRADING_SIGNALS,
                    event_type='trading_signal',
                    data={'signals': signals, 'count': len(signals)},
                    priority=1  # High priority for trading signals
                )
                
            logger.debug(f"🚨 Broadcast {len(signals)} trading signals via SSE")
        
        except Exception as e:
            logger.error(f"❌ Error handling trading signals: {e}")
    
    async def _handle_generic_updates(self, message_type: str, messages: List[Dict[str, Any]]) -> None:
        """Handle generic update messages"""
        try:
            # Default to system status channel for unknown message types
            combined_data = []
            
            for message in messages:
                message_data = message.get('update_data', {})
                combined_data.append(message_data)
            
            if combined_data:
                await self._sse_manager.broadcast_to_channel(
                    channel=SSEChannel.SYSTEM_STATUS,
                    event_type=message_type,
                    data={'updates': combined_data, 'count': len(combined_data)},
                    priority=5  # Lower priority for generic updates
                )
            
            logger.debug(f"📡 Broadcast {len(messages)} generic {message_type} updates")
        
        except Exception as e:
            logger.error(f"❌ Error handling generic updates: {e}")
    
    def _should_broadcast(self, message_type: str) -> bool:
        """Check if message type should be broadcast based on throttling"""
        try:
            now = datetime.now()
            last_broadcast = self._last_broadcast_by_type.get(message_type)
            
            if not last_broadcast:
                return True
            
            time_since_last = (now - last_broadcast).total_seconds()
            return time_since_last >= self._throttle_interval
        
        except Exception:
            return True  # Default to allowing broadcast
    
    def get_bridge_stats(self) -> Dict[str, Any]:
        """Get bridge performance statistics"""
        return {
            'processed_messages': self._processed_messages,
            'broadcast_count': self._broadcast_count,
            'last_broadcast_time': self._last_broadcast_time.isoformat(),
            'throttle_interval_seconds': self._throttle_interval,
            'message_types_tracked': len(self._last_broadcast_by_type),
            'is_running': self._is_running
        }
    
    def update_throttle_settings(self, interval_seconds: float) -> None:
        """Update message throttling interval"""
        self._throttle_interval = max(0.01, interval_seconds)  # Minimum 10ms
        logger.info(f"⚙️ Updated throttle interval to {self._throttle_interval}s")


# Singleton instance
_kafka_sse_bridge: Optional[KafkaSSEBridge] = None


async def get_kafka_sse_bridge() -> KafkaSSEBridge:
    """Get singleton Kafka-SSE bridge instance"""
    global _kafka_sse_bridge
    if _kafka_sse_bridge is None:
        _kafka_sse_bridge = KafkaSSEBridge()
        await _kafka_sse_bridge.initialize()
    return _kafka_sse_bridge


async def start_kafka_sse_bridge() -> None:
    """Start the Kafka-SSE bridge consumer"""
    bridge = await get_kafka_sse_bridge()
    await bridge.start_consuming()


async def cleanup_kafka_sse_bridge() -> None:
    """Cleanup Kafka-SSE bridge resources"""
    global _kafka_sse_bridge
    if _kafka_sse_bridge:
        await _kafka_sse_bridge.stop_consuming()
        _kafka_sse_bridge = None