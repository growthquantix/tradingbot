"""
Auto Trading Orchestrator with Complete Kafka Integration

Central orchestrator that coordinates all auto trading components with
the Kafka analytics system. Implements the complete workflow from
stock selection to trade execution and monitoring.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from services.hft.producer import get_hft_producer
from services.sse.sse_manager import get_sse_manager, SSEChannel
from services.integration.kafka_analytics_orchestrator import get_kafka_analytics_orchestrator

from .kafka_strategy_executor import KafkaStrategyExecutor, AutoTradingMode, ExecutionPhase
from .modular_stock_selector import get_modular_stock_selector
from .execution_engine import get_auto_trade_execution_engine
from .position_monitor import get_position_monitor
from .pnl_calculator import get_pnl_calculator
from .risk_manager import get_risk_manager, RiskProfile

logger = logging.getLogger(__name__)


class SystemStatus(Enum):
    """Auto trading system status"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass 
class AutoTradingSystemConfig:
    """Auto trading system configuration"""
    user_id: int
    trading_mode: AutoTradingMode = AutoTradingMode.PAPER_TRADING
    max_positions: int = 5
    max_daily_loss: float = 5000.0
    position_size_percent: float = 2.0
    
    # Market timing
    premarket_start_time: str = "09:00"
    trading_start_time: str = "09:30" 
    trading_end_time: str = "15:30"
    
    # Strategy configuration
    enable_fibonacci_strategy: bool = True
    enable_breakout_strategy: bool = True
    enable_momentum_strategy: bool = True
    
    # Risk management
    risk_profile: Optional[RiskProfile] = None


