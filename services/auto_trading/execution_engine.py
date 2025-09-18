"""
Auto-Trade Execution Engine with Live Feed Integration

Comprehensive execution engine that processes selected stocks/indices,
executes trading strategies using live feed data, manages positions,
and implements risk management with real-time PnL tracking.

Features:
- Strategy-based trade execution
- Live feed data integration via Kafka
- Real-time position monitoring
- Dynamic stop loss and target management
- Risk management and position sizing
- PnL calculation and tracking
- Trade lifecycle management

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import json
import uuid

import numpy as np
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import TradeExecution, Position, User, BrokerConfig

from .modular_stock_selector import SelectionResult, MarketCondition

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    """Trade direction types"""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"
    BRACKET = "BRACKET"


class OrderStatus(Enum):
    """Order status types"""
    PENDING = "PENDING"
    PLACED = "PLACED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class PositionStatus(Enum):
    """Position status types"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    STOPPED_OUT = "STOPPED_OUT"
    TARGET_HIT = "TARGET_HIT"


class TradeStrategy(Enum):
    """Trading strategy types"""
    MOMENTUM_LONG = "MOMENTUM_LONG"
    MOMENTUM_SHORT = "MOMENTUM_SHORT"
    BREAKOUT_LONG = "BREAKOUT_LONG"
    BREAKOUT_SHORT = "BREAKOUT_SHORT"
    GAP_FILL = "GAP_FILL"
    GAP_CONTINUATION = "GAP_CONTINUATION"
    MEAN_REVERSION = "MEAN_REVERSION"
    TREND_FOLLOWING = "TREND_FOLLOWING"
    VOLATILITY_STRADDLE = "VOLATILITY_STRADDLE"
    PAIRS_TRADING = "PAIRS_TRADING"


@dataclass
class LiveFeedData:
    """Live feed data structure"""
    symbol: str
    instrument_key: str
    current_price: float
    change_percent: float
    volume: int
    bid_price: float
    ask_price: float
    high: float
    low: float
    open_price: float
    previous_close: float
    timestamp: datetime
    
    # Derived metrics
    spread: float = 0.0
    volume_ratio: float = 1.0
    volatility: float = 0.0


@dataclass
class TradeOrder:
    """Trade order details"""
    order_id: str
    symbol: str
    instrument_key: str
    direction: TradeDirection
    order_type: OrderType
    quantity: int
    price: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    strategy: TradeStrategy
    created_at: datetime
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    
    # Risk management
    max_loss: float = 0.0
    risk_amount: float = 0.0
    position_size_factor: float = 1.0


@dataclass
class ActivePosition:
    """Active trading position"""
    position_id: str
    symbol: str
    instrument_key: str
    direction: TradeDirection
    strategy: TradeStrategy
    
    # Position details
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float
    target_price: float
    
    # PnL tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Position management
    entry_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    status: PositionStatus = PositionStatus.OPEN
    
    # Risk metrics
    current_risk: float = 0.0
    max_risk: float = 0.0
    risk_reward_ratio: float = 0.0
    
    # Trailing stop
    trailing_stop_enabled: bool = False
    trailing_stop_percent: float = 0.0
    highest_price: float = 0.0  # For long positions
    lowest_price: float = 0.0   # For short positions


@dataclass
class TradingSignal:
    """Trading signal from strategy analysis"""
    symbol: str
    instrument_key: str
    signal_type: str  # BUY/SELL/HOLD
    strategy: TradeStrategy
    confidence: float
    entry_price: float
    stop_loss: float
    target_price: float
    quantity: int
    signal_time: datetime
    
    # Signal context
    market_condition: MarketCondition
    technical_factors: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)


