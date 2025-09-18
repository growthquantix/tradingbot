"""
Kafka Integration Module for Trading System
Provides a clean, modular interface for Kafka integration without modifying existing files
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from services.kafka_service import get_kafka_service

logger = logging.getLogger(__name__)

class TradingKafkaIntegration:
    """Modular Kafka integration for trading system components"""

    def __init__(self):
        self.kafka_service = get_kafka_service()
        self.enabled = False
        self.initialized = False

    async def initialize(self) -> bool:
        """Initialize Kafka integration"""
        try:
            success = self.kafka_service.initialize_producer()
            if success:
                self.enabled = True
                self.initialized = True
                logger.info("✅ Kafka integration initialized successfully")
                return True
            else:
                logger.warning("⚠️ Kafka integration failed to initialize")
                return False
        except Exception as e:
            logger.error(f"❌ Kafka integration initialization error: {e}")
            return False

    def process_market_data(self, market_data: Dict[str, Any]) -> bool:
        """Process and send market data to Kafka"""
        if not self.enabled:
            return False

        try:
            # Send raw market data
            success = self.kafka_service.send_market_data(market_data, 'raw')

            # Process and send processed data
            processed_data = self._normalize_market_data(market_data)
            if processed_data:
                self.kafka_service.send_market_data(processed_data, 'processed')

            # Send UI updates
            ui_update = self._prepare_ui_update(market_data)
            if ui_update:
                self.kafka_service.send_ui_update(ui_update, 'price_updates')

            return success

        except Exception as e:
            logger.error(f"Error processing market data for Kafka: {e}")
            return False

    def process_trading_signal(self, signal_data: Dict[str, Any], strategy: str) -> bool:
        """Process and send trading signal to Kafka"""
        if not self.enabled:
            return False

        try:
            return self.kafka_service.send_trading_signal(signal_data, strategy)
        except Exception as e:
            logger.error(f"Error processing trading signal for Kafka: {e}")
            return False

    def process_analytics_data(self, analytics_data: Dict[str, Any]) -> bool:
        """Process and send analytics data to Kafka"""
        if not self.enabled:
            return False

        try:
            return self.kafka_service.send_analytics_data(analytics_data)
        except Exception as e:
            logger.error(f"Error processing analytics data for Kafka: {e}")
            return False

    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert to Kafka"""
        if not self.enabled:
            return False

        try:
            return self.kafka_service.send_ui_update(alert_data, 'alerts')
        except Exception as e:
            logger.error(f"Error sending alert to Kafka: {e}")
            return False

    def _normalize_market_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize market data for processing"""
        try:
            if not raw_data:
                return None

            normalized = {
                'timestamp': datetime.now().isoformat(),
                'source': 'centralized_ws_manager',
                'data': raw_data.copy()
            }

            # Add common fields if available
            if 'symbol' in raw_data:
                normalized['symbol'] = raw_data['symbol']
            if 'ltp' in raw_data:
                normalized['price'] = raw_data['ltp']
            if 'volume' in raw_data:
                normalized['volume'] = raw_data['volume']

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing market data: {e}")
            return None

    def _prepare_ui_update(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Prepare UI update from market data"""
        try:
            if not market_data:
                return None

            ui_update = {
                'type': 'price_update',
                'timestamp': datetime.now().isoformat(),
            }

            # Extract relevant fields for UI
            ui_fields = ['symbol', 'ltp', 'change', 'change_percent', 'volume', 'high', 'low', 'open']

            for field in ui_fields:
                if field in market_data:
                    ui_update[field] = market_data[field]

            return ui_update if len(ui_update) > 2 else None  # More than just type and timestamp

        except Exception as e:
            logger.error(f"Error preparing UI update: {e}")
            return None

    def create_message_consumer(self, topics: List[str], callback_function, consumer_id: str = None):
        """Create a consumer for Kafka messages"""
        if not self.enabled:
            logger.warning("Kafka integration not enabled, cannot create consumer")
            return False

        try:
            return self.kafka_service.create_consumer(topics, callback_function, consumer_id)
        except Exception as e:
            logger.error(f"Error creating Kafka consumer: {e}")
            return False

    def start_consumers(self):
        """Start all Kafka consumers"""
        if not self.enabled:
            return False

        try:
            return self.kafka_service.start_consumers()
        except Exception as e:
            logger.error(f"Error starting Kafka consumers: {e}")
            return False

    def stop(self):
        """Stop Kafka integration"""
        try:
            if self.kafka_service:
                self.kafka_service.close()
            self.enabled = False
            logger.info("Kafka integration stopped")
        except Exception as e:
            logger.error(f"Error stopping Kafka integration: {e}")

    def is_healthy(self) -> bool:
        """Check if Kafka integration is healthy"""
        return self.enabled and self.initialized

    def get_status(self) -> Dict[str, Any]:
        """Get Kafka integration status"""
        return {
            'enabled': self.enabled,
            'initialized': self.initialized,
            'healthy': self.is_healthy(),
            'topics': self.kafka_service.topics if self.kafka_service else {},
            'timestamp': datetime.now().isoformat()
        }

# Global instance for easy access
kafka_integration = TradingKafkaIntegration()

def get_kafka_integration() -> TradingKafkaIntegration:
    """Get the global Kafka integration instance"""
    return kafka_integration

# Convenience functions for easy integration
async def publish_market_data(data: Dict[str, Any]) -> bool:
    """Convenience function to publish market data"""
    return kafka_integration.process_market_data(data)

async def publish_trading_signal(signal: Dict[str, Any], strategy: str) -> bool:
    """Convenience function to publish trading signal"""
    return kafka_integration.process_trading_signal(signal, strategy)

async def publish_analytics(analytics: Dict[str, Any]) -> bool:
    """Convenience function to publish analytics"""
    return kafka_integration.process_analytics_data(analytics)

async def send_alert(alert: Dict[str, Any]) -> bool:
    """Convenience function to send alerts"""
    return kafka_integration.send_alert(alert)