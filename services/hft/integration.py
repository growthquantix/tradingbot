"""
HFT System Integration Module

Complete integration orchestrator for HFT Kafka architecture with all
trading services and comprehensive lifecycle management.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import json

from .config import get_hft_kafka_config, get_topic_manager
from .producer import get_hft_producer, cleanup_hft_producer
from .memory_bridge import get_hft_memory_bridge, cleanup_hft_memory_bridge
from .consumers import (
    HFTInstrumentRegistryConsumer,
    HFTBreakoutEngineConsumer,
    HFTPremarketConsumer,
    HFTMarketAnalyticsConsumer
)
from .monitor import get_hft_monitor, start_hft_monitoring, stop_hft_monitoring

logger = logging.getLogger(__name__)


@dataclass
class ServiceRegistration:
    """Service registration information"""
    service_name: str
    service_instance: Any
    consumer_instance: Optional[Any] = None
    is_active: bool = False
    start_time: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class HFTSystemStatus:
    """HFT system status information"""
    is_initialized: bool = False
    is_running: bool = False
    services_count: int = 0
    active_services: List[str] = field(default_factory=list)
    failed_services: List[str] = field(default_factory=list)
    total_messages_processed: int = 0
    avg_system_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    last_health_check: Optional[datetime] = None


class HFTSystemIntegration:
    """
    HFT System Integration Orchestrator
    
    Features:
    - Complete lifecycle management
    - Service discovery and registration
    - Health monitoring and recovery
    - Performance optimization
    - Graceful shutdown handling
    """
    
    def __init__(self):
        self._config = get_hft_kafka_config()
        self._topic_manager = get_topic_manager()
        
        # System state
        self._status = HFTSystemStatus()
        self._services: Dict[str, ServiceRegistration] = {}
        self._consumer_tasks: Set[asyncio.Task] = set()
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Components
        self._producer = None
        self._memory_bridge = None
        self._performance_monitor = None
        
        # System lifecycle
        self._initialization_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._start_time = None
        
        logger.info("HFT System Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize the complete HFT system"""
        async with self._initialization_lock:
            if self._status.is_initialized:
                logger.warning("HFT system already initialized")
                return True
            
            try:
                logger.info("🚀 Initializing HFT Kafka system...")
                
                # 1. Initialize core components
                await self._initialize_core_components()
                
                # 2. Initialize performance monitoring
                await self._initialize_monitoring()
                
                # 3. Register default services
                await self._register_default_services()
                
                # 4. Validate system health
                health_status = await self._perform_health_check()
                if not health_status["is_healthy"]:
                    raise Exception(f"System health check failed: {health_status}")
                
                self._status.is_initialized = True
                self._start_time = datetime.now()
                
                logger.info("✅ HFT Kafka system initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize HFT system: {e}")
                await self._cleanup_on_failure()
                return False
    
    async def start_system(self) -> bool:
        """Start all HFT system components"""
        if not self._status.is_initialized:
            if not await self.initialize():
                return False
        
        try:
            logger.info("🚀 Starting HFT system components...")
            
            # 1. Start memory bridge
            if self._memory_bridge:
                bridge_task = asyncio.create_task(self._memory_bridge.start_bridge())
                self._consumer_tasks.add(bridge_task)
            
            # 2. Start all service consumers
            await self._start_service_consumers()
            
            # 3. Start monitoring
            if self._performance_monitor:
                self._monitoring_task = asyncio.create_task(
                    self._performance_monitor.start_monitoring()
                )
            
            self._status.is_running = True
            self._status.active_services = [
                name for name, reg in self._services.items() 
                if reg.is_active
            ]
            
            logger.info(
                f"✅ HFT system started with {len(self._status.active_services)} services"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start HFT system: {e}")
            await self.stop_system()
            return False
    
    async def stop_system(self) -> None:
        """Stop all HFT system components gracefully"""
        logger.info("🛑 Stopping HFT system...")
        
        self._status.is_running = False
        self._shutdown_event.set()
        
        try:
            # 1. Stop monitoring first
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # 2. Stop all consumer tasks
            if self._consumer_tasks:
                for task in self._consumer_tasks:
                    if not task.done():
                        task.cancel()
                
                await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
                self._consumer_tasks.clear()
            
            # 3. Stop core components
            await self._cleanup_core_components()
            
            # 4. Update service statuses
            for service_reg in self._services.values():
                service_reg.is_active = False
            
            self._status.active_services.clear()
            
            logger.info("✅ HFT system stopped successfully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping HFT system: {e}")
    
    async def register_service(
        self,
        service_name: str,
        service_instance: Any,
        consumer_class: Optional[type] = None
    ) -> bool:
        """
        Register a service with the HFT system
        
        Args:
            service_name: Unique service identifier
            service_instance: Service instance to register
            consumer_class: Optional consumer class for Kafka integration
            
        Returns:
            True if registration successful
        """
        try:
            if service_name in self._services:
                logger.warning(f"Service {service_name} already registered")
                return False
            
            # Create service registration
            registration = ServiceRegistration(
                service_name=service_name,
                service_instance=service_instance,
                start_time=datetime.now()
            )
            
            # Create consumer if class provided
            if consumer_class:
                registration.consumer_instance = consumer_class(service_instance)
            
            self._services[service_name] = registration
            self._status.services_count = len(self._services)
            
            # Register with performance monitor
            if self._performance_monitor:
                self._performance_monitor.register_service(service_name)
            
            logger.info(f"✅ Registered service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to register service {service_name}: {e}")
            return False
    
    async def unregister_service(self, service_name: str) -> bool:
        """Unregister a service from the HFT system"""
        try:
            if service_name not in self._services:
                logger.warning(f"Service {service_name} not registered")
                return False
            
            registration = self._services[service_name]
            
            # Stop consumer if running
            if registration.consumer_instance and registration.is_active:
                await self._stop_service_consumer(service_name)
            
            del self._services[service_name]
            self._status.services_count = len(self._services)
            
            logger.info(f"✅ Unregistered service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to unregister service {service_name}: {e}")
            return False
    
    async def _initialize_core_components(self) -> None:
        """Initialize core HFT components"""
        try:
            # Initialize producer
            self._producer = await get_hft_producer()
            logger.debug("✅ HFT producer initialized")
            
            # Initialize memory bridge
            try:
                from .memory_bridge import get_hft_memory_bridge
                self._memory_bridge = await get_hft_memory_bridge()
                logger.debug("✅ HFT memory bridge initialized")
            except ImportError:
                logger.warning("⚠️ HFT memory bridge not available - fallback mode")
                self._memory_bridge = None
            
        except Exception as e:
            logger.error(f"❌ Core components initialization failed: {e}")
            raise
    
    async def _initialize_monitoring(self) -> None:
        """Initialize performance monitoring"""
        try:
            self._performance_monitor = get_hft_monitor()
            logger.debug("✅ Performance monitor initialized")
        except Exception as e:
            logger.error(f"❌ Monitoring initialization failed: {e}")
            raise
    
    async def _register_default_services(self) -> None:
        """Register default trading services"""
        try:
            # Register instrument registry
            try:
                from services.instrument_registry import InstrumentRegistry
                instrument_registry = InstrumentRegistry()
                await self.register_service(
                    "instrument_registry",
                    instrument_registry,
                    HFTInstrumentRegistryConsumer
                )
            except ImportError:
                logger.warning("⚠️ Instrument registry not available")
            
            # Register breakout engine
            try:
                from services.enhanced_breakout_engine import enhanced_breakout_engine
                await self.register_service(
                    "breakout_engine",
                    enhanced_breakout_engine,
                    HFTBreakoutEngineConsumer
                )
            except ImportError:
                logger.warning("⚠️ Enhanced breakout engine not available")
            
            # Register premarket candle builder
            try:
                from services.premarket_candle_builder import PremarketCandleBuilder
                premarket_builder = PremarketCandleBuilder()
                await self.register_service(
                    "premarket_candle",
                    premarket_builder,
                    HFTPremarketConsumer
                )
            except ImportError:
                logger.warning("⚠️ Premarket candle builder not available")
            
            # Register market analytics
            try:
                from services.enhanced_market_analytics import enhanced_analytics
                await self.register_service(
                    "market_analytics",
                    enhanced_analytics,
                    HFTMarketAnalyticsConsumer
                )
            except ImportError:
                logger.warning("⚠️ Enhanced market analytics not available")
            
            logger.info(f"✅ Registered {len(self._services)} default services")
            
        except Exception as e:
            logger.error(f"❌ Default service registration failed: {e}")
            raise
    
    async def _start_service_consumers(self) -> None:
        """Start all registered service consumers"""
        try:
            for service_name, registration in self._services.items():
                if registration.consumer_instance:
                    await self._start_service_consumer(service_name)
            
            logger.info(f"✅ Started consumers for {len(self._consumer_tasks)} services")
            
        except Exception as e:
            logger.error(f"❌ Service consumer startup failed: {e}")
            raise
    
    async def _start_service_consumer(self, service_name: str) -> None:
        """Start consumer for a specific service"""
        try:
            registration = self._services[service_name]
            if not registration.consumer_instance:
                return
            
            # Start consumer task
            consumer_task = asyncio.create_task(
                registration.consumer_instance.start_consuming()
            )
            self._consumer_tasks.add(consumer_task)
            
            registration.is_active = True
            registration.start_time = datetime.now()
            
            logger.debug(f"✅ Started consumer for service: {service_name}")
            
        except Exception as e:
            registration = self._services.get(service_name)
            if registration:
                registration.error_count += 1
                registration.last_error = str(e)
            logger.error(f"❌ Failed to start consumer for {service_name}: {e}")
    
    async def _stop_service_consumer(self, service_name: str) -> None:
        """Stop consumer for a specific service"""
        try:
            registration = self._services.get(service_name)
            if not registration or not registration.consumer_instance:
                return
            
            if hasattr(registration.consumer_instance, 'stop_consuming'):
                await registration.consumer_instance.stop_consuming()
            
            registration.is_active = False
            
            logger.debug(f"✅ Stopped consumer for service: {service_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to stop consumer for {service_name}: {e}")
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive system health check"""
        try:
            health_status = {
                "is_healthy": True,
                "timestamp": datetime.now().isoformat(),
                "components": {},
                "issues": []
            }
            
            # Check producer health
            if self._producer:
                producer_health = await self._producer.health_check()
                health_status["components"]["producer"] = producer_health
                if producer_health.get("status") != "healthy":
                    health_status["is_healthy"] = False
                    health_status["issues"].append(f"Producer: {producer_health.get('reason', 'Unknown')}")
            
            # Check memory bridge health
            if self._memory_bridge:
                bridge_health = await self._memory_bridge.health_check()
                health_status["components"]["memory_bridge"] = bridge_health
                if bridge_health.get("status") != "healthy":
                    health_status["is_healthy"] = False
                    health_status["issues"].append(f"Memory Bridge: {bridge_health.get('reason', 'Unknown')}")
            
            # Check service health
            failed_services = [
                name for name, reg in self._services.items()
                if not reg.is_active and reg.error_count > 0
            ]
            
            if failed_services:
                health_status["is_healthy"] = False
                health_status["issues"].extend([f"Service failed: {s}" for s in failed_services])
            
            health_status["components"]["services"] = {
                "total": len(self._services),
                "active": len([r for r in self._services.values() if r.is_active]),
                "failed": len(failed_services)
            }
            
            self._status.last_health_check = datetime.now()
            return health_status
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                "is_healthy": False,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def _cleanup_core_components(self) -> None:
        """Cleanup core components"""
        try:
            # Cleanup producer
            if self._producer:
                await cleanup_hft_producer()
                self._producer = None
            
            # Cleanup memory bridge
            if self._memory_bridge:
                await cleanup_hft_memory_bridge()
                self._memory_bridge = None
            
            # Stop monitoring
            if self._performance_monitor:
                await stop_hft_monitoring()
                self._performance_monitor = None
            
            logger.debug("✅ Core components cleaned up")
            
        except Exception as e:
            logger.error(f"❌ Core components cleanup failed: {e}")
    
    async def _cleanup_on_failure(self) -> None:
        """Cleanup resources after initialization failure"""
        try:
            await self._cleanup_core_components()
            self._services.clear()
            self._consumer_tasks.clear()
            self._status = HFTSystemStatus()
        except Exception as e:
            logger.error(f"❌ Failure cleanup error: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
            self._status.uptime_seconds = uptime
        
        return {
            "is_initialized": self._status.is_initialized,
            "is_running": self._status.is_running,
            "services_count": self._status.services_count,
            "active_services": self._status.active_services,
            "failed_services": [
                name for name, reg in self._services.items()
                if reg.error_count > 0
            ],
            "uptime_seconds": self._status.uptime_seconds,
            "last_health_check": self._status.last_health_check.isoformat() if self._status.last_health_check else None,
            "performance": self._performance_monitor.get_system_health() if self._performance_monitor else None
        }
    
    def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific service"""
        if service_name not in self._services:
            return None
        
        registration = self._services[service_name]
        return {
            "service_name": service_name,
            "is_active": registration.is_active,
            "start_time": registration.start_time.isoformat() if registration.start_time else None,
            "error_count": registration.error_count,
            "last_error": registration.last_error,
            "has_consumer": registration.consumer_instance is not None,
            "performance": self._performance_monitor.get_service_metrics(service_name) if self._performance_monitor else None
        }
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a specific service"""
        try:
            if service_name not in self._services:
                logger.error(f"Service {service_name} not registered")
                return False
            
            # Stop service
            await self._stop_service_consumer(service_name)
            
            # Wait a moment
            await asyncio.sleep(1.0)
            
            # Start service
            await self._start_service_consumer(service_name)
            
            logger.info(f"✅ Restarted service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to restart service {service_name}: {e}")
            return False


# Singleton instance
_hft_system: Optional[HFTSystemIntegration] = None


def get_hft_system() -> HFTSystemIntegration:
    """Get singleton HFT System Integration instance"""
    global _hft_system
    if _hft_system is None:
        _hft_system = HFTSystemIntegration()
    return _hft_system


async def initialize_hft_system() -> bool:
    """Initialize the HFT system"""
    system = get_hft_system()
    return await system.initialize()


async def cleanup_hft_system() -> None:
    """Cleanup HFT system resources"""
    global _hft_system
    if _hft_system:
        await _hft_system.stop_system()
        _hft_system = None


# Export main classes and functions
__all__ = [
    "ServiceRegistration",
    "HFTSystemStatus",
    "HFTSystemIntegration",
    "get_hft_system",
    "initialize_hft_system",
    "cleanup_hft_system"
]