"""
Auto Trading Position Monitor with Kafka Integration

Real-time position monitoring and PnL calculation for auto trading system.
Integrates with Kafka for live data streaming and SSE for UI updates.

Author: Trading System  
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from services.hft.consumers import BaseHFTConsumer
from services.hft.producer import get_hft_producer
from services.sse.sse_manager import get_sse_manager, SSEChannel

logger = logging.getLogger(__name__)


class PositionType(Enum):
    """Position types for options trading"""
    LONG_CALL = "long_call"
    SHORT_CALL = "short_call"
    LONG_PUT = "long_put"
    SHORT_PUT = "short_put"


class PositionStatus(Enum):
    """Position status states"""
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"
    ASSIGNED = "assigned"
    EXERCISED = "exercised"


@dataclass
class Position:
    """Position data structure"""
    position_id: str
    user_id: int
    session_id: str
    instrument_key: str
    symbol: str
    position_type: PositionType
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    entry_time: datetime
    
    # PnL calculations
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    
    # Risk metrics
    max_profit: Decimal = Decimal('0')
    max_loss: Decimal = Decimal('0')
    break_even_price: Decimal = Decimal('0')
    
    # Status and metadata
    status: PositionStatus = PositionStatus.ACTIVE
    last_update: datetime = field(default_factory=datetime.now)
    
    def update_price(self, new_price: Decimal) -> None:
        """Update position with new market price"""
        self.current_price = new_price
        self.last_update = datetime.now()
        
        # Calculate unrealized PnL
        if self.position_type in [PositionType.LONG_CALL, PositionType.LONG_PUT]:
            # Long positions: profit when price increases above entry
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        else:
            # Short positions: profit when price decreases below entry
            self.unrealized_pnl = (self.entry_price - new_price) * self.quantity
            
        self.total_pnl = self.unrealized_pnl + self.realized_pnl
        
        # Update max profit/loss tracking
        if self.total_pnl > self.max_profit:
            self.max_profit = self.total_pnl
        if self.total_pnl < self.max_loss:
            self.max_loss = self.total_pnl


class AutoTradingPositionMonitor(BaseHFTConsumer):
    """
    Real-time position monitor with Kafka integration
    
    Monitors all active positions, calculates live PnL, and streams
    updates to the UI via SSE channels.
    """
    
    def __init__(self):
        super().__init__(
            service_name="auto_trading_position_monitor",
            topics=["hft.analytics.market_data", "hft.trading.executions"],
            group_id="position_monitor_group"
        )
        
        # Dependencies
        self._kafka_producer = None
        self._sse_manager = None
        
        # Position tracking
        self._active_positions: Dict[str, Position] = {}
        self._user_positions: Dict[int, Set[str]] = {}
        self._session_positions: Dict[str, Set[str]] = {}
        
        # Performance metrics
        self._total_positions_monitored = 0
        self._pnl_updates_sent = 0
        self._last_update_time = datetime.now()
        
        # Configuration
        self._update_interval_ms = 100  # 100ms updates for real-time
        self._pnl_threshold = Decimal('0.01')  # Minimum PnL change to broadcast
        
        logger.info("📊 Auto Trading Position Monitor initialized")
    
    async def initialize_dependencies(self) -> None:
        """Initialize Kafka and SSE dependencies"""
        try:
            # Initialize Kafka producer
            self._kafka_producer = await get_hft_producer()
            
            # Initialize SSE manager
            self._sse_manager = await get_sse_manager()
            
            logger.info("✅ Position monitor dependencies initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize position monitor dependencies: {e}")
            raise
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process Kafka messages - required by BaseHFTConsumer"""
        await self._process_message_batch(messages)
    
    async def _process_message_batch(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of market data and execution messages"""
        try:
            price_updates = []
            execution_updates = []
            
            # Categorize messages
            for message in messages:
                message_type = message.get('type', '')
                
                if message_type == 'live_feed' or 'feeds' in message:
                    # Market data update
                    price_updates.append(message)
                elif message_type == 'trade_execution':
                    # Trade execution update
                    execution_updates.append(message)
            
            # Process trade executions first (creates/closes positions)
            if execution_updates:
                await self._process_trade_executions(execution_updates)
            
            # Process price updates (updates PnL)
            if price_updates:
                await self._process_price_updates(price_updates)
            
        except Exception as e:
            logger.error(f"❌ Error processing position monitor messages: {e}")
    
    async def _process_trade_executions(self, executions: List[Dict[str, Any]]) -> None:
        """Process trade execution messages to create/update positions"""
        try:
            for execution in executions:
                await self._handle_trade_execution(execution)
                
        except Exception as e:
            logger.error(f"❌ Error processing trade executions: {e}")
    
    async def _handle_trade_execution(self, execution: Dict[str, Any]) -> None:
        """Handle individual trade execution"""
        try:
            # Extract execution details
            position_id = execution.get('position_id')
            user_id = execution.get('user_id')
            session_id = execution.get('session_id')
            instrument_key = execution.get('instrument_key')
            
            if not all([position_id, user_id, session_id, instrument_key]):
                logger.warning("⚠️ Incomplete trade execution data")
                return
            
            action = execution.get('action', '').lower()
            
            if action in ['buy', 'sell']:
                if action == 'buy':
                    # Create new position
                    await self._create_position(execution)
                else:
                    # Close existing position
                    await self._close_position(execution)
            
        except Exception as e:
            logger.error(f"❌ Error handling trade execution: {e}")
    
    async def _create_position(self, execution: Dict[str, Any]) -> None:
        """Create new position from trade execution"""
        try:
            position = Position(
                position_id=execution['position_id'],
                user_id=execution['user_id'],
                session_id=execution['session_id'],
                instrument_key=execution['instrument_key'],
                symbol=execution.get('symbol', ''),
                position_type=self._get_position_type(execution),
                quantity=execution.get('quantity', 0),
                entry_price=Decimal(str(execution.get('price', 0))),
                current_price=Decimal(str(execution.get('price', 0))),
                entry_time=datetime.now()
            )
            
            # Store position
            self._active_positions[position.position_id] = position
            
            # Update user tracking
            if position.user_id not in self._user_positions:
                self._user_positions[position.user_id] = set()
            self._user_positions[position.user_id].add(position.position_id)
            
            # Update session tracking
            if position.session_id not in self._session_positions:
                self._session_positions[position.session_id] = set()
            self._session_positions[position.session_id].add(position.position_id)
            
            self._total_positions_monitored += 1
            
            # Broadcast position creation
            await self._broadcast_position_update(position, 'position_created')
            
            logger.info(f"📊 Created position {position.position_id} for {position.symbol}")
            
        except Exception as e:
            logger.error(f"❌ Error creating position: {e}")
    
    async def _close_position(self, execution: Dict[str, Any]) -> None:
        """Close existing position"""
        try:
            position_id = execution['position_id']
            
            if position_id in self._active_positions:
                position = self._active_positions[position_id]
                
                # Calculate final PnL
                exit_price = Decimal(str(execution.get('price', 0)))
                position.update_price(exit_price)
                position.realized_pnl = position.unrealized_pnl
                position.unrealized_pnl = Decimal('0')
                position.status = PositionStatus.CLOSED
                
                # Broadcast position closure
                await self._broadcast_position_update(position, 'position_closed')
                
                # Remove from active positions
                del self._active_positions[position_id]
                
                # Update tracking sets
                if position.user_id in self._user_positions:
                    self._user_positions[position.user_id].discard(position_id)
                if position.session_id in self._session_positions:
                    self._session_positions[position.session_id].discard(position_id)
                
                logger.info(f"📊 Closed position {position_id} with PnL: {position.total_pnl}")
            
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
    
    async def _process_price_updates(self, price_updates: List[Dict[str, Any]]) -> None:
        """Process price updates for position PnL calculation"""
        try:
            updated_positions = []
            
            for update in price_updates:
                if 'feeds' in update:
                    feeds = update['feeds']
                    
                    for instrument_key, feed_data in feeds.items():
                        # Find positions for this instrument
                        matching_positions = [
                            pos for pos in self._active_positions.values()
                            if pos.instrument_key == instrument_key
                        ]
                        
                        if matching_positions:
                            # Extract current price
                            current_price = self._extract_current_price(feed_data)
                            
                            if current_price:
                                for position in matching_positions:
                                    old_pnl = position.total_pnl
                                    position.update_price(current_price)
                                    
                                    # Check if PnL change is significant enough to broadcast
                                    pnl_change = abs(position.total_pnl - old_pnl)
                                    if pnl_change >= self._pnl_threshold:
                                        updated_positions.append(position)
            
            # Broadcast significant updates
            if updated_positions:
                await self._broadcast_pnl_updates(updated_positions)
            
        except Exception as e:
            logger.error(f"❌ Error processing price updates: {e}")
    
    def _get_position_type(self, execution: Dict[str, Any]) -> PositionType:
        """Determine position type from execution data"""
        # This is a simplified implementation
        # In practice, you'd analyze the option contract details
        instrument_key = execution.get('instrument_key', '')
        action = execution.get('action', '').lower()
        
        if 'CE' in instrument_key:  # Call option
            return PositionType.LONG_CALL if action == 'buy' else PositionType.SHORT_CALL
        elif 'PE' in instrument_key:  # Put option
            return PositionType.LONG_PUT if action == 'buy' else PositionType.SHORT_PUT
        else:
            # Default to long call for non-options
            return PositionType.LONG_CALL
    
    def _extract_current_price(self, feed_data: Dict[str, Any]) -> Optional[Decimal]:
        """Extract current price from feed data"""
        try:
            full_feed = feed_data.get('fullFeed', {})
            market_data = full_feed.get('marketFF') or full_feed.get('indexFF')
            
            if market_data and 'ltpc' in market_data:
                ltp = market_data['ltpc'].get('ltp')
                if ltp:
                    return Decimal(str(ltp))
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting current price: {e}")
            return None
    
    async def _broadcast_position_update(self, position: Position, event_type: str) -> None:
        """Broadcast individual position update via SSE"""
        try:
            position_data = {
                'position_id': position.position_id,
                'user_id': position.user_id,
                'session_id': position.session_id,
                'symbol': position.symbol,
                'position_type': position.position_type.value,
                'quantity': position.quantity,
                'entry_price': float(position.entry_price),
                'current_price': float(position.current_price),
                'unrealized_pnl': float(position.unrealized_pnl),
                'realized_pnl': float(position.realized_pnl),
                'total_pnl': float(position.total_pnl),
                'status': position.status.value,
                'last_update': position.last_update.isoformat()
            }
            
            # Broadcast to trading signals channel
            await self._sse_manager.broadcast_to_channel(
                channel=SSEChannel.TRADING_SIGNALS,
                event_type=event_type,
                data=position_data,
                priority=1  # High priority for position updates
            )
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting position update: {e}")
    
    async def _broadcast_pnl_updates(self, updated_positions: List[Position]) -> None:
        """Broadcast batch PnL updates"""
        try:
            # Group by user and session
            user_updates = {}
            session_updates = {}
            
            for position in updated_positions:
                # User-level aggregation
                if position.user_id not in user_updates:
                    user_updates[position.user_id] = {
                        'total_pnl': Decimal('0'),
                        'positions': [],
                        'active_count': 0
                    }
                
                user_data = user_updates[position.user_id]
                user_data['total_pnl'] += position.total_pnl
                user_data['positions'].append({
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'pnl': float(position.total_pnl)
                })
                user_data['active_count'] += 1
                
                # Session-level aggregation
                if position.session_id not in session_updates:
                    session_updates[position.session_id] = {
                        'total_pnl': Decimal('0'),
                        'positions': [],
                        'user_id': position.user_id
                    }
                
                session_data = session_updates[position.session_id]
                session_data['total_pnl'] += position.total_pnl
                session_data['positions'].append({
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'pnl': float(position.total_pnl)
                })
            
            # Broadcast aggregated updates
            pnl_update_data = {
                'timestamp': datetime.now().isoformat(),
                'user_pnl': {
                    str(user_id): {
                        'total_pnl': float(data['total_pnl']),
                        'active_positions': data['active_count'],
                        'positions': data['positions']
                    }
                    for user_id, data in user_updates.items()
                },
                'session_pnl': {
                    session_id: {
                        'total_pnl': float(data['total_pnl']),
                        'user_id': data['user_id'],
                        'positions': data['positions']
                    }
                    for session_id, data in session_updates.items()
                }
            }
            
            # Broadcast to trading signals channel
            await self._sse_manager.broadcast_to_channel(
                channel=SSEChannel.TRADING_SIGNALS,
                event_type='live_pnl_update',
                data=pnl_update_data,
                priority=1
            )
            
            self._pnl_updates_sent += 1
            self._last_update_time = datetime.now()
            
            logger.debug(f"📊 Broadcasted PnL updates for {len(updated_positions)} positions")
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting PnL updates: {e}")
    
    def get_user_positions(self, user_id: int) -> List[Position]:
        """Get all active positions for a user"""
        if user_id not in self._user_positions:
            return []
        
        return [
            self._active_positions[pos_id]
            for pos_id in self._user_positions[user_id]
            if pos_id in self._active_positions
        ]
    
    def get_session_positions(self, session_id: str) -> List[Position]:
        """Get all positions for a trading session"""
        if session_id not in self._session_positions:
            return []
        
        return [
            self._active_positions[pos_id]
            for pos_id in self._session_positions[session_id]
            if pos_id in self._active_positions
        ]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get position monitor performance statistics"""
        return {
            'total_positions_monitored': self._total_positions_monitored,
            'active_positions': len(self._active_positions),
            'pnl_updates_sent': self._pnl_updates_sent,
            'last_update_time': self._last_update_time.isoformat(),
            'users_tracked': len(self._user_positions),
            'sessions_tracked': len(self._session_positions)
        }


# Singleton instance
_position_monitor: Optional[AutoTradingPositionMonitor] = None


async def get_position_monitor() -> AutoTradingPositionMonitor:
    """Get singleton position monitor instance"""
    global _position_monitor
    if _position_monitor is None:
        _position_monitor = AutoTradingPositionMonitor()
        await _position_monitor.initialize_dependencies()
    return _position_monitor


async def start_position_monitoring() -> None:
    """Start the position monitoring consumer"""
    monitor = await get_position_monitor()
    await monitor.start_consuming()


async def stop_position_monitoring() -> None:
    """Stop position monitoring"""
    global _position_monitor
    if _position_monitor:
        await _position_monitor.stop_consuming()


# Export main functions
__all__ = [
    "AutoTradingPositionMonitor",
    "Position",
    "PositionType",
    "PositionStatus",
    "get_position_monitor",
    "start_position_monitoring",
    "stop_position_monitoring"
]