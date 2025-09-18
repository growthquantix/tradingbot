"""
Market Session-Based HFT Scheduler

Production-grade scheduler that manages HFT processing based on market sessions:
- Premarket (9:00-9:15 AM): Gap detection, volume analysis
- Opening (9:15-9:30 AM): Breakout detection, range analysis  
- Regular Hours (9:30 AM-3:30 PM): Full feature processing
- Closing (3:30-4:00 PM): Summary calculations
- Post-Market/Closed: Reduced processing, historical analysis

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Set, Optional, Any, Callable
from datetime import datetime, time as time_obj, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json

from .enhanced_live_feed_processor import (
    get_enhanced_live_feed_processor, 
    MarketSession,
    ProcessingMode
)
from .partition_strategy import get_enhanced_partition_manager, ServiceType
from .producer import get_hft_producer

logger = logging.getLogger(__name__)


class SchedulerMode(Enum):
    """Scheduler operation modes"""
    ACTIVE = "active"           # Full processing during market hours
    REDUCED = "reduced"         # Reduced processing during off-hours  
    MAINTENANCE = "maintenance" # Maintenance mode with minimal processing
    STOPPED = "stopped"         # Scheduler stopped


@dataclass
class SessionSchedule:
    """Schedule configuration for market session"""
    session: MarketSession
    start_time: time_obj
    end_time: time_obj
    processing_mode: ProcessingMode
    enabled_services: Set[ServiceType]
    processing_interval_seconds: int
    batch_size: int
    priority_level: int


@dataclass
class SchedulerStats:
    """Scheduler performance statistics"""
    current_session: MarketSession
    scheduler_mode: SchedulerMode
    sessions_processed: int = 0
    total_processing_time_seconds: float = 0.0
    last_session_change: Optional[datetime] = None
    processing_errors: int = 0
    services_active: Set[ServiceType] = field(default_factory=set)
    avg_session_processing_time: float = 0.0


class MarketSessionScheduler:
    """
    Market session-aware scheduler for HFT processing
    
    Features:
    - Automatic session detection and switching
    - Session-specific processing configurations
    - Dynamic service enablement/disablement
    - Performance monitoring and optimization
    - Error handling and recovery
    """
    
    def __init__(self):
        self.live_feed_processor = get_enhanced_live_feed_processor()
        self.partition_manager = get_enhanced_partition_manager()
        self.producer = get_hft_producer()
        
        # Scheduler state
        self.current_session = MarketSession.CLOSED
        self.scheduler_mode = SchedulerMode.STOPPED
        self.is_running = False
        
        # Session schedules
        self.session_schedules = self._initialize_session_schedules()
        
        # Performance tracking
        self.stats = SchedulerStats(
            current_session=self.current_session,
            scheduler_mode=self.scheduler_mode
        )
        
        # Background tasks
        self.scheduler_task: Optional[asyncio.Task] = None
        self.session_monitor_task: Optional[asyncio.Task] = None
        self.performance_monitor_task: Optional[asyncio.Task] = None
        
        # Service registry
        self.registered_services: Dict[ServiceType, Callable] = {}
        self.service_states: Dict[ServiceType, bool] = {}
        
        logger.info("Market Session Scheduler initialized")
    
    def _initialize_session_schedules(self) -> Dict[MarketSession, SessionSchedule]:
        """Initialize processing schedules for each market session"""
        
        return {
            MarketSession.PRE_MARKET: SessionSchedule(
                session=MarketSession.PRE_MARKET,
                start_time=time_obj(9, 0),
                end_time=time_obj(9, 15),
                processing_mode=ProcessingMode.STREAM,
                enabled_services={
                    ServiceType.GAP_DETECTION,
                    ServiceType.SECTOR_ANALYTICS,
                    ServiceType.ADR_CALCULATION,
                    ServiceType.MARKET_SENTIMENT,
                    ServiceType.REAL_TIME_UI
                },
                processing_interval_seconds=5,
                batch_size=100,
                priority_level=1
            ),
            
            MarketSession.OPENING: SessionSchedule(
                session=MarketSession.OPENING,
                start_time=time_obj(9, 15),
                end_time=time_obj(9, 30),
                processing_mode=ProcessingMode.STREAM,
                enabled_services={
                    ServiceType.BREAKOUT_DETECTION,
                    ServiceType.TOP_MOVERS,
                    ServiceType.SECTOR_ANALYTICS,
                    ServiceType.AUTO_TRADING,
                    ServiceType.REAL_TIME_UI
                },
                processing_interval_seconds=2,
                batch_size=50,
                priority_level=1
            ),
            
            MarketSession.REGULAR_HOURS: SessionSchedule(
                session=MarketSession.REGULAR_HOURS,
                start_time=time_obj(9, 30),
                end_time=time_obj(15, 30),
                processing_mode=ProcessingMode.STREAM,
                enabled_services={
                    ServiceType.BREAKOUT_DETECTION,
                    ServiceType.TOP_MOVERS,
                    ServiceType.SECTOR_ANALYTICS,
                    ServiceType.HEATMAP_GENERATION,
                    ServiceType.ADR_CALCULATION,
                    ServiceType.MARKET_SENTIMENT,
                    ServiceType.AUTO_TRADING,
                    ServiceType.STOCK_SELECTION,
                    ServiceType.REAL_TIME_UI
                },
                processing_interval_seconds=1,
                batch_size=200,
                priority_level=1
            ),
            
            MarketSession.CLOSING: SessionSchedule(
                session=MarketSession.CLOSING,
                start_time=time_obj(15, 30),
                end_time=time_obj(16, 0),
                processing_mode=ProcessingMode.STREAM,
                enabled_services={
                    ServiceType.SECTOR_ANALYTICS,
                    ServiceType.ADR_CALCULATION,
                    ServiceType.MARKET_SENTIMENT,
                    ServiceType.HEATMAP_GENERATION,
                    ServiceType.REAL_TIME_UI
                },
                processing_interval_seconds=10,
                batch_size=300,
                priority_level=2
            ),
            
            MarketSession.POST_MARKET: SessionSchedule(
                session=MarketSession.POST_MARKET,
                start_time=time_obj(16, 0),
                end_time=time_obj(18, 0),
                processing_mode=ProcessingMode.BATCH,
                enabled_services={
                    ServiceType.SECTOR_ANALYTICS,
                    ServiceType.HEATMAP_GENERATION,
                    ServiceType.STOCK_SELECTION
                },
                processing_interval_seconds=30,
                batch_size=1000,
                priority_level=3
            ),
            
            MarketSession.CLOSED: SessionSchedule(
                session=MarketSession.CLOSED,
                start_time=time_obj(18, 0),
                end_time=time_obj(9, 0),
                processing_mode=ProcessingMode.REDUCED,
                enabled_services={
                    ServiceType.STOCK_SELECTION,
                    ServiceType.HEATMAP_GENERATION
                },
                processing_interval_seconds=300,  # 5 minutes
                batch_size=500,
                priority_level=4
            )
        }
    
    def register_service(
        self, 
        service_type: ServiceType, 
        service_handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """Register a service handler for processing"""
        
        self.registered_services[service_type] = service_handler
        self.service_states[service_type] = False
        
        logger.info(f"Registered service: {service_type.value}")
    
    async def start_scheduler(self) -> bool:
        """Start the market session scheduler"""
        
        if self.is_running:
            logger.warning("Scheduler is already running")
            return True
        
        try:
            # Update current session
            self.current_session = self._determine_current_session()
            self.scheduler_mode = SchedulerMode.ACTIVE
            self.is_running = True
            
            # Start background tasks
            self.scheduler_task = asyncio.create_task(self._scheduler_main_loop())
            self.session_monitor_task = asyncio.create_task(self._session_monitor_loop())
            self.performance_monitor_task = asyncio.create_task(self._performance_monitor_loop())
            
            # Apply current session configuration
            await self._apply_session_configuration(self.current_session)
            
            logger.info(f"Market Session Scheduler started in {self.current_session.value} mode")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            self.is_running = False
            return False
    
    async def stop_scheduler(self) -> None:
        """Stop the market session scheduler"""
        
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            self.scheduler_mode = SchedulerMode.STOPPED
            
            # Cancel background tasks
            tasks_to_cancel = [
                self.scheduler_task,
                self.session_monitor_task, 
                self.performance_monitor_task
            ]
            
            for task in tasks_to_cancel:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Disable all services
            await self._disable_all_services()
            
            logger.info("Market Session Scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def _determine_current_session(self) -> MarketSession:
        """Determine current market session based on time"""
        
        now = datetime.now().time()
        
        # Check each session schedule
        for session, schedule in self.session_schedules.items():
            if self._is_time_in_session(now, schedule):
                return session
        
        # Default to CLOSED if no session matches
        return MarketSession.CLOSED
    
    def _is_time_in_session(self, current_time: time_obj, schedule: SessionSchedule) -> bool:
        """Check if current time falls within session schedule"""
        
        start_time = schedule.start_time
        end_time = schedule.end_time
        
        # Handle overnight sessions (CLOSED session crosses midnight)
        if start_time > end_time:  
            return current_time >= start_time or current_time < end_time
        else:
            return start_time <= current_time < end_time
    
    async def _scheduler_main_loop(self) -> None:
        """Main scheduler loop"""
        
        while self.is_running:
            try:
                session_schedule = self.session_schedules[self.current_session]
                
                # Process based on current session configuration
                await self._process_session_tasks(session_schedule)
                
                # Wait for next processing cycle
                await asyncio.sleep(session_schedule.processing_interval_seconds)
                
            except Exception as e:
                self.stats.processing_errors += 1
                logger.error(f"Error in scheduler main loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _session_monitor_loop(self) -> None:
        """Monitor for market session changes"""
        
        while self.is_running:
            try:
                new_session = self._determine_current_session()
                
                if new_session != self.current_session:
                    await self._handle_session_change(self.current_session, new_session)
                
                # Check every 30 seconds for session changes
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in session monitor: {e}")
                await asyncio.sleep(30)
    
    async def _performance_monitor_loop(self) -> None:
        """Monitor scheduler performance and health"""
        
        while self.is_running:
            try:
                # Update performance statistics
                await self._update_performance_stats()
                
                # Log performance metrics every 5 minutes
                if self.stats.sessions_processed > 0:
                    logger.info(
                        f"Scheduler Performance - Session: {self.current_session.value}, "
                        f"Processed: {self.stats.sessions_processed}, "
                        f"Avg Time: {self.stats.avg_session_processing_time:.2f}s, "
                        f"Errors: {self.stats.processing_errors}, "
                        f"Active Services: {len(self.stats.services_active)}"
                    )
                
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")
                await asyncio.sleep(300)
    
    async def _process_session_tasks(self, schedule: SessionSchedule) -> None:
        """Process tasks for current session"""
        
        start_time = datetime.now()
        
        try:
            # Execute enabled services
            service_tasks = []
            
            for service_type in schedule.enabled_services:
                if service_type in self.registered_services and self.service_states.get(service_type, False):
                    service_handler = self.registered_services[service_type]
                    
                    # Create service task with session context
                    task_context = {
                        'session': schedule.session.value,
                        'processing_mode': schedule.processing_mode.value,
                        'batch_size': schedule.batch_size,
                        'priority_level': schedule.priority_level,
                        'timestamp': start_time.isoformat()
                    }
                    
                    task = asyncio.create_task(service_handler(task_context))
                    service_tasks.append(task)
            
            # Execute all service tasks concurrently
            if service_tasks:
                results = await asyncio.gather(*service_tasks, return_exceptions=True)
                
                # Log any service errors
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        service_type = list(schedule.enabled_services)[i]
                        logger.error(f"Service {service_type.value} error: {result}")
            
            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats.sessions_processed += 1
            self.stats.total_processing_time_seconds += processing_time
            
            # Update average processing time
            self.stats.avg_session_processing_time = (
                self.stats.total_processing_time_seconds / self.stats.sessions_processed
            )
            
        except Exception as e:
            self.stats.processing_errors += 1
            logger.error(f"Error processing session tasks: {e}")
    
    async def _handle_session_change(self, old_session: MarketSession, new_session: MarketSession) -> None:
        """Handle transition between market sessions"""
        
        logger.info(f"Market session changing: {old_session.value} -> {new_session.value}")
        
        try:
            # Disable services from old session
            old_schedule = self.session_schedules[old_session]
            for service_type in old_schedule.enabled_services:
                if service_type not in self.session_schedules[new_session].enabled_services:
                    await self._disable_service(service_type)
            
            # Apply new session configuration
            await self._apply_session_configuration(new_session)
            
            # Update state
            self.current_session = new_session
            self.stats.current_session = new_session
            self.stats.last_session_change = datetime.now()
            
            # Broadcast session change
            await self._broadcast_session_change(old_session, new_session)
            
            logger.info(f"Successfully transitioned to {new_session.value}")
            
        except Exception as e:
            logger.error(f"Error handling session change: {e}")
    
    async def _apply_session_configuration(self, session: MarketSession) -> None:
        """Apply configuration for market session"""
        
        schedule = self.session_schedules[session]
        
        try:
            # Enable services for this session
            enabled_services = set()
            
            for service_type in schedule.enabled_services:
                if service_type in self.registered_services:
                    await self._enable_service(service_type)
                    enabled_services.add(service_type)
            
            self.stats.services_active = enabled_services
            
            logger.info(f"Applied configuration for {session.value} - {len(enabled_services)} services active")
            
        except Exception as e:
            logger.error(f"Error applying session configuration: {e}")
    
    async def _enable_service(self, service_type: ServiceType) -> None:
        """Enable a specific service"""
        
        try:
            self.service_states[service_type] = True
            
            # Send service enablement message to Kafka
            await self._send_service_control_message(service_type, "enable")
            
            logger.debug(f"Enabled service: {service_type.value}")
            
        except Exception as e:
            logger.error(f"Error enabling service {service_type.value}: {e}")
    
    async def _disable_service(self, service_type: ServiceType) -> None:
        """Disable a specific service"""
        
        try:
            self.service_states[service_type] = False
            
            # Send service disablement message to Kafka
            await self._send_service_control_message(service_type, "disable")
            
            logger.debug(f"Disabled service: {service_type.value}")
            
        except Exception as e:
            logger.error(f"Error disabling service {service_type.value}: {e}")
    
    async def _disable_all_services(self) -> None:
        """Disable all registered services"""
        
        for service_type in self.registered_services.keys():
            await self._disable_service(service_type)
        
        self.stats.services_active.clear()
    
    async def _send_service_control_message(self, service_type: ServiceType, action: str) -> None:
        """Send service control message to Kafka"""
        
        try:
            control_message = {
                'action': action,
                'service_type': service_type.value,
                'timestamp': datetime.now().isoformat(),
                'scheduler_id': 'market_session_scheduler',
                'session': self.current_session.value
            }
            
            # Send to control topic
            topic_name = f"hft.control.{service_type.value}"
            await self.producer.send_to_topic(topic_name, control_message)
            
        except Exception as e:
            logger.error(f"Error sending service control message: {e}")
    
    async def _broadcast_session_change(self, old_session: MarketSession, new_session: MarketSession) -> None:
        """Broadcast session change to all consumers"""
        
        try:
            session_change_message = {
                'event_type': 'session_change',
                'old_session': old_session.value,
                'new_session': new_session.value,
                'timestamp': datetime.now().isoformat(),
                'enabled_services': [s.value for s in self.stats.services_active],
                'processing_mode': self.session_schedules[new_session].processing_mode.value
            }
            
            # Broadcast to all service topics
            broadcast_tasks = []
            for service_type in ServiceType:
                topic_name = f"hft.session_events.{service_type.value}"
                task = self.producer.send_to_topic(topic_name, session_change_message)
                broadcast_tasks.append(task)
            
            await asyncio.gather(*broadcast_tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Error broadcasting session change: {e}")
    
    async def _update_performance_stats(self) -> None:
        """Update performance statistics"""
        
        try:
            # Get processor stats
            processor_stats = self.live_feed_processor.get_processing_stats()
            
            # Update scheduler stats with processor information
            self.stats.scheduler_mode = self.scheduler_mode
            
            # Get partition manager stats
            partition_stats = self.partition_manager.get_partition_load_stats()
            
            # Log detailed stats periodically
            detailed_stats = {
                'scheduler_stats': {
                    'current_session': self.stats.current_session.value,
                    'sessions_processed': self.stats.sessions_processed,
                    'avg_processing_time': self.stats.avg_session_processing_time,
                    'processing_errors': self.stats.processing_errors,
                    'active_services_count': len(self.stats.services_active)
                },
                'processor_stats': processor_stats,
                'partition_stats': partition_stats
            }
            
            # Store stats for monitoring
            self.last_performance_stats = detailed_stats
            
        except Exception as e:
            logger.error(f"Error updating performance stats: {e}")
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        
        current_schedule = self.session_schedules[self.current_session]
        
        return {
            'is_running': self.is_running,
            'current_session': self.current_session.value,
            'scheduler_mode': self.scheduler_mode.value,
            'processing_interval_seconds': current_schedule.processing_interval_seconds,
            'enabled_services': [s.value for s in self.stats.services_active],
            'registered_services': list(self.registered_services.keys()),
            'performance_stats': {
                'sessions_processed': self.stats.sessions_processed,
                'avg_processing_time_seconds': self.stats.avg_session_processing_time,
                'processing_errors': self.stats.processing_errors,
                'last_session_change': self.stats.last_session_change.isoformat() if self.stats.last_session_change else None
            },
            'next_session_change': self._get_next_session_change_time(),
            'uptime_seconds': (datetime.now() - (self.stats.last_session_change or datetime.now())).total_seconds()
        }
    
    def _get_next_session_change_time(self) -> Optional[str]:
        """Get the next expected session change time"""
        
        try:
            now = datetime.now()
            current_schedule = self.session_schedules[self.current_session]
            
            # Calculate next session end time
            today = now.date()
            next_session_time = datetime.combine(today, current_schedule.end_time)
            
            # If end time has passed today, it's tomorrow
            if next_session_time <= now:
                next_session_time = datetime.combine(today + timedelta(days=1), current_schedule.end_time)
            
            return next_session_time.isoformat()
            
        except Exception as e:
            logger.error(f"Error calculating next session change: {e}")
            return None
    
    async def force_session_change(self, target_session: MarketSession) -> bool:
        """Force a session change for testing or manual control"""
        
        if not self.is_running:
            logger.error("Cannot force session change - scheduler not running")
            return False
        
        try:
            old_session = self.current_session
            await self._handle_session_change(old_session, target_session)
            
            logger.info(f"Forced session change to {target_session.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error forcing session change: {e}")
            return False
    
    def set_maintenance_mode(self, enabled: bool) -> None:
        """Enable or disable maintenance mode"""
        
        if enabled:
            self.scheduler_mode = SchedulerMode.MAINTENANCE
            logger.info("Scheduler entered maintenance mode")
        else:
            self.scheduler_mode = SchedulerMode.ACTIVE
            logger.info("Scheduler exited maintenance mode")


# Singleton instance
_scheduler: Optional[MarketSessionScheduler] = None


def get_market_session_scheduler() -> MarketSessionScheduler:
    """Get singleton market session scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = MarketSessionScheduler()
    return _scheduler


async def initialize_market_session_scheduler() -> bool:
    """Initialize and start the market session scheduler"""
    try:
        scheduler = get_market_session_scheduler()
        success = await scheduler.start_scheduler()
        
        if success:
            logger.info("Market Session Scheduler initialized and started successfully")
        else:
            logger.error("Failed to initialize Market Session Scheduler")
        
        return success
        
    except Exception as e:
        logger.error(f"Error initializing market session scheduler: {e}")
        return False


async def cleanup_market_session_scheduler() -> None:
    """Cleanup the market session scheduler"""
    try:
        global _scheduler
        if _scheduler:
            await _scheduler.stop_scheduler()
            _scheduler = None
        logger.info("Market Session Scheduler cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up market session scheduler: {e}")


# Export main components
__all__ = [
    "MarketSessionScheduler",
    "SchedulerMode", 
    "SessionSchedule",
    "SchedulerStats",
    "get_market_session_scheduler",
    "initialize_market_session_scheduler",
    "cleanup_market_session_scheduler"
]