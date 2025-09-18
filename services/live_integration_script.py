#!/usr/bin/env python3
"""
Live Integration Script

Simple script to initialize the queue system and register services
with the running application without interfering with existing processes.

This script directly interfaces with the running application's services.

Usage:
    python services/live_integration_script.py
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class LiveIntegrationScript:
    """
    Direct integration with running application services
    """
    
    def __init__(self):
        """Initialize integration script"""
        self.realtime_hub = None
        self.services_registered = []
        self.is_initialized = False
        
        logger.info("🚀 Live Integration Script initialized")
    
    async def initialize_queue_system(self) -> bool:
        """Initialize the queue system components"""
        try:
            logger.info("📋 Initializing queue system components...")
            
            # Import and initialize realtime data hub
            from services.realtime import realtime_data_hub, DataType, ServicePriority, ServiceConfig
            
            self.realtime_hub = realtime_data_hub
            
            # Initialize the hub
            await self.realtime_hub.initialize()
            
            # Test hub initialization
            hub_status = self.realtime_hub.get_status()
            logger.info(f"✅ Realtime data hub initialized: {hub_status.get('hub', {}).get('initialized', 'unknown')}")
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize queue system: {e}")
            return False
    
    async def register_premarket_candle_builder(self) -> bool:
        """Register premarket candle builder with queue system"""
        try:
            logger.info("🕘 Registering premarket candle builder...")
            
            # Import service
            from services.premarket_candle_builder import premarket_candle_service
            from services.realtime import ServiceConfig, ServicePriority, DataType
            
            # Create adapter for premarket candle builder
            async def premarket_adapter(data: Any) -> bool:
                try:
                    # Convert data to expected Upstox format
                    upstox_data = {
                        "type": "live_feed",
                        "feeds": data.get("feeds", data.get("data", {})),
                        "currentTs": str(int(time.time() * 1000))
                    }
                    
                    # Call the service
                    await premarket_candle_service._handle_direct_market_data(upstox_data)
                    logger.debug("📊 Premarket candle builder processed data")
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Premarket candle builder adapter error: {e}")
                    return False
            
            # Register with hub
            config = ServiceConfig(
                name="premarket_candle_builder",
                priority=ServicePriority.CRITICAL
            )
            
            registration = await self.realtime_hub.register_service(config, premarket_adapter)
            
            if registration.is_active:
                self.services_registered.append("premarket_candle_builder")
                logger.info("✅ Premarket candle builder registered successfully")
                return True
            else:
                logger.error("❌ Failed to register premarket candle builder")
                return False
                
        except ImportError as e:
            logger.warning(f"⚠️ Premarket candle builder not available: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error registering premarket candle builder: {e}")
            return False
    
    async def register_enhanced_breakout_engine(self) -> bool:
        """Register enhanced breakout engine with queue system"""
        try:
            logger.info("🎯 Registering enhanced breakout engine...")
            
            # Import service
            from services.enhanced_breakout_engine import enhanced_breakout_engine
            from services.realtime import ServiceConfig, ServicePriority, DataType
            
            # Create adapter for enhanced breakout engine
            async def breakout_adapter(data: Any) -> bool:
                try:
                    # Convert data to expected normalized format
                    normalized_data = {
                        "data": data.get("feeds", data.get("data", {}))
                    }
                    
                    # Call the service
                    await enhanced_breakout_engine._process_centralized_data(normalized_data)
                    logger.debug("📊 Enhanced breakout engine processed data")
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Enhanced breakout engine adapter error: {e}")
                    return False
            
            # Register with hub
            config = ServiceConfig(
                name="enhanced_breakout_engine",
                priority=ServicePriority.CRITICAL
            )
            
            registration = await self.realtime_hub.register_service(config, breakout_adapter)
            
            if registration.is_active:
                self.services_registered.append("enhanced_breakout_engine")
                logger.info("✅ Enhanced breakout engine registered successfully")
                return True
            else:
                logger.error("❌ Failed to register enhanced breakout engine")
                return False
                
        except ImportError as e:
            logger.warning(f"⚠️ Enhanced breakout engine not available: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error registering enhanced breakout engine: {e}")
            return False
    
    async def setup_data_bridge(self) -> bool:
        """Setup data bridge from centralized manager to queue system"""
        try:
            logger.info("🌉 Setting up data bridge...")
            
            # Import centralized manager
            from services.centralized_ws_manager import centralized_ws_manager
            from services.realtime import DataType
            
            if not centralized_ws_manager:
                logger.error("❌ Centralized WebSocket manager not available")
                return False
            
            # Create bridge callback
            async def bridge_callback(data: Dict[str, Any]) -> None:
                try:
                    # Forward data to queue system
                    if self.realtime_hub:
                        await self.realtime_hub.distribute_data(data, DataType.MARKET_DATA)
                        logger.debug("🌉 Data bridged to queue system")
                        
                except Exception as e:
                    logger.error(f"❌ Bridge callback error: {e}")
            
            # Register bridge callback with centralized manager
            success = centralized_ws_manager.register_callback("live_feed", bridge_callback)
            
            if success:
                logger.info("✅ Data bridge established successfully")
                return True
            else:
                logger.error("❌ Failed to establish data bridge")
                return False
                
        except ImportError as e:
            logger.error(f"❌ Cannot import centralized manager: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error setting up data bridge: {e}")
            return False
    
    async def test_data_flow(self, duration: int = 30) -> Dict[str, Any]:
        """Test data flow through the system"""
        try:
            logger.info(f"🧪 Testing data flow for {duration} seconds...")
            
            # Get initial metrics
            initial_status = self.realtime_hub.get_status()
            initial_messages = initial_status["hub"]["metrics"]["total_messages_received"]
            
            # Wait for test period
            await asyncio.sleep(duration)
            
            # Get final metrics
            final_status = self.realtime_hub.get_status()
            final_messages = final_status["hub"]["metrics"]["total_messages_received"]
            
            messages_processed = final_messages - initial_messages
            throughput = messages_processed / duration
            
            test_results = {
                "duration_seconds": duration,
                "messages_processed": messages_processed,
                "average_throughput": throughput,
                "success_rate": final_status["hub"]["metrics"]["success_rate"],
                "services_registered": len(self.services_registered),
                "test_status": "pass" if messages_processed > 0 else "warning"
            }
            
            logger.info("📊 Data Flow Test Results:")
            logger.info(f"   Messages processed: {messages_processed}")
            logger.info(f"   Average throughput: {throughput:.1f} msg/s")
            logger.info(f"   Success rate: {test_results['success_rate']}%")
            logger.info(f"   Test status: {test_results['test_status']}")
            
            return test_results
            
        except Exception as e:
            logger.error(f"❌ Data flow test failed: {e}")
            return {"error": str(e)}
    
    async def run_integration(self) -> bool:
        """Run complete integration process"""
        logger.info("🚀 Starting live integration process...")
        
        try:
            # Step 1: Initialize queue system
            logger.info("📋 Step 1: Initializing queue system...")
            if not await self.initialize_queue_system():
                logger.error("❌ Failed at Step 1")
                return False
            
            # Step 2: Register services
            logger.info("📋 Step 2: Registering services...")
            
            premarket_success = await self.register_premarket_candle_builder()
            breakout_success = await self.register_enhanced_breakout_engine()
            
            if not (premarket_success or breakout_success):
                logger.error("❌ Failed to register any services")
                return False
            
            # Step 3: Setup data bridge
            logger.info("📋 Step 3: Setting up data bridge...")
            if not await self.setup_data_bridge():
                logger.error("❌ Failed to setup data bridge")
                return False
            
            # Step 4: Test data flow
            logger.info("📋 Step 4: Testing data flow...")
            test_results = await self.test_data_flow(30)
            
            if test_results.get("error"):
                logger.error(f"❌ Data flow test failed: {test_results['error']}")
                return False
            
            # Success summary
            logger.info("🎉 Live integration completed successfully!")
            logger.info(f"📊 Services registered: {len(self.services_registered)}")
            logger.info(f"📊 Data bridge: Active")
            logger.info(f"📊 Test results: {test_results['test_status']}")
            logger.info("💡 Services should now receive data through queue system")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Integration process failed: {e}")
            return False

async def main():
    """Main execution function"""
    logger.info("🚀 Live Integration Script")
    logger.info("=" * 50)
    
    integration_script = LiveIntegrationScript()
    
    try:
        success = await integration_script.run_integration()
        
        if success:
            logger.info("✅ Integration completed successfully!")
            logger.info("🔥 Queue system is now active and processing live data")
        else:
            logger.error("❌ Integration failed")
            
    except KeyboardInterrupt:
        logger.info("⚠️ Integration interrupted by user")
    except Exception as e:
        logger.error(f"❌ Integration script error: {e}")
    
    logger.info("🏁 Integration script complete")

if __name__ == "__main__":
    asyncio.run(main())