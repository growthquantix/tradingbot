"""
Kafka Analytics Integration Orchestrator

Central orchestrator that coordinates all Kafka-based analytics services.
Implements proper system design principles with clean separation of concerns.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from services.hft.integration import get_hft_system
from services.analytics.real_time_analytics_engine import get_analytics_engine
from services.analytics.kafka_sse_bridge import get_kafka_sse_bridge
from services.stock_selection.real_time_stock_selector import get_stock_selector
from services.centralized_ws_manager import centralized_manager

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Service status information"""
    name: str
    is_running: bool
    last_health_check: datetime
    error_count: int
    performance_stats: Dict[str, Any]


class KafkaAnalyticsOrchestrator:
    """
    Orchestrator for Kafka-based analytics system.
    
    Coordinates:
    1. Live data ingestion (Centralized WS Manager → Kafka)
    2. Feature calculation (Analytics Engine) 
    3. Real-time analytics (Top movers, breakouts, etc.)
    4. Stock selection (Daily + Real-time)
    5. UI broadcasting (Kafka → SSE)
    
    Follows clean architecture principles:
    - Single Responsibility: Each service has one purpose
    - Dependency Inversion: Services depend on abstractions
    - Open/Closed: Easy to add new analytics services
    """
    
    def __init__(self):
        # System components
        self._hft_system = None
        self._analytics_engine = None
        self._kafka_sse_bridge = None
        self._stock_selector = None
        
        # Service management
        self._services: Dict[str, ServiceStatus] = {}
        self._is_running = False
        self._orchestrator_tasks = set()
        
        # Health monitoring
        self._health_check_interval = 30  # seconds
        self._performance_check_interval = 60  # seconds
        
        logger.info("✅ Kafka Analytics Orchestrator initialized")
    
    async def initialize_system(self) -> bool:
        """Initialize all system components"""
        try:
            logger.info("🚀 Initializing Kafka Analytics System...")
            
            # 1. Initialize HFT Kafka infrastructure
            self._hft_system = get_hft_system()
            if not await self._hft_system.initialize():
                raise Exception("HFT system initialization failed")
            
            # 2. Initialize Analytics Engine
            self._analytics_engine = await get_analytics_engine()
            
            # 3. Initialize Kafka-SSE Bridge
            self._kafka_sse_bridge = await get_kafka_sse_bridge()
            
            # 4. Initialize Stock Selector
            self._stock_selector = await get_stock_selector()
            
            # 5. Initialize service status tracking
            self._initialize_service_status()
            
            logger.info("✅ All system components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}")
            await self._cleanup_on_failure()
            return False
    
    async def start_system(self) -> bool:
        """Start all system components in proper order"""
        try:
            if not await self.initialize_system():
                return False
            
            logger.info("🚀 Starting Kafka Analytics System...")
            
            # 1. Start HFT Kafka system
            if not await self._hft_system.start_system():
                raise Exception("HFT system start failed")
            
            # 2. Start analytics services as background tasks
            await self._start_analytics_services()
            
            # 3. Start health monitoring
            await self._start_health_monitoring()
            
            # 4. Register with centralized WS manager for live data
            await self._register_with_ws_manager()
            
            self._is_running = True
            logger.info("✅ Kafka Analytics System started successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ System start failed: {e}")
            await self.stop_system()
            return False
    
    async def _start_analytics_services(self) -> None:
        """Start analytics services as background tasks"""
        try:
            # Start analytics engine consumer
            analytics_task = asyncio.create_task(
                self._analytics_engine.start_consuming()
            )
            self._orchestrator_tasks.add(analytics_task)
            analytics_task.add_done_callback(
                lambda t: self._orchestrator_tasks.discard(t)
            )
            
            # Start Kafka-SSE bridge consumer  
            bridge_task = asyncio.create_task(
                self._kafka_sse_bridge.start_consuming()
            )
            self._orchestrator_tasks.add(bridge_task)
            bridge_task.add_done_callback(
                lambda t: self._orchestrator_tasks.discard(t)
            )
            
            # Start stock selector consumer
            selector_task = asyncio.create_task(
                self._stock_selector.start_consuming()
            )
            self._orchestrator_tasks.add(selector_task)
            selector_task.add_done_callback(
                lambda t: self._orchestrator_tasks.discard(t)
            )
            
            logger.info("✅ All analytics services started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start analytics services: {e}")
            raise
    
    async def _start_health_monitoring(self) -> None:
        """Start system health monitoring"""
        try:
            # Start health check task
            health_task = asyncio.create_task(self._health_monitoring_loop())
            self._orchestrator_tasks.add(health_task)
            health_task.add_done_callback(
                lambda t: self._orchestrator_tasks.discard(t)
            )
            
            # Start performance monitoring task
            perf_task = asyncio.create_task(self._performance_monitoring_loop())
            self._orchestrator_tasks.add(perf_task)
            perf_task.add_done_callback(
                lambda t: self._orchestrator_tasks.discard(t)
            )
            
            logger.info("✅ Health monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start health monitoring: {e}")
            raise
    
    async def _register_with_ws_manager(self) -> None:
        """Register callback with centralized WebSocket manager for live data"""
        try:
            # Register callback for live market data
            def live_data_callback(data):
                """Callback for live market data from WebSocket"""
                try:
                    # This data will automatically flow to Kafka via the existing
                    # centralized_ws_manager._hft_kafka_stream() method
                    logger.debug("📡 Received live data for Kafka processing")
                except Exception as e:
                    logger.error(f"❌ Error in live data callback: {e}")
            
            # The centralized_ws_manager already has Kafka integration
            # We just need to ensure it's properly initialized
            if not centralized_manager.hft_producer:
                await centralized_manager.initialize_hft_kafka()
            
            logger.info("✅ Integrated with centralized WebSocket manager")
            
        except Exception as e:
            logger.error(f"❌ Failed to register with WS manager: {e}")
    
    async def _health_monitoring_loop(self) -> None:
        """Monitor system health continuously"""
        while self._is_running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self._health_check_interval)
            except Exception as e:
                logger.error(f"❌ Health monitoring error: {e}")
                await asyncio.sleep(self._health_check_interval)
    
    async def _performance_monitoring_loop(self) -> None:
        """Monitor system performance continuously"""
        while self._is_running:
            try:
                await self._collect_performance_stats()
                await asyncio.sleep(self._performance_check_interval)
            except Exception as e:
                logger.error(f"❌ Performance monitoring error: {e}")
                await asyncio.sleep(self._performance_check_interval)
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all services"""
        try:
            current_time = datetime.now()
            
            # Check HFT system health
            if self._hft_system:
                hft_status = await self._hft_system.get_system_health()
                self._update_service_status(
                    "hft_system", 
                    hft_status.get("is_healthy", False),
                    current_time,
                    hft_status
                )
            
            # Check analytics engine health
            if self._analytics_engine:
                analytics_stats = self._analytics_engine.get_performance_stats()
                self._update_service_status(
                    "analytics_engine",
                    self._analytics_engine._is_running,
                    current_time,
                    analytics_stats
                )
            
            # Check Kafka-SSE bridge health
            if self._kafka_sse_bridge:
                bridge_stats = self._kafka_sse_bridge.get_bridge_stats()
                self._update_service_status(
                    "kafka_sse_bridge",
                    self._kafka_sse_bridge._is_running,
                    current_time,
                    bridge_stats
                )
            
            # Check stock selector health
            if self._stock_selector:
                selector_stats = self._stock_selector.get_selection_stats()
                self._update_service_status(
                    "stock_selector",
                    self._stock_selector._is_running,
                    current_time,
                    selector_stats
                )
            
            logger.debug("🔍 Health checks completed")
            
        except Exception as e:
            logger.error(f"❌ Error performing health checks: {e}")
    
    async def _collect_performance_stats(self) -> None:
        """Collect performance statistics from all services"""
        try:
            performance_summary = {
                "system_uptime": (datetime.now() - (self._start_time if hasattr(self, '_start_time') else datetime.now())).total_seconds(),
                "services_running": sum(1 for s in self._services.values() if s.is_running),
                "total_services": len(self._services),
                "orchestrator_tasks": len(self._orchestrator_tasks)
            }
            
            # Add individual service stats
            for service_name, status in self._services.items():
                performance_summary[f"{service_name}_stats"] = status.performance_stats
            
            logger.info(f"📊 System Performance: {performance_summary['services_running']}/{performance_summary['total_services']} services running")
            
        except Exception as e:
            logger.error(f"❌ Error collecting performance stats: {e}")
    
    def _initialize_service_status(self) -> None:
        """Initialize service status tracking"""
        service_names = [
            "hft_system",
            "analytics_engine", 
            "kafka_sse_bridge",
            "stock_selector"
        ]
        
        for name in service_names:
            self._services[name] = ServiceStatus(
                name=name,
                is_running=False,
                last_health_check=datetime.now(),
                error_count=0,
                performance_stats={}
            )
    
    def _update_service_status(
        self, 
        service_name: str, 
        is_running: bool,
        check_time: datetime,
        stats: Dict[str, Any]
    ) -> None:
        """Update service status information"""
        if service_name in self._services:
            service = self._services[service_name]
            
            # Update error count if service went down
            if service.is_running and not is_running:
                service.error_count += 1
            
            service.is_running = is_running
            service.last_health_check = check_time
            service.performance_stats = stats
    
    async def stop_system(self) -> None:
        """Stop all system components gracefully"""
        try:
            logger.info("🛑 Stopping Kafka Analytics System...")
            self._is_running = False
            
            # Stop orchestrator tasks
            for task in list(self._orchestrator_tasks):
                if not task.done():
                    task.cancel()
            
            if self._orchestrator_tasks:
                await asyncio.gather(*self._orchestrator_tasks, return_exceptions=True)
            
            # Stop analytics services
            if self._analytics_engine:
                await self._analytics_engine.stop_consuming()
            
            if self._kafka_sse_bridge:
                await self._kafka_sse_bridge.stop_consuming()
            
            if self._stock_selector:
                await self._stock_selector.stop_consuming()
            
            # Stop HFT system
            if self._hft_system:
                await self._hft_system.stop_system()
            
            logger.info("✅ Kafka Analytics System stopped gracefully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping system: {e}")
    
    async def _cleanup_on_failure(self) -> None:
        """Cleanup resources on initialization failure"""
        try:
            if self._hft_system:
                await self._hft_system.stop_system()
            
            # Clear references
            self._hft_system = None
            self._analytics_engine = None
            self._kafka_sse_bridge = None
            self._stock_selector = None
            
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "is_running": self._is_running,
            "services": {
                name: {
                    "is_running": status.is_running,
                    "last_health_check": status.last_health_check.isoformat(),
                    "error_count": status.error_count,
                    "performance_stats": status.performance_stats
                }
                for name, status in self._services.items()
            },
            "orchestrator_tasks": len(self._orchestrator_tasks),
            "health_check_interval": self._health_check_interval,
            "performance_check_interval": self._performance_check_interval
        }
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a specific service"""
        try:
            logger.info(f"🔄 Restarting service: {service_name}")
            
            # Implementation would restart specific service
            # For now, just log the request
            logger.info(f"✅ Service restart requested for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to restart {service_name}: {e}")
            return False


# Singleton instance
_orchestrator: Optional[KafkaAnalyticsOrchestrator] = None


async def get_kafka_analytics_orchestrator() -> KafkaAnalyticsOrchestrator:
    """Get singleton orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = KafkaAnalyticsOrchestrator()
    return _orchestrator


async def start_kafka_analytics_system() -> bool:
    """Start the complete Kafka analytics system"""
    orchestrator = await get_kafka_analytics_orchestrator()
    return await orchestrator.start_system()


async def stop_kafka_analytics_system() -> None:
    """Stop the complete Kafka analytics system"""
    global _orchestrator
    if _orchestrator:
        await _orchestrator.stop_system()
        _orchestrator = None


async def get_system_status() -> Dict[str, Any]:
    """Get system status without starting it"""
    if _orchestrator:
        return _orchestrator.get_system_status()
    return {"is_running": False, "services": {}}


# Export main functions
__all__ = [
    "KafkaAnalyticsOrchestrator",
    "get_kafka_analytics_orchestrator",
    "start_kafka_analytics_system",
    "stop_kafka_analytics_system", 
    "get_system_status"
]