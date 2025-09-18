"""
Kafka Service for Trading Application
Provides centralized Kafka producer and consumer management
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional, Any, List, Callable
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class TradingKafkaService:
    """Centralized Kafka service for the trading application"""

    def __init__(self):
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')
        self.client_id = os.getenv('KAFKA_CLIENT_ID', 'hft_trading_app')
        self.group_id = os.getenv('KAFKA_GROUP_ID', 'trading_system_group')
        self.producer: Optional[KafkaProducer] = None
        self.consumers: Dict[str, KafkaConsumer] = {}
        self.consumer_threads: Dict[str, threading.Thread] = {}
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Topic definitions
        self.topics = {
            'market_data': {
                'raw': 'trading.market_data.raw',
                'processed': 'trading.market_data.processed'
            },
            'signals': {
                'breakout': 'trading.signals.breakout',
                'gap': 'trading.signals.gap',
                'momentum': 'trading.signals.momentum'
            },
            'analytics': {
                'market': 'trading.analytics.market'
            },
            'ui': {
                'price_updates': 'trading.ui.price_updates',
                'alerts': 'trading.ui.alerts'
            }
        }

    def initialize_producer(self) -> bool:
        """Initialize Kafka producer"""
        try:
            producer_config = {
                'bootstrap_servers': self.bootstrap_servers,
                'client_id': f'{self.client_id}_producer',
                'value_serializer': lambda v: json.dumps(v, default=str).encode('utf-8'),
                'key_serializer': lambda k: k.encode('utf-8') if k else None,
                'acks': 'all',
                'retries': 3,
                'batch_size': 16384,
                'linger_ms': 5,
                'buffer_memory': 33554432,
                'compression_type': 'snappy'
            }

            self.producer = KafkaProducer(**producer_config)
            logger.info("✅ Kafka producer initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka producer: {e}")
            return False

    def send_market_data(self, data: Dict[str, Any], topic_type: str = 'raw') -> bool:
        """Send market data to Kafka"""
        try:
            if not self.producer:
                logger.warning("Producer not initialized")
                return False

            topic = self.topics['market_data'][topic_type]
            key = data.get('instrument_key', data.get('symbol', ''))

            # Add timestamp if not present
            if 'kafka_timestamp' not in data:
                data['kafka_timestamp'] = datetime.now().isoformat()

            future = self.producer.send(topic, key=key, value=data)
            # Don't wait for delivery in high-frequency scenarios
            logger.debug(f"Sent market data to {topic}: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to send market data: {e}")
            return False

    def send_trading_signal(self, signal: Dict[str, Any], strategy: str) -> bool:
        """Send trading signal to Kafka"""
        try:
            if not self.producer:
                logger.warning("Producer not initialized")
                return False

            topic = self.topics['signals'].get(strategy, 'trading.signals.general')
            key = f"{strategy}_{signal.get('symbol', 'UNKNOWN')}"

            # Add metadata
            signal['kafka_timestamp'] = datetime.now().isoformat()
            signal['strategy'] = strategy

            future = self.producer.send(topic, key=key, value=signal)
            logger.info(f"Sent {strategy} signal for {signal.get('symbol')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send trading signal: {e}")
            return False

    def send_analytics_data(self, analytics: Dict[str, Any]) -> bool:
        """Send analytics data to Kafka"""
        try:
            if not self.producer:
                logger.warning("Producer not initialized")
                return False

            topic = self.topics['analytics']['market']
            key = analytics.get('type', 'general')

            analytics['kafka_timestamp'] = datetime.now().isoformat()

            future = self.producer.send(topic, key=key, value=analytics)
            logger.debug(f"Sent analytics data: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to send analytics data: {e}")
            return False

    def send_ui_update(self, update_data: Dict[str, Any], update_type: str = 'price_updates') -> bool:
        """Send UI update to Kafka"""
        try:
            if not self.producer:
                logger.warning("Producer not initialized")
                return False

            topic = self.topics['ui'][update_type]
            key = update_data.get('symbol', update_data.get('type', ''))

            update_data['kafka_timestamp'] = datetime.now().isoformat()

            future = self.producer.send(topic, key=key, value=update_data)
            logger.debug(f"Sent UI update to {topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to send UI update: {e}")
            return False

    def create_consumer(self, topics: List[str], callback: Callable, consumer_id: str = None) -> bool:
        """Create a consumer for specified topics"""
        try:
            if consumer_id is None:
                consumer_id = f"consumer_{len(self.consumers)}"

            consumer_config = {
                'bootstrap_servers': self.bootstrap_servers,
                'group_id': self.group_id,
                'client_id': f'{self.client_id}_{consumer_id}',
                'auto_offset_reset': os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest'),
                'enable_auto_commit': True,
                'value_deserializer': lambda m: json.loads(m.decode('utf-8')),
                'key_deserializer': lambda k: k.decode('utf-8') if k else None,
                'consumer_timeout_ms': 1000
            }

            consumer = KafkaConsumer(*topics, **consumer_config)
            self.consumers[consumer_id] = consumer

            # Start consumer thread
            def consume_messages():
                try:
                    for message in consumer:
                        if not self.running:
                            break
                        try:
                            callback(message.topic, message.key, message.value, message.timestamp)
                        except Exception as e:
                            logger.error(f"Error in message callback: {e}")
                except Exception as e:
                    logger.error(f"Consumer error: {e}")
                finally:
                    consumer.close()

            thread = threading.Thread(target=consume_messages, daemon=True)
            self.consumer_threads[consumer_id] = thread

            logger.info(f"✅ Created consumer {consumer_id} for topics: {topics}")
            return True

        except Exception as e:
            logger.error(f"Failed to create consumer: {e}")
            return False

    def start_consumers(self) -> bool:
        """Start all consumer threads"""
        try:
            self.running = True
            for consumer_id, thread in self.consumer_threads.items():
                if not thread.is_alive():
                    thread.start()
                    logger.info(f"Started consumer thread: {consumer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start consumers: {e}")
            return False

    def stop_consumers(self):
        """Stop all consumer threads"""
        self.running = False
        for consumer_id, consumer in self.consumers.items():
            try:
                consumer.close()
                logger.info(f"Stopped consumer: {consumer_id}")
            except Exception as e:
                logger.error(f"Error stopping consumer {consumer_id}: {e}")

        # Wait for threads to finish
        for thread in self.consumer_threads.values():
            if thread.is_alive():
                thread.join(timeout=5)

    def close(self):
        """Close all Kafka connections"""
        self.stop_consumers()
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed")
        self.executor.shutdown(wait=True)

    def get_topic_name(self, category: str, topic_type: str) -> str:
        """Get topic name by category and type"""
        return self.topics.get(category, {}).get(topic_type, f"trading.{category}.{topic_type}")

# Global instance
kafka_service = TradingKafkaService()

def get_kafka_service() -> TradingKafkaService:
    """Get the global Kafka service instance"""
    return kafka_service