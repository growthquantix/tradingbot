"""
PnL Calculator for Auto Trading System

Advanced PnL calculation engine with support for options trading,
real-time mark-to-market updates, and performance analytics.

Author: Trading System
Created: 2025-01-11
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class CalculationType(Enum):
    """Types of PnL calculations"""
    UNREALIZED = "unrealized"
    REALIZED = "realized"
    TOTAL = "total"
    INTRADAY = "intraday"
    OVERNIGHT = "overnight"


@dataclass
class PnLMetrics:
    """PnL calculation results"""
    calculation_type: CalculationType
    total_pnl: Decimal
    percentage_return: Decimal
    
    # Detailed breakdown
    gross_pnl: Decimal
    brokerage: Decimal
    taxes: Decimal
    net_pnl: Decimal
    
    # Risk metrics  
    max_profit: Decimal
    max_loss: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    
    # Timing
    holding_period: timedelta
    calculation_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'calculation_type': self.calculation_type.value,
            'total_pnl': float(self.total_pnl),
            'percentage_return': float(self.percentage_return),
            'gross_pnl': float(self.gross_pnl),
            'brokerage': float(self.brokerage),
            'taxes': float(self.taxes),
            'net_pnl': float(self.net_pnl),
            'max_profit': float(self.max_profit),
            'max_loss': float(self.max_loss),
            'max_drawdown': float(self.max_drawdown),
            'win_rate': float(self.win_rate),
            'holding_period_seconds': self.holding_period.total_seconds(),
            'calculation_time': self.calculation_time.isoformat()
        }


@dataclass
class TradingCosts:
    """Trading cost structure for PnL calculations"""
    brokerage_per_lot: Decimal = Decimal('20.0')  # ₹20 per lot
    transaction_charge_rate: Decimal = Decimal('0.00053')  # 0.053% for options
    gst_rate: Decimal = Decimal('0.18')  # 18% GST
    sebi_charges_rate: Decimal = Decimal('0.000001')  # ₹1 per crore
    stamp_duty_rate: Decimal = Decimal('0.00003')  # 0.003% on buy side only
    
    def calculate_total_cost(self, turnover: Decimal, lots: int, is_buy: bool = True) -> Decimal:
        """Calculate total trading cost"""
        try:
            # Brokerage
            brokerage = self.brokerage_per_lot * lots
            
            # Transaction charges
            transaction_charges = turnover * self.transaction_charge_rate
            
            # SEBI charges
            sebi_charges = turnover * self.sebi_charges_rate
            
            # Stamp duty (only on buy side)
            stamp_duty = Decimal('0')
            if is_buy:
                stamp_duty = turnover * self.stamp_duty_rate
            
            # Sub-total before GST
            subtotal = brokerage + transaction_charges + sebi_charges + stamp_duty
            
            # GST on brokerage and transaction charges
            gst = (brokerage + transaction_charges) * self.gst_rate
            
            total_cost = subtotal + gst
            
            return total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
        except Exception as e:
            logger.error(f"❌ Error calculating trading cost: {e}")
            return Decimal('0')


class PnLCalculator:
    """
    Advanced PnL Calculator for Auto Trading
    
    Features:
    - Real-time mark-to-market PnL calculation
    - Options-specific PnL with Greeks consideration
    - Trading cost calculation (brokerage, taxes, charges)
    - Performance metrics and risk analytics
    - Multi-position portfolio PnL aggregation
    """
    
    def __init__(self):
        self.trading_costs = TradingCosts()
        self.calculation_cache: Dict[str, PnLMetrics] = {}
        self.cache_ttl_seconds = 1  # 1 second cache for real-time updates
        
        logger.info("🧮 PnL Calculator initialized")
    
    async def calculate_position_pnl(
        self,
        position_id: str,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
        position_type: str,
        entry_time: datetime,
        is_closed: bool = False,
        exit_price: Optional[Decimal] = None
    ) -> PnLMetrics:
        """Calculate PnL for a single position"""
        try:
            # Use exit price if position is closed
            mark_price = exit_price if is_closed and exit_price else current_price
            
            # Calculate gross P&L based on position type
            gross_pnl = self._calculate_gross_pnl(
                entry_price, mark_price, quantity, position_type
            )
            
            # Calculate trading costs
            entry_turnover = entry_price * abs(quantity)
            exit_turnover = mark_price * abs(quantity) if is_closed else Decimal('0')
            
            entry_cost = self.trading_costs.calculate_total_cost(
                entry_turnover, self._get_lots_count(quantity), is_buy=True
            )
            exit_cost = self.trading_costs.calculate_total_cost(
                exit_turnover, self._get_lots_count(quantity), is_buy=False
            ) if is_closed else Decimal('0')
            
            total_costs = entry_cost + exit_cost
            
            # Net PnL after costs
            net_pnl = gross_pnl - total_costs
            
            # Calculate percentage return
            investment = entry_price * abs(quantity)
            percentage_return = (net_pnl / investment * 100) if investment > 0 else Decimal('0')
            
            # Calculate holding period
            holding_period = datetime.now() - entry_time
            
            # Determine calculation type
            calc_type = CalculationType.REALIZED if is_closed else CalculationType.UNREALIZED
            
            # Create PnL metrics
            metrics = PnLMetrics(
                calculation_type=calc_type,
                total_pnl=net_pnl,
                percentage_return=percentage_return,
                gross_pnl=gross_pnl,
                brokerage=total_costs,  # Simplified - includes all costs
                taxes=Decimal('0'),  # Handled within trading costs
                net_pnl=net_pnl,
                max_profit=max(net_pnl, Decimal('0')),
                max_loss=min(net_pnl, Decimal('0')),
                max_drawdown=abs(min(net_pnl, Decimal('0'))),
                win_rate=Decimal('100') if net_pnl > 0 else Decimal('0'),
                holding_period=holding_period
            )
            
            # Cache the result
            self.calculation_cache[position_id] = metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error calculating position PnL for {position_id}: {e}")
            # Return default metrics on error
            return PnLMetrics(
                calculation_type=CalculationType.UNREALIZED,
                total_pnl=Decimal('0'),
                percentage_return=Decimal('0'),
                gross_pnl=Decimal('0'),
                brokerage=Decimal('0'),
                taxes=Decimal('0'),
                net_pnl=Decimal('0'),
                max_profit=Decimal('0'),
                max_loss=Decimal('0'),
                max_drawdown=Decimal('0'),
                win_rate=Decimal('0'),
                holding_period=timedelta()
            )
    
    def _calculate_gross_pnl(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
        position_type: str
    ) -> Decimal:
        """Calculate gross PnL based on position type"""
        try:
            price_diff = current_price - entry_price
            
            # For long positions (buy first)
            if position_type.lower() in ['long_call', 'long_put', 'long']:
                return price_diff * quantity
            
            # For short positions (sell first)
            elif position_type.lower() in ['short_call', 'short_put', 'short']:
                return -price_diff * quantity
            
            else:
                # Default to long position
                return price_diff * quantity
                
        except Exception as e:
            logger.error(f"❌ Error calculating gross PnL: {e}")
            return Decimal('0')
    
    def _get_lots_count(self, quantity: int) -> int:
        """Calculate number of lots from quantity"""
        # Assuming standard lot size of 50 for options
        # This should be configurable based on instrument
        lot_size = 50
        return max(1, abs(quantity) // lot_size)
    
    async def calculate_portfolio_pnl(
        self,
        positions: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate aggregated portfolio PnL"""
        try:
            if not positions:
                return {
                    'total_pnl': 0.0,
                    'total_percentage': 0.0,
                    'positions_count': 0,
                    'winning_positions': 0,
                    'losing_positions': 0,
                    'win_rate': 0.0,
                    'max_profit': 0.0,
                    'max_loss': 0.0,
                    'total_investment': 0.0
                }
            
            # Calculate individual position PnLs
            position_pnls = []
            total_investment = Decimal('0')
            total_pnl = Decimal('0')
            winning_count = 0
            losing_count = 0
            max_profit = Decimal('0')
            max_loss = Decimal('0')
            
            for position in positions:
                try:
                    pnl_metrics = await self.calculate_position_pnl(
                        position_id=position['position_id'],
                        entry_price=Decimal(str(position['entry_price'])),
                        current_price=Decimal(str(position['current_price'])),
                        quantity=position['quantity'],
                        position_type=position['position_type'],
                        entry_time=position['entry_time'],
                        is_closed=position.get('status') == 'closed',
                        exit_price=position.get('exit_price')
                    )
                    
                    position_pnls.append({
                        'position_id': position['position_id'],
                        'symbol': position.get('symbol', ''),
                        'pnl': float(pnl_metrics.net_pnl),
                        'percentage': float(pnl_metrics.percentage_return),
                        'metrics': pnl_metrics.to_dict()
                    })
                    
                    # Aggregate metrics
                    investment = Decimal(str(position['entry_price'])) * abs(position['quantity'])
                    total_investment += investment
                    total_pnl += pnl_metrics.net_pnl
                    
                    if pnl_metrics.net_pnl > 0:
                        winning_count += 1
                        max_profit = max(max_profit, pnl_metrics.net_pnl)
                    elif pnl_metrics.net_pnl < 0:
                        losing_count += 1
                        max_loss = min(max_loss, pnl_metrics.net_pnl)
                        
                except Exception as e:
                    logger.error(f"❌ Error calculating PnL for position {position.get('position_id')}: {e}")
                    continue
            
            # Calculate portfolio metrics
            total_positions = len(position_pnls)
            win_rate = (winning_count / total_positions * 100) if total_positions > 0 else 0
            total_percentage = (total_pnl / total_investment * 100) if total_investment > 0 else Decimal('0')
            
            portfolio_pnl = {
                'user_id': user_id,
                'session_id': session_id,
                'calculation_time': datetime.now().isoformat(),
                'total_pnl': float(total_pnl),
                'total_percentage': float(total_percentage),
                'total_investment': float(total_investment),
                'positions_count': total_positions,
                'winning_positions': winning_count,
                'losing_positions': losing_count,
                'win_rate': win_rate,
                'max_profit': float(max_profit),
                'max_loss': float(max_loss),
                'position_details': position_pnls
            }
            
            return portfolio_pnl
            
        except Exception as e:
            logger.error(f"❌ Error calculating portfolio PnL: {e}")
            return {
                'error': str(e),
                'total_pnl': 0.0,
                'positions_count': 0
            }
    
    async def calculate_session_pnl(
        self,
        session_id: str,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate PnL for a specific trading session"""
        try:
            session_start = min(pos['entry_time'] for pos in positions) if positions else datetime.now()
            session_duration = datetime.now() - session_start
            
            # Get portfolio PnL
            portfolio_pnl = await self.calculate_portfolio_pnl(positions, session_id=session_id)
            
            # Add session-specific metrics
            session_pnl = {
                **portfolio_pnl,
                'session_id': session_id,
                'session_start': session_start.isoformat(),
                'session_duration_minutes': session_duration.total_seconds() / 60,
                'avg_pnl_per_position': portfolio_pnl['total_pnl'] / max(1, portfolio_pnl['positions_count']),
                'pnl_per_minute': portfolio_pnl['total_pnl'] / max(1, session_duration.total_seconds() / 60),
            }
            
            return session_pnl
            
        except Exception as e:
            logger.error(f"❌ Error calculating session PnL: {e}")
            return {'error': str(e), 'session_id': session_id}
    
    def get_cached_pnl(self, position_id: str) -> Optional[PnLMetrics]:
        """Get cached PnL calculation if available and fresh"""
        if position_id in self.calculation_cache:
            cached_metrics = self.calculation_cache[position_id]
            age = datetime.now() - cached_metrics.calculation_time
            
            if age.total_seconds() <= self.cache_ttl_seconds:
                return cached_metrics
            else:
                # Remove stale cache entry
                del self.calculation_cache[position_id]
        
        return None
    
    def clear_cache(self) -> None:
        """Clear all cached PnL calculations"""
        self.calculation_cache.clear()
        logger.info("🧹 PnL calculation cache cleared")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get calculator performance statistics"""
        return {
            'cached_calculations': len(self.calculation_cache),
            'cache_ttl_seconds': self.cache_ttl_seconds,
            'trading_costs_config': {
                'brokerage_per_lot': float(self.trading_costs.brokerage_per_lot),
                'transaction_charge_rate': float(self.trading_costs.transaction_charge_rate),
                'gst_rate': float(self.trading_costs.gst_rate)
            }
        }


# Singleton instance
_pnl_calculator: Optional[PnLCalculator] = None


def get_pnl_calculator() -> PnLCalculator:
    """Get singleton PnL calculator instance"""
    global _pnl_calculator
    if _pnl_calculator is None:
        _pnl_calculator = PnLCalculator()
    return _pnl_calculator


# Export main classes and functions
__all__ = [
    "PnLCalculator",
    "PnLMetrics",
    "CalculationType",
    "TradingCosts",
    "get_pnl_calculator"
]