"""
Advanced Position Monitoring and P&L Tracking System
Real-time position tracking with sophisticated risk management
Features: Live P&L, trailing stops, Greeks monitoring, portfolio heat
"""

import asyncio
import logging
import time
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class PositionType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class PositionStatus(Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    PARTIAL = "PARTIAL"
    SUSPENDED = "SUSPENDED"

class ExitReason(Enum):
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    MANUAL_EXIT = "MANUAL_EXIT"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"
    RISK_LIMIT = "RISK_LIMIT"

@dataclass
class GreeksData:
    """Options Greeks data"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    iv: float = 0.0  # Implied Volatility

@dataclass
class RiskMetrics:
    """Position risk metrics"""
    var_1d: float = 0.0  # 1-day Value at Risk
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0
    portfolio_heat: float = 0.0  # Position heat in portfolio

@dataclass
class PositionSnapshot:
    """Real-time position snapshot"""
    position_id: str
    symbol: str
    instrument_key: str
    position_type: PositionType
    quantity: int
    entry_price: float
    current_price: float
    average_price: float
    
    # P&L Data
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    day_pnl: float = 0.0
    total_pnl: float = 0.0
    
    # Risk Data
    stop_loss: float = 0.0
    target: float = 0.0
    trailing_stop: Optional[float] = None
    
    # Performance Tracking
    max_profit: float = 0.0
    max_loss: float = 0.0
    duration_minutes: int = 0
    
    # Options Specific
    greeks: Optional[GreeksData] = None
    option_type: Optional[str] = None  # CE/PE
    strike_price: Optional[float] = None
    expiry_date: Optional[datetime] = None
    
    # Risk Metrics
    risk_metrics: RiskMetrics = field(default_factory=RiskMetrics)
    
    # Status
    status: PositionStatus = PositionStatus.ACTIVE
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    exit_reason: Optional[ExitReason] = None
    
    # Internal tracking
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    price_history: deque = field(default_factory=lambda: deque(maxlen=100))
    pnl_history: deque = field(default_factory=lambda: deque(maxlen=100))

class TrailingStopManager:
    """Advanced trailing stop management"""
    
    def __init__(self):
        self.trailing_configs = {
            'percentage': 0.02,  # 2% trailing stop
            'atr_multiplier': 1.5,
            'fibonacci_levels': [0.236, 0.382, 0.5, 0.618],
            'min_profit_threshold': 0.01  # Minimum 1% profit before trailing
        }
    
    def update_trailing_stop(self, position: PositionSnapshot, 
                           atr: Optional[float] = None) -> Optional[float]:
        """Update trailing stop based on multiple methods"""
        try:
            if position.position_type == PositionType.LONG:
                return self._update_long_trailing_stop(position, atr)
            else:
                return self._update_short_trailing_stop(position, atr)
        except Exception as e:
            logger.error(f"Error updating trailing stop for {position.position_id}: {e}")
            return position.trailing_stop
    
    def _update_long_trailing_stop(self, position: PositionSnapshot, 
                                  atr: Optional[float] = None) -> Optional[float]:
        """Update trailing stop for long position"""
        current_profit_pct = (position.current_price - position.entry_price) / position.entry_price
        
        # Only activate trailing stop after minimum profit
        if current_profit_pct < self.trailing_configs['min_profit_threshold']:
            return position.trailing_stop
        
        # Calculate new trailing stop
        if atr:
            # ATR-based trailing stop
            new_trailing = position.current_price - (atr * self.trailing_configs['atr_multiplier'])
        else:
            # Percentage-based trailing stop
            new_trailing = position.current_price * (1 - self.trailing_configs['percentage'])
        
        # Only move trailing stop up (for long positions)
        if position.trailing_stop is None or new_trailing > position.trailing_stop:
            return new_trailing
        
        return position.trailing_stop
    
    def _update_short_trailing_stop(self, position: PositionSnapshot, 
                                   atr: Optional[float] = None) -> Optional[float]:
        """Update trailing stop for short position"""
        current_profit_pct = (position.entry_price - position.current_price) / position.entry_price
        
        if current_profit_pct < self.trailing_configs['min_profit_threshold']:
            return position.trailing_stop
        
        if atr:
            new_trailing = position.current_price + (atr * self.trailing_configs['atr_multiplier'])
        else:
            new_trailing = position.current_price * (1 + self.trailing_configs['percentage'])
        
        # Only move trailing stop down (for short positions)
        if position.trailing_stop is None or new_trailing < position.trailing_stop:
            return new_trailing
        
        return position.trailing_stop

class GreeksCalculator:
    """Options Greeks calculation and monitoring"""
    
    @staticmethod
    def calculate_greeks(spot_price: float, strike_price: float, 
                        time_to_expiry: float, risk_free_rate: float, 
                        volatility: float, option_type: str) -> GreeksData:
        """Calculate Options Greeks using Black-Scholes model"""
        try:
            if time_to_expiry <= 0:
                return GreeksData()
            
            # Black-Scholes calculations
            d1 = (math.log(spot_price / strike_price) + 
                  (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
            d2 = d1 - volatility * math.sqrt(time_to_expiry)
            
            # Standard normal cumulative distribution function
            def norm_cdf(x):
                return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
            
            # Standard normal probability density function
            def norm_pdf(x):
                return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
            
            # Greeks calculation
            if option_type.upper() == 'CE':
                delta = norm_cdf(d1)
            else:  # PE
                delta = norm_cdf(d1) - 1
            
            gamma = norm_pdf(d1) / (spot_price * volatility * math.sqrt(time_to_expiry))
            theta = (-spot_price * norm_pdf(d1) * volatility / (2 * math.sqrt(time_to_expiry)) -
                    risk_free_rate * strike_price * math.exp(-risk_free_rate * time_to_expiry) * norm_cdf(d2))
            vega = spot_price * norm_pdf(d1) * math.sqrt(time_to_expiry)
            rho = strike_price * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * norm_cdf(d2)
            
            if option_type.upper() == 'PE':
                theta += risk_free_rate * strike_price * math.exp(-risk_free_rate * time_to_expiry)
                rho = -rho
            
            return GreeksData(
                delta=delta,
                gamma=gamma,
                theta=theta / 365,  # Daily theta
                vega=vega / 100,   # Vega per 1% volatility change
                rho=rho / 100,     # Rho per 1% interest rate change
                iv=volatility
            )
            
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return GreeksData()

class PortfolioHeatMonitor:
    """Monitor portfolio heat and concentration risk"""
    
    def __init__(self, max_portfolio_risk: float = 0.05):  # 5% max portfolio risk
        self.max_portfolio_risk = max_portfolio_risk
        self.sector_limits = {
            'FINANCIAL': 0.30,
            'TECHNOLOGY': 0.25,
            'ENERGY': 0.20,
            'HEALTHCARE': 0.15,
            'OTHER': 0.10
        }
    
    def calculate_portfolio_heat(self, positions: List[PositionSnapshot], 
                               portfolio_value: float) -> Dict[str, Any]:
        """Calculate portfolio heat metrics"""
        if portfolio_value <= 0:
            return {'total_heat': 0.0, 'risk_score': 'LOW'}
        
        total_exposure = sum(abs(pos.unrealized_pnl + pos.current_price * pos.quantity) 
                           for pos in positions if pos.status == PositionStatus.ACTIVE)
        
        portfolio_heat = total_exposure / portfolio_value
        
        # Calculate sector concentration
        sector_exposure = defaultdict(float)
        for pos in positions:
            if pos.status == PositionStatus.ACTIVE:
                sector = self._get_sector(pos.symbol)  # Would integrate with sector mapping
                position_value = pos.current_price * pos.quantity
                sector_exposure[sector] += abs(position_value) / portfolio_value
        
        # Risk assessment
        risk_score = 'LOW'
        if portfolio_heat > 0.8:
            risk_score = 'CRITICAL'
        elif portfolio_heat > 0.6:
            risk_score = 'HIGH'
        elif portfolio_heat > 0.4:
            risk_score = 'MEDIUM'
        
        return {
            'total_heat': portfolio_heat,
            'risk_score': risk_score,
            'sector_exposure': dict(sector_exposure),
            'concentration_risk': max(sector_exposure.values()) > 0.35,
            'total_exposure': total_exposure
        }
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for symbol (would integrate with sector mapping service)"""
        # Mock sector mapping
        financial_stocks = ['HDFCBANK', 'ICICIBANK', 'AXISBANK', 'SBIN']
        tech_stocks = ['TCS', 'INFY', 'WIPRO', 'TECHM']
        
        if any(stock in symbol for stock in financial_stocks):
            return 'FINANCIAL'
        elif any(stock in symbol for stock in tech_stocks):
            return 'TECHNOLOGY'
        else:
            return 'OTHER'

class PositionMonitor:
    """
    Advanced Position Monitoring System
    Features:
    - Real-time P&L tracking
    - Advanced risk metrics
    - Options Greeks monitoring
    - Portfolio heat analysis
    - Automated risk management
    """
    
    def __init__(self, db_service, ws_manager):
        self.db_service = db_service
        self.ws_manager = ws_manager
        
        # Position tracking
        self.positions: Dict[str, PositionSnapshot] = {}
        self.closed_positions: Dict[str, PositionSnapshot] = {}
        
        # Risk management
        self.trailing_stop_manager = TrailingStopManager()
        self.greeks_calculator = GreeksCalculator()
        self.portfolio_monitor = PortfolioHeatMonitor()
        
        # Callbacks
        self.exit_callbacks: List[Callable] = []
        
        # Performance tracking
        self.portfolio_metrics = {
            'total_pnl': 0.0,
            'day_pnl': 0.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0
        }
        
        # Risk limits
        self.risk_limits = {
            'max_position_size': 100000.0,  # Max position value
            'max_daily_loss': 50000.0,      # Max daily loss
            'max_portfolio_heat': 0.7,      # Max portfolio exposure
            'max_correlation': 0.8,         # Max position correlation
            'max_single_position': 0.2      # Max single position as % of portfolio
        }
        
        # Monitoring state
        self.monitoring_active = False
        self.last_portfolio_update = datetime.now(timezone.utc)
        
        # Event callbacks
        self.position_callbacks: List[Callable] = []
        self.risk_callbacks: List[Callable] = []
        
        logger.info("Position Monitor initialized")
    
    async def start_monitoring(self):
        """Start position monitoring tasks"""
        try:
            self.monitoring_active = True
            
            # Start monitoring tasks
            asyncio.create_task(self._monitor_positions())
            asyncio.create_task(self._update_portfolio_metrics())
            asyncio.create_task(self._monitor_risk_limits())
            asyncio.create_task(self._update_greeks())
            
            logger.info("Position monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start position monitoring: {e}")
            raise
    
    def add_position(self, position_data: Dict[str, Any]) -> str:
        """Add new position for monitoring"""
        position_id = f"POS_{int(time.time() * 1000000)}"
        
        position = PositionSnapshot(
            position_id=position_id,
            symbol=position_data['symbol'],
            instrument_key=position_data['instrument_key'],
            position_type=PositionType(position_data.get('position_type', 'LONG')),
            quantity=position_data['quantity'],
            entry_price=position_data['entry_price'],
            current_price=position_data['current_price'],
            average_price=position_data.get('average_price', position_data['entry_price']),
            stop_loss=position_data.get('stop_loss', 0.0),
            target=position_data.get('target', 0.0),
            option_type=position_data.get('option_type'),
            strike_price=position_data.get('strike_price'),
            expiry_date=position_data.get('expiry_date')
        )
        
        self.positions[position_id] = position
        self._update_position_pnl(position)
        
        logger.info(f"Added position for monitoring: {position_id}")
        return position_id
    
    async def update_position_price(self, instrument_key: str, new_price: float):
        """Update position with new market price"""
        updated_positions = []
        
        for position in self.positions.values():
            if position.instrument_key == instrument_key and position.status == PositionStatus.ACTIVE:
                position.current_price = new_price
                position.last_updated = datetime.now(timezone.utc)
                
                # Update price history
                position.price_history.append((time.time(), new_price))
                
                # Update P&L
                self._update_position_pnl(position)
                
                # Update trailing stop
                new_trailing = self.trailing_stop_manager.update_trailing_stop(position)
                if new_trailing != position.trailing_stop:
                    position.trailing_stop = new_trailing
                    logger.debug(f"Updated trailing stop for {position.position_id}: {new_trailing}")
                
                # Check exit conditions
                exit_reason = self._check_exit_conditions(position)
                if exit_reason:
                    await self._close_position(position, exit_reason)
                
                updated_positions.append(position.position_id)
        
        # Notify callbacks if positions updated
        if updated_positions:
            await self._notify_position_update(updated_positions)
    
    def _update_position_pnl(self, position: PositionSnapshot):
        """Update position P&L calculations"""
        if position.position_type == PositionType.LONG:
            position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity
        else:
            position.unrealized_pnl = (position.entry_price - position.current_price) * position.quantity
        
        position.total_pnl = position.realized_pnl + position.unrealized_pnl
        
        # Update max profit/loss
        if position.unrealized_pnl > position.max_profit:
            position.max_profit = position.unrealized_pnl
        
        if position.unrealized_pnl < position.max_loss:
            position.max_loss = position.unrealized_pnl
        
        # Update duration
        position.duration_minutes = int(
            (datetime.now(timezone.utc) - position.entry_time).total_seconds() / 60
        )
        
        # Add to P&L history
        position.pnl_history.append((time.time(), position.unrealized_pnl))
    
    def _check_exit_conditions(self, position: PositionSnapshot) -> Optional[ExitReason]:
        """Check if position should be closed"""
        current_price = position.current_price
        
        # Check stop loss
        if position.position_type == PositionType.LONG:
            if current_price <= position.stop_loss:
                return ExitReason.STOP_LOSS
            if position.trailing_stop and current_price <= position.trailing_stop:
                return ExitReason.TRAILING_STOP
            if position.target > 0 and current_price >= position.target:
                return ExitReason.TARGET_HIT
        else:  # SHORT
            if current_price >= position.stop_loss:
                return ExitReason.STOP_LOSS
            if position.trailing_stop and current_price >= position.trailing_stop:
                return ExitReason.TRAILING_STOP
            if position.target > 0 and current_price <= position.target:
                return ExitReason.TARGET_HIT
        
        # Check time-based exit (for intraday strategies)
        if position.option_type and position.expiry_date:
            time_to_expiry = (position.expiry_date - datetime.now(timezone.utc)).total_seconds() / 3600
            if time_to_expiry < 0.5:  # 30 minutes to expiry
                return ExitReason.TIME_EXIT
        
        return None
    
    async def _close_position(self, position: PositionSnapshot, exit_reason: ExitReason):
        """Close position and update records"""
        try:
            position.status = PositionStatus.CLOSED
            position.exit_time = datetime.now(timezone.utc)
            position.exit_reason = exit_reason
            position.realized_pnl = position.unrealized_pnl
            position.unrealized_pnl = 0.0
            
            # Move to closed positions
            self.closed_positions[position.position_id] = position
            self.positions.pop(position.position_id, None)
            
            # Update database
            await self.db_service.update_auto_trade_execution(position.position_id, {
                'exit_price': position.current_price,
                'actual_pnl': position.realized_pnl,
                'exit_reason': exit_reason.value,
                'status': 'CLOSED',
                'max_profit_achieved': position.max_profit,
                'max_drawdown': position.max_loss
            })
            
            logger.info(f"Closed position {position.position_id}: {exit_reason.value}, P&L: {position.realized_pnl:.2f}")
            
            # Notify callbacks
            await self._notify_position_closed(position)
            
        except Exception as e:
            logger.error(f"Error closing position {position.position_id}: {e}")
    
    async def _monitor_positions(self):
        """Main position monitoring loop"""
        while self.monitoring_active:
            try:
                # Update Greeks for options positions
                for position in self.positions.values():
                    if position.option_type and position.strike_price:
                        await self._update_position_greeks(position)
                
                # Check risk limits
                await self._check_risk_limits()
                
                await asyncio.sleep(1.0)  # Monitor every second
                
            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(5.0)
    
    async def _update_position_greeks(self, position: PositionSnapshot):
        """Update Greeks for options position"""
        try:
            if not position.expiry_date:
                return
            
            time_to_expiry = (position.expiry_date - datetime.now(timezone.utc)).total_seconds() / (365 * 24 * 3600)
            
            if time_to_expiry > 0:
                greeks = self.greeks_calculator.calculate_greeks(
                    spot_price=position.current_price,
                    strike_price=position.strike_price,
                    time_to_expiry=time_to_expiry,
                    risk_free_rate=0.06,  # 6% risk-free rate
                    volatility=0.20,      # 20% volatility (should be dynamic)
                    option_type=position.option_type
                )
                position.greeks = greeks
                
        except Exception as e:
            logger.error(f"Error updating Greeks for {position.position_id}: {e}")
    
    async def _update_portfolio_metrics(self):
        """Update overall portfolio metrics"""
        while self.monitoring_active:
            try:
                # Calculate total P&L
                total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
                total_realized = sum(pos.realized_pnl for pos in self.closed_positions.values())
                
                self.portfolio_metrics['unrealized_pnl'] = total_unrealized
                self.portfolio_metrics['realized_pnl'] = total_realized
                self.portfolio_metrics['total_pnl'] = total_unrealized + total_realized
                
                # Calculate trade statistics
                closed_trades = list(self.closed_positions.values())
                if closed_trades:
                    winning_trades = [t for t in closed_trades if t.realized_pnl > 0]
                    losing_trades = [t for t in closed_trades if t.realized_pnl < 0]
                    
                    self.portfolio_metrics['total_trades'] = len(closed_trades)
                    self.portfolio_metrics['winning_trades'] = len(winning_trades)
                    self.portfolio_metrics['losing_trades'] = len(losing_trades)
                    self.portfolio_metrics['win_rate'] = len(winning_trades) / len(closed_trades) * 100
                    
                    if winning_trades:
                        self.portfolio_metrics['avg_win'] = sum(t.realized_pnl for t in winning_trades) / len(winning_trades)
                    
                    if losing_trades:
                        self.portfolio_metrics['avg_loss'] = sum(t.realized_pnl for t in losing_trades) / len(losing_trades)
                        
                        if self.portfolio_metrics['avg_loss'] != 0:
                            self.portfolio_metrics['profit_factor'] = abs(
                                self.portfolio_metrics['avg_win'] / self.portfolio_metrics['avg_loss']
                            )
                
                self.last_portfolio_update = datetime.now(timezone.utc)
                await asyncio.sleep(10.0)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error updating portfolio metrics: {e}")
                await asyncio.sleep(30.0)
    
    async def _check_risk_limits(self):
        """Check immediate risk limits and trigger actions if needed"""
        try:
            active_positions = [pos for pos in self.positions.values() if pos.status == PositionStatus.ACTIVE]
            
            if not active_positions:
                return
            
            # Check individual position limits
            for position in active_positions:
                # Check stop loss
                if (position.position_type == PositionType.LONG and 
                    position.current_price <= position.stop_loss):
                    await self._trigger_exit_signal(position.position_id, ExitReason.STOP_LOSS)
                    
                elif (position.position_type == PositionType.SHORT and 
                      position.current_price >= position.stop_loss):
                    await self._trigger_exit_signal(position.position_id, ExitReason.STOP_LOSS)
                
                # Check max loss per position
                max_loss_per_position = self.risk_limits.get('max_loss_per_position', 10000)
                if position.unrealized_pnl < -max_loss_per_position:
                    await self._trigger_exit_signal(position.position_id, ExitReason.RISK_LIMIT)
            
            # Check portfolio level limits
            total_pnl = sum(pos.unrealized_pnl for pos in active_positions)
            max_daily_loss = self.risk_limits.get('max_daily_loss', 50000)
            
            if total_pnl < -max_daily_loss:
                logger.error(f"❌ Daily loss limit breached: {total_pnl}")
                await self._trigger_emergency_exit("DAILY_LOSS_LIMIT")
                
        except Exception as e:
            logger.error(f"❌ Error checking risk limits: {e}")
    
    async def _trigger_exit_signal(self, position_id: str, reason: ExitReason):
        """Trigger exit signal for a specific position"""
        try:
            if position_id not in self.positions:
                return
                
            position = self.positions[position_id]
            logger.warning(f"⚠️ Exit signal triggered for {position.symbol}: {reason.value}")
            
            # Update position status
            position.status = PositionStatus.SUSPENDED
            position.exit_reason = reason
            
            # Trigger exit callbacks
            for callback in self.exit_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(position_id, reason)
                    else:
                        callback(position_id, reason)
                except Exception as e:
                    logger.error(f"❌ Error in exit callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error triggering exit signal: {e}")
    
    async def _trigger_emergency_exit(self, reason: str):
        """Trigger emergency exit for all positions"""
        try:
            logger.error(f"🚨 EMERGENCY EXIT TRIGGERED: {reason}")
            
            active_positions = [pos for pos in self.positions.values() if pos.status == PositionStatus.ACTIVE]
            
            for position in active_positions:
                await self._trigger_exit_signal(position.position_id, ExitReason.EMERGENCY_EXIT)
                
        except Exception as e:
            logger.error(f"❌ Error in emergency exit: {e}")
    
    async def _monitor_risk_limits(self):
        """Monitor portfolio risk limits"""
        while self.monitoring_active:
            try:
                # Calculate portfolio heat
                portfolio_value = 1000000.0  # Mock portfolio value
                active_positions = [pos for pos in self.positions.values() if pos.status == PositionStatus.ACTIVE]
                
                heat_metrics = self.portfolio_monitor.calculate_portfolio_heat(active_positions, portfolio_value)
                
                # Check risk limits
                if heat_metrics['total_heat'] > self.risk_limits['max_portfolio_heat']:
                    await self._trigger_risk_limit_breach('PORTFOLIO_HEAT', heat_metrics['total_heat'])
                
                # Check daily loss limit
                daily_loss = sum(pos.unrealized_pnl for pos in active_positions if pos.unrealized_pnl < 0)
                if abs(daily_loss) > self.risk_limits['max_daily_loss']:
                    await self._trigger_risk_limit_breach('DAILY_LOSS', abs(daily_loss))
                
                await asyncio.sleep(30.0)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring risk limits: {e}")
                await asyncio.sleep(60.0)
    
    async def _trigger_risk_limit_breach(self, limit_type: str, current_value: float):
        """Handle risk limit breach"""
        logger.critical(f"Risk limit breach: {limit_type} = {current_value}")
        
        # Notify risk callbacks
        for callback in self.risk_callbacks:
            try:
                await callback(limit_type, current_value)
            except Exception as e:
                logger.error(f"Error in risk callback: {e}")
    
    async def _notify_position_update(self, position_ids: List[str]):
        """Notify about position updates"""
        for callback in self.position_callbacks:
            try:
                await callback('POSITION_UPDATED', position_ids)
            except Exception as e:
                logger.error(f"Error in position callback: {e}")
    
    async def _notify_position_closed(self, position: PositionSnapshot):
        """Notify about position closure"""
        for callback in self.position_callbacks:
            try:
                await callback('POSITION_CLOSED', position.position_id)
            except Exception as e:
                logger.error(f"Error in position callback: {e}")
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get comprehensive position summary"""
        active_positions = [pos for pos in self.positions.values() if pos.status == PositionStatus.ACTIVE]
        
        return {
            'active_positions': len(active_positions),
            'total_positions': len(self.positions) + len(self.closed_positions),
            'portfolio_metrics': self.portfolio_metrics.copy(),
            'positions': [
                {
                    'position_id': pos.position_id,
                    'symbol': pos.symbol,
                    'position_type': pos.position_type.value,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'unrealized_pnl': pos.unrealized_pnl,
                    'max_profit': pos.max_profit,
                    'max_loss': pos.max_loss,
                    'duration_minutes': pos.duration_minutes,
                    'greeks': asdict(pos.greeks) if pos.greeks else None
                }
                for pos in active_positions
            ]
        }
    
    def add_position_callback(self, callback: Callable):
        """Add position update callback"""
        self.position_callbacks.append(callback)
    
    def add_risk_callback(self, callback: Callable):
        """Add risk limit callback"""
        self.risk_callbacks.append(callback)
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down position monitor...")
        self.monitoring_active = False
        
        # Close all active positions
        for position in list(self.positions.values()):
            if position.status == PositionStatus.ACTIVE:
                await self._close_position(position, ExitReason.EMERGENCY_EXIT)
        
        logger.info("Position monitor shutdown complete")