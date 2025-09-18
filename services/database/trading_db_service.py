"""
Trading Database Service - HFT Grade Database Operations
Handles all database operations for the auto-trading system with performance optimization
"""

import asyncio
import logging
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal
import numpy as np
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func, and_, or_, desc, asc

# Database imports
from database.connection import SessionLocal, engine
from database.models import (
    User, AutoTradeExecution, ActivePosition, DailyTradingPerformance,
    TradingSystemLog, EmergencyControl, TradingAuditTrail,
    AutoTradingSession
)

logger = logging.getLogger(__name__)


class TradingDatabaseService:
    """
    High-performance database service for auto-trading system
    
    Features:
    - Async operations for HFT requirements
    - Batch operations for performance
    - Connection pooling for concurrent access
    - Transaction management with rollback safety
    - Real-time position tracking
    - Comprehensive performance analytics
    """
    
    def __init__(self):
        self.session_factory = SessionLocal
        self.logger = logging.getLogger(__name__)
        
    def get_session(self) -> Session:
        """Get database session with error handling"""
        try:
            return self.session_factory()
        except Exception as e:
            self.logger.error(f"Failed to create database session: {e}")
            raise
    
    async def log_trade_execution(self, trade_data: Dict[str, Any]) -> Optional[int]:
        """
        Log complete trade execution to database with all Fibonacci strategy data
        
        Args:
            trade_data: Dictionary containing all trade execution data
            
        Returns:
            trade_execution_id if successful, None if failed
        """
        db = self.get_session()
        try:
            trade_execution = AutoTradeExecution(
                user_id=trade_data['user_id'],
                session_id=trade_data.get('session_id'),
                
                # Trade identification
                trade_id=trade_data['trade_id'],
                symbol=trade_data['symbol'],
                instrument_key=trade_data['instrument_key'],
                
                # Strategy details
                strategy_name=trade_data.get('strategy_name', 'fibonacci_ema'),
                signal_type=trade_data['signal_type'],  # BUY_CE, BUY_PE
                signal_strength=Decimal(str(trade_data.get('signal_strength', 0))),
                
                # Fibonacci strategy specific data
                fibonacci_levels=trade_data.get('fibonacci_levels', {}),
                ema_values=trade_data.get('ema_values', {}),
                swing_high=Decimal(str(trade_data.get('swing_high', 0))) if trade_data.get('swing_high') else None,
                swing_low=Decimal(str(trade_data.get('swing_low', 0))) if trade_data.get('swing_low') else None,
                
                # Trade execution
                entry_time=trade_data.get('entry_time', datetime.utcnow()),
                entry_price=Decimal(str(trade_data['entry_price'])),
                entry_order_id=trade_data.get('entry_order_id'),
                quantity=trade_data['quantity'],
                lot_size=trade_data.get('lot_size', 1),
                
                # Risk management
                initial_stop_loss=Decimal(str(trade_data.get('initial_stop_loss', 0))) if trade_data.get('initial_stop_loss') else None,
                target_1=Decimal(str(trade_data.get('target_1', 0))) if trade_data.get('target_1') else None,
                target_2=Decimal(str(trade_data.get('target_2', 0))) if trade_data.get('target_2') else None,
                
                # Performance metrics
                signal_generation_latency_ms=trade_data.get('signal_generation_latency_ms'),
                order_execution_latency_ms=trade_data.get('order_execution_latency_ms'),
                total_execution_latency_ms=trade_data.get('total_execution_latency_ms'),
                
                # Status
                status='ACTIVE'
            )
            
            db.add(trade_execution)
            db.commit()
            
            trade_id = trade_execution.id
            
            # Create corresponding active position
            await self.create_active_position(trade_id, trade_data)
            
            # Log to audit trail
            await self.log_audit_trail(
                user_id=trade_data['user_id'],
                action_type='TRADE_EXECUTED',
                entity_type='TRADE',
                entity_id=trade_data['trade_id'],
                details={
                    'symbol': trade_data['symbol'],
                    'signal_type': trade_data['signal_type'],
                    'entry_price': float(trade_data['entry_price']),
                    'quantity': trade_data['quantity']
                }
            )
            
            self.logger.info(f"✅ Trade execution logged: {trade_data['trade_id']} for {trade_data['symbol']}")
            return trade_id
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to log trade execution: {e}")
            return None
        finally:
            db.close()
    
    async def create_active_position(self, trade_execution_id: int, trade_data: Dict[str, Any]) -> Optional[int]:
        """Create active position record for real-time tracking"""
        db = self.get_session()
        try:
            position = ActivePosition(
                trade_execution_id=trade_execution_id,
                user_id=trade_data['user_id'],
                symbol=trade_data['symbol'],
                instrument_key=trade_data['instrument_key'],
                current_price=Decimal(str(trade_data['entry_price'])),
                current_pnl=Decimal('0'),
                current_pnl_percentage=Decimal('0'),
                current_stop_loss=Decimal(str(trade_data.get('initial_stop_loss', 0))) if trade_data.get('initial_stop_loss') else None,
                highest_price_reached=Decimal(str(trade_data['entry_price'])),
                is_active=True,
                mark_to_market_time=datetime.utcnow()
            )
            
            db.add(position)
            db.commit()
            
            self.logger.info(f"✅ Active position created for trade {trade_execution_id}")
            return position.id
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to create active position: {e}")
            return None
        finally:
            db.close()
    
    async def update_active_position(self, trade_execution_id: int, position_data: Dict[str, Any]) -> bool:
        """Update real-time position data with current market prices"""
        db = self.get_session()
        try:
            position = db.query(ActivePosition).filter(
                ActivePosition.trade_execution_id == trade_execution_id,
                ActivePosition.is_active == True
            ).first()
            
            if not position:
                self.logger.warning(f"No active position found for trade {trade_execution_id}")
                return False
            
            # Update position data
            current_price = Decimal(str(position_data['current_price']))
            entry_price = position.trade_execution.entry_price
            
            # Calculate P&L
            if position.trade_execution.signal_type == 'BUY_CE':
                pnl = (current_price - entry_price) * position.trade_execution.quantity
            else:  # BUY_PE
                pnl = (current_price - entry_price) * position.trade_execution.quantity
            
            pnl_percentage = (pnl / (entry_price * position.trade_execution.quantity)) * 100
            
            # Update fields
            position.current_price = current_price
            position.current_pnl = pnl
            position.current_pnl_percentage = pnl_percentage
            position.mark_to_market_time = datetime.utcnow()
            position.last_updated = datetime.utcnow()
            
            # Update highest price reached
            if current_price > position.highest_price_reached:
                position.highest_price_reached = current_price
            
            # Update trailing stop if provided
            if 'current_stop_loss' in position_data:
                position.current_stop_loss = Decimal(str(position_data['current_stop_loss']))
                position.trailing_stop_triggered = position_data.get('trailing_stop_triggered', False)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to update active position: {e}")
            return False
        finally:
            db.close()
    
    async def close_trade_execution(self, trade_id: str, exit_data: Dict[str, Any]) -> bool:
        """Close trade execution and update all related records"""
        db = self.get_session()
        try:
            # Get trade execution
            trade_execution = db.query(AutoTradeExecution).filter(
                AutoTradeExecution.trade_id == trade_id
            ).first()
            
            if not trade_execution:
                self.logger.error(f"Trade execution not found: {trade_id}")
                return False
            
            # Update trade execution
            exit_price = Decimal(str(exit_data['exit_price']))
            exit_time = exit_data.get('exit_time', datetime.utcnow())
            
            trade_execution.exit_time = exit_time
            trade_execution.exit_price = exit_price
            trade_execution.exit_order_id = exit_data.get('exit_order_id')
            trade_execution.exit_reason = exit_data['exit_reason']
            trade_execution.status = 'CLOSED'
            
            # Calculate P&L
            entry_price = trade_execution.entry_price
            quantity = trade_execution.quantity
            
            if trade_execution.signal_type == 'BUY_CE':
                gross_pnl = (exit_price - entry_price) * quantity
            else:  # BUY_PE
                gross_pnl = (exit_price - entry_price) * quantity
            
            # Calculate net P&L (subtract brokerage)
            brokerage = exit_data.get('brokerage', 0)
            net_pnl = gross_pnl - Decimal(str(brokerage))
            
            trade_execution.gross_pnl = gross_pnl
            trade_execution.net_pnl = net_pnl
            trade_execution.pnl_percentage = (net_pnl / (entry_price * quantity)) * 100
            
            # Calculate actual risk-reward
            if trade_execution.initial_stop_loss:
                risk = abs(entry_price - trade_execution.initial_stop_loss) * quantity
                if risk > 0:
                    trade_execution.risk_reward_actual = abs(net_pnl) / risk
            
            # Calculate time in trade
            time_diff = exit_time - trade_execution.entry_time
            trade_execution.time_in_trade_minutes = int(time_diff.total_seconds() / 60)
            
            # Update active position to inactive
            active_position = db.query(ActivePosition).filter(
                ActivePosition.trade_execution_id == trade_execution.id
            ).first()
            
            if active_position:
                active_position.is_active = False
                active_position.current_price = exit_price
                active_position.current_pnl = net_pnl
                active_position.last_updated = datetime.utcnow()
            
            db.commit()
            
            # Update daily performance
            await self.update_daily_performance(trade_execution.user_id, exit_time.date())
            
            # Log to audit trail
            await self.log_audit_trail(
                user_id=trade_execution.user_id,
                action_type='TRADE_CLOSED',
                entity_type='TRADE',
                entity_id=trade_id,
                details={
                    'symbol': trade_execution.symbol,
                    'exit_price': float(exit_price),
                    'pnl': float(net_pnl),
                    'exit_reason': exit_data['exit_reason']
                }
            )
            
            self.logger.info(f"✅ Trade closed: {trade_id} P&L: {net_pnl}")
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to close trade execution: {e}")
            return False
        finally:
            db.close()
    
    async def update_daily_performance(self, user_id: int, trading_date: date) -> bool:
        """Calculate and update daily trading performance metrics"""
        db = self.get_session()
        try:
            # Get all closed trades for the day
            trades = db.query(AutoTradeExecution).filter(
                AutoTradeExecution.user_id == user_id,
                func.date(AutoTradeExecution.entry_time) == trading_date,
                AutoTradeExecution.status == 'CLOSED'
            ).all()
            
            if not trades:
                return True  # No trades to process
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.net_pnl and t.net_pnl > 0])
            losing_trades = len([t for t in trades if t.net_pnl and t.net_pnl < 0])
            breakeven_trades = len([t for t in trades if t.net_pnl and t.net_pnl == 0])
            
            gross_pnl = sum(t.gross_pnl for t in trades if t.gross_pnl)
            net_pnl = sum(t.net_pnl for t in trades if t.net_pnl)
            
            winning_trades_pnl = [t.net_pnl for t in trades if t.net_pnl and t.net_pnl > 0]
            losing_trades_pnl = [t.net_pnl for t in trades if t.net_pnl and t.net_pnl < 0]
            
            largest_win = max(winning_trades_pnl, default=0)
            largest_loss = min(losing_trades_pnl, default=0)
            
            # Calculate performance ratios
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            avg_win = np.mean(winning_trades_pnl) if winning_trades_pnl else 0
            avg_loss = np.mean(losing_trades_pnl) if losing_trades_pnl else 0
            
            total_wins = sum(winning_trades_pnl) if winning_trades_pnl else 0
            total_losses = abs(sum(losing_trades_pnl)) if losing_trades_pnl else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
            
            expectancy = net_pnl / total_trades if total_trades > 0 else 0
            
            # Calculate Sharpe ratio (simplified daily version)
            returns = [float(t.net_pnl) for t in trades if t.net_pnl]
            if len(returns) > 1:
                sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Calculate consecutive streaks
            max_consecutive_wins, max_consecutive_losses = self._calculate_streaks(trades)
            
            # Calculate max drawdown
            max_drawdown = self._calculate_max_drawdown(trades)
            
            # Count Fibonacci signals
            fibonacci_signals = len([t for t in trades if t.strategy_name == 'fibonacci_ema'])
            
            # Get or create daily performance record
            daily_perf = db.query(DailyTradingPerformance).filter(
                DailyTradingPerformance.user_id == user_id,
                DailyTradingPerformance.trading_date == trading_date
            ).first()
            
            if daily_perf:
                # Update existing record
                daily_perf.total_trades = total_trades
                daily_perf.winning_trades = winning_trades
                daily_perf.losing_trades = losing_trades
                daily_perf.breakeven_trades = breakeven_trades
                daily_perf.gross_pnl = gross_pnl
                daily_perf.net_pnl = net_pnl
                daily_perf.largest_win = largest_win
                daily_perf.largest_loss = largest_loss
                daily_perf.win_rate = Decimal(str(win_rate))
                daily_perf.avg_win = Decimal(str(avg_win))
                daily_perf.avg_loss = Decimal(str(avg_loss))
                daily_perf.profit_factor = Decimal(str(profit_factor))
                daily_perf.expectancy = Decimal(str(expectancy))
                daily_perf.max_drawdown = Decimal(str(max_drawdown))
                daily_perf.max_consecutive_wins = max_consecutive_wins
                daily_perf.max_consecutive_losses = max_consecutive_losses
                daily_perf.sharpe_ratio = Decimal(str(sharpe_ratio))
                daily_perf.fibonacci_signals_executed = fibonacci_signals
            else:
                # Create new record
                daily_perf = DailyTradingPerformance(
                    user_id=user_id,
                    trading_date=trading_date,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    breakeven_trades=breakeven_trades,
                    gross_pnl=gross_pnl,
                    net_pnl=net_pnl,
                    largest_win=largest_win,
                    largest_loss=largest_loss,
                    win_rate=Decimal(str(win_rate)),
                    avg_win=Decimal(str(avg_win)),
                    avg_loss=Decimal(str(avg_loss)),
                    profit_factor=Decimal(str(profit_factor)),
                    expectancy=Decimal(str(expectancy)),
                    max_drawdown=Decimal(str(max_drawdown)),
                    max_consecutive_wins=max_consecutive_wins,
                    max_consecutive_losses=max_consecutive_losses,
                    sharpe_ratio=Decimal(str(sharpe_ratio)),
                    fibonacci_signals_executed=fibonacci_signals
                )
                db.add(daily_perf)
            
            db.commit()
            self.logger.info(f"✅ Daily performance updated for user {user_id} on {trading_date}")
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to update daily performance: {e}")
            return False
        finally:
            db.close()
    
    def _calculate_streaks(self, trades: List[AutoTradeExecution]) -> tuple[int, int]:
        """Calculate maximum consecutive wins and losses"""
        if not trades:
            return 0, 0
        
        # Sort trades by entry time
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in sorted_trades:
            if trade.net_pnl and trade.net_pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.net_pnl and trade.net_pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0
        
        return max_wins, max_losses
    
    def _calculate_max_drawdown(self, trades: List[AutoTradeExecution]) -> float:
        """Calculate maximum drawdown from peak equity"""
        if not trades:
            return 0
        
        # Sort trades by entry time
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        
        running_pnl = 0
        peak_equity = 0
        max_drawdown = 0
        
        for trade in sorted_trades:
            if trade.net_pnl:
                running_pnl += float(trade.net_pnl)
                peak_equity = max(peak_equity, running_pnl)
                current_drawdown = peak_equity - running_pnl
                max_drawdown = max(max_drawdown, current_drawdown)
        
        return max_drawdown
    
    async def log_system_event(self, log_data: Dict[str, Any]) -> bool:
        """Log system events with structured data"""
        db = self.get_session()
        try:
            log_entry = TradingSystemLog(
                log_level=log_data['level'],
                component=log_data['component'],
                message=log_data['message'],
                user_id=log_data.get('user_id'),
                trade_id=log_data.get('trade_id'),
                symbol=log_data.get('symbol'),
                latency_ms=log_data.get('latency_ms'),
                function_name=log_data.get('function_name'),
                line_number=log_data.get('line_number'),
                stack_trace=log_data.get('stack_trace'),
                additional_data=log_data.get('additional_data', {})
            )
            
            db.add(log_entry)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to log system event: {e}")
            return False
        finally:
            db.close()
    
    async def log_audit_trail(self, user_id: int, action_type: str, entity_type: str, 
                             entity_id: str, details: Dict[str, Any], 
                             state_before: Dict = None, state_after: Dict = None) -> bool:
        """Log audit trail for compliance"""
        db = self.get_session()
        try:
            audit_entry = TradingAuditTrail(
                user_id=user_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                state_before=state_before,
                state_after=state_after,
                triggered_by='SYSTEM',
                details=details
            )
            
            db.add(audit_entry)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to log audit trail: {e}")
            return False
        finally:
            db.close()
    
    async def get_active_positions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active positions for a user"""
        db = self.get_session()
        try:
            positions = db.query(ActivePosition).filter(
                ActivePosition.user_id == user_id,
                ActivePosition.is_active == True
            ).all()
            
            return [
                {
                    'trade_execution_id': pos.trade_execution_id,
                    'symbol': pos.symbol,
                    'current_price': float(pos.current_price) if pos.current_price else 0,
                    'current_pnl': float(pos.current_pnl) if pos.current_pnl else 0,
                    'current_pnl_percentage': float(pos.current_pnl_percentage) if pos.current_pnl_percentage else 0,
                    'current_stop_loss': float(pos.current_stop_loss) if pos.current_stop_loss else None,
                    'entry_price': float(pos.trade_execution.entry_price),
                    'quantity': pos.trade_execution.quantity,
                    'signal_type': pos.trade_execution.signal_type,
                    'entry_time': pos.trade_execution.entry_time.isoformat()
                }
                for pos in positions
            ]
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get active positions: {e}")
            return []
        finally:
            db.close()
    
    async def get_daily_performance(self, user_id: int, trading_date: date) -> Optional[Dict[str, Any]]:
        """Get daily performance metrics"""
        db = self.get_session()
        try:
            performance = db.query(DailyTradingPerformance).filter(
                DailyTradingPerformance.user_id == user_id,
                DailyTradingPerformance.trading_date == trading_date
            ).first()
            
            if not performance:
                return None
            
            return {
                'total_trades': performance.total_trades,
                'winning_trades': performance.winning_trades,
                'losing_trades': performance.losing_trades,
                'win_rate': float(performance.win_rate) if performance.win_rate else 0,
                'net_pnl': float(performance.net_pnl) if performance.net_pnl else 0,
                'gross_pnl': float(performance.gross_pnl) if performance.gross_pnl else 0,
                'largest_win': float(performance.largest_win) if performance.largest_win else 0,
                'largest_loss': float(performance.largest_loss) if performance.largest_loss else 0,
                'profit_factor': float(performance.profit_factor) if performance.profit_factor else 0,
                'sharpe_ratio': float(performance.sharpe_ratio) if performance.sharpe_ratio else 0,
                'max_drawdown': float(performance.max_drawdown) if performance.max_drawdown else 0,
                'fibonacci_signals_executed': performance.fibonacci_signals_executed
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get daily performance: {e}")
            return None
        finally:
            db.close()
    
    async def check_emergency_conditions(self, user_id: int) -> List[str]:
        """Check if emergency conditions are met"""
        db = self.get_session()
        try:
            emergency_control = db.query(EmergencyControl).filter(
                EmergencyControl.user_id == user_id,
                EmergencyControl.is_active == True
            ).first()
            
            if not emergency_control:
                return []
            
            triggers = []
            
            # Get today's performance
            today_perf = await self.get_daily_performance(user_id, date.today())
            if today_perf:
                # Daily loss check
                if (today_perf['net_pnl'] < 0 and 
                    abs(today_perf['net_pnl']) >= float(emergency_control.max_daily_loss or 0)):
                    triggers.append('DAILY_LOSS_LIMIT')
                
                # Max drawdown check
                if (emergency_control.max_drawdown_percentage and
                    today_perf['max_drawdown'] >= float(emergency_control.max_drawdown_percentage)):
                    triggers.append('MAX_DRAWDOWN')
            
            # Active position count check
            active_positions = await self.get_active_positions(user_id)
            if len(active_positions) >= emergency_control.max_position_count:
                triggers.append('POSITION_LIMIT')
            
            return triggers
            
        except Exception as e:
            self.logger.error(f"❌ Failed to check emergency conditions: {e}")
            return []
        finally:
            db.close()
    
    # ==================================================================================
    # LIVE DATA PIPELINE INTEGRATION METHODS
    # ==================================================================================
    
    async def log_fibonacci_signal(self, signal_data: Dict[str, Any], user_id: int = None) -> Optional[int]:
        """
        Log Fibonacci trading signal from auto_trading_data_service to database
        Optimized for high-frequency signal logging with minimal latency
        
        Args:
            signal_data: FibonacciSignal data dict from auto_trading_data_service
            user_id: User ID for the trading session
            
        Returns:
            trade_execution_id if successful, None if failed
        """
        db = self.get_session()
        try:
            # Convert signal data to trade execution format
            trade_execution_data = {
                'user_id': user_id or 1,  # Default to user 1 for auto-trading
                'trade_id': f"AUTO_{signal_data.get('instrument_key', 'UNK')}_{int(datetime.utcnow().timestamp())}",
                'symbol': self._extract_symbol_from_instrument_key(signal_data.get('instrument_key', '')),
                'instrument_key': signal_data.get('instrument_key'),
                'strategy_name': 'fibonacci_ema_hft',
                'signal_type': f"{signal_data.get('signal_type', 'HOLD')}_{signal_data.get('option_type', 'CE')}",
                'signal_strength': signal_data.get('signal_strength', 0),
                'fibonacci_levels': {
                    'level_name': signal_data.get('fibonacci_level'),
                    'level_value': signal_data.get('fibonacci_value'),
                    'market_structure': signal_data.get('market_structure')
                },
                'ema_values': signal_data.get('ema_alignment', {}),
                'entry_time': signal_data.get('timestamp', datetime.utcnow()),
                'entry_price': signal_data.get('entry_price', 0),
                'quantity': 1,  # Default quantity for signal logging
                'initial_stop_loss': signal_data.get('stop_loss'),
                'target_1': signal_data.get('target_1'),
                'target_2': signal_data.get('target_2'),
                'signal_generation_latency_ms': signal_data.get('processing_time_ms'),
                'total_execution_latency_ms': signal_data.get('processing_time_ms')
            }
            
            # Log the signal as a trade execution
            trade_id = await self.log_trade_execution(trade_execution_data)
            
            # Log to system for monitoring
            await self.log_system_event({
                'level': 'INFO',
                'component': 'fibonacci_signal',
                'message': 'Fibonacci signal generated',
                'user_id': user_id,
                'symbol': signal_data.get('symbol'),
                'latency_ms': signal_data.get('processing_time_ms'),
                'additional_data': {
                    'instrument_key': signal_data.get('instrument_key'),
                    'signal_type': signal_data.get('signal_type'),
                    'confidence': signal_data.get('confidence_score'),
                    'processing_time_ms': signal_data.get('processing_time_ms')
                }
            })
            
            return trade_id
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to log Fibonacci signal: {e}")
            return None
        finally:
            db.close()
    
    async def update_live_position_price(self, instrument_key: str, current_price: float, 
                                       user_id: int = None) -> bool:
        """
        Update active position with real-time price data for P&L calculation
        Optimized for high-frequency price updates
        
        Args:
            instrument_key: Instrument being tracked
            current_price: Current market price
            user_id: User ID for position filtering
            
        Returns:
            True if updated successfully, False otherwise
        """
        db = self.get_session()
        try:
            # Find active positions for this instrument
            query = db.query(ActivePosition).filter(
                ActivePosition.instrument_key == instrument_key,
                ActivePosition.is_active == True
            )
            
            if user_id:
                query = query.filter(ActivePosition.user_id == user_id)
            
            active_positions = query.all()
            
            if not active_positions:
                return True  # No active positions to update
            
            updated_count = 0
            for position in active_positions:
                # Calculate new P&L
                entry_price = float(position.current_price) if position.current_price else current_price
                quantity = position.quantity or 1
                
                # P&L calculation based on position type
                if 'BUY' in str(position.position_type or ''):
                    pnl = (current_price - entry_price) * quantity
                else:
                    pnl = (entry_price - current_price) * quantity
                
                pnl_percentage = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
                
                # Update position
                position.current_price = Decimal(str(current_price))
                position.current_pnl = Decimal(str(pnl))
                position.current_pnl_percentage = Decimal(str(pnl_percentage))
                position.last_update_time = datetime.utcnow()
                
                # Update drawdown if necessary
                if pnl < 0 and (not position.max_drawdown or abs(pnl_percentage) > float(position.max_drawdown)):
                    position.max_drawdown = Decimal(str(abs(pnl_percentage)))
                
                updated_count += 1
            
            db.commit()
            
            if updated_count > 0:
                self.logger.debug(f"✅ Updated {updated_count} positions for {instrument_key} @ {current_price}")
            
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to update live position price: {e}")
            return False
        finally:
            db.close()
    
    async def log_tick_processing_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """
        Log tick processing performance metrics for HFT monitoring
        
        Args:
            metrics_data: Performance metrics from auto_trading_data_service
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            await self.log_system_event({
                'level': 'INFO',
                'component': 'tick_processing',
                'message': 'Tick processing metrics recorded',
                'latency_ms': metrics_data.get('avg_processing_time_ms', 0),
                'additional_data': {
                    'total_ticks_processed': metrics_data.get('total_ticks_processed', 0),
                    'avg_processing_time_ms': metrics_data.get('avg_processing_time_ms', 0),
                    'max_processing_time_ms': metrics_data.get('max_processing_time_ms', 0),
                    'signals_generated': metrics_data.get('signals_generated', 0),
                    'fibonacci_calculations': metrics_data.get('fibonacci_calculations', 0),
                    'database_writes': metrics_data.get('database_writes', 0),
                    'errors_count': metrics_data.get('errors_count', 0),
                    'circuit_breaker_triggers': metrics_data.get('circuit_breaker_triggers', 0),
                    'active_instruments': metrics_data.get('active_instruments', 0),
                    'queue_size': metrics_data.get('queue_size', 0)
                }
            })
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to log tick processing metrics: {e}")
            return False
    
    async def get_live_trading_dashboard_data(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive live trading dashboard data for real-time monitoring
        
        Args:
            user_id: User ID for data filtering
            
        Returns:
            Dict with live trading statistics and positions
        """
        try:
            # Get active positions with current P&L
            active_positions = await self.get_active_positions(user_id)
            
            # Get today's performance
            today_performance = await self.get_daily_performance(user_id, date.today())
            
            # Get recent signals (last 50)
            recent_signals = await self.get_recent_trade_executions(user_id, limit=50)
            
            # Calculate real-time statistics
            total_active_positions = len(active_positions)
            total_pnl = sum(float(pos.get('current_pnl', 0)) for pos in active_positions)
            winning_positions = len([pos for pos in active_positions if float(pos.get('current_pnl', 0)) > 0])
            losing_positions = len([pos for pos in active_positions if float(pos.get('current_pnl', 0)) < 0])
            
            win_rate = (winning_positions / total_active_positions * 100) if total_active_positions > 0 else 0
            
            # Get emergency status
            emergency_triggers = await self.check_emergency_conditions(user_id)
            
            return {
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat(),
                'active_positions': {
                    'total_count': total_active_positions,
                    'winning_count': winning_positions,
                    'losing_count': losing_positions,
                    'win_rate_percentage': round(win_rate, 2),
                    'total_pnl': round(total_pnl, 2),
                    'positions': active_positions
                },
                'daily_performance': today_performance or {},
                'recent_signals': recent_signals,
                'emergency_status': {
                    'is_emergency': len(emergency_triggers) > 0,
                    'triggers': emergency_triggers
                },
                'system_health': {
                    'database_status': 'healthy',
                    'last_update': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get live trading dashboard data: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def bulk_update_positions_from_live_data(self, price_updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update multiple positions from live data feed for performance
        
        Args:
            price_updates: List of dicts with {instrument_key, current_price, timestamp}
            
        Returns:
            Number of positions updated
        """
        if not price_updates:
            return 0
        
        db = self.get_session()
        try:
            updated_count = 0
            
            for price_update in price_updates:
                instrument_key = price_update.get('instrument_key')
                current_price = price_update.get('current_price')
                
                if not instrument_key or not current_price:
                    continue
                
                # Update all active positions for this instrument
                active_positions = db.query(ActivePosition).filter(
                    ActivePosition.instrument_key == instrument_key,
                    ActivePosition.is_active == True
                ).all()
                
                for position in active_positions:
                    # Get trade execution details for entry price
                    trade_execution = db.query(AutoTradeExecution).filter(
                        AutoTradeExecution.id == position.trade_execution_id
                    ).first()
                    
                    if not trade_execution:
                        continue
                    
                    entry_price = float(trade_execution.entry_price)
                    quantity = trade_execution.quantity or 1
                    
                    # Calculate P&L
                    if 'BUY' in trade_execution.signal_type:
                        pnl = (current_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - current_price) * quantity
                    
                    pnl_percentage = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
                    
                    # Update position
                    position.current_price = Decimal(str(current_price))
                    position.current_pnl = Decimal(str(pnl))
                    position.current_pnl_percentage = Decimal(str(pnl_percentage))
                    position.last_update_time = datetime.utcnow()
                    
                    updated_count += 1
            
            db.commit()
            
            if updated_count > 0:
                self.logger.debug(f"✅ Bulk updated {updated_count} positions from live data")
            
            return updated_count
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ Failed to bulk update positions: {e}")
            return 0
        finally:
            db.close()
    
    def _extract_symbol_from_instrument_key(self, instrument_key: str) -> str:
        """Extract trading symbol from instrument key"""
        try:
            if '|' in instrument_key:
                return instrument_key.split('|')[-1]
            return instrument_key
        except:
            return instrument_key or 'UNKNOWN'
    
    async def get_recent_trade_executions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade executions for dashboard display"""
        db = self.get_session()
        try:
            executions = db.query(AutoTradeExecution).filter(
                AutoTradeExecution.user_id == user_id
            ).order_by(desc(AutoTradeExecution.entry_time)).limit(limit).all()
            
            result = []
            for exec in executions:
                result.append({
                    'id': exec.id,
                    'trade_id': exec.trade_id,
                    'symbol': exec.symbol,
                    'signal_type': exec.signal_type,
                    'entry_price': float(exec.entry_price) if exec.entry_price else 0,
                    'quantity': exec.quantity,
                    'status': exec.status,
                    'entry_time': exec.entry_time.isoformat() if exec.entry_time else None,
                    'signal_strength': float(exec.signal_strength) if exec.signal_strength else 0,
                    'processing_latency_ms': exec.total_execution_latency_ms
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get recent trade executions: {e}")
            return []
        finally:
            db.close()


# Global service instance
trading_db_service = TradingDatabaseService()