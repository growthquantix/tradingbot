"""
Kafka-Based Strategy Execution System

Comprehensive Kafka-integrated system that orchestrates the complete auto-trading
workflow from stock selection to trade execution, position monitoring, and PnL tracking.

Features:
- Live feed data consumption via Kafka
- Strategy-specific data routing and processing
- Real-time trade execution and monitoring
- Position management with live PnL updates
- Risk management and stop-loss automation
- Performance analytics and reporting
- UI-ready data streaming via SSE

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid

from services.hft.partition_strategy import get_enhanced_partition_manager, ServiceType
from services.hft.producer import get_hft_producer

from .modular_stock_selector import (
    get_modular_stock_selector,
    StockSelectionConfig,
    MarketCondition,
)
from .execution_engine import (
    get_auto_trade_execution_engine,
    TradeDirection,
    PositionStatus,
)

logger = logging.getLogger(__name__)


class ExecutionPhase(Enum):
    """Auto-trading execution phases"""

    PREMARKET_ANALYSIS = "premarket_analysis"
    STOCK_SELECTION = "stock_selection"
    STRATEGY_ASSIGNMENT = "strategy_assignment"
    TRADE_EXECUTION = "trade_execution"
    POSITION_MONITORING = "position_monitoring"
    RISK_MANAGEMENT = "risk_management"
    PERFORMANCE_TRACKING = "performance_tracking"


class AutoTradingMode(Enum):
    """Auto-trading operation modes"""

    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"
    SIMULATION = "simulation"
    BACKTESTING = "backtesting"


@dataclass
class TradingSession:
    """Auto-trading session state"""

    session_id: str
    user_id: int
    mode: AutoTradingMode
    start_time: datetime
    current_phase: ExecutionPhase = ExecutionPhase.PREMARKET_ANALYSIS

    # Configuration
    max_positions: int = 5
    max_risk_per_trade: float = 2.0
    daily_loss_limit: float = 5000.0

    # Session metrics
    total_trades: int = 0
    active_positions: int = 0
    daily_pnl: float = 0.0
    win_rate: float = 0.0

    # State tracking
    selected_stocks: List[Dict[str, Any]] = field(default_factory=list)
    active_strategies: Dict[str, str] = field(
        default_factory=dict
    )  # symbol -> strategy
    subscribed_instruments: Set[str] = field(default_factory=set)

    last_update: datetime = field(default_factory=datetime.now)
    is_active: bool = True


class KafkaStrategyExecutor:
    """
    Kafka-Based Strategy Execution Orchestrator

    Coordinates the complete auto-trading workflow:
    1. Consume live feed data via Kafka
    2. Route data to appropriate strategy processors
    3. Execute trades based on strategy signals
    4. Monitor positions with real-time updates
    5. Manage risk and stop-losses
    6. Stream PnL data to UI via SSE
    """

    def __init__(
        self,
        user_id: int,
        trading_mode: AutoTradingMode = AutoTradingMode.PAPER_TRADING,
    ):
        self.user_id = user_id
        self.trading_mode = trading_mode

        # Initialize core components
        self.partition_manager = get_enhanced_partition_manager()
        self.hft_producer = None  # Will be initialized async

        # Initialize trading components
        self.stock_selector = get_modular_stock_selector()
        self.execution_engine = get_auto_trade_execution_engine(user_id)

        # Session management
        self.current_session: Optional[TradingSession] = None
        self.session_history: List[TradingSession] = []

        # Kafka consumers for different data streams
        self.live_feed_consumer = None
        self.analytics_consumer = None
        self.strategy_consumers: Dict[str, Any] = {}

        # Data caches
        self.live_data_cache: Dict[str, Dict[str, Any]] = {}
        self.analytics_cache: Dict[str, Any] = {}
        self.position_cache: Dict[str, Dict[str, Any]] = {}

        # Performance tracking
        self.performance_tracker = {
            "session_start": None,
            "total_signals_generated": 0,
            "total_trades_executed": 0,
            "total_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_holding_time": 0.0,
        }

        logger.info(
            f"KafkaStrategyExecutor initialized for user {user_id} in {trading_mode.value} mode"
        )

    async def initialize_kafka_infrastructure(self) -> bool:
        """Initialize Kafka infrastructure and consumers"""
        try:
            # Initialize HFT producer
            self.hft_producer = await get_hft_producer()

            # Initialize consumers for different data streams
            await self._initialize_consumers()

            # Set up data routing
            await self._setup_data_routing()

            logger.info("Kafka infrastructure initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Kafka infrastructure initialization failed: {e}")
            return False

    async def _initialize_consumers(self) -> None:
        """Initialize Kafka consumers for different data streams"""
        try:
            from services.hft.consumers import get_consumer_for_service

            # Live feed consumer for real-time market data
            self.live_feed_consumer = await get_consumer_for_service(
                ServiceType.AUTO_TRADING,
                consumer_group=f"auto_trading_user_{self.user_id}",
            )

            # Analytics consumer for market analytics updates
            self.analytics_consumer = await get_consumer_for_service(
                ServiceType.MARKET_SENTIMENT,
                consumer_group=f"analytics_user_{self.user_id}",
            )

            logger.info("Kafka consumers initialized")

        except Exception as e:
            logger.error(f"Consumer initialization error: {e}")

    async def _setup_data_routing(self) -> None:
        """Set up data routing for selected instruments"""
        try:
            # This will be called after stock selection to route specific instruments
            # to the auto-trading partition for real-time processing
            pass

        except Exception as e:
            logger.error(f"Data routing setup error: {e}")

    async def start_trading_session(
        self, session_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new auto-trading session"""
        try:
            # Create new trading session
            session_id = f"SESSION_{uuid.uuid4().hex[:8]}"

            self.current_session = TradingSession(
                session_id=session_id,
                user_id=self.user_id,
                mode=self.trading_mode,
                start_time=datetime.now(),
                max_positions=(
                    session_config.get("max_positions", 5) if session_config else 5
                ),
                max_risk_per_trade=(
                    session_config.get("max_risk_per_trade", 2.0)
                    if session_config
                    else 2.0
                ),
                daily_loss_limit=(
                    session_config.get("daily_loss_limit", 5000.0)
                    if session_config
                    else 5000.0
                ),
            )

            # Initialize execution engine
            await self.execution_engine.initialize_trading_session()

            # Start the main execution loop
            asyncio.create_task(self._main_execution_loop())

            # Broadcast session start to UI
            await self._broadcast_session_update("SESSION_STARTED")

            logger.info(f"Trading session {session_id} started successfully")
            return session_id

        except Exception as e:
            logger.error(f"Trading session start error: {e}")
            raise

    async def _main_execution_loop(self) -> None:
        """Main execution loop that orchestrates the complete trading workflow"""
        try:
            while self.current_session and self.current_session.is_active:
                current_phase = self.current_session.current_phase

                if current_phase == ExecutionPhase.PREMARKET_ANALYSIS:
                    await self._execute_premarket_analysis()

                elif current_phase == ExecutionPhase.STOCK_SELECTION:
                    await self._execute_stock_selection()

                elif current_phase == ExecutionPhase.STRATEGY_ASSIGNMENT:
                    await self._execute_strategy_assignment()

                elif current_phase == ExecutionPhase.TRADE_EXECUTION:
                    await self._execute_trade_execution()

                elif current_phase == ExecutionPhase.POSITION_MONITORING:
                    await self._execute_position_monitoring()

                elif current_phase == ExecutionPhase.RISK_MANAGEMENT:
                    await self._execute_risk_management()

                elif current_phase == ExecutionPhase.PERFORMANCE_TRACKING:
                    await self._execute_performance_tracking()

                # Process live feed data continuously
                await self._process_live_feed_updates()

                # Update session metrics
                await self._update_session_metrics()

                # Brief pause to prevent excessive CPU usage
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Main execution loop error: {e}")
            await self._handle_execution_error(e)

    async def _execute_premarket_analysis(self) -> None:
        """Execute premarket analysis phase"""
        try:
            current_time = datetime.now().time()

            # Check if it's premarket time (9:00-9:15 AM)
            if not (
                datetime.strptime("09:00", "%H:%M").time()
                <= current_time
                <= datetime.strptime("09:15", "%H:%M").time()
            ):
                return

            logger.info("📊 Starting premarket analysis...")

            # Update analytics cache
            await self._update_analytics_cache()

            # Evaluate market conditions
            market_condition = await self._evaluate_market_conditions()

            # Broadcast market analysis to UI
            await self._broadcast_market_analysis(market_condition)

            # Move to stock selection phase
            self.current_session.current_phase = ExecutionPhase.STOCK_SELECTION

            logger.info(
                f"Premarket analysis completed. Market condition: {market_condition.value}"
            )

        except Exception as e:
            logger.error(f"Premarket analysis error: {e}")

    async def _execute_stock_selection(self) -> None:
        """Execute stock selection phase"""
        try:
            logger.info("🎯 Starting stock selection...")

            # Run modular stock selection
            selected_stocks = await self.stock_selector.select_stocks_for_trading()

            if selected_stocks:
                # Store selected stocks in session
                self.current_session.selected_stocks = [
                    {
                        "symbol": stock.symbol,
                        "instrument_key": stock.instrument_key,
                        "selection_score": stock.selection_score,
                        "expected_direction": stock.expected_direction,
                        "recommended_strategy": stock.primary_strategy,
                        "confidence_level": stock.confidence_level,
                        "position_size": stock.position_size,
                        "stop_loss": stock.stop_loss,
                        "target_price": stock.target_price,
                    }
                    for stock in selected_stocks
                ]

                # Subscribe to live feed for selected instruments
                for stock in selected_stocks:
                    await self._subscribe_to_instrument_feed(stock.instrument_key)
                    self.current_session.subscribed_instruments.add(
                        stock.instrument_key
                    )

                # Broadcast selections to UI
                await self._broadcast_stock_selections()

                # Move to strategy assignment phase
                self.current_session.current_phase = ExecutionPhase.STRATEGY_ASSIGNMENT

                logger.info(
                    f"Stock selection completed: {len(selected_stocks)} stocks selected"
                )
            else:
                logger.warning("No stocks selected, waiting for next cycle")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

        except Exception as e:
            logger.error(f"Stock selection error: {e}")

    async def _subscribe_to_instrument_feed(self, instrument_key: str) -> None:
        """Subscribe to live feed for specific instrument"""
        try:
            # Register instrument with partition manager for auto-trading routing
            # This would be enhanced with actual instrument metadata
            self.partition_manager.register_instrument(
                instrument_key=instrument_key,
                symbol=(
                    instrument_key.split("|")[-1]
                    if "|" in instrument_key
                    else instrument_key
                ),
                sector="OTHER",  # Would be resolved from instrument registry
                exchange="NSE",  # Would be parsed from instrument key
                instrument_type="EQ",  # Would be determined from key format
                market_cap_category="LARGE_CAP",  # Would be looked up
                average_volume=100000,  # Would be from historical data
            )

            logger.debug(f"Subscribed to live feed for {instrument_key}")

        except Exception as e:
            logger.error(f"Feed subscription error for {instrument_key}: {e}")

    async def _execute_strategy_assignment(self) -> None:
        """Execute strategy assignment phase"""
        try:
            logger.info("⚙️ Assigning strategies to selected stocks...")

            for stock_data in self.current_session.selected_stocks:
                symbol = stock_data["symbol"]
                recommended_strategy = stock_data["recommended_strategy"]

                # Assign strategy to symbol
                self.current_session.active_strategies[symbol] = recommended_strategy

            # Move to trade execution phase
            self.current_session.current_phase = ExecutionPhase.TRADE_EXECUTION

            logger.info("Strategy assignment completed")

        except Exception as e:
            logger.error(f"Strategy assignment error: {e}")

    async def _execute_trade_execution(self) -> None:
        """Execute trade execution phase"""
        try:
            logger.info("🚀 Starting trade execution...")

            # Convert selected stocks to trading signals
            trading_signals = await self.execution_engine.process_selected_stocks(
                [
                    self._convert_to_selection_result(stock)
                    for stock in self.current_session.selected_stocks
                ]
            )

            # Execute trading signals
            if trading_signals:
                executed_orders = await self.execution_engine.execute_trading_signals(
                    trading_signals
                )

                self.current_session.total_trades += len(executed_orders)
                self.performance_tracker["total_trades_executed"] += len(
                    executed_orders
                )

                # Broadcast trade executions to UI
                await self._broadcast_trade_executions(executed_orders)

                logger.info(
                    f"Trade execution completed: {len(executed_orders)} orders executed"
                )

            # Move to position monitoring phase
            self.current_session.current_phase = ExecutionPhase.POSITION_MONITORING

        except Exception as e:
            logger.error(f"Trade execution error: {e}")

    def _convert_to_selection_result(self, stock_data: Dict[str, Any]):
        """Convert stock data dict to SelectionResult for engine compatibility"""
        # This is a helper method to maintain compatibility
        # In practice, we'd use the actual SelectionResult objects
        from .modular_stock_selector import SelectionResult, MarketCondition

        class MockSelectionResult:
            def __init__(self, data):
                self.symbol = data["symbol"]
                self.instrument_key = data["instrument_key"]
                self.selection_score = data["selection_score"]
                self.expected_direction = data["expected_direction"]
                self.primary_strategy = data["recommended_strategy"]
                self.confidence_level = data["confidence_level"]
                self.position_size = data["position_size"]
                self.stop_loss = data["stop_loss"]
                self.target_price = data["target_price"]
                self.current_price = 100.0  # Would be from live feed
                self.market_condition = MarketCondition.NEUTRAL
                self.selection_reasons = []
                self.risk_reward_ratio = 1.5

        return MockSelectionResult(stock_data)

    async def _execute_position_monitoring(self) -> None:
        """Execute position monitoring phase"""
        try:
            # Get active positions from execution engine
            active_positions = self.execution_engine.get_active_positions_summary()

            if active_positions:
                self.current_session.active_positions = len(active_positions)

                # Update position cache for UI streaming
                for position in active_positions:
                    self.position_cache[position["position_id"]] = position

                # Broadcast position updates to UI
                await self._broadcast_position_updates(active_positions)

                # Continue monitoring
                await asyncio.sleep(1)  # Check positions every second
            else:
                # No active positions, move to performance tracking
                self.current_session.current_phase = ExecutionPhase.PERFORMANCE_TRACKING

        except Exception as e:
            logger.error(f"Position monitoring error: {e}")

    async def _execute_risk_management(self) -> None:
        """Execute risk management phase"""
        try:
            # Get current performance metrics
            performance = self.execution_engine.get_trading_performance()

            daily_pnl = performance["daily_summary"]["daily_pnl"]
            self.current_session.daily_pnl = daily_pnl

            # Check daily loss limit
            if daily_pnl <= -self.current_session.daily_loss_limit:
                logger.warning(f"Daily loss limit reached: ₹{daily_pnl:.2f}")
                await self._emergency_stop_trading("DAILY_LOSS_LIMIT")
                return

            # Check other risk parameters
            capital_utilization = performance["capital_summary"][
                "capital_utilization_percent"
            ]
            if capital_utilization > 90:
                logger.warning(f"High capital utilization: {capital_utilization:.1f}%")

            # Continue with normal monitoring
            self.current_session.current_phase = ExecutionPhase.POSITION_MONITORING

        except Exception as e:
            logger.error(f"Risk management error: {e}")

    async def _execute_performance_tracking(self) -> None:
        """Execute performance tracking phase"""
        try:
            # Update performance metrics
            performance = self.execution_engine.get_trading_performance()

            self.current_session.daily_pnl = performance["daily_summary"]["daily_pnl"]
            self.current_session.win_rate = performance["performance_metrics"][
                "win_rate"
            ]

            # Broadcast performance update to UI
            await self._broadcast_performance_update(performance)

            # Check if market is still open for more trades
            current_time = datetime.now().time()
            market_close = datetime.strptime("15:30", "%H:%M").time()

            if current_time >= market_close:
                # Market closed, end session
                await self._end_trading_session("MARKET_CLOSE")
            else:
                # Continue monitoring positions if any are active
                if self.current_session.active_positions > 0:
                    self.current_session.current_phase = (
                        ExecutionPhase.POSITION_MONITORING
                    )
                else:
                    # Wait for next opportunity
                    await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Performance tracking error: {e}")

    async def _process_live_feed_updates(self) -> None:
        """Process live feed data updates"""
        try:
            # This would consume from Kafka live feed topic
            # For now, we'll simulate with cached data processing

            if hasattr(self.execution_engine, "process_live_feed_update"):
                # Process any cached live feed data
                for instrument_key, feed_data in self.live_data_cache.items():
                    if instrument_key in self.current_session.subscribed_instruments:
                        await self.execution_engine.process_live_feed_update(
                            {"feeds": {instrument_key: feed_data}}
                        )

        except Exception as e:
            logger.error(f"Live feed processing error: {e}")

    async def _update_analytics_cache(self) -> None:
        """Update analytics data cache"""
        try:
            # This would consume from analytics Kafka topics
            # Update various analytics caches for decision making
            pass

        except Exception as e:
            logger.error(f"Analytics cache update error: {e}")

    async def _evaluate_market_conditions(self):
        """Evaluate current market conditions"""
        try:
            # Use stock selector's market condition evaluation
            return await self.stock_selector._evaluate_market_conditions()

        except Exception as e:
            logger.error(f"Market condition evaluation error: {e}")
            from .modular_stock_selector import MarketCondition

            return MarketCondition.NEUTRAL

    async def _update_session_metrics(self) -> None:
        """Update session metrics"""
        try:
            if self.current_session:
                self.current_session.last_update = datetime.now()

                # Update from execution engine
                performance = self.execution_engine.get_trading_performance()
                self.current_session.daily_pnl = performance["daily_summary"][
                    "daily_pnl"
                ]
                self.current_session.active_positions = performance["daily_summary"][
                    "active_positions"
                ]

                if performance["performance_metrics"]["total_trades"] > 0:
                    self.current_session.win_rate = performance["performance_metrics"][
                        "win_rate"
                    ]

        except Exception as e:
            logger.error(f"Session metrics update error: {e}")

    # UI Broadcasting methods
    async def _broadcast_session_update(self, event_type: str) -> None:
        """Broadcast session update to UI"""
        try:
            session_data = {
                "event_type": event_type,
                "session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
                "user_id": self.user_id,
                "mode": self.trading_mode.value,
                "phase": (
                    self.current_session.current_phase.value
                    if self.current_session
                    else None
                ),
                "timestamp": datetime.now().isoformat(),
            }

            await self.sse_manager.broadcast_to_channel(
                event_type=event_type.lower(), data=session_data
            )

        except Exception as e:
            logger.error(f"Session update broadcast error: {e}")

    async def _broadcast_market_analysis(self, market_condition) -> None:
        """Broadcast market analysis to UI"""
        try:
            analysis_data = {
                "market_condition": market_condition.value,
                "analysis_time": datetime.now().isoformat(),
                "user_id": self.user_id,
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="market_analysis_update", data=analysis_data
            )

        except Exception as e:
            logger.error(f"Market analysis broadcast error: {e}")

    async def _broadcast_stock_selections(self) -> None:
        """Broadcast stock selections to UI"""
        try:
            selections_data = {
                "selected_stocks": self.current_session.selected_stocks,
                "selection_time": datetime.now().isoformat(),
                "user_id": self.user_id,
                "total_selected": len(self.current_session.selected_stocks),
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="stock_selections_update", data=selections_data
            )

        except Exception as e:
            logger.error(f"Stock selections broadcast error: {e}")

    async def _broadcast_trade_executions(self, executed_orders) -> None:
        """Broadcast trade executions to UI"""
        try:
            executions_data = {
                "executed_orders": [
                    {
                        "symbol": order.symbol,
                        "direction": order.direction.value,
                        "quantity": order.quantity,
                        "price": order.avg_fill_price,
                        "strategy": order.strategy.value,
                        "order_id": order.order_id,
                    }
                    for order in executed_orders
                ],
                "execution_time": datetime.now().isoformat(),
                "user_id": self.user_id,
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="trade_executions_update", data=executions_data
            )

        except Exception as e:
            logger.error(f"Trade executions broadcast error: {e}")

    async def _broadcast_position_updates(self, active_positions) -> None:
        """Broadcast position updates to UI"""
        try:
            positions_data = {
                "active_positions": active_positions,
                "update_time": datetime.now().isoformat(),
                "user_id": self.user_id,
                "total_positions": len(active_positions),
                "total_unrealized_pnl": sum(
                    pos["unrealized_pnl"] for pos in active_positions
                ),
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="positions_update", data=positions_data
            )

        except Exception as e:
            logger.error(f"Position updates broadcast error: {e}")

    async def _broadcast_performance_update(self, performance) -> None:
        """Broadcast performance update to UI"""
        try:
            performance_data = {
                "performance_metrics": performance,
                "session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
                "update_time": datetime.now().isoformat(),
                "user_id": self.user_id,
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="performance_update", data=performance_data
            )

        except Exception as e:
            logger.error(f"Performance update broadcast error: {e}")

    async def _emergency_stop_trading(self, reason: str) -> None:
        """Emergency stop all trading activities"""
        try:
            logger.critical(f"🛑 EMERGENCY STOP: {reason}")

            if self.current_session:
                self.current_session.is_active = False

            # Broadcast emergency stop to UI
            emergency_data = {
                "reason": reason,
                "stop_time": datetime.now().isoformat(),
                "user_id": self.user_id,
                "session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="emergency_stop", data=emergency_data
            )

        except Exception as e:
            logger.error(f"Emergency stop error: {e}")

    async def _end_trading_session(self, reason: str) -> None:
        """End current trading session"""
        try:
            if self.current_session:
                self.current_session.is_active = False
                self.session_history.append(self.current_session)

                # Final performance summary
                final_performance = self.execution_engine.get_trading_performance()

                # Broadcast session end
                session_end_data = {
                    "reason": reason,
                    "session_id": self.current_session.session_id,
                    "final_pnl": final_performance["daily_summary"]["daily_pnl"],
                    "total_trades": final_performance["daily_summary"][
                        "completed_trades_today"
                    ],
                    "win_rate": final_performance["performance_metrics"]["win_rate"],
                    "end_time": datetime.now().isoformat(),
                    "user_id": self.user_id,
                }

                await self.sse_manager.broadcast_to_channel(
                    event_type="session_ended", data=session_end_data
                )

                self.current_session = None
                logger.info(f"Trading session ended: {reason}")

        except Exception as e:
            logger.error(f"Session end error: {e}")

    async def _handle_execution_error(self, error: Exception) -> None:
        """Handle execution errors gracefully"""
        try:
            logger.error(f"Execution error: {error}")

            # Broadcast error to UI
            error_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now().isoformat(),
                "user_id": self.user_id,
                "session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
            }

            await self.sse_manager.broadcast_to_channel(
                event_type="execution_error", data=error_data
            )

        except Exception as e:
            logger.error(f"Error handling error: {e}")

    def get_session_status(self) -> Dict[str, Any]:
        """Get current session status"""
        if not self.current_session:
            return {"status": "NO_ACTIVE_SESSION"}

        return {
            "status": "ACTIVE" if self.current_session.is_active else "INACTIVE",
            "session_id": self.current_session.session_id,
            "current_phase": self.current_session.current_phase.value,
            "selected_stocks_count": len(self.current_session.selected_stocks),
            "active_positions": self.current_session.active_positions,
            "daily_pnl": self.current_session.daily_pnl,
            "total_trades": self.current_session.total_trades,
            "session_duration_minutes": (
                datetime.now() - self.current_session.start_time
            ).total_seconds()
            / 60,
        }

    async def stop_trading_session(self) -> bool:
        """Manually stop current trading session"""
        try:
            if self.current_session and self.current_session.is_active:
                await self._end_trading_session("MANUAL_STOP")
                return True
            return False

        except Exception as e:
            logger.error(f"Manual session stop error: {e}")
            return False


# Singleton instance
_kafka_strategy_executor: Optional[KafkaStrategyExecutor] = None


def get_kafka_strategy_executor(
    user_id: int, trading_mode: AutoTradingMode = AutoTradingMode.PAPER_TRADING
) -> KafkaStrategyExecutor:
    """Get Kafka strategy executor instance"""
    global _kafka_strategy_executor
    if _kafka_strategy_executor is None:
        _kafka_strategy_executor = KafkaStrategyExecutor(user_id, trading_mode)
    return _kafka_strategy_executor


# Export main classes
__all__ = [
    "KafkaStrategyExecutor",
    "TradingSession",
    "ExecutionPhase",
    "AutoTradingMode",
    "get_kafka_strategy_executor",
]