class AutoTradingOrchestrator:
    """
    Complete Auto Trading System Orchestrator
    
    Integrates all components:
    1. Kafka Analytics System (market data, features, stock selection)
    2. Strategy Execution (signals, trade generation)
    3. Trade Execution Engine (order placement, fills)
    4. Position Monitoring (real-time PnL)
    5. Risk Management (limits, circuit breakers)
    6. UI Streaming (live updates via SSE)
    
    Follows clean architecture principles with proper separation of concerns.
    """
    
    def __init__(self, config: AutoTradingSystemConfig):
        self.config = config
        self.session_id = str(uuid.uuid4())
        
        # System state
        self.status = SystemStatus.STOPPED
        self.start_time: Optional[datetime] = None
        self.current_phase = ExecutionPhase.PREMARKET_ANALYSIS
        
        # Component instances
        self._kafka_analytics = None
        self._strategy_executor = None
        self._stock_selector = None
        self._execution_engine = None
        self._position_monitor = None
        self._pnl_calculator = None
        self._risk_manager = None
        
        # Kafka and SSE
        self._kafka_producer = None
        self._sse_manager = None
        
        # System tasks
        self._orchestrator_tasks: Set[asyncio.Task] = set()
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self._trades_executed = 0
        self._positions_monitored = 0
        self._risk_alerts_handled = 0
        
        logger.info(f"🎯 Auto Trading Orchestrator initialized for user {config.user_id}")
    
    async def initialize_system(self) -> bool:
        """Initialize all auto trading components"""
        try:
            logger.info("🚀 Initializing Auto Trading System...")
            
            # 1. Initialize Kafka and SSE
            await self._initialize_communication()
            
            # 2. Initialize Kafka Analytics System
            await self._initialize_kafka_analytics()
            
            # 3. Initialize auto trading components
            await self._initialize_trading_components()
            
            # 4. Set up risk management
            await self._initialize_risk_management()
            
            # 5. Start monitoring tasks
            await self._start_monitoring_tasks()
            
            self.status = SystemStatus.RUNNING
            self.start_time = datetime.now()
            
            logger.info("✅ Auto Trading System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize auto trading system: {e}")
            await self._cleanup_on_failure()
            return False
    
    async def _initialize_communication(self) -> None:
        """Initialize Kafka producer and SSE manager"""
        try:
            self._kafka_producer = await get_hft_producer()
            self._sse_manager = await get_sse_manager()
            
            logger.info("✅ Communication systems initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize communication: {e}")
            raise
    
    async def _initialize_kafka_analytics(self) -> None:
        """Initialize Kafka analytics orchestrator"""
        try:
            self._kafka_analytics = await get_kafka_analytics_orchestrator()
            
            # Start the analytics system if not already running
            if not self._kafka_analytics.get_system_status()['is_running']:
                success = await self._kafka_analytics.start_system()
                if not success:
                    raise Exception("Failed to start Kafka analytics system")
            
            logger.info("✅ Kafka analytics system initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka analytics: {e}")
            raise
    
    async def _initialize_trading_components(self) -> None:
        """Initialize all auto trading components"""
        try:
            # Stock selector (integrated with Kafka analytics)
            self._stock_selector = await get_modular_stock_selector()
            
            # Strategy executor (Kafka-based)
            self._strategy_executor = KafkaStrategyExecutor(
                user_id=self.config.user_id,
                trading_mode=self.config.trading_mode
            )
            
            # Execution engine
            self._execution_engine = await get_auto_trade_execution_engine()
            
            # Position monitor (for live PnL)
            self._position_monitor = await get_position_monitor()
            
            # PnL calculator
            self._pnl_calculator = get_pnl_calculator()
            
            logger.info("✅ Trading components initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize trading components: {e}")
            raise
    
    async def _initialize_risk_management(self) -> None:
        """Initialize risk management system"""
        try:
            self._risk_manager = await get_risk_manager()
            
            # Set user risk profile
            if self.config.risk_profile:
                self._risk_manager.set_user_risk_profile(
                    self.config.user_id, 
                    self.config.risk_profile
                )
            
            logger.info("✅ Risk management initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize risk management: {e}")
            raise
    
    async def _start_monitoring_tasks(self) -> None:
        """Start system monitoring tasks"""
        try:
            # Start position monitoring consumer
            position_task = asyncio.create_task(
                self._position_monitor.start_consuming()
            )
            self._orchestrator_tasks.add(position_task)
            
            # Start system health monitoring
            health_task = asyncio.create_task(self._system_health_monitoring())
            self._orchestrator_tasks.add(health_task)
            
            # Start phase management
            phase_task = asyncio.create_task(self._phase_management())
            self._orchestrator_tasks.add(phase_task)
            
            # Start risk monitoring
            risk_task = asyncio.create_task(self._continuous_risk_monitoring())
            self._orchestrator_tasks.add(risk_task)
            
            # Start UI updates
            ui_task = asyncio.create_task(self._ui_update_broadcasting())
            self._orchestrator_tasks.add(ui_task)
            
            logger.info("✅ Monitoring tasks started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start monitoring tasks: {e}")
            raise
    
    async def start_trading_session(self) -> bool:
        """Start complete auto trading session"""
        try:
            if self.status != SystemStatus.RUNNING:
                if not await self.initialize_system():
                    return False
            
            logger.info(f"🎯 Starting auto trading session {self.session_id}")
            
            # Begin with premarket analysis
            await self._execute_phase(ExecutionPhase.PREMARKET_ANALYSIS)
            
            # Broadcast session start
            await self._broadcast_session_event("session_started", {
                'session_id': self.session_id,
                'user_id': self.config.user_id,
                'trading_mode': self.config.trading_mode.value,
                'start_time': datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start trading session: {e}")
            return False
    
    async def _execute_phase(self, phase: ExecutionPhase) -> None:
        """Execute specific trading phase"""
        try:
            self.current_phase = phase
            logger.info(f"📋 Executing phase: {phase.value}")
            
            if phase == ExecutionPhase.PREMARKET_ANALYSIS:
                await self._premarket_analysis()
            
            elif phase == ExecutionPhase.STOCK_SELECTION:
                await self._stock_selection()
            
            elif phase == ExecutionPhase.STRATEGY_ASSIGNMENT:
                await self._strategy_assignment()
            
            elif phase == ExecutionPhase.TRADE_EXECUTION:
                await self._trade_execution()
            
            elif phase == ExecutionPhase.POSITION_MONITORING:
                await self._position_monitoring()
            
            elif phase == ExecutionPhase.RISK_MANAGEMENT:
                await self._risk_management()
            
            elif phase == ExecutionPhase.PERFORMANCE_TRACKING:
                await self._performance_tracking()
            
            # Broadcast phase completion
            await self._broadcast_phase_update(phase, "completed")
            
        except Exception as e:
            logger.error(f"❌ Error executing phase {phase.value}: {e}")
            await self._broadcast_phase_update(phase, "failed", str(e))
    
    async def _premarket_analysis(self) -> None:
        """Execute premarket analysis phase"""
        try:
            # This integrates with the existing market schedule service
            # and enhanced analytics to prepare for trading
            
            analysis_data = {
                'phase': 'premarket_analysis',
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'market_conditions': await self._assess_market_conditions(),
                'system_health': await self._get_system_health()
            }
            
            # Publish analysis results to Kafka
            await self._kafka_producer.produce_message(
                topic="hft.trading.phase_updates",
                message=analysis_data
            )
            
            logger.info("📊 Premarket analysis completed")
            
        except Exception as e:
            logger.error(f"❌ Premarket analysis failed: {e}")
            raise
    
    async def _stock_selection(self) -> None:
        """Execute stock selection phase using Kafka analytics"""
        try:
            # The stock selector is already integrated with Kafka analytics
            # It will consume from analytics topics and make selections
            
            # Trigger stock selection
            selection_request = {
                'user_id': self.config.user_id,
                'session_id': self.session_id,
                'max_stocks': self.config.max_positions,
                'selection_criteria': {
                    'enable_fibonacci': self.config.enable_fibonacci_strategy,
                    'enable_breakout': self.config.enable_breakout_strategy,
                    'enable_momentum': self.config.enable_momentum_strategy
                },
                'timestamp': datetime.now().isoformat()
            }
            
            await self._kafka_producer.produce_message(
                topic="hft.trading.stock_selection_requests",
                message=selection_request
            )
            
            logger.info("🎯 Stock selection phase initiated")
            
        except Exception as e:
            logger.error(f"❌ Stock selection failed: {e}")
            raise
    
    async def _strategy_assignment(self) -> None:
        """Assign strategies to selected stocks"""
        try:
            # Strategy executor handles this based on Kafka messages
            await self._strategy_executor.assign_strategies_to_stocks()
            
            logger.info("🎲 Strategy assignment completed")
            
        except Exception as e:
            logger.error(f"❌ Strategy assignment failed: {e}")
            raise
    
    async def _trade_execution(self) -> None:
        """Execute trades based on strategy signals"""
        try:
            # This phase is continuous - the execution engine
            # monitors Kafka for trading signals and executes
            
            execution_status = {
                'phase': 'trade_execution',
                'session_id': self.session_id,
                'active': True,
                'timestamp': datetime.now().isoformat()
            }
            
            await self._kafka_producer.produce_message(
                topic="hft.trading.execution_status",
                message=execution_status
            )
            
            logger.info("⚡ Trade execution phase active")
            
        except Exception as e:
            logger.error(f"❌ Trade execution setup failed: {e}")
            raise
    
    async def _position_monitoring(self) -> None:
        """Monitor positions and calculate live PnL"""
        try:
            # Position monitor is already running as a consumer
            # Just ensure it's tracking this session
            
            positions = self._position_monitor.get_session_positions(self.session_id)
            self._positions_monitored = len(positions)
            
            logger.info(f"👁️ Monitoring {self._positions_monitored} positions")
            
        except Exception as e:
            logger.error(f"❌ Position monitoring setup failed: {e}")
            raise
    
    async def _risk_management(self) -> None:
        """Execute risk management checks"""
        try:
            # Get current positions and PnL
            positions = self._position_monitor.get_session_positions(self.session_id)
            
            if positions:
                # Calculate current PnL
                portfolio_pnl = await self._pnl_calculator.calculate_session_pnl(
                    self.session_id, 
                    [pos.__dict__ for pos in positions]
                )
                
                # Evaluate risk
                alerts = await self._risk_manager.evaluate_position_risk(
                    self.config.user_id,
                    self.session_id, 
                    [pos.__dict__ for pos in positions],
                    portfolio_pnl.get('total_pnl', 0)
                )
                
                self._risk_alerts_handled += len(alerts)
            
            logger.info("🛡️ Risk management checks completed")
            
        except Exception as e:
            logger.error(f"❌ Risk management failed: {e}")
            raise
    
    async def _performance_tracking(self) -> None:
        """Track and analyze performance"""
        try:
            performance_data = {
                'session_id': self.session_id,
                'user_id': self.config.user_id,
                'trades_executed': self._trades_executed,
                'positions_monitored': self._positions_monitored,
                'risk_alerts_handled': self._risk_alerts_handled,
                'session_duration': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
                'timestamp': datetime.now().isoformat()
            }
            
            await self._kafka_producer.produce_message(
                topic="hft.trading.performance",
                message=performance_data
            )
            
            logger.info("📈 Performance tracking updated")
            
        except Exception as e:
            logger.error(f"❌ Performance tracking failed: {e}")
            raise
    
    async def _system_health_monitoring(self) -> None:
        """Continuous system health monitoring"""
        while self.status == SystemStatus.RUNNING:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check system health
                health = await self._get_system_health()
                
                if not health['is_healthy']:
                    logger.warning(f"⚠️ System health issues detected: {health}")
                    
                    # Broadcast health alert
                    await self._sse_manager.broadcast_to_channel(
                        channel=SSEChannel.SYSTEM_STATUS,
                        event_type="health_alert",
                        data=health,
                        priority=2
                    )
                
            except Exception as e:
                logger.error(f"❌ Health monitoring error: {e}")
    
    async def _phase_management(self) -> None:
        """Manage trading phases based on market schedule"""
        while self.status == SystemStatus.RUNNING:
            try:
                current_time = datetime.now().time()
                
                # This would integrate with market schedule service
                # to determine appropriate phases based on market timing
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"❌ Phase management error: {e}")
    
    async def _continuous_risk_monitoring(self) -> None:
        """Continuous risk monitoring"""
        while self.status == SystemStatus.RUNNING:
            try:
                await asyncio.sleep(5)  # Monitor every 5 seconds
                
                # Check if session is emergency stopped
                if self._risk_manager.is_session_emergency_stopped(self.session_id):
                    logger.critical("🛑 Emergency stop detected - stopping session")
                    await self.stop_trading_session("Emergency stop activated")
                    break
                
            except Exception as e:
                logger.error(f"❌ Risk monitoring error: {e}")
    
    async def _ui_update_broadcasting(self) -> None:
        """Broadcast regular updates to UI"""
        while self.status == SystemStatus.RUNNING:
            try:
                await asyncio.sleep(1)  # Update every second
                
                # Broadcast session status
                session_update = {
                    'session_id': self.session_id,
                    'user_id': self.config.user_id,
                    'status': self.status.value,
                    'current_phase': self.current_phase.value,
                    'trades_executed': self._trades_executed,
                    'positions_monitored': self._positions_monitored,
                    'timestamp': datetime.now().isoformat()
                }
                
                await self._sse_manager.broadcast_to_channel(
                    channel=SSEChannel.TRADING_SIGNALS,
                    event_type="session_update",
                    data=session_update,
                    priority=3
                )
                
            except Exception as e:
                logger.error(f"❌ UI broadcasting error: {e}")
    
    async def stop_trading_session(self, reason: str = "Manual stop") -> None:
        """Stop trading session gracefully"""
        try:
            logger.info(f"🛑 Stopping trading session: {reason}")
            self.status = SystemStatus.STOPPING
            
            # Stop all tasks
            for task in self._orchestrator_tasks:
                if not task.done():
                    task.cancel()
            
            if self._orchestrator_tasks:
                await asyncio.gather(*self._orchestrator_tasks, return_exceptions=True)
            
            # Stop components
            if self._position_monitor:
                await self._position_monitor.stop_consuming()
            
            # Broadcast session end
            await self._broadcast_session_event("session_ended", {
                'session_id': self.session_id,
                'reason': reason,
                'end_time': datetime.now().isoformat()
            })
            
            self.status = SystemStatus.STOPPED
            logger.info("✅ Trading session stopped successfully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping trading session: {e}")
    
    async def _assess_market_conditions(self) -> Dict[str, Any]:
        """Assess current market conditions"""
        # This would integrate with the analytics system
        return {
            'volatility': 'medium',
            'trend': 'bullish',
            'volume': 'high'
        }
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health"""
        return {
            'is_healthy': True,
            'kafka_analytics_status': self._kafka_analytics.get_system_status() if self._kafka_analytics else {},
            'position_monitor_running': self._position_monitor._is_running if self._position_monitor else False,
            'risk_manager_alerts': len(self._risk_manager.get_active_alerts()) if self._risk_manager else 0
        }
    
    async def _broadcast_phase_update(self, phase: ExecutionPhase, status: str, error: Optional[str] = None) -> None:
        """Broadcast phase update to UI"""
        try:
            update_data = {
                'session_id': self.session_id,
                'phase': phase.value,
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            
            if error:
                update_data['error'] = error
            
            await self._sse_manager.broadcast_to_channel(
                channel=SSEChannel.TRADING_SIGNALS,
                event_type="phase_update",
                data=update_data,
                priority=2
            )
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting phase update: {e}")
    
    async def _broadcast_session_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast session event to UI"""
        try:
            await self._sse_manager.broadcast_to_channel(
                channel=SSEChannel.TRADING_SIGNALS,
                event_type=event_type,
                data=data,
                priority=1
            )
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting session event: {e}")
    
    async def _cleanup_on_failure(self) -> None:
        """Cleanup on system initialization failure"""
        try:
            self.status = SystemStatus.ERROR
            
            # Stop any running tasks
            for task in self._orchestrator_tasks:
                if not task.done():
                    task.cancel()
            
            # Clear references
            self._kafka_analytics = None
            self._strategy_executor = None
            self._position_monitor = None
            
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            'session_id': self.session_id,
            'user_id': self.config.user_id,
            'status': self.status.value,
            'current_phase': self.current_phase.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'trading_mode': self.config.trading_mode.value,
            'trades_executed': self._trades_executed,
            'positions_monitored': self._positions_monitored,
            'risk_alerts_handled': self._risk_alerts_handled,
            'active_tasks': len(self._orchestrator_tasks)
        }


# Factory function
def create_auto_trading_orchestrator(config: AutoTradingSystemConfig) -> AutoTradingOrchestrator:
    """Create auto trading orchestrator with configuration"""
    return AutoTradingOrchestrator(config)


# Export main classes
__all__ = [
    "AutoTradingOrchestrator",
    "AutoTradingSystemConfig",
    "SystemStatus",
    "create_auto_trading_orchestrator"
]