"""
Trade Execution Handler
Handles both paper trading (virtual) and live trading (real broker API) execution
"""

import logging
import uuid
import asyncio
from decimal import Decimal
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from sqlalchemy.orm import Session

from database.models import AutoTradeExecution, ActivePosition, User, BrokerConfig
from services.trading_execution.capital_manager import TradingMode
from services.trading_execution.trade_prep import PreparedTrade, TradeStatus
from services.trading_execution.fund_manager import fund_manager
from utils.timezone_utils import get_ist_now_naive, get_ist_isoformat
from utils.logging_utils import log_structured, log_trade_result
from services.notifications.telegram_service import telegram_notifier

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    Trade execution result

    Attributes:
        success: Whether execution succeeded
        trade_id: Unique trade identifier
        order_id: Broker order ID (or paper trade ID)
        entry_price: Actual entry price
        quantity: Actual quantity executed
        status: Execution status
        message: Execution message/reason
        trade_execution_id: Database ID for trade execution record
        active_position_id: Database ID for active position record
        timestamp: Execution timestamp
        metadata: Additional execution metadata
    """

    success: bool
    trade_id: str
    order_id: Optional[str]
    entry_price: Decimal
    quantity: int
    status: str
    message: str
    trade_execution_id: Optional[int]
    active_position_id: Optional[int]
    timestamp: str
    metadata: Dict[str, Any]


class TradeExecutionHandler:
    """
    Handles trade execution for both paper and live trading

    Features:
    - Paper trading: Virtual execution with mock orders
    - Live trading: Real execution via broker API
    - Creates trade execution records
    - Creates active position for monitoring
    - Validates all parameters before execution
    - Logs execution details for tracking
    """

    def __init__(self):
        """Initialize execution handler"""
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        logger.info("Trade Execution Handler initialized")

    def initialize(self, loop: asyncio.AbstractEventLoop):
        """Initialize with event loop for thread-safe dispatch"""
        self.loop = loop
        logger.info("Trade Execution Handler initialized with event loop")

    def _safe_dispatch(self, coro):
        """Safely dispatch a coroutine to the main event loop from any thread"""
        try:
            # Use stored loop or try to get current one
            target_loop = self.loop or asyncio.get_event_loop()
            
            if target_loop.is_running():
                target_loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))
            else:
                # If loop not running, we might be in startup/shutdown
                asyncio.run_coroutine_threadsafe(coro, target_loop)
        except Exception as e:
            logger.error(f"Error in thread-safe dispatch: {e}")

    def execute_trade(
        self,
        prepared_trade: PreparedTrade,
        db: Session,
        parent_trade_id: Optional[str] = None,
        broker_name: Optional[str] = None,
        broker_id: Optional[int] = None,
        allocated_capital: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Execute trade (paper or live based on trading_mode)

        Args:
            prepared_trade: Prepared trade with all execution details
            db: Database session

        Returns:
            ExecutionResult with execution details

        Raises:
            ValueError: If prepared_trade is invalid
        """
        if not prepared_trade:
            raise ValueError("Prepared trade cannot be None")

        if prepared_trade.status != TradeStatus.READY:
            return ExecutionResult(
                success=False,
                trade_id="",
                order_id=None,
                entry_price=Decimal("0"),
                quantity=0,
                status="FAILED",
                message=f"Trade not ready for execution: {prepared_trade.status.value}",
                trade_execution_id=None,
                active_position_id=None,
                timestamp=get_ist_isoformat(),
                metadata={"error": "Trade not ready"},
            )

        # CRITICAL SAFETY CHECK: Ensure Stop Loss is valid (> 0)
        if prepared_trade.stop_loss <= 0:
            logger.error(f"Safety Block: Attempted to execute trade with Stop Loss <= 0 for {prepared_trade.stock_symbol}")
            return ExecutionResult(
                success=False,
                trade_id="",
                order_id=None,
                entry_price=Decimal("0"),
                quantity=0,
                status="FAILED",
                message="Safety Block: Invalid Stop Loss (<= 0)",
                trade_execution_id=None,
                active_position_id=None,
                timestamp=get_ist_isoformat(),
                metadata={"error": "Invalid Stop Loss"},
            )

        # 0. CRITICAL KILL SWITCH & RECOVERY CHECK
        from services.trading_execution.trading_kill_switch import trading_kill_switch
        if not trading_kill_switch.can_execute_new_trade():
            logger.error("Safety Block: Trade entry blocked by Active Trading Kill Switch")
            return ExecutionResult(
                success=False,
                trade_id="",
                order_id=None,
                entry_price=Decimal("0"),
                quantity=0,
                status="BLOCKED",
                message="Trade blocked by active kill switch",
                trade_execution_id=None,
                active_position_id=None,
                timestamp=get_ist_isoformat(),
                metadata={"error": "Kill switch active"},
            )

        # Create unique trade intent ID for idempotency
        from services.trading_execution.order_lifecycle_service import order_lifecycle_service, OrderState
        intent_id = order_lifecycle_service.create_trade_intent(
            user_id=prepared_trade.user_id,
            symbol=prepared_trade.stock_symbol,
            option_type=prepared_trade.option_type,
            quantity=prepared_trade.position_size_lots * prepared_trade.lot_size
        )
        order_lifecycle_service.transition_state(intent_id, OrderState.VALIDATED)

        trading_mode = TradingMode(prepared_trade.trading_mode)

        # HARD SAFETY ASSERTION: SHADOW MODE MUST NEVER PLACE BROKER ORDERS
        if trading_mode == TradingMode.SHADOW:
            logger.info(f"🔮 SHADOW MODE ASSERTION: Intercepting trade decision for {prepared_trade.stock_symbol} ({prepared_trade.option_type}). NO REAL ORDERS DISPATCHED.")
            from services.validation.shadow_trading_service import shadow_trading_service
            shadow_result = shadow_trading_service.record_decision(prepared_trade)
            return ExecutionResult(
                success=True,
                trade_id=shadow_result.get("decision_id", "SHADOW_DECISION"),
                order_id=None,
                entry_price=prepared_trade.entry_price,
                quantity=prepared_trade.position_size_lots * prepared_trade.lot_size,
                status="SHADOW_RECORDED",
                message="Decision recorded in SHADOW mode. Zero broker orders placed.",
                trade_execution_id=None,
                active_position_id=None,
                timestamp=get_ist_isoformat(),
                metadata=shadow_result
            )
            
        try:
            if trading_mode == TradingMode.PAPER:
                return self._execute_paper_trade(
                    prepared_trade,
                    db,
                    intent_id=intent_id,
                    broker_name=broker_name,
                    broker_id=broker_id,
                    allocated_capital=allocated_capital,
                )
            else:
                return self._execute_live_trade(prepared_trade, db, intent_id=intent_id)

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return ExecutionResult(
                success=False,
                trade_id="",
                order_id=None,
                entry_price=Decimal("0"),
                quantity=0,
                status="ERROR",
                message=str(e),
                trade_execution_id=None,
                active_position_id=None,
                timestamp=get_ist_isoformat(),
                metadata={"error": str(e)},
            )

    def _execute_paper_trade(
        self,
        prepared_trade: PreparedTrade,
        db: Session,
        intent_id: Optional[str] = None,
        broker_name: Optional[str] = None,
        broker_id: Optional[int] = None,
        allocated_capital: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Execute paper trade (virtual/mock execution)

        Args:
            prepared_trade: Prepared trade details
            db: Database session

        Returns:
            ExecutionResult with virtual execution details
        """
        try:
            # Generate unique trade ID
            trade_id = f"PAPER_{uuid.uuid4().hex[:12].upper()}"

            # Generate mock order ID
            order_id = f"PT{get_ist_now_naive().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

            # Simulate execution at prepared entry price with SLIPPAGE
            # In paper trading, we usually get a slightly worse price than LTP
            # Adding 0.05% slippage to simulate real market impact
            raw_entry_price = prepared_trade.entry_price
            slippage = raw_entry_price * Decimal("0.0005")  # 0.05% slippage
            entry_price = raw_entry_price + slippage
            
            quantity = prepared_trade.position_size_lots * prepared_trade.lot_size
            lots_traded = prepared_trade.position_size_lots
            total_investment = entry_price * Decimal(str(quantity))

            log_structured(
                event="PAPER_TRADE_EXECUTION",
                message=f"Executing PAPER trade {trade_id} (Price: {raw_entry_price} -> {entry_price} with slippage)",
                data={
                    "trade_id": trade_id,
                    "symbol": prepared_trade.stock_symbol,
                    "option_type": prepared_trade.option_type,
                    "strike": float(prepared_trade.strike_price),
                    "entry_price": float(entry_price),
                    "quantity": quantity,
                    "lots": lots_traded,
                    "investment": float(total_investment)
                },
                user_id=str(prepared_trade.user_id)
            )

            # BLOCK MARGIN & CREATE LEDGER ENTRY (New Fund Management System)
            margin_blocked = fund_manager.block_margin(
                user_id=prepared_trade.user_id,
                amount=float(total_investment),
                trading_mode="paper",
                reference_id=trade_id,
                db=db
            )
            
            if not margin_blocked:
                raise ValueError("Insufficient funds to block margin for this trade")

            # Create trade execution record
            trade_execution = AutoTradeExecution(
                user_id=prepared_trade.user_id,
                trade_id=trade_id,
                symbol=prepared_trade.stock_symbol,
                instrument_key=prepared_trade.option_instrument_key,
                strategy_name="supertrend_ema",
                signal_type=f"BUY_{prepared_trade.option_type}",
                signal_strength=float(
                    prepared_trade.metadata.get("signal_confidence", 0) * 100
                ),
                strike_price=prepared_trade.strike_price,
                expiry_date=prepared_trade.expiry_date,
                entry_time=get_ist_now_naive(),
                entry_price=float(entry_price),
                entry_order_id=order_id,
                quantity=quantity,
                lot_size=prepared_trade.lot_size,
                lots_traded=lots_traded,
                total_investment=float(total_investment),
                initial_stop_loss=float(prepared_trade.stop_loss),
                target_1=float(prepared_trade.target_price),
                target_2=float(
                    prepared_trade.target_price * Decimal("1.1")
                ),  # 10% beyond first target
                status="ACTIVE",
                # Multi-demat support
                broker_name=broker_name or "Paper Trading",
                broker_config_id=broker_id,
                allocated_capital=allocated_capital,
                parent_trade_id=None,
                trading_mode=prepared_trade.trading_mode,
                segment=prepared_trade.segment,
            )

            db.add(trade_execution)
            db.flush()  # Get the ID

            # Create active position for real-time tracking
            active_position = ActivePosition(
                trade_execution_id=trade_execution.id,
                user_id=prepared_trade.user_id,
                symbol=prepared_trade.stock_symbol,
                instrument_key=prepared_trade.option_instrument_key,
                current_price=float(entry_price),
                current_pnl=0.0,
                current_pnl_percentage=0.0,
                current_stop_loss=float(prepared_trade.stop_loss),
                trailing_stop_triggered=False,
                highest_price_reached=float(entry_price),
                unrealized_risk=float(prepared_trade.max_loss_amount),
                mark_to_market_time=get_ist_now_naive(),
                is_active=True,
                last_updated=get_ist_now_naive(),
            )

            db.add(active_position)
            db.commit()

            # Send Alert via AlertManager (Professional Unified Interface)
            from services.notifications.alert_manager import alert_manager
            self._safe_dispatch(alert_manager.notify_trade_entry(
                user_id=prepared_trade.user_id,
                trade_data={
                    "symbol": prepared_trade.stock_symbol,
                    "option_type": prepared_trade.option_type,
                    "entry_price": float(entry_price),
                    "stop_loss": float(prepared_trade.stop_loss),
                    "target": float(prepared_trade.target_price),
                    "trading_mode": "paper"
                }
            ))

            logger.info(f"✅ Paper trade executed successfully: {trade_id}")
            logger.info(f"  Trade Execution ID: {trade_execution.id}")
            logger.info(f"  Active Position ID: {active_position.id}")

            return ExecutionResult(
                success=True,
                trade_id=trade_id,
                order_id=order_id,
                entry_price=entry_price,
                quantity=quantity,
                status="EXECUTED",
                message="Paper trade executed successfully",
                trade_execution_id=trade_execution.id,
                active_position_id=active_position.id,
                timestamp=get_ist_isoformat(),
                metadata={
                    "trading_mode": "paper",
                    "symbol": prepared_trade.stock_symbol,
                    "option_type": prepared_trade.option_type,
                    "strike": float(prepared_trade.strike_price),
                    "expiry": prepared_trade.expiry_date,
                    "stop_loss": float(prepared_trade.stop_loss),
                    "target": float(prepared_trade.target_price),
                    "investment": float(prepared_trade.total_investment),
                    "max_loss": float(prepared_trade.max_loss_amount),
                },
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Error executing paper trade: {e}")
            raise

    def _execute_live_trade(
        self, prepared_trade: PreparedTrade, db: Session, intent_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute live trade via broker API
        """
        from services.trading_execution.order_lifecycle_service import order_lifecycle_service, OrderState
        if intent_id:
            order_lifecycle_service.transition_state(intent_id, OrderState.SUBMITTING)

        try:
            # Get broker configuration
            broker_config = (
                db.query(BrokerConfig)
                .join(User)
                .filter(
                    User.id == prepared_trade.user_id,
                    BrokerConfig.broker_name.ilike(f"%{prepared_trade.broker_name}%"),
                    BrokerConfig.is_active == True,
                )
                .first()
            )

            if not broker_config:
                raise ValueError(
                    f"No active broker configuration found: {prepared_trade.broker_name}"
                )

            # Generate unique trade ID
            trade_id = f"LIVE_{uuid.uuid4().hex[:12].upper()}"

            # Place order via broker
            order_result = self._place_broker_order(broker_config, prepared_trade, db)

            if not order_result.get("success"):
                if intent_id:
                    order_lifecycle_service.transition_state(intent_id, OrderState.REJECTED)
                raise ValueError(
                    f"Order placement failed: {order_result.get('message')}"
                )

            broker_order_id = order_result.get("order_id")
            if intent_id:
                order_lifecycle_service.transition_state(intent_id, OrderState.ACKNOWLEDGED, {"broker_order_id": broker_order_id})
                # Check status field from broker response
                broker_status = str(order_result.get("status", "")).upper()
                if broker_status in ("COMPLETE", "FILLED", "EXECUTED"):
                    order_lifecycle_service.transition_state(intent_id, OrderState.FILLED)
                    order_lifecycle_service.record_fill(intent_id, broker_order_id, prepared_trade.position_size_lots * prepared_trade.lot_size, prepared_trade.entry_price)
                else:
                    logger.warning(f"⚠️ Live order {broker_order_id} ACKNOWLEDGED but not yet confirmed FILLED (status={broker_status})")

            broker_order_id = order_result.get("order_id")
            actual_entry_price = Decimal(
                str(order_result.get("price", prepared_trade.entry_price))
            )
            actual_quantity = order_result.get(
                "quantity", prepared_trade.position_size_lots * prepared_trade.lot_size
            )
            lots_traded = prepared_trade.position_size_lots
            total_investment = actual_entry_price * Decimal(str(actual_quantity))

            log_structured(
                event="LIVE_TRADE_EXECUTION",
                message=f"Executing LIVE trade {trade_id}",
                data={
                    "trade_id": trade_id,
                    "broker_order_id": broker_order_id,
                    "symbol": prepared_trade.stock_symbol,
                    "entry_price": float(actual_entry_price),
                    "quantity": actual_quantity,
                    "lots": lots_traded,
                    "investment": float(total_investment),
                    "broker": prepared_trade.broker_name
                },
                user_id=str(prepared_trade.user_id)
            )

            # Create trade execution record
            signal_conf = prepared_trade.metadata.get("signal_confidence", 0.7)
            signal_strength = float(signal_conf * 100) if signal_conf else 70.0

            trade_execution = AutoTradeExecution(
                user_id=prepared_trade.user_id,
                trade_id=trade_id,
                symbol=prepared_trade.stock_symbol,
                instrument_key=prepared_trade.option_instrument_key,
                strategy_name="supertrend_ema",
                signal_type=f"BUY_{prepared_trade.option_type}",
                signal_strength=signal_strength,
                strike_price=prepared_trade.strike_price,
                expiry_date=prepared_trade.expiry_date,
                entry_time=get_ist_now_naive(),
                entry_price=float(actual_entry_price),
                entry_order_id=broker_order_id,
                quantity=actual_quantity,
                lot_size=prepared_trade.lot_size,
                lots_traded=lots_traded,
                total_investment=float(total_investment),
                initial_stop_loss=float(prepared_trade.stop_loss),
                target_1=float(prepared_trade.target_price),
                target_2=float(prepared_trade.target_price * Decimal("1.1")),
                status="ACTIVE",
                # Multi-demat support - use actual broker details from config
                broker_name=prepared_trade.broker_name,
                broker_config_id=broker_config.id,
                allocated_capital=float(prepared_trade.total_investment),
                parent_trade_id=prepared_trade.parent_trade_id or None,
                trading_mode=prepared_trade.trading_mode,
                segment=prepared_trade.segment,
            )

            db.add(trade_execution)
            db.flush()

            # Create active position
            active_position = ActivePosition(
                trade_execution_id=trade_execution.id,
                user_id=prepared_trade.user_id,
                symbol=prepared_trade.stock_symbol,
                instrument_key=prepared_trade.option_instrument_key,
                current_price=float(actual_entry_price),
                current_pnl=0.0,
                current_pnl_percentage=0.0,
                current_stop_loss=float(prepared_trade.stop_loss),
                trailing_stop_triggered=False,
                highest_price_reached=float(actual_entry_price),
                unrealized_risk=float(prepared_trade.max_loss_amount),
                mark_to_market_time=get_ist_now_naive(),
                is_active=True,
                last_updated=get_ist_now_naive(),
            )

            db.add(active_position)
            db.commit()

            # Send Alert via AlertManager (Professional Unified Interface)
            from services.notifications.alert_manager import alert_manager
            self._safe_dispatch(alert_manager.notify_trade_entry(
                user_id=prepared_trade.user_id,
                trade_data={
                    "symbol": prepared_trade.stock_symbol,
                    "option_type": prepared_trade.option_type,
                    "entry_price": float(actual_entry_price),
                    "stop_loss": float(prepared_trade.stop_loss),
                    "target": float(prepared_trade.target_price),
                    "trading_mode": "live"
                }
            ))

            logger.info(f"✅ Live trade executed successfully: {trade_id}")

            return ExecutionResult(
                success=True,
                trade_id=trade_id,
                order_id=broker_order_id,
                entry_price=actual_entry_price,
                quantity=actual_quantity,
                status="EXECUTED",
                message="Live trade executed successfully",
                trade_execution_id=trade_execution.id,
                active_position_id=active_position.id,
                timestamp=get_ist_isoformat(),
                metadata={
                    "trading_mode": "live",
                    "broker": prepared_trade.broker_name,
                    "broker_order_id": broker_order_id,
                    "symbol": prepared_trade.stock_symbol,
                    "option_type": prepared_trade.option_type,
                    "strike": float(prepared_trade.strike_price),
                    "expiry": prepared_trade.expiry_date,
                },
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Error executing live trade: {e}")
            raise

    def exit_all_positions(
        self,
        user_id: int,
        db: Session,
        trading_mode: TradingMode
    ) -> Dict[str, Any]:
        """
        Emergency Exit: Close all active positions for a user

        Args:
            user_id: User identifier
            db: Database session
            trading_mode: Trading mode (Paper/Live)

        Returns:
            Dict with success status and summary
        """
        try:
            # 1. Get all active positions
            active_positions = db.query(ActivePosition).join(
                AutoTradeExecution,
                ActivePosition.trade_execution_id == AutoTradeExecution.id
            ).filter(
                ActivePosition.user_id == user_id,
                ActivePosition.is_active == True,
                AutoTradeExecution.trading_mode == trading_mode.value
            ).all()

            if not active_positions:
                return {"success": True, "message": "No active positions to exit"}

            logger.info(f"Emergency Exit: Found {len(active_positions)} active positions for user {user_id} ({trading_mode.value})")

            if trading_mode == TradingMode.PAPER:
                # Close all paper positions
                count = 0
                from services.paper_trading_account import paper_trading_service
                
                # Fetch paper account once
                paper_account = paper_trading_service.accounts.get(user_id)
                if not paper_account:
                    # Try to load from DB synchronously if not in memory
                    pass

                for position in active_positions:
                    try:
                        trade = position.trade_execution
                        current_price = float(position.current_price) if position.current_price else float(trade.entry_price)
                        
                        # Close logic
                        self._close_paper_position(db, position, trade, Decimal(str(current_price)), "EMERGENCY_EXIT")
                        count += 1
                    except Exception as e:
                        logger.error(f"Error closing paper position {position.id}: {e}")
                
                # CRITICAL: Commit changes to database
                db.commit()
                
                return {
                    "success": True, 
                    "message": f"Closed {count} paper positions", 
                    "closed_count": count
                }

            elif trading_mode == TradingMode.LIVE:
                # Close live positions via Upstox API
                
                broker_config = (
                    db.query(BrokerConfig)
                    .filter(
                        BrokerConfig.user_id == user_id,
                        BrokerConfig.is_active == True
                    )
                    .first()
                )

                if not broker_config:
                    raise ValueError("No active broker configuration found for live exit")

                if "upstox" in broker_config.broker_name.lower():
                    from services.upstox.upstox_order_service import get_upstox_order_service
                    
                    order_service = get_upstox_order_service(
                        access_token=broker_config.access_token,
                        use_sandbox=False
                    )
                    
                    # Call Exit All Positions API
                    result = order_service.exit_all_positions(tag="auto_trading")
                    
                    # Mark local DB positions as closed
                    for position in active_positions:
                        position.is_active = False
                        if position.trade_execution:
                            position.trade_execution.status = "CLOSED"
                            position.trade_execution.exit_reason = "EMERGENCY_EXIT"
                            position.trade_execution.exit_time = get_ist_now_naive()
                    
                    db.commit()
                    
                    return {
                        "success": result.get("success", False),
                        "message": result.get("message", "Live exit triggered"),
                        "details": result
                    }
                else:
                    return {"success": False, "message": f"Emergency exit not implemented for broker: {broker_config.broker_name}"}

            return {"success": False, "message": "Invalid trading mode"}

        except Exception as e:
            logger.error(f"Error in exit_all_positions: {e}")
            return {"success": False, "message": str(e)}

    def _close_paper_position(self, db: Session, position: ActivePosition, trade: AutoTradeExecution, exit_price: Decimal, reason: str):
        """Helper to close a single paper position synchronously"""
        # Calculate PnL
        entry_price = Decimal(str(trade.entry_price))
        quantity = trade.quantity
        
        buy_val = entry_price * Decimal(str(quantity))
        sell_val = exit_price * Decimal(str(quantity))
        gross_pnl = sell_val - buy_val
        
        # Charges
        brokerage = Decimal('40.0')
        taxes = (buy_val + sell_val) * Decimal('0.001')
        net_pnl = gross_pnl - brokerage - taxes
        
        total_inv = Decimal(str(trade.total_investment)) if trade.total_investment else buy_val
        pnl_pct = (net_pnl / total_inv * 100) if total_inv > 0 else 0

        # Update DB
        trade.exit_price = float(exit_price)
        trade.exit_time = get_ist_now_naive()
        trade.exit_reason = reason
        trade.gross_pnl = float(gross_pnl)
        trade.net_pnl = float(net_pnl)
        trade.pnl_percentage = float(pnl_pct)
        trade.status = "CLOSED"
        
        position.is_active = False
        position.last_updated = get_ist_now_naive()
        
        # Update Paper Account (DB)
        # BUG-08 FIX: The previous code did:
        #   available_margin += release   (release = sell_val - charges = investment + net_pnl)
        #   current_balance  += release   ← WRONG: adds full investment+profit to balance
        #   used_margin      -= total_inv
        #
        # The correct accounting:
        #   available_margin += total_inv + net_pnl  (release investment + realised profit/loss)
        #   current_balance  += net_pnl              (only the profit/loss changes the balance)
        #   used_margin      -= total_inv            (unblock the margin that was locked)
        from database.models import PaperTradingAccount
        paper_acc = db.query(PaperTradingAccount).filter(PaperTradingAccount.user_id == position.user_id).first()
        if paper_acc:
            paper_acc.available_margin += float(total_inv) + float(net_pnl)
            paper_acc.current_balance += float(net_pnl)
            paper_acc.used_margin = max(0.0, paper_acc.used_margin - float(total_inv))
            paper_acc.total_pnl += float(net_pnl)
            if hasattr(paper_acc, 'positions_count') and paper_acc.positions_count is not None:
                paper_acc.positions_count = max(0, paper_acc.positions_count - 1)

        # Sync in-memory paper account service if it exists
        from services.paper_trading_account import paper_trading_service
        mem_acc = paper_trading_service.accounts.get(position.user_id)
        if mem_acc and paper_acc:
            mem_acc.available_margin = float(paper_acc.available_margin)
            mem_acc.used_margin = float(paper_acc.used_margin)
            mem_acc.current_balance = float(paper_acc.current_balance)
            mem_acc.total_pnl = float(paper_acc.total_pnl)

        # Add ledger entry via fund_manager for statement accuracy
        # Previously emergency exit skipped this, causing the fund statement to be inconsistent.
        try:
            from services.trading_execution.fund_manager import fund_manager
            fund_manager.release_margin_and_settle(
                user_id=position.user_id,
                trading_mode="paper",
                reference_id=trade.trade_id,
                invested_amount=float(total_inv),
                gross_pnl=float(gross_pnl),
                brokerage=float(brokerage),
                taxes=float(taxes),
                db=db,
            )
        except Exception as ledger_err:
            logger.warning(f"Could not write ledger entry for emergency exit {trade.trade_id}: {ledger_err}")

        db.commit()


    def _place_broker_order(
        self, broker_config: BrokerConfig, prepared_trade: PreparedTrade, db: Session
    ) -> Dict[str, Any]:
        """
        Place order via broker API

        Args:
            broker_config: Broker configuration with credentials
            prepared_trade: Prepared trade details

        Returns:
            Order result dict with success, order_id, price, quantity
        """
        try:
            broker_name = broker_config.broker_name.lower()
            quantity = prepared_trade.position_size_lots * prepared_trade.lot_size

            # Determine transaction type (BUY for both CE and PE initial entry)
            transaction_type = "BUY"

            if "upstox" in broker_name:
                from services.upstox.upstox_order_service import get_upstox_order_service

                # Get Upstox Order Service with V3 API
                order_service = get_upstox_order_service(
                    access_token=broker_config.access_token,
                    use_sandbox=False
                )

                # Place order using V3 API with auto-slicing
                result = order_service.place_order_v3(
                    quantity=quantity,
                    instrument_token=prepared_trade.option_instrument_key,
                    order_type="MARKET",
                    transaction_type=transaction_type,
                    product=prepared_trade.product,  # I or D
                    validity="DAY",
                    price=0.0,  # Market order
                    trigger_price=0.0,
                    disclosed_quantity=0,
                    is_amo=False,
                    tag="auto_trading",
                    slice=True  # Enable auto-slicing for freeze quantity handling
                )

                if not result.get("success"):
                    raise Exception(f"Upstox order failed: {result.get('message')}")

                # Extract order IDs (may be multiple due to slicing)
                order_ids = result.get("data", {}).get("order_ids", [])
                primary_order_id = order_ids[0] if order_ids else None
                latency = result.get("metadata", {}).get("latency", 0)

                logger.info(
                    f"Upstox V3 order placed: {len(order_ids)} orders, "
                    f"latency: {latency}ms, IDs: {order_ids}"
                )

                # Calculate total investment for ledger
                actual_price = Decimal(str(prepared_trade.entry_price))
                total_investment = actual_price * Decimal(str(quantity))
                trade_id = f"LIVE_{primary_order_id}"

                # Record margin blocking in ledger for live trade (informational)
                fund_manager.block_margin(
                    user_id=prepared_trade.user_id,
                    amount=float(total_investment),
                    trading_mode="live",
                    reference_id=trade_id,
                    db=db
                )

                return {
                    "success": True,
                    "order_id": primary_order_id,
                    "order_ids": order_ids,  # All order IDs (for sliced orders)
                    "price": prepared_trade.entry_price,
                    "quantity": quantity,
                    "broker": "Upstox",
                    "latency_ms": latency,
                    "sliced": len(order_ids) > 1
                }

            elif "angel" in broker_name:
                from brokers.angel_broker import AngelOneBroker

                broker = AngelOneBroker(broker_config)

                order_result = broker.place_order(
                    symbol=prepared_trade.stock_symbol,
                    quantity=quantity,
                    order_type="MARKET",
                    transaction_type=transaction_type,
                )

                return {
                    "success": True,
                    "order_id": order_result.get("orderid"),
                    "price": prepared_trade.entry_price,
                    "quantity": quantity,
                    "broker": "AngelOne",
                }

            elif "dhan" in broker_name:
                from brokers.dhan_broker import DhanBroker

                broker = DhanBroker(broker_config)

                order_result = broker.place_order(
                    instrument_key=prepared_trade.option_instrument_key,
                    quantity=quantity,
                    order_type="MARKET",
                    transaction_type=transaction_type,
                )

                return {
                    "success": True,
                    "order_id": order_result.get("orderId"),
                    "price": prepared_trade.entry_price,
                    "quantity": quantity,
                    "broker": "Dhan",
                }

            else:
                raise ValueError(f"Unsupported broker: {broker_name}")

        except Exception as e:
            logger.error(f"Error placing broker order: {e}")
            return {"success": False, "message": str(e)}


# Create singleton instance
execution_handler = TradeExecutionHandler()