class AutoTradeExecutionEngine:
    """
    Comprehensive Auto-Trade Execution Engine
    
    Features:
    - Live feed data integration via Kafka
    - Multi-strategy trade execution
    - Real-time position monitoring
    - Dynamic risk management
    - Trailing stop loss implementation
    - Real-time PnL calculation
    - Trade lifecycle management
    - Performance analytics
    """
    
    def __init__(
        self,
        user_id: int,
        max_positions: int = 5,
        max_risk_per_trade: float = 2.0,  # 2% of capital per trade
        trailing_stop_enabled: bool = True
    ):
        self.user_id = user_id
        self.max_positions = max_positions
        self.max_risk_per_trade = max_risk_per_trade
        self.trailing_stop_enabled = trailing_stop_enabled
        
        # Trading state
        self.active_positions: Dict[str, ActivePosition] = {}
        self.pending_orders: Dict[str, TradeOrder] = {}
        self.completed_trades: List[Dict[str, Any]] = []
        
        # Live feed integration
        self.live_feed_cache: Dict[str, LiveFeedData] = {}
        self.subscribed_instruments: Set[str] = set()
        
        # Risk management
        self.total_capital: float = 100000.0  # Default capital
        self.available_capital: float = 100000.0
        self.used_capital: float = 0.0
        self.daily_pnl: float = 0.0
        self.max_daily_loss: float = 5000.0  # Max daily loss limit
        
        # Strategy processors
        self.strategy_processors = {
            TradeStrategy.MOMENTUM_LONG: self._process_momentum_long,
            TradeStrategy.MOMENTUM_SHORT: self._process_momentum_short,
            TradeStrategy.BREAKOUT_LONG: self._process_breakout_long,
            TradeStrategy.BREAKOUT_SHORT: self._process_breakout_short,
            TradeStrategy.GAP_FILL: self._process_gap_fill,
            TradeStrategy.GAP_CONTINUATION: self._process_gap_continuation,
            TradeStrategy.MEAN_REVERSION: self._process_mean_reversion,
            TradeStrategy.TREND_FOLLOWING: self._process_trend_following,
            TradeStrategy.VOLATILITY_STRADDLE: self._process_volatility_straddle
        }
        
        # Performance tracking
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
        
        logger.info(f"AutoTradeExecutionEngine initialized for user {user_id}")
    
    async def initialize_trading_session(self) -> bool:
        """Initialize trading session with capital and broker setup"""
        try:
            # Load user trading configuration
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == self.user_id).first()
                if not user:
                    logger.error(f"User {self.user_id} not found")
                    return False
                
                # Load capital from configuration
                # This would integrate with user trading configuration
                self.total_capital = 100000.0  # Default for now
                self.available_capital = self.total_capital
                
                logger.info(f"Trading session initialized with capital: ₹{self.total_capital:,.2f}")
                return True
                
        except Exception as e:
            logger.error(f"Trading session initialization error: {e}")
            return False
    
    async def process_selected_stocks(
        self, 
        selected_stocks: List[SelectionResult]
    ) -> List[TradingSignal]:
        """Process selected stocks and generate trading signals"""
        try:
            trading_signals = []
            
            for selection in selected_stocks:
                # Subscribe to live feed for this instrument
                await self._subscribe_to_live_feed(selection.instrument_key)
                
                # Generate trading signal based on selection
                signal = await self._generate_trading_signal(selection)
                if signal:
                    trading_signals.append(signal)
            
            logger.info(f"Generated {len(trading_signals)} trading signals")
            return trading_signals
            
        except Exception as e:
            logger.error(f"Selected stocks processing error: {e}")
            return []
    
    async def _subscribe_to_live_feed(self, instrument_key: str) -> None:
        """Subscribe to live feed data for instrument"""
        try:
            if instrument_key not in self.subscribed_instruments:
                self.subscribed_instruments.add(instrument_key)
                
                # This would integrate with Kafka subscription
                # For now, we'll simulate the subscription
                logger.debug(f"Subscribed to live feed for {instrument_key}")
                
        except Exception as e:
            logger.error(f"Live feed subscription error: {e}")
    
    async def _generate_trading_signal(
        self, 
        selection: SelectionResult
    ) -> Optional[TradingSignal]:
        """Generate trading signal from selection result"""
        try:
            # Determine signal type based on expected direction
            signal_type = "HOLD"
            if selection.expected_direction == "BULLISH":
                signal_type = "BUY"
            elif selection.expected_direction == "BEARISH":
                signal_type = "SELL"
            
            # Map primary strategy to trade strategy
            trade_strategy = self._map_to_trade_strategy(
                selection.primary_strategy, 
                selection.expected_direction
            )
            
            return TradingSignal(
                symbol=selection.symbol,
                instrument_key=selection.instrument_key,
                signal_type=signal_type,
                strategy=trade_strategy,
                confidence=selection.confidence_level,
                entry_price=selection.current_price,
                stop_loss=selection.stop_loss,
                target_price=selection.target_price,
                quantity=selection.position_size,
                signal_time=datetime.now(),
                market_condition=selection.market_condition,
                technical_factors=selection.selection_reasons
            )
            
        except Exception as e:
            logger.error(f"Trading signal generation error: {e}")
            return None
    
    def _map_to_trade_strategy(
        self, 
        primary_strategy: str, 
        direction: str
    ) -> TradeStrategy:
        """Map selection strategy to trade strategy"""
        strategy_mapping = {
            ("BREAKOUT_MOMENTUM", "BULLISH"): TradeStrategy.BREAKOUT_LONG,
            ("BREAKOUT_MOMENTUM", "BEARISH"): TradeStrategy.BREAKOUT_SHORT,
            ("GAP_TRADING", "BULLISH"): TradeStrategy.GAP_CONTINUATION,
            ("GAP_TRADING", "BEARISH"): TradeStrategy.GAP_FILL,
            ("TREND_FOLLOWING", "BULLISH"): TradeStrategy.MOMENTUM_LONG,
            ("TREND_FOLLOWING", "BEARISH"): TradeStrategy.MOMENTUM_SHORT,
            ("VOLATILITY_TRADING", "NEUTRAL"): TradeStrategy.VOLATILITY_STRADDLE,
            ("MARKET_NEUTRAL", "NEUTRAL"): TradeStrategy.MEAN_REVERSION
        }
        
        return strategy_mapping.get(
            (primary_strategy, direction), 
            TradeStrategy.TREND_FOLLOWING
        )
    
    async def execute_trading_signals(
        self, 
        signals: List[TradingSignal]
    ) -> List[TradeOrder]:
        """Execute trading signals as market orders"""
        try:
            executed_orders = []
            
            for signal in signals:
                # Check if we can place more trades
                if len(self.active_positions) >= self.max_positions:
                    logger.warning(f"Maximum positions ({self.max_positions}) reached")
                    break
                
                # Check daily loss limit
                if self.daily_pnl <= -self.max_daily_loss:
                    logger.warning(f"Daily loss limit (₹{self.max_daily_loss}) reached")
                    break
                
                # Execute the signal
                order = await self._execute_signal(signal)
                if order:
                    executed_orders.append(order)
            
            logger.info(f"Executed {len(executed_orders)} trading orders")
            return executed_orders
            
        except Exception as e:
            logger.error(f"Trading signals execution error: {e}")
            return []
    
    async def _execute_signal(self, signal: TradingSignal) -> Optional[TradeOrder]:
        """Execute a single trading signal"""
        try:
            # Validate signal
            if signal.signal_type == "HOLD":
                return None
            
            # Calculate position size based on risk
            position_size = self._calculate_position_size(signal)
            
            # Determine trade direction
            direction = TradeDirection.LONG if signal.signal_type == "BUY" else TradeDirection.SHORT
            
            # Create trade order
            order = TradeOrder(
                order_id=f"ORDER_{uuid.uuid4().hex[:8]}",
                symbol=signal.symbol,
                instrument_key=signal.instrument_key,
                direction=direction,
                order_type=OrderType.MARKET,
                quantity=position_size,
                price=signal.entry_price,
                stop_loss=signal.stop_loss,
                target=signal.target_price,
                strategy=signal.strategy,
                created_at=datetime.now(),
                max_loss=abs(signal.entry_price - signal.stop_loss) * position_size,
                risk_amount=self._calculate_risk_amount(signal, position_size)
            )
            
            # Place the order (simulate for now)
            success = await self._place_order(order)
            if success:
                self.pending_orders[order.order_id] = order
                logger.info(f"Order placed: {order.symbol} {order.direction.value} {order.quantity}")
                return order
            
            return None
            
        except Exception as e:
            logger.error(f"Signal execution error: {e}")
            return None
    
    def _calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate appropriate position size based on risk management"""
        try:
            # Risk-based position sizing
            risk_per_share = abs(signal.entry_price - signal.stop_loss)
            max_risk_amount = self.available_capital * (self.max_risk_per_trade / 100)
            
            if risk_per_share > 0:
                max_shares = int(max_risk_amount / risk_per_share)
                
                # Apply confidence factor
                confidence_factor = min(signal.confidence, 1.0)
                adjusted_shares = int(max_shares * confidence_factor)
                
                # Ensure minimum position size
                return max(adjusted_shares, 1)
            
            return signal.quantity  # Fallback to signal quantity
            
        except Exception as e:
            logger.error(f"Position size calculation error: {e}")
            return 1
    
    def _calculate_risk_amount(self, signal: TradingSignal, position_size: int) -> float:
        """Calculate total risk amount for the trade"""
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        return risk_per_share * position_size
    
    async def _place_order(self, order: TradeOrder) -> bool:
        """Place order with broker (simulated for now)"""
        try:
            # This would integrate with actual broker API
            # For now, simulate immediate fill
            await asyncio.sleep(0.1)  # Simulate order processing delay
            
            # Simulate order fill
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.avg_fill_price = order.price or 0.0
            
            # Create position from filled order
            await self._create_position_from_order(order)
            
            return True
            
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return False
    
    async def _create_position_from_order(self, order: TradeOrder) -> None:
        """Create active position from filled order"""
        try:
            position = ActivePosition(
                position_id=f"POS_{uuid.uuid4().hex[:8]}",
                symbol=order.symbol,
                instrument_key=order.instrument_key,
                direction=order.direction,
                strategy=order.strategy,
                quantity=order.filled_quantity,
                entry_price=order.avg_fill_price,
                current_price=order.avg_fill_price,
                stop_loss=order.stop_loss or 0.0,
                target_price=order.target or 0.0,
                max_risk=order.risk_amount,
                trailing_stop_enabled=self.trailing_stop_enabled,
                trailing_stop_percent=2.0,  # 2% trailing stop
                highest_price=order.avg_fill_price,
                lowest_price=order.avg_fill_price
            )
            
            # Calculate initial risk-reward ratio
            if position.stop_loss > 0:
                risk = abs(position.entry_price - position.stop_loss)
                reward = abs(position.target_price - position.entry_price)
                position.risk_reward_ratio = reward / risk if risk > 0 else 0
            
            self.active_positions[position.position_id] = position
            
            # Update capital allocation
            position_value = position.entry_price * position.quantity
            self.used_capital += position_value
            self.available_capital -= position_value
            
            logger.info(f"Position created: {position.symbol} {position.direction.value}")
            
        except Exception as e:
            logger.error(f"Position creation error: {e}")
    
    async def process_live_feed_update(self, feed_data: Dict[str, Any]) -> None:
        """Process live feed data update for position monitoring"""
        try:
            feeds = feed_data.get('feeds', {})
            
            for instrument_key, raw_feed in feeds.items():
                if instrument_key in self.subscribed_instruments:
                    # Parse live feed data
                    live_data = self._parse_live_feed_data(instrument_key, raw_feed)
                    if live_data:
                        self.live_feed_cache[instrument_key] = live_data
                        
                        # Update positions for this instrument
                        await self._update_positions_for_instrument(instrument_key, live_data)
            
        except Exception as e:
            logger.error(f"Live feed processing error: {e}")
    
    def _parse_live_feed_data(
        self, 
        instrument_key: str, 
        raw_feed: Dict[str, Any]
    ) -> Optional[LiveFeedData]:
        """Parse raw live feed data into structured format"""
        try:
            # Extract data based on live feed format
            if 'ltp' in raw_feed:
                # Normalized format
                return LiveFeedData(
                    symbol=self._extract_symbol_from_key(instrument_key),
                    instrument_key=instrument_key,
                    current_price=float(raw_feed.get('ltp', 0)),
                    change_percent=float(raw_feed.get('change_percent', 0)),
                    volume=int(raw_feed.get('volume', 0)),
                    bid_price=float(raw_feed.get('bid_price', 0)),
                    ask_price=float(raw_feed.get('ask_price', 0)),
                    high=float(raw_feed.get('high', 0)),
                    low=float(raw_feed.get('low', 0)),
                    open_price=float(raw_feed.get('open', 0)),
                    previous_close=float(raw_feed.get('previous_close', 0)),
                    timestamp=datetime.now(),
                    spread=float(raw_feed.get('ask_price', 0)) - float(raw_feed.get('bid_price', 0))
                )
            
            # Raw Upstox format parsing
            full_feed = raw_feed.get('fullFeed', {})
            market_data = full_feed.get('marketFF') or full_feed.get('indexFF')
            
            if not market_data:
                return None
            
            ltpc = market_data.get('ltpc', {})
            ltp = float(ltpc.get('ltp', 0))
            previous_close = float(ltpc.get('cp', 0))
            
            # Extract OHLC
            ohlc_data = market_data.get('marketOHLC', {}).get('ohlc', [])
            high = low = open_price = ltp
            
            for ohlc in ohlc_data:
                if ohlc.get('interval') == '1d':
                    high = float(ohlc.get('high', ltp))
                    low = float(ohlc.get('low', ltp))
                    open_price = float(ohlc.get('open', ltp))
                    break
            
            # Extract bid/ask
            bid_ask = market_data.get('marketLevel', {}).get('bidAskQuote', [])
            bid_price = ask_price = ltp
            if bid_ask:
                best_quote = bid_ask[0]
                bid_price = float(best_quote.get('bidP', ltp))
                ask_price = float(best_quote.get('askP', ltp))
            
            change_percent = ((ltp - previous_close) / previous_close * 100) if previous_close > 0 else 0
            volume = int(market_data.get('vtt', 0))
            
            return LiveFeedData(
                symbol=self._extract_symbol_from_key(instrument_key),
                instrument_key=instrument_key,
                current_price=ltp,
                change_percent=change_percent,
                volume=volume,
                bid_price=bid_price,
                ask_price=ask_price,
                high=high,
                low=low,
                open_price=open_price,
                previous_close=previous_close,
                timestamp=datetime.now(),
                spread=ask_price - bid_price
            )
            
        except Exception as e:
            logger.error(f"Live feed parsing error: {e}")
            return None
    
    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        return instrument_key.replace('|', '_').replace('NSE_EQ|', '').replace('NSE_INDEX|', '')
    
    async def _update_positions_for_instrument(
        self, 
        instrument_key: str, 
        live_data: LiveFeedData
    ) -> None:
        """Update all positions for the given instrument"""
        try:
            for position in self.active_positions.values():
                if position.instrument_key == instrument_key and position.status == PositionStatus.OPEN:
                    await self._update_position(position, live_data)
                    
        except Exception as e:
            logger.error(f"Position update error: {e}")
    
    async def _update_position(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Update individual position with live data"""
        try:
            # Update current price
            position.current_price = live_data.current_price
            position.last_update = datetime.now()
            
            # Calculate PnL
            if position.direction == TradeDirection.LONG:
                position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity
            else:  # SHORT
                position.unrealized_pnl = (position.entry_price - position.current_price) * position.quantity
            
            position.total_pnl = position.realized_pnl + position.unrealized_pnl
            position.pnl_percent = (position.unrealized_pnl / (position.entry_price * position.quantity)) * 100
            
            # Update risk metrics
            position.current_risk = abs(position.current_price - position.stop_loss) * position.quantity
            
            # Update highest/lowest prices for trailing stop
            if position.direction == TradeDirection.LONG:
                if position.current_price > position.highest_price:
                    position.highest_price = position.current_price
            else:  # SHORT
                if position.current_price < position.lowest_price or position.lowest_price == 0:
                    position.lowest_price = position.current_price
            
            # Process strategy-specific logic
            await self._process_strategy_logic(position, live_data)
            
            # Check stop loss and target conditions
            await self._check_exit_conditions(position)
            
            # Update trailing stop if enabled
            if position.trailing_stop_enabled:
                await self._update_trailing_stop(position)
            
        except Exception as e:
            logger.error(f"Position update error: {e}")
    
    async def _process_strategy_logic(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process strategy-specific logic for position management"""
        try:
            processor = self.strategy_processors.get(position.strategy)
            if processor:
                await processor(position, live_data)
                
        except Exception as e:
            logger.error(f"Strategy processing error: {e}")
    
    # Strategy-specific processors
    async def _process_momentum_long(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process momentum long strategy"""
        # Tighten stop loss as position moves in favor
        if position.current_price > position.entry_price * 1.02:  # 2% profit
            new_stop = max(position.stop_loss, position.entry_price * 1.01)  # Break-even + 1%
            position.stop_loss = new_stop
    
    async def _process_momentum_short(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process momentum short strategy"""
        # Tighten stop loss as position moves in favor
        if position.current_price < position.entry_price * 0.98:  # 2% profit
            new_stop = min(position.stop_loss, position.entry_price * 0.99)  # Break-even - 1%
            position.stop_loss = new_stop
    
    async def _process_breakout_long(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process breakout long strategy"""
        # Aggressive trailing stop for breakout trades
        if position.current_price > position.entry_price * 1.03:  # 3% profit
            position.trailing_stop_percent = 1.5  # Tighter trailing stop
    
    async def _process_breakout_short(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process breakout short strategy"""
        # Aggressive trailing stop for breakout trades
        if position.current_price < position.entry_price * 0.97:  # 3% profit
            position.trailing_stop_percent = 1.5  # Tighter trailing stop
    
    async def _process_gap_fill(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process gap fill strategy"""
        # Quick profit taking for gap fill trades
        if abs(position.pnl_percent) >= 1.5:  # 1.5% profit
            await self._close_position(position, "GAP_FILL_TARGET")
    
    async def _process_gap_continuation(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process gap continuation strategy"""
        # Let winners run for gap continuation
        position.trailing_stop_percent = 3.0  # Wider trailing stop
    
    async def _process_mean_reversion(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process mean reversion strategy"""
        # Quick profit taking for mean reversion
        if abs(position.pnl_percent) >= 1.0:  # 1% profit
            await self._close_position(position, "MEAN_REVERSION_TARGET")
    
    async def _process_trend_following(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process trend following strategy"""
        # Standard trailing stop management
        pass  # Default trailing stop logic applies
    
    async def _process_volatility_straddle(
        self, 
        position: ActivePosition, 
        live_data: LiveFeedData
    ) -> None:
        """Process volatility straddle strategy"""
        # Complex straddle management would go here
        pass
    
    async def _check_exit_conditions(self, position: ActivePosition) -> None:
        """Check if position should be closed due to stop loss or target"""
        try:
            if position.direction == TradeDirection.LONG:
                # Check stop loss
                if position.current_price <= position.stop_loss:
                    await self._close_position(position, "STOP_LOSS")
                    return
                
                # Check target
                if position.target_price > 0 and position.current_price >= position.target_price:
                    await self._close_position(position, "TARGET_HIT")
                    return
            
            else:  # SHORT
                # Check stop loss
                if position.current_price >= position.stop_loss:
                    await self._close_position(position, "STOP_LOSS")
                    return
                
                # Check target
                if position.target_price > 0 and position.current_price <= position.target_price:
                    await self._close_position(position, "TARGET_HIT")
                    return
                    
        except Exception as e:
            logger.error(f"Exit conditions check error: {e}")
    
    async def _update_trailing_stop(self, position: ActivePosition) -> None:
        """Update trailing stop loss"""
        try:
            if not position.trailing_stop_enabled or position.trailing_stop_percent <= 0:
                return
            
            if position.direction == TradeDirection.LONG:
                # Calculate trailing stop from highest price
                trailing_stop_price = position.highest_price * (1 - position.trailing_stop_percent / 100)
                # Only move stop loss up, never down
                if trailing_stop_price > position.stop_loss:
                    position.stop_loss = trailing_stop_price
                    
            else:  # SHORT
                # Calculate trailing stop from lowest price
                trailing_stop_price = position.lowest_price * (1 + position.trailing_stop_percent / 100)
                # Only move stop loss down, never up
                if trailing_stop_price < position.stop_loss or position.stop_loss == 0:
                    position.stop_loss = trailing_stop_price
                    
        except Exception as e:
            logger.error(f"Trailing stop update error: {e}")
    
    async def _close_position(self, position: ActivePosition, reason: str) -> None:
        """Close position and update performance metrics"""
        try:
            # Update position status
            if reason == "STOP_LOSS":
                position.status = PositionStatus.STOPPED_OUT
            elif reason == "TARGET_HIT":
                position.status = PositionStatus.TARGET_HIT
            else:
                position.status = PositionStatus.CLOSED
            
            # Realize PnL
            position.realized_pnl = position.unrealized_pnl
            position.unrealized_pnl = 0.0
            
            # Update capital
            position_value = position.current_price * position.quantity
            self.used_capital -= (position.entry_price * position.quantity)
            self.available_capital += position_value
            
            # Update daily PnL
            self.daily_pnl += position.realized_pnl
            
            # Update performance metrics
            self._update_performance_metrics(position)
            
            # Store completed trade
            trade_record = {
                'symbol': position.symbol,
                'direction': position.direction.value,
                'strategy': position.strategy.value,
                'entry_price': position.entry_price,
                'exit_price': position.current_price,
                'quantity': position.quantity,
                'pnl': position.realized_pnl,
                'pnl_percent': position.pnl_percent,
                'hold_time': (position.last_update - position.entry_time).total_seconds() / 60,  # minutes
                'exit_reason': reason,
                'timestamp': datetime.now()
            }
            self.completed_trades.append(trade_record)
            
            logger.info(
                f"Position closed: {position.symbol} {position.direction.value} "
                f"PnL: ₹{position.realized_pnl:.2f} ({position.pnl_percent:.2f}%) "
                f"Reason: {reason}"
            )
            
        except Exception as e:
            logger.error(f"Position closing error: {e}")
    
    def _update_performance_metrics(self, position: ActivePosition) -> None:
        """Update overall performance metrics"""
        try:
            self.performance_metrics['total_trades'] += 1
            
            if position.realized_pnl > 0:
                self.performance_metrics['winning_trades'] += 1
                # Update average win
                current_avg_win = self.performance_metrics['avg_win']
                winning_trades = self.performance_metrics['winning_trades']
                self.performance_metrics['avg_win'] = (
                    (current_avg_win * (winning_trades - 1) + position.realized_pnl) / winning_trades
                )
            else:
                self.performance_metrics['losing_trades'] += 1
                # Update average loss
                current_avg_loss = self.performance_metrics['avg_loss']
                losing_trades = self.performance_metrics['losing_trades']
                self.performance_metrics['avg_loss'] = (
                    (current_avg_loss * (losing_trades - 1) + abs(position.realized_pnl)) / losing_trades
                )
            
            # Calculate win rate
            total_trades = self.performance_metrics['total_trades']
            winning_trades = self.performance_metrics['winning_trades']
            self.performance_metrics['win_rate'] = (winning_trades / total_trades) * 100
            
            # Calculate profit factor
            total_profits = self.performance_metrics['avg_win'] * winning_trades
            total_losses = self.performance_metrics['avg_loss'] * self.performance_metrics['losing_trades']
            self.performance_metrics['profit_factor'] = (
                total_profits / total_losses if total_losses > 0 else 0
            )
            
        except Exception as e:
            logger.error(f"Performance metrics update error: {e}")
    
    def get_active_positions_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all active positions"""
        positions_summary = []
        
        for position in self.active_positions.values():
            if position.status == PositionStatus.OPEN:
                positions_summary.append({
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'direction': position.direction.value,
                    'strategy': position.strategy.value,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'pnl_percent': position.pnl_percent,
                    'stop_loss': position.stop_loss,
                    'target_price': position.target_price,
                    'risk_reward_ratio': position.risk_reward_ratio,
                    'entry_time': position.entry_time.isoformat(),
                    'hold_time_minutes': (datetime.now() - position.entry_time).total_seconds() / 60
                })
        
        return positions_summary
    
    def get_trading_performance(self) -> Dict[str, Any]:
        """Get comprehensive trading performance metrics"""
        return {
            'capital_summary': {
                'total_capital': self.total_capital,
                'available_capital': self.available_capital,
                'used_capital': self.used_capital,
                'capital_utilization_percent': (self.used_capital / self.total_capital) * 100
            },
            'daily_summary': {
                'daily_pnl': self.daily_pnl,
                'daily_pnl_percent': (self.daily_pnl / self.total_capital) * 100,
                'active_positions': len([p for p in self.active_positions.values() if p.status == PositionStatus.OPEN]),
                'completed_trades_today': len(self.completed_trades)
            },
            'performance_metrics': self.performance_metrics,
            'risk_metrics': {
                'max_daily_loss': self.max_daily_loss,
                'remaining_daily_risk': self.max_daily_loss + self.daily_pnl,
                'max_positions': self.max_positions,
                'available_position_slots': self.max_positions - len(self.active_positions)
            }
        }


# Singleton instance
_auto_trade_execution_engine: Optional[AutoTradeExecutionEngine] = None


def get_auto_trade_execution_engine(
    user_id: int,
    max_positions: int = 5,
    max_risk_per_trade: float = 2.0
) -> AutoTradeExecutionEngine:
    """Get auto-trade execution engine instance"""
    global _auto_trade_execution_engine
    if _auto_trade_execution_engine is None:
        _auto_trade_execution_engine = AutoTradeExecutionEngine(
            user_id=user_id,
            max_positions=max_positions,
            max_risk_per_trade=max_risk_per_trade
        )
    return _auto_trade_execution_engine


# Export main classes
__all__ = [
    "AutoTradeExecutionEngine",
    "TradeOrder",
    "ActivePosition",
    "TradingSignal",
    "LiveFeedData",
    "TradeDirection",
    "TradeStrategy",
    "PositionStatus",
    "get_auto_trade_execution_engine"
]