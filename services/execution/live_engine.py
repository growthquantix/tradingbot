"""
Live Trading Execution Engine

Coordinates real-time strategy execution with proper market hours scheduling,
risk management, and position monitoring. Integrates with Live Feed Adapter
and Order Manager for complete trade lifecycle management.

Features:
- Indian market hours scheduling with holiday calendar
- Real-time strategy execution with configurable intervals
- Position monitoring and automated exit conditions
- Risk management with circuit breakers and daily limits
- Comprehensive logging and trade audit trail
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Callable
import pytz
import pandas as pd
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class EngineState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class StrategyConfig:
    """Configuration for a strategy instance"""
    name: str
    strategy_function: Callable
    instruments: List[str]
    parameters: Dict[str, Any]
    enabled: bool = True
    risk_limit: float = 5000.0  # Max risk per strategy
    max_positions: int = 3
    execution_interval: int = 60  # seconds
    
@dataclass
class Position:
    """Active position tracking"""
    strategy_name: str
    instrument_key: str
    side: str  # 'BUY' or 'SELL'
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float
    target: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    order_id: Optional[str] = None

class LiveTradingEngine:
    """
    Real-time trading execution engine with market hours scheduling.
    """
    
    def __init__(self, live_adapter, order_manager, user_id: int):
        self.live_adapter = live_adapter
        self.order_manager = order_manager
        self.user_id = user_id
        
        # Engine state
        self.state = EngineState.STOPPED
        self.strategies: Dict[str, StrategyConfig] = {}
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        
        # Market hours (Indian timezone)
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.market_open = time(9, 15)  # 9:15 AM IST
        self.market_close = time(15, 30)  # 3:30 PM IST
        
        # Execution control
        self.execution_tasks: Dict[str, asyncio.Task] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Risk management
        self.daily_pnl = 0.0
        self.max_daily_loss = 10000.0  # Circuit breaker
        self.max_total_positions = 10
        
        # Performance tracking
        self.trades_today = 0
        self.trades_log = []
        
        logger.info(f"🚀 LiveTradingEngine initialized for user {user_id}")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()
    
    def add_strategy(self, config: StrategyConfig) -> bool:
        """Add a strategy to the execution engine"""
        try:
            # Validate strategy
            if not callable(config.strategy_function):
                raise ValueError("Strategy function must be callable")
            
            if not config.instruments:
                raise ValueError("Strategy must specify instruments")
            
            # Store strategy
            self.strategies[config.name] = config
            
            logger.info(f"📈 Added strategy: {config.name} for instruments {config.instruments}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add strategy {config.name}: {e}")
            return False
    
    async def remove_strategy(self, strategy_name: str) -> bool:
        """Remove a strategy from execution"""
        try:
            if strategy_name in self.strategies:
                # Stop execution task if running
                if strategy_name in self.execution_tasks:
                    self.execution_tasks[strategy_name].cancel()
                    del self.execution_tasks[strategy_name]
                
                # Close any open positions for this strategy
                await self._close_strategy_positions(strategy_name)
                
                # Remove strategy
                del self.strategies[strategy_name]
                
                logger.info(f"🗑️ Removed strategy: {strategy_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to remove strategy {strategy_name}: {e}")
            return False
    
    async def start_engine(self) -> bool:
        """Start the live trading engine"""
        try:
            if self.state != EngineState.STOPPED:
                logger.warning("⚠️ Engine already running or in transition")
                return False
            
            self.state = EngineState.STARTING
            
            # Check if market is open
            if not self.is_market_open():
                logger.info("🕐 Market is closed. Engine will wait for market hours.")
            
            # Register tick callbacks for all strategy instruments
            await self._register_tick_callbacks()
            
            # Start position monitoring
            self.monitoring_task = asyncio.create_task(self._monitor_positions())
            
            # Start strategy execution tasks
            for strategy_name, config in self.strategies.items():
                if config.enabled:
                    task = asyncio.create_task(
                        self._execute_strategy_loop(strategy_name, config)
                    )
                    self.execution_tasks[strategy_name] = task
            
            self.state = EngineState.RUNNING
            logger.info("🟢 Live trading engine started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start engine: {e}")
            self.state = EngineState.ERROR
            return False
    
    async def stop_engine(self) -> bool:
        """Stop the live trading engine"""
        try:
            if self.state == EngineState.STOPPED:
                return True
            
            self.state = EngineState.STOPPING
            
            # Cancel all execution tasks
            for task_name, task in self.execution_tasks.items():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"⏹️ Stopped strategy execution: {task_name}")
            
            self.execution_tasks.clear()
            
            # Cancel monitoring task
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Signal shutdown
            self._shutdown_event.set()
            
            self.state = EngineState.STOPPED
            logger.info("🔴 Live trading engine stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping engine: {e}")
            self.state = EngineState.ERROR
            return False
    
    async def shutdown(self):
        """Complete shutdown with cleanup"""
        await self.stop_engine()
        logger.info("🏁 Live trading engine shutdown complete")
    
    def is_market_open(self) -> bool:
        """Check if Indian stock market is currently open"""
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check if within market hours
        return self.market_open <= current_time <= self.market_close
    
    def get_time_to_market_open(self) -> Optional[timedelta]:
        """Get time remaining until market opens"""
        now = datetime.now(self.timezone)
        
        if self.is_market_open():
            return None
        
        # Calculate next market open
        next_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        
        # If market already closed today, move to next trading day
        if now.time() > self.market_close:
            next_open += timedelta(days=1)
        
        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
        
        return next_open - now
    
    async def _register_tick_callbacks(self):
        """Register tick callbacks for all strategy instruments"""
        try:
            # Collect all instruments across strategies
            all_instruments = set()
            for config in self.strategies.values():
                all_instruments.update(config.instruments)
            
            if all_instruments:
                # Register callback for price updates
                self.live_adapter.register_tick_callback(
                    name="live_engine",
                    instruments=list(all_instruments),
                    callback=self._on_price_update
                )
                
                logger.info(f"📡 Registered tick callbacks for {len(all_instruments)} instruments")
            
        except Exception as e:
            logger.error(f"❌ Failed to register tick callbacks: {e}")
    
    def _on_price_update(self, instrument_key: str, tick_data: Dict[str, Any]):
        """Handle real-time price updates"""
        try:
            # Update position PnL if we have positions for this instrument
            for position_id, position in self.positions.items():
                if position.instrument_key == instrument_key:
                    position.current_price = tick_data.get('ltp', position.current_price)
                    
                    # Calculate unrealized PnL
                    if position.side == 'BUY':
                        position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity
                    else:
                        position.unrealized_pnl = (position.entry_price - position.current_price) * position.quantity
            
        except Exception as e:
            logger.error(f"❌ Error processing price update for {instrument_key}: {e}")
    
    async def _execute_strategy_loop(self, strategy_name: str, config: StrategyConfig):
        """Main execution loop for a strategy"""
        try:
            logger.info(f"🔄 Starting execution loop for strategy: {strategy_name}")
            
            while not self._shutdown_event.is_set():
                try:
                    # Check if market is open
                    if not self.is_market_open():
                        # Wait until market opens
                        wait_time = self.get_time_to_market_open()
                        if wait_time:
                            logger.info(f"⏰ Market closed. Waiting {wait_time} for market open.")
                            await asyncio.sleep(min(wait_time.total_seconds(), 300))  # Max 5 min wait
                        continue
                    
                    # Check risk limits
                    if not self._check_risk_limits():
                        logger.warning(f"🚨 Risk limits exceeded. Pausing strategy: {strategy_name}")
                        await asyncio.sleep(60)  # Wait 1 minute before checking again
                        continue
                    
                    # Execute strategy for each instrument
                    for instrument_key in config.instruments:
                        await self._execute_strategy_for_instrument(
                            strategy_name, config, instrument_key
                        )
                    
                    # Wait for next execution cycle
                    await asyncio.sleep(config.execution_interval)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"❌ Error in strategy loop {strategy_name}: {e}")
                    await asyncio.sleep(30)  # Wait 30 seconds before retrying
            
        except Exception as e:
            logger.error(f"❌ Strategy loop {strategy_name} crashed: {e}")
        finally:
            logger.info(f"🏁 Strategy loop ended: {strategy_name}")
    
    async def _execute_strategy_for_instrument(
        self, 
        strategy_name: str, 
        config: StrategyConfig, 
        instrument_key: str
    ):
        """Execute strategy logic for a specific instrument"""
        try:
            # Get 5-minute data for strategy
            df_5m = self.live_adapter.get_5m_df(instrument_key, window_minutes=300)
            
            if df_5m.empty:
                logger.debug(f"📊 No data available for {instrument_key}")
                return
            
            # Execute strategy function
            signal = config.strategy_function(df_5m, config.parameters)
            
            if not signal or signal.get('signal') == 'HOLD':
                return
            
            # Check if we already have a position for this instrument
            existing_position = self._find_position(strategy_name, instrument_key)
            
            if signal['signal'] == 'BUY' and not existing_position:
                await self._execute_buy_signal(strategy_name, config, instrument_key, signal)
            elif signal['signal'] == 'SELL' and not existing_position:
                await self._execute_sell_signal(strategy_name, config, instrument_key, signal)
            
        except Exception as e:
            logger.error(f"❌ Error executing strategy {strategy_name} for {instrument_key}: {e}")
    
    async def _execute_buy_signal(
        self, 
        strategy_name: str, 
        config: StrategyConfig, 
        instrument_key: str, 
        signal: Dict[str, Any]
    ):
        """Execute a BUY signal"""
        try:
            # Calculate position size based on risk
            quantity = self._calculate_position_size(
                signal['entry_price'], 
                signal['stop_loss'], 
                config.risk_limit
            )
            
            if quantity <= 0:
                logger.debug(f"📊 Position size too small for {instrument_key}")
                return
            
            # Place order
            order_result = await self.order_manager.place_order(
                symbol=instrument_key,
                side='BUY',
                quantity=quantity,
                price=signal['entry_price'],
                order_type='MARKET',
                strategy=strategy_name
            )
            
            if order_result.get('success'):
                # Create position record
                position = Position(
                    strategy_name=strategy_name,
                    instrument_key=instrument_key,
                    side='BUY',
                    quantity=quantity,
                    entry_price=signal['entry_price'],
                    current_price=signal['entry_price'],
                    stop_loss=signal['stop_loss'],
                    target=signal['target'],
                    entry_time=datetime.now(),
                    order_id=order_result.get('order_id')
                )
                
                position_id = f"{strategy_name}_{instrument_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.positions[position_id] = position
                
                logger.info(f"🟢 BUY: {quantity} {instrument_key} @ {signal['entry_price']:.2f} (Strategy: {strategy_name})")
            
        except Exception as e:
            logger.error(f"❌ Error executing BUY signal: {e}")
    
    async def _execute_sell_signal(
        self, 
        strategy_name: str, 
        config: StrategyConfig, 
        instrument_key: str, 
        signal: Dict[str, Any]
    ):
        """Execute a SELL signal"""
        try:
            # Calculate position size
            quantity = self._calculate_position_size(
                signal['entry_price'], 
                signal['stop_loss'], 
                config.risk_limit
            )
            
            if quantity <= 0:
                return
            
            # Place order
            order_result = await self.order_manager.place_order(
                symbol=instrument_key,
                side='SELL',
                quantity=quantity,
                price=signal['entry_price'],
                order_type='MARKET',
                strategy=strategy_name
            )
            
            if order_result.get('success'):
                # Create position record
                position = Position(
                    strategy_name=strategy_name,
                    instrument_key=instrument_key,
                    side='SELL',
                    quantity=quantity,
                    entry_price=signal['entry_price'],
                    current_price=signal['entry_price'],
                    stop_loss=signal['stop_loss'],
                    target=signal['target'],
                    entry_time=datetime.now(),
                    order_id=order_result.get('order_id')
                )
                
                position_id = f"{strategy_name}_{instrument_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.positions[position_id] = position
                
                logger.info(f"🔴 SELL: {quantity} {instrument_key} @ {signal['entry_price']:.2f} (Strategy: {strategy_name})")
            
        except Exception as e:
            logger.error(f"❌ Error executing SELL signal: {e}")
    
    async def _monitor_positions(self):
        """Monitor open positions for exit conditions"""
        try:
            logger.info("👁️ Starting position monitoring")
            
            while not self._shutdown_event.is_set():
                try:
                    positions_to_close = []
                    
                    for position_id, position in self.positions.items():
                        # Check stop loss
                        if self._should_exit_position(position):
                            positions_to_close.append(position_id)
                    
                    # Close positions that hit exit conditions
                    for position_id in positions_to_close:
                        await self._close_position(position_id, "Exit condition triggered")
                    
                    # Wait before next monitoring cycle
                    await asyncio.sleep(10)  # Monitor every 10 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"❌ Error in position monitoring: {e}")
                    await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"❌ Position monitoring crashed: {e}")
        finally:
            logger.info("🏁 Position monitoring stopped")
    
    def _should_exit_position(self, position: Position) -> bool:
        """Check if position should be exited"""
        current_price = position.current_price
        
        if position.side == 'BUY':
            # Check stop loss or target for long position
            return current_price <= position.stop_loss or current_price >= position.target
        else:
            # Check stop loss or target for short position
            return current_price >= position.stop_loss or current_price <= position.target
    
    async def _close_position(self, position_id: str, reason: str):
        """Close a specific position"""
        try:
            position = self.positions.get(position_id)
            if not position:
                return
            
            # Determine exit side (opposite of entry)
            exit_side = 'SELL' if position.side == 'BUY' else 'BUY'
            
            # Place exit order
            order_result = await self.order_manager.place_order(
                symbol=position.instrument_key,
                side=exit_side,
                quantity=position.quantity,
                order_type='MARKET',
                strategy=position.strategy_name
            )
            
            if order_result.get('success'):
                # Calculate realized PnL
                if position.side == 'BUY':
                    realized_pnl = (position.current_price - position.entry_price) * position.quantity
                else:
                    realized_pnl = (position.entry_price - position.current_price) * position.quantity
                
                # Update daily PnL
                self.daily_pnl += realized_pnl
                
                # Log trade
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'strategy': position.strategy_name,
                    'instrument': position.instrument_key,
                    'side': position.side,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'exit_price': position.current_price,
                    'pnl': realized_pnl,
                    'reason': reason
                }
                self.trades_log.append(trade_record)
                self.trades_today += 1
                
                logger.info(f"🔚 CLOSED: {position.side} {position.quantity} {position.instrument_key} @ {position.current_price:.2f} (PnL: {realized_pnl:.2f}) - {reason}")
                
                # Remove position
                del self.positions[position_id]
            
        except Exception as e:
            logger.error(f"❌ Error closing position {position_id}: {e}")
    
    async def _close_strategy_positions(self, strategy_name: str):
        """Close all positions for a specific strategy"""
        positions_to_close = [
            pos_id for pos_id, position in self.positions.items()
            if position.strategy_name == strategy_name
        ]
        
        for position_id in positions_to_close:
            await self._close_position(position_id, f"Strategy {strategy_name} removed")
    
    def _find_position(self, strategy_name: str, instrument_key: str) -> Optional[Position]:
        """Find existing position for strategy and instrument"""
        for position in self.positions.values():
            if (position.strategy_name == strategy_name and 
                position.instrument_key == instrument_key):
                return position
        return None
    
    def _calculate_position_size(self, entry_price: float, stop_loss: float, risk_amount: float) -> int:
        """Calculate position size based on risk management"""
        try:
            if entry_price <= 0 or stop_loss <= 0 or risk_amount <= 0:
                return 0
            
            # Calculate risk per share
            risk_per_share = abs(entry_price - stop_loss)
            
            if risk_per_share <= 0:
                return 0
            
            # Calculate quantity based on risk amount
            quantity = int(risk_amount / risk_per_share)
            
            # Ensure minimum and reasonable limits
            return max(1, min(quantity, 1000))  # Min 1, Max 1000 shares
            
        except Exception as e:
            logger.error(f"❌ Error calculating position size: {e}")
            return 0
    
    def _check_risk_limits(self) -> bool:
        """Check if risk limits are within bounds"""
        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            logger.warning(f"🚨 Daily loss limit exceeded: {self.daily_pnl:.2f}")
            return False
        
        # Check total positions
        if len(self.positions) >= self.max_total_positions:
            logger.warning(f"🚨 Maximum positions limit exceeded: {len(self.positions)}")
            return False
        
        return True
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status"""
        return {
            'state': self.state.value,
            'market_open': self.is_market_open(),
            'time_to_market_open': str(self.get_time_to_market_open()) if not self.is_market_open() else None,
            'strategies': {
                name: {
                    'enabled': config.enabled,
                    'instruments': config.instruments,
                    'running': name in self.execution_tasks
                }
                for name, config in self.strategies.items()
            },
            'positions': {
                position_id: {
                    'strategy': pos.strategy_name,
                    'instrument': pos.instrument_key,
                    'side': pos.side,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'unrealized_pnl': pos.unrealized_pnl,
                    'entry_time': pos.entry_time.isoformat()
                }
                for position_id, pos in self.positions.items()
            },
            'daily_stats': {
                'pnl': self.daily_pnl,
                'trades_count': self.trades_today,
                'max_loss_limit': self.max_daily_loss,
                'positions_count': len(self.positions),
                'max_positions_limit': self.max_total_positions
            }
        }
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get today's trade history"""
        return self.trades_log.copy()
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at start of trading day)"""
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.trades_log.clear()
        logger.info("📊 Daily statistics reset")

# Helper functions
async def create_live_engine(user_id: int, mode: str = "PAPER") -> LiveTradingEngine:
    """Create LiveTradingEngine with proper dependencies"""
    try:
        from services.live_adapter import LiveFeedAdapter
        from services.execution.order_manager import create_order_manager
        
        # Create dependencies
        live_adapter = LiveFeedAdapter()
        order_manager = await create_order_manager(user_id, mode)
        
        # Create engine
        engine = LiveTradingEngine(
            live_adapter=live_adapter,
            order_manager=order_manager,
            user_id=user_id
        )
        
        return engine
        
    except Exception as e:
        logger.error(f"❌ Failed to create live engine: {e}")
        raise