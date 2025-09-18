"""
Auto-Trading Coordinator Service
Main orchestrator for the complete auto-trading system
Integrates all components: Strategy, Execution, Risk Management, Monitoring
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
from contextlib import asynccontextmanager

from services.strategies.fibonacci_ema_strategy import FibonacciEMAStrategy, FibonacciSignal
from services.strategies.dynamic_risk_reward import DynamicRiskReward
from services.strategies.nifty_09_40_integration import get_nifty_strategy_integration, initialize_nifty_strategy
from services.execution.real_time_execution_engine import RealTimeExecutionEngine
from services.execution.broker_integration_manager import BrokerIntegrationManager, BrokerType
from services.execution.position_monitor import PositionMonitor
from services.execution.order_management_system import OrderManagementSystem
from services.unified_trading_executor import unified_trading_executor, UnifiedTradeSignal, TradingMode
from services.auto_stock_selection_service import AutoStockSelectionService
from services.auto_trading_data_service import AutoTradingDataService
from services.database.trading_db_service import TradingDatabaseService
from services.centralized_ws_manager import CentralizedWebSocketManager
from services.margin_aware_trading_service import MarginAwareTradingService
from services.broker_funds_sync_service import broker_funds_sync_service
from database.connection import SessionLocal

logger = logging.getLogger(__name__)

class TradingSystemState(Enum):
    INACTIVE = "INACTIVE"
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SHUTTING_DOWN = "SHUTTING_DOWN"

class SystemMode(Enum):
    PAPER_TRADING = "PAPER_TRADING"
    LIVE_TRADING = "LIVE_TRADING"
    BACKTEST = "BACKTEST"

@dataclass
class TradingSession:
    """Trading session configuration and state"""
    session_id: str
    user_id: int
    mode: SystemMode
    selected_stocks: List[Dict[str, Any]]
    risk_parameters: Dict[str, Any]
    strategy_config: Dict[str, Any]
    max_positions: int = 5
    max_daily_loss: float = 50000.0
    session_start_time: datetime = None
    session_end_time: Optional[datetime] = None
    total_pnl: float = 0.0
    trades_count: int = 0
    
    # Enhanced margin management fields
    margin_utilization_limit: float = 0.8  # 80% max utilization
    risk_per_trade: float = 0.02  # 2% risk per trade
    margin_buffer: float = 0.1  # 10% safety buffer
    auto_margin_sync: bool = True  # Auto sync margin data
    position_sizing_mode: str = "margin_based"  # margin_based, fixed, risk_based

@dataclass
class SystemHealth:
    """System health monitoring"""
    overall_status: str = "HEALTHY"
    data_feed_status: str = "CONNECTED"
    broker_status: str = "CONNECTED"
    strategy_status: str = "ACTIVE"
    execution_status: str = "ACTIVE"
    database_status: str = "CONNECTED"
    last_health_check: datetime = None
    error_count_24h: int = 0
    uptime_seconds: int = 0

class AutoTradingCoordinator:
    """
    Main Auto-Trading System Coordinator
    
    Orchestrates the complete auto-trading workflow:
    1. Market data ingestion and processing
    2. F&O stock selection and filtering
    3. Fibonacci + EMA strategy signal generation
    4. Risk management and position sizing
    5. Order execution and management
    6. Real-time position monitoring
    7. Performance tracking and reporting
    8. Emergency controls and kill switch
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.system_state = TradingSystemState.INACTIVE
        self.system_health = SystemHealth()
        self.start_time = datetime.now(timezone.utc)
        
        # Core services - will be initialized later
        self.db_service: Optional[TradingDatabaseService] = None
        self.ws_manager: Optional[CentralizedWebSocketManager] = None
        self.data_service: Optional[AutoTradingDataService] = None
        self.stock_selection_service: Optional[AutoStockSelectionService] = None
        self.fibonacci_strategy: Optional[FibonacciEMAStrategy] = None
        self.risk_manager: Optional[DynamicRiskReward] = None
        self.broker_manager: Optional[BrokerIntegrationManager] = None
        self.execution_engine: Optional[RealTimeExecutionEngine] = None
        self.position_monitor: Optional[PositionMonitor] = None
        self.order_manager: Optional[OrderManagementSystem] = None
        
        # Enhanced margin-aware services
        self.margin_service: Optional[MarginAwareTradingService] = None
        self.margin_sync_interval = 300  # 5 minutes
        self.last_margin_sync = None
        
        # Session management
        self.active_sessions: Dict[str, TradingSession] = {}
        self.system_metrics = {
            'total_trades_today': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_pnl_today': 0.0,
            'active_positions': 0,
            'signals_generated': 0,
            'signals_executed': 0,
            'avg_execution_time_ms': 0.0,
            'uptime_percentage': 100.0
        }
        
        # Control flags
        self.emergency_stop_active = False
        self.daily_loss_limit_hit = False
        self.max_positions_reached = False
        
        # Callbacks for UI updates
        self.status_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        logger.info("Auto-Trading Coordinator initialized")
    
    async def initialize_system(self) -> bool:
        """Initialize all system components"""
        try:
            self.system_state = TradingSystemState.INITIALIZING
            logger.info("Initializing Auto-Trading System...")
            
            # Initialize database service
            self.db_service = TradingDatabaseService()
            if hasattr(self.db_service, 'initialize'):
                await self.db_service.initialize()
            else:
                logger.info("✅ Database service ready (no initialization method needed)")
            
            # Initialize WebSocket manager
            self.ws_manager = CentralizedWebSocketManager()
            await self.ws_manager.initialize()
            
            # Initialize data processing service with error handling
            try:
                self.data_service = AutoTradingDataService()
                data_service_initialized = await self.data_service.initialize()
                
                if data_service_initialized:
                    # Start the data service for live data processing
                    await self.data_service.start_service()
                    logger.info("✅ Data processing service started successfully")
                else:
                    logger.error("❌ Data service initialization failed")
                    raise RuntimeError("Data service initialization failed")
                    
            except Exception as e:
                logger.error(f"❌ Critical error initializing data service: {e}")
                # Don't fail the entire system, but log the issue
                self.data_service = None
            
            # Initialize stock selection service
            self.stock_selection_service = AutoStockSelectionService(self.db_service)
            
            # Initialize strategy components
            self.fibonacci_strategy = FibonacciEMAStrategy()
            self.risk_manager = DynamicRiskReward()
            
            # Initialize NIFTY 09:40 strategy (with error handling)
            try:
                from services.strategies.nifty_09_40_integration import get_nifty_strategy_integration, initialize_nifty_strategy
                self.nifty_strategy = await get_nifty_strategy_integration()
                logger.info("✅ NIFTY 09:40 strategy initialized")
            except ImportError as e:
                logger.warning(f"⚠️ NIFTY 09:40 strategy not available: {e}")
                self.nifty_strategy = None
            
            # Initialize broker integration
            self.broker_manager = BrokerIntegrationManager()
            await self._setup_brokers()
            
            # Initialize position monitor
            self.position_monitor = PositionMonitor(self.db_service, self.ws_manager)
            await self.position_monitor.start_monitoring()
            
            # Initialize order management system
            self.order_manager = OrderManagementSystem(
                self.broker_manager, 
                self.db_service, 
                self.position_monitor
            )
            await self.order_manager.start_system()
            
            # Initialize execution engine
            self.execution_engine = RealTimeExecutionEngine(
                self.db_service,
                self.ws_manager,
                self.fibonacci_strategy,
                self.risk_manager
            )
            await self.execution_engine.start_execution_engine()
            
            # Initialize margin-aware trading service with proper connection management
            self.margin_service = None  # Will be initialized with proper DB sessions when needed
            
            # Start margin sync service if not already running
            if not broker_funds_sync_service.is_running:
                asyncio.create_task(broker_funds_sync_service.start_background_sync())
            
            # Setup event callbacks
            await self._setup_callbacks()
            
            # Start system monitoring
            asyncio.create_task(self._system_health_monitor())
            asyncio.create_task(self._market_data_processor())
            asyncio.create_task(self._signal_generator())
            asyncio.create_task(self._performance_tracker())
            asyncio.create_task(self._margin_monitoring_loop())  # New margin monitoring
            
            self.system_state = TradingSystemState.ACTIVE
            logger.info("Auto-Trading System initialized successfully")
            
            await self._notify_system_status("SYSTEM_INITIALIZED")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Auto-Trading System: {e}")
            self.system_state = TradingSystemState.INACTIVE
            await self._notify_error("INITIALIZATION_FAILED", str(e))
            return False
    
    async def _setup_brokers(self):
        """Setup broker connections"""
        try:
            # Add configured brokers
            broker_configs = self.config.get('brokers', {})
            
            for broker_name, credentials in broker_configs.items():
                if broker_name.upper() == 'UPSTOX':
                    await self.broker_manager.add_broker(BrokerType.UPSTOX, credentials)
                elif broker_name.upper() == 'ANGEL_ONE':
                    await self.broker_manager.add_broker(BrokerType.ANGEL_ONE, credentials)
                # Add more brokers as needed
            
            logger.info("Broker connections established")
            
        except Exception as e:
            logger.error(f"Failed to setup brokers: {e}")
            raise
    
    async def _setup_callbacks(self):
        """Setup inter-service callbacks"""
        try:
            # Position monitor callbacks
            self.position_monitor.add_position_callback(self._handle_position_update)
            self.position_monitor.add_risk_callback(self._handle_risk_limit_breach)
            
            # Order manager callbacks
            self.order_manager.add_order_callback(self._handle_order_event)
            
            # Data service callbacks (if available)
            if self.data_service:
                await self.data_service.register_fibonacci_callback(
                    "MAIN_STRATEGY", 
                    self._handle_fibonacci_signal
                )
            
            logger.info("Inter-service callbacks configured")
            
        except Exception as e:
            logger.error(f"Failed to setup callbacks: {e}")
            raise
    
    async def start_trading_session(self, session_config: Dict[str, Any]) -> str:
        """Start a new trading session"""
        try:
            session_id = f"SESSION_{int(time.time() * 1000)}"
            
            # Validate session config
            if not self._validate_session_config(session_config):
                raise ValueError("Invalid session configuration")
            
            # Create trading session
            session = TradingSession(
                session_id=session_id,
                user_id=session_config['user_id'],
                mode=SystemMode(session_config.get('mode', 'PAPER_TRADING')),
                selected_stocks=session_config.get('selected_stocks', []),
                risk_parameters=session_config.get('risk_parameters', {}),
                strategy_config=session_config.get('strategy_config', {}),
                max_positions=session_config.get('max_positions', 5),
                max_daily_loss=session_config.get('max_daily_loss', 50000.0),
                session_start_time=datetime.now(timezone.utc)
            )
            
            self.active_sessions[session_id] = session
            
            # Initialize session-specific components
            await self._initialize_session_components(session)
            
            # Start stock selection if not provided
            if not session.selected_stocks:
                session.selected_stocks = await self._select_trading_stocks(session)
            
            # Subscribe to market data for selected stocks
            await self._subscribe_to_market_data(session.selected_stocks)
            
            logger.info(f"Trading session started: {session_id} with {len(session.selected_stocks)} stocks")
            
            await self._notify_session_event("SESSION_STARTED", session_id)
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start trading session: {e}")
            await self._notify_error("SESSION_START_FAILED", str(e))
            raise
    
    async def _select_trading_stocks(self, session: TradingSession) -> List[Dict[str, Any]]:
        """Select F&O stocks for trading based on Fibonacci strategy suitability"""
        try:
            # Get F&O stock universe
            fno_stocks = await self.stock_selection_service.get_fno_stocks_from_indices()
            
            # Score stocks for Fibonacci strategy
            scored_stocks = await self.stock_selection_service.score_fno_stocks_for_fibonacci_strategy(fno_stocks)
            
            # Select top stocks
            max_stocks = session.strategy_config.get('max_stocks', 20)
            selected = scored_stocks[:max_stocks]
            
            logger.info(f"Selected {len(selected)} stocks for trading")
            return selected
            
        except Exception as e:
            logger.error(f"Error selecting trading stocks: {e}")
            return []
    
    async def _subscribe_to_market_data(self, selected_stocks: List[Dict[str, Any]]):
        """Subscribe to real-time market data for selected stocks"""
        try:
            instrument_keys = [stock['instrument_key'] for stock in selected_stocks]
            
            # Primary: Subscribe to Live Feed Manager for ZERO-DELAY access
            try:
                from services.live_feed_manager import subscribe_to_live_feed
                
                success = await subscribe_to_live_feed(
                    service_name="auto_trading_coordinator",
                    callback=self._process_live_market_data,
                    instrument_keys=instrument_keys,
                    priority=1,  # Highest priority for trading
                    filter_func=self._filter_trading_data
                )
                
                if success:
                    logger.info(f"✅ Subscribed to {len(instrument_keys)} instruments via Live Feed Manager (ZERO-DELAY)")
                else:
                    logger.warning("⚠️ Failed to subscribe to Live Feed Manager")
                    
            except ImportError as e:
                logger.warning(f"❌ Live Feed Manager not available: {e}")
            
            # Fallback: Add instruments to data service for processing (if available)
            if self.data_service:
                self.data_service.add_instruments(instrument_keys, priority=True)
                logger.info(f"✅ Fallback: Added {len(instrument_keys)} instruments to data service")
            else:
                logger.warning("⚠️ Data service not available, skipping instrument registration")
            
            # Priority subscription for selected stocks via WebSocket manager
            if self.ws_manager:
                await self.ws_manager.priority_subscription(selected_stocks)
                logger.info(f"✅ Subscribed to WebSocket data for {len(instrument_keys)} instruments")
            else:
                logger.warning("⚠️ WebSocket manager not available")
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to market data: {e}")
    
    def _filter_trading_data(self, live_data) -> bool:
        """Filter function for trading-relevant market data"""
        try:
            # Only process during active trading hours
            if self.system_state not in [TradingSystemState.ACTIVE]:
                return False
            
            # Filter by minimum volume threshold
            if live_data.volume < 1000:
                return False
            
            # Filter by minimum price movement for efficiency
            if abs(live_data.change_percent) < 0.1:  # 0.1% threshold
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in trading data filter: {e}")
            return False
    
    async def _process_live_market_data(self, live_data):
        """Process live market data for trading decisions"""
        try:
            # Update current prices cache
            if not hasattr(self.current_session, 'current_prices'):
                self.current_session.current_prices = {}
                
            self.current_session.current_prices[live_data.instrument_key] = {
                'ltp': float(live_data.ltp),
                'change_percent': float(live_data.change_percent),
                'volume': live_data.volume,
                'timestamp': live_data.timestamp
            }
            
            # Process for strategy signals
            await self._analyze_trading_signal(live_data)
            
            # Update position monitoring
            if hasattr(self, 'position_monitor') and self.position_monitor:
                await self.position_monitor.update_live_price(
                    live_data.instrument_key,
                    float(live_data.ltp)
                )
            
            # Update risk monitoring
            await self._update_risk_metrics(live_data)
            
        except Exception as e:
            logger.error(f"❌ Error processing live market data: {e}")
    
    async def _analyze_trading_signal(self, live_data):
        """Analyze live data for trading signals"""
        try:
            # Check if we have an active strategy for this instrument
            if not hasattr(self, 'active_strategies'):
                return
            
            # Process through Fibonacci + EMA strategy
            if hasattr(self, 'fibonacci_strategy') and self.fibonacci_strategy:
                try:
                    # Convert live data to strategy format
                    price_data = {
                        'instrument_key': live_data.instrument_key,
                        'symbol': live_data.symbol,
                        'ltp': float(live_data.ltp),
                        'volume': live_data.volume,
                        'change_percent': float(live_data.change_percent),
                        'timestamp': live_data.timestamp
                    }
                    
                    # Generate signal
                    signal = await self.fibonacci_strategy.generate_signal(price_data)
                    
                    if signal and hasattr(signal, 'action') and signal.action in ['BUY', 'SELL']:
                        logger.info(f"🎯 Trading signal generated: {signal.action} {live_data.symbol} at {live_data.ltp}")
                        await self._execute_trading_signal(signal, live_data)
                        
                except Exception as e:
                    logger.error(f"❌ Error in strategy signal generation: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error analyzing trading signal: {e}")
    
    async def _execute_trading_signal(self, signal, live_data):
        """Execute trading signal with risk management"""
        try:
            # Check if we can place new trades
            if not self._can_place_new_trade():
                logger.warning(f"⚠️ Cannot place new trade - limits reached")
                return
            
            # Execute via unified trading executor
            if hasattr(self, 'unified_executor') and self.unified_executor:
                try:
                    result = await self.unified_executor.execute_trade_signal(
                        signal=signal,
                        live_data=live_data,
                        risk_parameters=self.current_session.risk_parameters
                    )
                    
                    if result and result.get('success'):
                        logger.info(f"✅ Trade executed: {result.get('order_id')} for {live_data.symbol}")
                        self.current_session.trades_count += 1
                    else:
                        logger.warning(f"⚠️ Trade execution failed: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"❌ Error in unified executor: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error executing trading signal: {e}")
    
    async def _update_risk_metrics(self, live_data):
        """Update risk metrics based on live data"""
        try:
            # Update current P&L if we have positions
            if hasattr(self, 'current_positions') and self.current_positions:
                for position in self.current_positions:
                    if position.get('instrument_key') == live_data.instrument_key:
                        # Calculate unrealized P&L
                        entry_price = position.get('entry_price', 0)
                        current_price = float(live_data.ltp)
                        quantity = position.get('quantity', 0)
                        
                        if entry_price > 0 and quantity != 0:
                            unrealized_pnl = (current_price - entry_price) * quantity
                            position['unrealized_pnl'] = unrealized_pnl
                            position['current_price'] = current_price
            
        except Exception as e:
            logger.error(f"❌ Error updating risk metrics: {e}")
    
    def _can_place_new_trade(self) -> bool:
        """Check if we can place a new trade based on limits"""
        try:
            # Check position count limit
            current_positions = len(getattr(self, 'current_positions', []))
            if current_positions >= self.current_session.max_positions:
                return False
            
            # Check daily loss limit
            if abs(self.current_session.total_pnl) >= self.current_session.max_daily_loss:
                return False
            
            # Check if system is active
            if self.system_state != TradingSystemState.ACTIVE:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking trade limits: {e}")
            return False
    
    async def _market_data_processor(self):
        """Main market data processing loop"""
        while self.system_state in [TradingSystemState.ACTIVE, TradingSystemState.PAUSED]:
            try:
                if self.system_state == TradingSystemState.PAUSED:
                    await asyncio.sleep(1.0)
                    continue
                
                # Process incoming market data (if data service available)
                if self.data_service:
                    await self.data_service.process_market_data_batch()
                else:
                    # No data service available, sleep longer
                    await asyncio.sleep(1.0)
                
                await asyncio.sleep(0.1)  # 100ms processing cycle
                
            except Exception as e:
                logger.error(f"Error in market data processing: {e}")
                await asyncio.sleep(1.0)
    
    async def _signal_generator(self):
        """Main signal generation loop"""
        while self.system_state in [TradingSystemState.ACTIVE, TradingSystemState.PAUSED]:
            try:
                if self.system_state == TradingSystemState.PAUSED:
                    await asyncio.sleep(1.0)
                    continue
                
                # Generate signals for all active sessions
                for session in self.active_sessions.values():
                    await self._generate_session_signals(session)
                
                await asyncio.sleep(5.0)  # 5-second signal generation cycle
                
            except Exception as e:
                logger.error(f"Error in signal generation: {e}")
                await asyncio.sleep(10.0)
    
    async def _generate_session_signals(self, session: TradingSession):
        """Generate trading signals for a session"""
        try:
            if self.emergency_stop_active or self.daily_loss_limit_hit:
                return
            
            for stock in session.selected_stocks:
                symbol = stock['symbol']
                instrument_key = stock['instrument_key']
                
                # Skip if data service not available
                if not self.data_service:
                    continue
                
                # Get current market data
                current_price = await self.data_service.get_current_price(instrument_key)
                if not current_price:
                    logger.debug(f"No current price for {symbol}")
                    continue
                
                # Get OHLC data for strategy
                ohlc_1m = await self.data_service.get_ohlc_data(instrument_key, '1m', 100)
                ohlc_5m = await self.data_service.get_ohlc_data(instrument_key, '5m', 50)
                
                if ohlc_1m.empty or ohlc_5m.empty:
                    logger.debug(f"Insufficient OHLC data for {symbol}")
                    continue
                
                # Extract LTP from current price data
                current_ltp = current_price.get('ltp', current_price.get('last_price', 0.0))
                
                # Generate Fibonacci signal
                signal = await self.fibonacci_strategy.generate_signal(
                    ohlc_1m, ohlc_5m, current_ltp, symbol
                )
                
                if signal and signal.strength >= 70:  # High-confidence signals only
                    self.system_metrics['signals_generated'] += 1
                    
                    # Check if we can execute the signal
                    if await self._can_execute_signal(session, signal):
                        await self._execute_fibonacci_signal(session, signal, symbol, current_ltp)
                
        except Exception as e:
            logger.error(f"Error generating session signals: {e}")
    
    async def _can_execute_signal(self, session: TradingSession, signal: FibonacciSignal) -> bool:
        """Check if signal can be executed based on risk limits"""
        # Check max positions limit
        active_positions = len([pos for pos in self.position_monitor.positions.values() 
                              if pos.status.value == 'ACTIVE'])
        
        if active_positions >= session.max_positions:
            return False
        
        # Check daily loss limit
        if abs(session.total_pnl) >= session.max_daily_loss and session.total_pnl < 0:
            return False
        
        # Check emergency stop
        if self.emergency_stop_active:
            return False
        
        return True
    
    async def _execute_fibonacci_signal(self, session: TradingSession, signal: FibonacciSignal, 
                                      symbol: str, current_price: float):
        """Execute Fibonacci trading signal using unified executor"""
        try:
            # Determine trading mode based on session
            trading_mode = TradingMode.PAPER if session.mode == SystemMode.PAPER_TRADING else TradingMode.LIVE
            
            # Calculate position size and option details
            position_size, lot_size = await self._calculate_position_size(session, signal, current_price)
            
            # Get option contract details for the signal
            option_details = await self._resolve_option_contract(
                symbol, signal.option_type, current_price, signal.fibonacci_level
            )
            
            if not option_details:
                logger.warning(f"Could not resolve option contract for {symbol}")
                return
            
            # Create unified trade signal
            unified_signal = UnifiedTradeSignal(
                user_id=session.user_id,
                symbol=symbol,
                instrument_key=option_details["instrument_key"],
                option_type=signal.option_type,
                strike_price=option_details["strike_price"],
                signal_type="BUY",  # Always buying options
                entry_price=current_price,
                quantity=position_size,
                lot_size=lot_size,
                invested_amount=position_size * current_price,
                stop_loss=signal.stop_loss,
                target=signal.target_1,  # Use first target
                confidence_score=signal.strength / 100.0,
                strategy_name="fibonacci_ema",
                trading_mode=trading_mode
            )
            
            # Execute through unified executor
            result = await unified_trading_executor.execute_trade_signal(unified_signal)
            
            if result.success:
                self.system_metrics['signals_executed'] += 1
                self.system_metrics['successful_trades'] += 1
                session.trades_count += 1
                
                logger.info(f"✅ Signal executed successfully for {symbol}: {signal.signal_type} ({trading_mode.value})")
                
                # Emit real-time updates
                await self._emit_execution_updates(session, signal, symbol, result, trading_mode)
                
                await self._notify_trade_event("SIGNAL_EXECUTED", {
                    'session_id': session.session_id,
                    'symbol': symbol,
                    'signal_type': signal.signal_type,
                    'strength': signal.strength,
                    'trading_mode': trading_mode.value,
                    'execution_result': {
                        'trade_id': result.trade_id,
                        'success': result.success,
                        'execution_price': result.execution_price,
                        'invested_amount': unified_signal.invested_amount
                    }
                })
            else:
                self.system_metrics['failed_trades'] += 1
                logger.warning(f"❌ Signal execution failed for {symbol}: {result.error_message}")
            
        except Exception as e:
            logger.error(f"❌ Error executing Fibonacci signal for {symbol}: {e}")
            self.system_metrics['failed_trades'] += 1
    
    async def _handle_fibonacci_signal(self, instrument_key: str, signal_data: Dict[str, Any]):
        """Handle Fibonacci signal from data service"""
        try:
            # This is called by the data service when a signal is detected
            symbol = signal_data.get('symbol', '')
            current_price = signal_data.get('current_price', 0.0)
            
            # Find relevant session and process signal
            for session in self.active_sessions.values():
                if any(stock['instrument_key'] == instrument_key for stock in session.selected_stocks):
                    # Create signal object
                    signal = FibonacciSignal(
                        signal_type=signal_data['signal_type'],
                        strength=signal_data['strength'],
                        instrument_key=instrument_key,
                        stop_loss=signal_data['stop_loss'],
                        target=signal_data['target']
                    )
                    
                    if await self._can_execute_signal(session, signal):
                        await self._execute_fibonacci_signal(session, signal, symbol, current_price)
                    
                    break
            
        except Exception as e:
            logger.error(f"Error handling Fibonacci signal: {e}")
    
    async def _handle_position_update(self, event_type: str, position_data: Any):
        """Handle position updates from position monitor"""
        try:
            if event_type == "POSITION_CLOSED":
                # Update session metrics
                for session in self.active_sessions.values():
                    # Update total P&L (would need position details to match session)
                    pass
            
            await self._notify_position_event(event_type, position_data)
            
        except Exception as e:
            logger.error(f"Error handling position update: {e}")
    
    async def _handle_risk_limit_breach(self, limit_type: str, current_value: float):
        """Handle risk limit breaches"""
        try:
            logger.critical(f"Risk limit breach: {limit_type} = {current_value}")
            
            if limit_type == "DAILY_LOSS":
                self.daily_loss_limit_hit = True
                await self.pause_trading()
            elif limit_type == "PORTFOLIO_HEAT":
                await self.pause_trading()
            
            await self._notify_risk_event("RISK_LIMIT_BREACH", {
                'limit_type': limit_type,
                'current_value': current_value,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling risk limit breach: {e}")
    
    async def _handle_order_event(self, event_type: str, order_id: str, order_data: Dict[str, Any]):
        """Handle order events from order manager"""
        try:
            await self._notify_order_event(event_type, {
                'order_id': order_id,
                'data': order_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling order event: {e}")
    
    async def _system_health_monitor(self):
        """Monitor system health"""
        while self.system_state != TradingSystemState.SHUTTING_DOWN:
            try:
                # Update system health
                self.system_health.last_health_check = datetime.now(timezone.utc)
                self.system_health.uptime_seconds = int(
                    (datetime.now(timezone.utc) - self.start_time).total_seconds()
                )
                
                # Check component health
                broker_health = self.broker_manager.get_broker_health() if self.broker_manager else {}
                
                # Update health status
                if all(status.get('status') == 'HEALTHY' for status in broker_health.values()):
                    self.system_health.broker_status = "CONNECTED"
                else:
                    self.system_health.broker_status = "DEGRADED"
                
                await asyncio.sleep(30.0)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in system health monitor: {e}")
                await asyncio.sleep(60.0)
    
    async def _performance_tracker(self):
        """Track system performance metrics"""
        while self.system_state != TradingSystemState.SHUTTING_DOWN:
            try:
                # Update system metrics
                if self.position_monitor:
                    position_summary = self.position_monitor.get_position_summary()
                    self.system_metrics['active_positions'] = position_summary['active_positions']
                    self.system_metrics['total_pnl_today'] = position_summary['portfolio_metrics']['total_pnl']
                
                if self.order_manager:
                    order_stats = self.order_manager.get_system_status()
                    self.system_metrics['avg_execution_time_ms'] = order_stats['statistics'].get('avg_execution_time_ms', 0.0)
                
                # Calculate success rates
                total_trades = self.system_metrics['successful_trades'] + self.system_metrics['failed_trades']
                if total_trades > 0:
                    success_rate = self.system_metrics['successful_trades'] / total_trades * 100
                    self.system_metrics['success_rate'] = success_rate
                
                await asyncio.sleep(10.0)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error tracking performance: {e}")
                await asyncio.sleep(30.0)
    
    async def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Trigger emergency stop"""
        try:
            logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")
            self.system_state = TradingSystemState.EMERGENCY_STOP
            self.emergency_stop_active = True
            
            # Stop execution engine
            if self.execution_engine:
                await self.execution_engine._trigger_emergency_stop(reason)
            
            # Cancel all pending orders
            if self.order_manager:
                for order_id in list(self.order_manager.active_orders.keys()):
                    await self.order_manager.cancel_order(order_id)
            
            # Close all positions
            if self.position_monitor:
                await self.position_monitor.shutdown()
            
            await self._notify_system_status("EMERGENCY_STOP_ACTIVATED")
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
    
    async def pause_trading(self):
        """Pause trading operations"""
        try:
            self.system_state = TradingSystemState.PAUSED
            logger.info("Trading operations paused")
            
            await self._notify_system_status("TRADING_PAUSED")
            
        except Exception as e:
            logger.error(f"Error pausing trading: {e}")
    
    async def resume_trading(self):
        """Resume trading operations"""
        try:
            if self.system_state == TradingSystemState.PAUSED:
                self.system_state = TradingSystemState.ACTIVE
                self.daily_loss_limit_hit = False
                logger.info("Trading operations resumed")
                
                await self._notify_system_status("TRADING_RESUMED")
            
        except Exception as e:
            logger.error(f"Error resuming trading: {e}")
    
    def _validate_session_config(self, config: Dict[str, Any]) -> bool:
        """Validate trading session configuration"""
        required_fields = ['user_id']
        return all(field in config for field in required_fields)
    
    async def _initialize_session_components(self, session: TradingSession):
        """Initialize session-specific components"""
        # Configure risk parameters
        if self.risk_manager and session.risk_parameters:
            # Apply session-specific risk parameters
            pass
        
        # Configure strategy parameters
        if self.fibonacci_strategy and session.strategy_config:
            # Apply session-specific strategy parameters
            pass
    
    async def _calculate_position_size(self, session: TradingSession, signal: FibonacciSignal, 
                                     current_price: float) -> tuple[int, int]:
        """Calculate position size and lot size for the signal"""
        try:
            # Default lot size for F&O
            lot_size = 50  # This should be retrieved from instrument master
            
            # Calculate position size based on risk management
            capital = session.risk_parameters.get('allocated_capital', 100000)  # Default ₹1L
            risk_per_trade = session.risk_parameters.get('risk_per_trade', 2.0)  # 2%
            
            max_loss_per_trade = capital * (risk_per_trade / 100)
            
            # Assuming 30% stop loss on options
            stop_loss_amount = current_price * 0.30
            
            if stop_loss_amount > 0:
                max_lots = int(max_loss_per_trade / (stop_loss_amount * lot_size))
                lots = max(1, min(max_lots, 2))  # Minimum 1, maximum 2 lots
            else:
                lots = 1
            
            position_size = lots * lot_size
            return position_size, lot_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            logger.error("❌ No valid support/resistance levels found")
        return None, None
    
    async def _resolve_option_contract(self, symbol: str, option_type: str, 
                                     current_price: float, fibonacci_level: str) -> Optional[Dict]:
        """Resolve option contract details"""
        try:
            # This would typically use option service to get ATM contract
            # Get actual strike price from option service
            if hasattr(self, 'option_service') and self.option_service:
                try:
                    option_chain = await self.option_service.get_option_chain(symbol)
                    if option_chain and 'data' in option_chain:
                        # Find ATM strike based on current price
                        strikes = option_chain['data'].get('strikes', [])
                        if strikes:
                            atm_strike = min(strikes, key=lambda x: abs(x - current_price))
                            
                            # Get actual instrument details
                            for strike_data in option_chain['data'].get('options', []):
                                if (strike_data.get('strike') == atm_strike and 
                                    strike_data.get('option_type').upper() == option_type.upper()):
                                    
                                    return {
                                        "instrument_key": strike_data.get('instrument_key'),
                                        "strike_price": atm_strike,
                                        "option_type": option_type,
                                        "symbol": symbol,
                                        "expiry": strike_data.get('expiry'),
                                        "lot_size": strike_data.get('lot_size', 1)
                                    }
                except Exception as e:
                    logger.error(f"❌ Error getting option contract: {e}")
            
            logger.error("❌ Could not resolve option contract - no option service available")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving option contract: {e}")
            return None
    
    async def _emit_execution_updates(self, session: TradingSession, signal: FibonacciSignal,
                                    symbol: str, result, trading_mode: TradingMode):
        """Emit real-time execution updates"""
        try:
            # Emit through WebSocket manager if available
            if hasattr(self, 'ws_manager') and self.ws_manager:
                update_data = {
                    'type': 'fibonacci_signal_executed',
                    'session_id': session.session_id,
                    'symbol': symbol,
                    'signal_type': signal.signal_type,
                    'strength': signal.strength,
                    'trading_mode': trading_mode.value,
                    'entry_price': result.execution_price,
                    'stop_loss': signal.stop_loss,
                    'target': signal.target_1,
                    'trade_id': result.trade_id,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Emit to all connected clients
                await self.ws_manager.broadcast_to_all(update_data)
            
        except Exception as e:
            logger.error(f"Error emitting execution updates: {e}")
    
    # Notification methods
    async def _notify_system_status(self, status: str):
        """Notify system status change"""
        for callback in self.status_callbacks:
            try:
                await callback("SYSTEM_STATUS", {
                    'status': status,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'system_state': self.system_state.value
                })
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    async def _notify_trade_event(self, event_type: str, data: Dict[str, Any]):
        """Notify trade events"""
        for callback in self.trade_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")
    
    async def _notify_position_event(self, event_type: str, data: Any):
        """Notify position events"""
        pass  # Implementation depends on UI requirements
    
    async def _notify_order_event(self, event_type: str, data: Dict[str, Any]):
        """Notify order events"""
        pass  # Implementation depends on UI requirements
    
    async def _notify_risk_event(self, event_type: str, data: Dict[str, Any]):
        """Notify risk events"""
        pass  # Implementation depends on UI requirements
    
    async def _notify_session_event(self, event_type: str, session_id: str):
        """Notify session events"""
        pass  # Implementation depends on UI requirements
    
    async def _notify_error(self, error_type: str, message: str):
        """Notify errors"""
        for callback in self.error_callbacks:
            try:
                await callback(error_type, {
                    'message': message,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    # Public API methods
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'system_state': self.system_state.value,
            'system_health': asdict(self.system_health),
            'system_metrics': self.system_metrics.copy(),
            'active_sessions': len(self.active_sessions),
            'emergency_stop_active': self.emergency_stop_active,
            'daily_loss_limit_hit': self.daily_loss_limit_hit,
            'uptime_seconds': self.system_health.uptime_seconds
        }
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get trading session status"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return asdict(session)
    
    def add_status_callback(self, callback: Callable):
        """Add system status callback"""
        self.status_callbacks.append(callback)
    
    def add_trade_callback(self, callback: Callable):
        """Add trade event callback"""
        self.trade_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """Add error callback"""
        self.error_callbacks.append(callback)
    
    async def shutdown(self):
        """Graceful system shutdown"""
        try:
            logger.info("Shutting down Auto-Trading System...")
            self.system_state = TradingSystemState.SHUTTING_DOWN
            
            # Close all active sessions
            for session_id in list(self.active_sessions.keys()):
                await self.stop_trading_session(session_id)
            
            # Shutdown components in reverse order
            if self.execution_engine:
                await self.execution_engine.shutdown()
            
            if self.order_manager:
                await self.order_manager.shutdown()
            
            if self.position_monitor:
                await self.position_monitor.shutdown()
            
            if self.broker_manager:
                await self.broker_manager.shutdown()
            
            # Shutdown data service
            if self.data_service:
                await self.data_service.shutdown()
            
            if self.ws_manager:
                await self.ws_manager.cleanup()
            
            logger.info("Auto-Trading System shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during system shutdown: {e}")
    
    async def stop_trading_session(self, session_id: str):
        """Stop a trading session"""
        try:
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.session_end_time = datetime.now(timezone.utc)
                
                # Remove from active sessions
                self.active_sessions.pop(session_id)
                
                logger.info(f"Trading session stopped: {session_id}")
                await self._notify_session_event("SESSION_STOPPED", session_id)
            
        except Exception as e:
            logger.error(f"Error stopping trading session {session_id}: {e}")
    
    async def stop_all_sessions(self):
        """Stop all active trading sessions"""
        try:
            session_ids = list(self.active_sessions.keys())
            for session_id in session_ids:
                await self.stop_trading_session(session_id)
            
            # Set system to inactive
            self.system_state = TradingSystemState.INACTIVE
            logger.info(f"All trading sessions stopped ({len(session_ids)} sessions)")
            
        except Exception as e:
            logger.error(f"Error stopping all sessions: {e}")
    
    async def resume_system(self):
        """Resume the trading system from paused state"""
        try:
            if self.system_state == TradingSystemState.PAUSED:
                self.system_state = TradingSystemState.ACTIVE
                self.daily_loss_limit_hit = False
                logger.info("Trading system resumed")
                await self._notify_system_status("SYSTEM_RESUMED")
            else:
                logger.warning(f"Cannot resume system from state: {self.system_state.value}")
            
        except Exception as e:
            logger.error(f"Error resuming system: {e}")

    async def _margin_monitoring_loop(self):
        """Continuous margin monitoring during trading"""
        logger.info("🔍 Started margin monitoring loop")
        
        while self.system_state in [TradingSystemState.ACTIVE, TradingSystemState.PAUSED]:
            try:
                if self.system_state == TradingSystemState.PAUSED:
                    await asyncio.sleep(60)  # Check less frequently when paused
                    continue
                
                # Check all active sessions for margin issues
                for session_id, session in self.active_sessions.items():
                    if not session.auto_margin_sync:
                        continue
                    
                    # Get current margin status
                    margin_summary = broker_funds_sync_service.get_user_margin_summary(session.user_id)
                    
                    if "error" not in margin_summary:
                        utilization = margin_summary.get('overall_utilization', 0)
                        
                        # Take action based on utilization levels
                        if utilization > 95:
                            logger.critical(f"🚨 CRITICAL: Margin utilization {utilization:.1f}% for session {session_id} - Emergency stop!")
                            await self._emergency_stop_session(session, "Critical margin utilization")
                            
                        elif utilization > session.margin_utilization_limit * 100:
                            logger.warning(f"⚠️ HIGH: Margin utilization {utilization:.1f}% for session {session_id} - Pausing new trades")
                            await self._pause_session_new_trades(session, "High margin utilization")
                            
                        elif utilization > 70:
                            logger.info(f"📊 MODERATE: Margin utilization {utilization:.1f}% for session {session_id} - Reducing position sizes")
                            await self._reduce_session_position_sizes(session)
                
                await asyncio.sleep(self.margin_sync_interval)
                
            except Exception as e:
                logger.error(f"Error in margin monitoring: {e}")
                await asyncio.sleep(60)

    async def _emergency_stop_session(self, session: TradingSession, reason: str):
        """Emergency stop for a specific session with margin protection"""
        logger.critical(f"🚨 EMERGENCY STOP for session {session.session_id}: {reason}")
        
        try:
            # Set session to emergency stop
            # TODO: Add session state tracking if needed
            
            # Stop new trade generation for this session
            # TODO: Implement session-specific trading controls
            
            # Log emergency event
            await self._log_emergency_event(session, reason)
            
        except Exception as e:
            logger.error(f"Error in emergency stop for session {session.session_id}: {e}")

    async def _pause_session_new_trades(self, session: TradingSession, reason: str):
        """Pause new trades for a session while keeping existing ones"""
        logger.warning(f"⏸️ PAUSING NEW TRADES for session {session.session_id}: {reason}")
        
        try:
            # TODO: Implement session-specific pause logic
            # For now, we can reduce risk per trade
            session.risk_per_trade *= 0.5
            
            # Log pause event
            await self._log_trading_event(session, "PAUSED_NEW_TRADES", reason)
            
        except Exception as e:
            logger.error(f"Error pausing new trades for session {session.session_id}: {e}")

    async def _reduce_session_position_sizes(self, session: TradingSession):
        """Reduce position sizes for a session due to margin pressure"""
        try:
            # Reduce risk per trade by 30%
            session.risk_per_trade *= 0.7
            logger.info(f"📉 Reduced risk per trade to {session.risk_per_trade:.3f} for session {session.session_id}")
            
        except Exception as e:
            logger.error(f"Error reducing position sizes for session {session.session_id}: {e}")

    async def calculate_margin_aware_position_size(self, session: TradingSession, stock_price: float, symbol: str) -> Dict[str, Any]:
        """Calculate intelligent position size based on margin and other factors"""
        db = None
        try:
            # Create margin service with proper DB session management
            db = SessionLocal()
            margin_service = MarginAwareTradingService(db)
            
            # Get margin-based position size
            position_calc = margin_service.calculate_position_size(
                user_id=session.user_id,
                stock_price=stock_price,
                risk_percentage=session.risk_per_trade
            )
            
            if not position_calc.get("can_trade", False):
                return {
                    "quantity": 0,
                    "method": "margin_blocked",
                    "reason": position_calc.get("reason", "Margin check failed")
                }
            
            base_quantity = position_calc.get("recommended_quantity", 1)
            
            # Apply session-specific adjustments
            if session.position_sizing_mode == "margin_based":
                # Use margin-calculated size
                final_quantity = base_quantity
            elif session.position_sizing_mode == "fixed":
                # Use fixed size from config
                final_quantity = session.strategy_config.get("fixed_quantity", 1)
            else:
                # Default to margin-based with buffer
                final_quantity = max(1, int(base_quantity * (1 - session.margin_buffer)))
            
            # Apply time-based adjustment (reduce size near market close)
            time_factor = await self._get_time_based_factor()
            final_quantity = max(1, int(final_quantity * time_factor))
            
            return {
                "quantity": final_quantity,
                "method": "margin_aware",
                "base_quantity": base_quantity,
                "time_factor": time_factor,
                "required_margin": position_calc.get("required_margin", 0),
                "margin_utilization": position_calc.get("margin_utilization_after_trade", 0),
                "session_risk": session.risk_per_trade
            }
            
        except Exception as e:
            logger.error(f"Error calculating margin-aware position size: {e}")
            logger.error("❌ Could not calculate position size - no valid data available")
            return {"quantity": 0, "method": "error_no_data", "error": "No valid position sizing data"}
        finally:
            if db:
                db.close()

    async def validate_trade_with_margin(self, session: TradingSession, quantity: int, stock_price: float) -> Dict[str, Any]:
        """Validate trade against margin requirements"""
        db = None
        try:
            # Create margin service with proper DB session management
            db = SessionLocal()
            margin_service = MarginAwareTradingService(db)
            
            validation = margin_service.validate_trade_order(
                user_id=session.user_id,
                quantity=quantity,
                stock_price=stock_price
            )
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating trade with margin: {e}")
            return {"valid": False, "reason": str(e)}
        finally:
            if db:
                db.close()

    async def _get_time_based_factor(self) -> float:
        """Get time-based position size adjustment"""
        now = datetime.now()
        hour = now.hour
        
        # Reduce position sizes in last hour of trading
        if hour >= 15:  # After 3 PM
            return 0.5
        elif hour >= 14:  # After 2 PM
            return 0.7
        else:
            return 1.0

    async def _log_emergency_event(self, session: TradingSession, reason: str):
        """Log emergency trading events"""
        try:
            event = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "event_type": "EMERGENCY_STOP",
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "margin_status": broker_funds_sync_service.get_user_margin_summary(session.user_id)
            }
            
            logger.critical(f"Emergency event logged: {event}")
            # TODO: Store in database via db_service
            
        except Exception as e:
            logger.error(f"Error logging emergency event: {e}")

    async def _log_trading_event(self, session: TradingSession, event_type: str, details: str):
        """Log general trading events"""
        try:
            event = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Trading event: {event}")
            # TODO: Store in database via db_service
            
        except Exception as e:
            logger.error(f"Error logging trading event: {e}")

    async def get_enhanced_system_status(self) -> Dict[str, Any]:
        """Get enhanced system status with margin information"""
        try:
            base_status = {
                "system_state": self.system_state.value,
                "active_sessions": len(self.active_sessions),
                "system_metrics": self.system_metrics,
                "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds()
            }
            
            # Add margin-related status
            enhanced_status = {
                **base_status,
                "margin_sync_enabled": broker_funds_sync_service.is_running,
                "last_margin_sync": self.last_margin_sync,
                "margin_monitoring": "active" if self.system_state == TradingSystemState.ACTIVE else "paused",
                "enhanced_features": {
                    "margin_aware_position_sizing": True,
                    "real_time_margin_monitoring": True,
                    "emergency_stops": True,
                    "dynamic_risk_adjustment": True
                }
            }
            
            return enhanced_status
            
        except Exception as e:
            logger.error(f"Error getting enhanced status: {e}")
            return {"error": str(e)}

# Context manager for easy system lifecycle management
@asynccontextmanager
async def auto_trading_system(config: Dict[str, Any]):
    """Context manager for auto-trading system lifecycle"""
    coordinator = AutoTradingCoordinator(config)
    
    try:
        # Initialize system
        success = await coordinator.initialize_system()
        if not success:
            raise RuntimeError("Failed to initialize auto-trading system")
        
        yield coordinator
        
    finally:
        # Always shutdown cleanly
        await coordinator.shutdown()