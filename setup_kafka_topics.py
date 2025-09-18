#!/usr/bin/env python3
"""
Simple Kafka Topics Setup for HFT Trading System
Creates all required topics for the system
"""

import asyncio
import logging
import time
from typing import List, Dict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_kafka_topics():
    """Create all required Kafka topics using aiokafka admin client"""
    try:
        from aiokafka.admin import AIOKafkaAdminClient, NewTopic
        from aiokafka.errors import TopicAlreadyExistsError
        
        # Connect to Kafka
        admin_client = AIOKafkaAdminClient(
            bootstrap_servers='localhost:9092',
            client_id='topic_creator'
        )
        
        await admin_client.start()
        logger.info("✅ Connected to Kafka")
        
        # Define all HFT topics
        topics_to_create = [
            # Core data flow
            {"name": "hft.raw.market_data", "partitions": 3, "replication": 1},
            {"name": "hft.shared_memory.feed", "partitions": 3, "replication": 1},
            
            # Strategy topics  
            {"name": "hft.strategy.breakout", "partitions": 2, "replication": 1},
            {"name": "hft.strategy.momentum", "partitions": 2, "replication": 1},
            {"name": "hft.strategy.gap_trading", "partitions": 2, "replication": 1},
            
            # Analytics
            {"name": "hft.analytics.market_data", "partitions": 2, "replication": 1},
            
            # Execution
            {"name": "hft.execution.signals", "partitions": 2, "replication": 1},
            
            # UI updates
            {"name": "hft.ui.price_updates", "partitions": 1, "replication": 1},
            
            # Premarket
            {"name": "hft.premarket.candles", "partitions": 1, "replication": 1},
        ]
        
        # Create topics
        new_topics = []
        for topic_config in topics_to_create:
            topic = NewTopic(
                name=topic_config["name"],
                num_partitions=topic_config["partitions"],
                replication_factor=topic_config["replication"]
            )
            new_topics.append(topic)
        
        try:
            await admin_client.create_topics(new_topics)
            logger.info(f"✅ Created {len(new_topics)} HFT topics successfully")
            
        except TopicAlreadyExistsError:
            logger.info("✅ Topics already exist - ready to use")
        except Exception as e:
            logger.warning(f"⚠️ Some topics may already exist: {e}")
        
        # List existing topics to verify
        metadata = await admin_client.describe_cluster()
        topics_result = await admin_client.list_topics()
        hft_topics = [t for t in topics_result.topics if t.startswith('hft.')]
        
        logger.info(f"✅ Found {len(hft_topics)} HFT topics:")
        for topic in sorted(hft_topics):
            logger.info(f"   📋 {topic}")
        
        await admin_client.close()
        return True
        
    except ImportError:
        logger.error("❌ aiokafka not installed. Install with: pip install aiokafka")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to create topics: {e}")
        return False

def wait_for_kafka(max_attempts=30):
    """Wait for Kafka to be ready"""
    import socket
    
    for attempt in range(max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 9092))
            sock.close()
            
            if result == 0:
                logger.info("✅ Kafka is ready")
                return True
            else:
                if attempt % 5 == 0:
                    logger.info(f"⏳ Waiting for Kafka... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(2)
                
        except Exception:
            time.sleep(2)
    
    logger.error("❌ Kafka not ready after waiting")
    return False

async def main():
    """Main setup function"""
    logger.info("🚀 Setting up Kafka topics for HFT Trading System")
    
    # Wait for Kafka to be ready
    if not wait_for_kafka():
        logger.error("❌ Cannot connect to Kafka at localhost:9092")
        logger.info("💡 Make sure Kafka is running:")
        logger.info("   docker-compose -f docker-compose.kafka.yml up -d")
        return False
    
    # Create topics
    success = await create_kafka_topics()
    
    if success:
        logger.info("🎉 Kafka setup complete! You can now run your trading application.")
        logger.info("🚀 Start with: python app.py")
        return True
    else:
        logger.error("❌ Kafka setup failed")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)