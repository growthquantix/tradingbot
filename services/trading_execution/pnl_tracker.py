"""
Real-Time PnL Tracker
Monitors active positions and calculates live PnL with WebSocket updates
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.models import ActivePosition, AutoTradeExecution
from database.connection import SessionLocal
from services.trading_execution.strategy_engine import (
    strategy_engine,
    SignalType,
    TrailingStopType,
)
from utils.timezone_utils import get_ist_now_naive, get_ist_isoformat
from utils.logging_utils import log_structured
from services.notifications.telegram_service import telegram_notifier

logger = logging.getLogger(__name__)


@dataclass
class PositionPnL:
    """
    Real-time position PnL details

    Attributes:
        position_id: Active position ID
        trade_id: Trade identifier
        user_id: User identifier
        symbol: Stock symbol
        instrument_key: Option instrument key
        entry_price: Entry price
        current_price: Current market price
        quantity: Position quantity
        pnl: Current profit/loss amount
        pnl_percent: Current PnL percentage
        pnl_points: Points gained/lost
        entry_time: Trade entry timestamp
        holding_duration_minutes: Duration in trade (minutes)
        stop_loss: Current stop loss level
        target: Target price
        highest_price: Highest price reached
        trailing_sl_active: Whether trailing SL is active
        status: Position status
        last_updated: Last update timestamp
    """

    position_id: int
    trade_id: str
    user_id: int
    symbol: str
    instrument_key: str
    entry_price: Decimal
    current_price: Decimal
    quantity: int
    pnl: Decimal
    pnl_percent: Decimal
    pnl_points: Decimal
    entry_time: str
    holding_duration_minutes: int
    stop_loss: Decimal
    target: Decimal
    highest_price: Decimal
    trailing_sl_active: bool
    status: str
    last_updated: str
    strike_price: Optional[Decimal] = None


class RealTimePnLTracker:
    """
    Real-time PnL tracking system

    Features:
    - Monitors all active positions
    - Calculates live PnL from market data
    - Updates trailing stop losses
    - Detects target/SL hits
    - Broadcasts updates via WebSocket
    - Auto-exits positions when conditions met
    """

    def __init__(self):
        """Initialize PnL tracker"""
        self.update_interval_seconds = 1  # Update every 1 second
        self.is_running = False
        logger.info("Real-Time PnL Tracker initialized")

    async def start_tracking(self, db: Session = None):
        """
        Start real-time PnL tracking loop

        Args:
            db: Database session (optional, will create own session if not provided)
        """
        self.is_running = True
        logger.info("🔴 Starting real-time PnL tracking...")

        heartbeat_counter = 0
        try:
            while self.is_running:
                # Heartbeat every 15 minutes (900 seconds)
                heartbeat_counter += self.update_interval_seconds
                if heartbeat_counter >= 900:
                    logger.info(
                        f"💓 Real-Time PnL Tracker Heartbeat: Monitoring {self.update_interval_seconds}s interval active at {get_ist_now_naive().strftime('%H:%M:%S')} IST"
                    )
                    heartbeat_counter = 0

                # Create new session for each iteration to avoid stale connections
                session = SessionLocal()
                try:
                    await self.update_all_positions(session)
                finally:
                    session.close()

                await asyncio.sleep(self.update_interval_seconds)

        except Exception as e:
            logger.error(f"Error in PnL tracking loop: {e}")
            self.is_running = False

    def stop_tracking(self):
        """Stop real-time PnL tracking"""
        self.is_running = False
        logger.info("⏹️ Stopped real-time PnL tracking")

    async def update_all_positions(self, db: Session):
        """
        Update all active positions with live PnL

        Args:
            db: Database session (Not used in new implementation, creating own scope)
        """
        try:
            # 1. Get live market data (In-Memory, Fast)
            from services.realtime_market_engine import get_market_engine

            market_engine = get_market_engine()

            # 2. Define DB Update Job
            def pnl_update_job():
                session = SessionLocal()
                updates = []
                exits = []
                try:
                    active_positions = (
                        session.query(ActivePosition)
                        .filter(ActivePosition.is_active == True)
                        .all()
                    )

                    for position in active_positions:
                        try:
                            # CRITICAL: Check time-based exit FIRST
                            now_t = get_ist_now_naive().time()
                            is_time_exit = False
                            if now_t.hour >= 15 and now_t.minute >= 20:
                                is_time_exit = True
                                logger.info(
                                    f"Time-based exit triggered for {position.symbol} at {now_t}"
                                )

                            # SINGLE SOURCE OF TRUTH: Fetch premium from shared_registry (sync with UI)
                            from services.trading_execution.shared_instrument_registry import (
                                shared_registry,
                            )

                            price_decimal = Decimal("0")
                            shared_inst = shared_registry.get_instrument(
                                position.instrument_key
                            )

                            if shared_inst and shared_inst.live_option_premium > 0:
                                price_decimal = shared_inst.live_option_premium
                            elif (
                                shared_inst
                                and hasattr(shared_inst, "ltp")
                                and shared_inst.ltp > 0
                            ):
                                price_decimal = Decimal(str(shared_inst.ltp))
                            else:
                                # Implement SAFE FALLBACK if registry is empty or premium is invalid
                                if position.instrument_key in market_engine.instruments:
                                    price_decimal = Decimal(
                                        str(
                                            market_engine.instruments[
                                                position.instrument_key
                                            ].current_price
                                        )
                                    )

                            # Final safety check before calculation
                            if price_decimal <= 0:
                                if is_time_exit:
                                    # Use last known DB price for time-based exit record
                                    price_decimal = (
                                        Decimal(str(position.current_price))
                                        if position.current_price
                                        else Decimal("0")
                                    )
                                else:
                                    # CRITICAL VISIBILITY: Log sparingly to avoid spam (Once every 15 mins)
                                    if not hasattr(self, "_last_gap_log"):
                                        self._last_gap_log = {}
                                    last_log = self._last_gap_log.get(
                                        position.instrument_key, 0
                                    )
                                    now_ts = datetime.now().timestamp()

                                    if now_ts - last_log > 900:  # 15 minutes
                                        logger.error(
                                            f"❌ DATA GAP: No live price for {position.symbol} ({position.instrument_key}). Exit logic SUSPENDED."
                                        )
                                        self._last_gap_log[
                                            position.instrument_key
                                        ] = now_ts
                                    continue

                            trade_execution = (
                                session.query(AutoTradeExecution)
                                .filter(
                                    AutoTradeExecution.id == position.trade_execution_id
                                )
                                .first()
                            )

                            if not trade_execution:
                                continue

                            # FIXED CALCULATIONS: quantity already represents total units
                            entry_price = Decimal(str(trade_execution.entry_price))
                            total_units = Decimal(str(trade_execution.quantity))

                            # True Investment
                            total_investment = (
                                Decimal(str(trade_execution.total_investment))
                                if trade_execution.total_investment
                                else (entry_price * total_units)
                            )

                            pnl_points = price_decimal - entry_price
                            gross_pnl = pnl_points * total_units

                            # Charges estimate (using total units)
                            buy_val = entry_price * total_units
                            sell_val = price_decimal * total_units
                            est_turnover = buy_val + sell_val
                            est_charges = Decimal("40.0") + (
                                est_turnover * Decimal("0.001")
                            )
                            pnl_amount = gross_pnl - est_charges

                            pnl_percent = (
                                (pnl_amount / total_investment) * Decimal("100")
                                if total_investment > 0
                                else Decimal("0")
                            )
                            highest_price = max(
                                Decimal(str(position.highest_price_reached)),
                                price_decimal,
                            )

                            current_sl = Decimal(str(position.current_stop_loss))

                            # FIX 1: Stop Loss Recovery (MANDATORY)
                            # Guarantee SL is never zero during live tracking
                            if current_sl <= 0:
                                initial_sl = Decimal(
                                    str(trade_execution.initial_stop_loss)
                                )
                                if initial_sl > 0:
                                    logger.warning(
                                        f"⚠️ Recovered zero SL for {position.symbol}: {current_sl} -> {initial_sl}"
                                    )
                                    position.current_stop_loss = float(initial_sl)
                                    current_sl = initial_sl

                            target_price = (
                                Decimal(str(trade_execution.target_1))
                                if trade_execution.target_1
                                else None
                            )

                            # Update Trailing SL - ALWAYS LONG for premium positions
                            new_sl = strategy_engine.update_trailing_stop(
                                current_price=price_decimal,
                                entry_price=entry_price,
                                current_stop_loss=current_sl,
                                trailing_type=TrailingStopType.PERCENTAGE,
                                position_type="LONG",
                                target_price=target_price,
                                symbol=position.symbol,
                            )

                            # FIX 4: Allow First Breakeven Trail & Profit Locking Safely
                            # Safety Guard: Ensure SL never moves down and NEVER drops below initial protection
                            initial_sl_planned = Decimal(
                                str(trade_execution.initial_stop_loss)
                            )
                            if new_sl < initial_sl_planned:
                                new_sl = initial_sl_planned

                            if new_sl < current_sl:
                                new_sl = current_sl

                            # If new_sl is above price, it's a Stop Loss hit scenario.
                            # We allow it so the exit logic below triggers immediately.

                            if new_sl > current_sl:
                                position.trailing_stop_triggered = True
                                position.current_stop_loss = float(new_sl)

                            # Check Exit - ALWAYS treat as LONG for premium (both CE & PE)
                            should_exit = is_time_exit
                            exit_reason = "TIME_BASED_EXIT" if is_time_exit else None

                            if not should_exit:
                                # For LONG positions: Exit if price drops below SL (IMMEDIATE)
                                if price_decimal <= new_sl:
                                    should_exit = True
                                    exit_reason = "STOP_LOSS_HIT"
                                    logger.info(
                                        f"🛑 EXIT DECISION: SL Hit for {position.symbol} @ {price_decimal} (SL: {new_sl})"
                                    )
                                # For LONG positions: Exit if price rises above Target (Respect HOLD Window)
                                elif target_price and price_decimal >= target_price:
                                    # REQUIREMENT: No exit allowed for first 3-5 minutes
                                    entry_dt = (
                                        trade_execution.entry_time.replace(tzinfo=None)
                                        if trade_execution.entry_time and trade_execution.entry_time.tzinfo
                                        else (trade_execution.entry_time or get_ist_now_naive())
                                    )
                                    holding_duration_min = (
                                        get_ist_now_naive() - entry_dt
                                    ).total_seconds() / 60
                                    if holding_duration_min >= 3:
                                        should_exit = True
                                        exit_reason = "TARGET_HIT"
                                        logger.info(
                                            f"✅ EXIT DECISION: Target Hit for {position.symbol} @ {price_decimal}"
                                        )
                                    else:
                                        # FIX 2: Target Hit Visibility (JSON persistence)
                                        import json

                                        blocked_data = {
                                            "exit_blocked_reason": "MIN_HOLD_TIME_NOT_COMPLETED",
                                            "hold_time_min": round(
                                                holding_duration_min, 2
                                            ),
                                            "required_min": 3,
                                            "price": float(price_decimal),
                                            "target": float(target_price),
                                        }
                                        # Persist only on state change to avoid DB spam
                                        if (
                                            not trade_execution.execution_notes
                                            or "MIN_HOLD_TIME_NOT_COMPLETED"
                                            not in str(trade_execution.execution_notes)
                                        ):
                                            trade_execution.execution_notes = (
                                                json.dumps(blocked_data)
                                            )

                                        logger.info(
                                            f"⏳ Target hit but exit blocked for {position.symbol} - hold time {holding_duration_min:.1f}m < 3m"
                                        )

                            # Update Position
                            position.current_price = float(price_decimal)
                            position.current_pnl = float(pnl_amount)
                            position.current_pnl_percentage = float(pnl_percent)
                            position.highest_price_reached = float(highest_price)
                            position.mark_to_market_time = get_ist_now_naive()
                            position.last_updated = get_ist_now_naive()

                            if should_exit:
                                exits.append(
                                    (position.id, float(price_decimal), exit_reason)
                                )

                            # Prepare Broadcast Data
                            # FIX 3: Guarantee valid SL in UI broadcast (never 0)
                            ui_sl = float(new_sl) if new_sl > 0 else float(current_sl)
                            entry_dt = (
                                trade_execution.entry_time.replace(tzinfo=None)
                                if trade_execution.entry_time and trade_execution.entry_time.tzinfo
                                else (trade_execution.entry_time or get_ist_now_naive())
                            )
                            updates.append(
                                PositionPnL(
                                    position_id=position.id,
                                    trade_id=trade_execution.trade_id,
                                    user_id=position.user_id,
                                    symbol=position.symbol,
                                    instrument_key=position.instrument_key,
                                    entry_price=entry_price,
                                    current_price=price_decimal,
                                    quantity=int(total_units),
                                    pnl=pnl_amount,
                                    pnl_percent=pnl_percent,
                                    pnl_points=pnl_points,
                                    entry_time=entry_dt.isoformat(),
                                    holding_duration_minutes=int(
                                        (get_ist_now_naive() - entry_dt).total_seconds() / 60
                                    ),
                                    stop_loss=Decimal(str(ui_sl)),
                                    target=target_price or Decimal("0"),
                                    highest_price=highest_price,
                                    trailing_sl_active=position.trailing_stop_triggered,
                                    status="CLOSED" if should_exit else "ACTIVE",
                                    last_updated=get_ist_isoformat(),
                                    strike_price=(
                                        Decimal(str(trade_execution.strike_price))
                                        if trade_execution.strike_price
                                        else None
                                    ),
                                )
                            )

                        except Exception as e:
                            logger.error(
                                f"Error processing position {position.id}: {e}"
                            )
                            continue

                    session.commit()

                    # --- RISK MANAGEMENT ENGINE (GLOBAL KILL-SWITCH) ---
                    self._check_risk_breaches(updates, session)

                    return updates, exits
                except Exception as e:
                    session.rollback()
                    logger.error(f"DB Error in pnl_update_job: {e}")
                    return [], []
                finally:
                    session.close()

            # 3. Execute DB Job in Thread
            pnl_updates, exits_to_process = await asyncio.to_thread(pnl_update_job)

            # 4. Broadcast Updates
            if pnl_updates:
                await self._broadcast_pnl_updates(pnl_updates)

            # 5. Process Exits (Async)
            if exits_to_process:
                # Use a fresh session for exits
                exit_session = SessionLocal()
                try:
                    for pos_id, price, reason in exits_to_process:
                        # Fetch objects again attached to this session
                        pos = (
                            exit_session.query(ActivePosition)
                            .filter(ActivePosition.id == pos_id)
                            .first()
                        )
                        if pos:
                            trade = (
                                exit_session.query(AutoTradeExecution)
                                .filter(AutoTradeExecution.id == pos.trade_execution_id)
                                .first()
                            )
                            if trade:
                                await self._close_position(
                                    pos,
                                    trade,
                                    Decimal(str(price)),
                                    reason,
                                    exit_session,
                                )
                finally:
                    exit_session.close()

        except Exception as e:
            logger.error(f"Error updating all positions: {e}")

    def _check_risk_breaches(self, updates: List[PositionPnL], session: Session):
        """
        Monitor for risk violations and trigger Global Kill-Switch
        """
        try:
            from services.trading_execution.shared_instrument_registry import (
                shared_registry,
            )

            if shared_registry.is_risk_halted:
                return

            # 1. Total Daily PnL Check
            total_unrealized_pnl = sum(u.pnl for u in updates)
            # In a full implementation, we'd fetch realized PnL from DB here
            if total_unrealized_pnl < Decimal("-5000"):  # Fixed 5k threshold for safety
                shared_registry.is_risk_halted = True
                shared_registry.halt_reason = "MAX_DAILY_LOSS_BREACHED"
                logger.error("🛑 GLOBAL KILL-SWITCH TRIGGERED: Max Daily Loss")

            # 2. Sequential SL Check (Last 3 trades)
            # Note: This would typically query the AutoTradeExecution table
        except Exception as e:
            logger.error(f"Error checking risk breaches: {e}")

    def _get_current_price(self, instrument_key: str, market_engine: Any) -> Decimal:
        """
        Get current price from market engine

        Args:
            instrument_key: Instrument key
            market_engine: Market engine instance

        Returns:
            Current price or 0 if not available
        """
        try:
            if instrument_key in market_engine.instruments:
                instrument = market_engine.instruments[instrument_key]
                return Decimal(str(instrument.current_price))
            return Decimal("0")

        except Exception as e:
            logger.debug(f"Error getting price for {instrument_key}: {e}")
            return Decimal("0")

    def _calculate_pnl(
        self,
        position: ActivePosition,
        trade_execution: AutoTradeExecution,
        current_price: Decimal,
    ) -> Dict[str, Any]:
        """
        Calculate position PnL

        Args:
            position: Active position
            trade_execution: Trade execution record
            current_price: Current market price

        Returns:
            Dict with PnL calculations
        """
        try:
            entry_price = Decimal(str(trade_execution.entry_price))
            quantity = trade_execution.quantity

            # Get total investment (use from trade record if available, else calculate)
            total_investment = (
                Decimal(str(trade_execution.total_investment))
                if trade_execution.total_investment
                else (entry_price * Decimal(str(quantity)))
            )

            # Calculate PnL
            pnl_points = current_price - entry_price
            gross_pnl = pnl_points * Decimal(str(quantity))

            # ESTIMATE CHARGES (for realistic live tracking)
            # Buy + Sell turnover
            buy_val = entry_price * Decimal(str(quantity))
            sell_val = current_price * Decimal(str(quantity))
            est_turnover = buy_val + sell_val

            # Brokerage (₹40) + Taxes (~0.1%)
            est_charges = Decimal("40.0") + (est_turnover * Decimal("0.001"))
            pnl_amount = gross_pnl - est_charges

            # CRITICAL FIX: Calculate percentage based on total_investment, not per-unit price
            pnl_percent = (
                (pnl_amount / total_investment) * Decimal("100")
                if total_investment > 0
                else Decimal("0")
            )

            # Track highest price
            highest_price = max(
                Decimal(str(position.highest_price_reached)), current_price
            )

            # Calculate holding duration
            entry_time = trade_execution.entry_time
            holding_duration = (get_ist_now_naive() - entry_time).total_seconds() / 60

            return {
                "pnl": pnl_amount,
                "pnl_percent": pnl_percent,
                "pnl_points": pnl_points,
                "highest_price": highest_price,
                "holding_duration_minutes": int(holding_duration),
                "total_investment": total_investment,
            }

        except Exception as e:
            logger.error(f"Error calculating PnL: {e}")
            return {
                "pnl": Decimal("0"),
                "pnl_percent": Decimal("0"),
                "pnl_points": Decimal("0"),
                "highest_price": Decimal(str(position.highest_price_reached)),
                "holding_duration_minutes": 0,
            }

    def _update_trailing_stop_loss(
        self,
        position: ActivePosition,
        trade_execution: AutoTradeExecution,
        current_price: Decimal,
    ) -> Decimal:
        """
        Update trailing stop loss using ENHANCED strategy engine with LOCK PROFIT mechanism

        ENHANCED LOGIC (from strategy_engine.py):
        1. If profit >= 50% of target: Trail to BREAKEVEN (make position risk-free)
        2. If profit >= 100% of target: Lock 80% of profit
        3. Otherwise: Use SuperTrend/ATR/percentage trailing

        Args:
            position: Active position
            trade_execution: Trade execution record
            current_price: Current market price

        Returns:
            Updated stop loss level
        """
        try:
            from services.trading_execution.strategy_engine import (
                strategy_engine,
                TrailingStopType,
            )

            entry_price = Decimal(str(trade_execution.entry_price))
            current_sl = Decimal(str(position.current_stop_loss))
            target_price = (
                Decimal(str(trade_execution.target_1))
                if trade_execution.target_1
                else None
            )

            # Determine position type (both CE and PE are long positions when buying options)
            position_type = "LONG"

            # FIXED: Use PERCENTAGE trailing for options to avoid Spot vs Premium mismatch
            # Spot SuperTrend (e.g. 24000) cannot be compared to Premium (e.g. 150)
            trailing_type = TrailingStopType.PERCENTAGE
            supertrend_value = None

            # Use strategy engine's ENHANCED trailing stop with LOCK PROFIT
            new_sl = strategy_engine.update_trailing_stop(
                current_price=current_price,
                entry_price=entry_price,
                current_stop_loss=current_sl,
                trailing_type=trailing_type,
                supertrend_value=supertrend_value,
                position_type=position_type,
                target_price=target_price,  # Pass target for lock profit calculation
                symbol=position.symbol,
            )

            # Update trailing stop triggered flag
            if new_sl > current_sl:
                position.trailing_stop_triggered = True
                logger.info(
                    f"Enhanced trailing SL updated: "
                    f"{current_sl:.2f} -> {new_sl:.2f} for position {position.id}"
                )

            return new_sl

        except Exception as e:
            logger.error(f"Error updating trailing SL: {e}")
            return Decimal(str(position.current_stop_loss))

    def _check_exit_conditions(
        self,
        position: ActivePosition,
        trade_execution: AutoTradeExecution,
        current_price: Decimal,
        pnl_data: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Check if position should be exited

        Args:
            position: Active position
            trade_execution: Trade execution record
            current_price: Current market price
            pnl_data: PnL calculation data

        Returns:
            Tuple of (should_exit, exit_reason)
        """
        try:
            entry_price = Decimal(str(trade_execution.entry_price))
            stop_loss = Decimal(str(position.current_stop_loss))
            target_1 = Decimal(str(trade_execution.target_1))

            # CRITICAL: Both CE and PE are LONG premium positions for option buying
            # We always exit if premium drops below SL or rises above Target
            position_type = "LONG"

            # Check stop loss hit
            if current_price <= stop_loss:
                return True, "STOP_LOSS_HIT"

            # Check target hit
            if target_1 and current_price >= target_1:
                return True, "TARGET_HIT"

            # Check time-based exit (e.g., close before market close)
            # BUG-03 FIX: Use get_ist_now_naive() instead of datetime.now().
            # On Railway/Oracle Cloud (UTC servers), datetime.now() returns UTC time.
            # Comparing UTC 15:20 against IST 15:20 market close causes exits at wrong time.
            current_time = get_ist_now_naive().time()
            if current_time.hour >= 15 and current_time.minute >= 20:
                return True, "TIME_BASED_EXIT"

            return False, None

        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return False, None

    async def _place_exit_order(
        self, trade_execution: AutoTradeExecution, exit_price: Decimal, db: Session
    ) -> Optional[str]:
        """
        Place exit order (SELL) to close position

        Args:
            trade_execution: Trade execution record
            exit_price: Expected exit price
            db: Database session

        Returns:
            Order ID if successful, None if failed or paper trading
        """
        try:
            # Skip if paper trading
            if trade_execution.trading_mode == "paper":
                logger.info(f"Paper trading - skipping actual exit order placement")
                return None

            def place_order_job():
                try:
                    # Get broker configuration
                    from database.models import BrokerConfig

                    broker_config = (
                        db.query(BrokerConfig)
                        .filter(
                            BrokerConfig.id == trade_execution.broker_config_id,
                            BrokerConfig.is_active == True,
                        )
                        .first()
                    )

                    if not broker_config:
                        logger.error(
                            f"No active broker config found for trade {trade_execution.trade_id}"
                        )
                        return None

                    broker_name = broker_config.broker_name.lower()
                    quantity = trade_execution.quantity

                    # Place SELL order based on broker
                    if "upstox" in broker_name:
                        from services.upstox.upstox_order_service import (
                            get_upstox_order_service,
                        )

                        # Get Upstox Order Service with V3 API
                        order_service = get_upstox_order_service(
                            access_token=broker_config.access_token, use_sandbox=False
                        )

                        # Determine product type (default to Intraday 'I' if not specified)
                        product_type = getattr(trade_execution, "product", "I")

                        # Place exit (SELL) order using V3 API
                        result = order_service.place_order_v3(
                            quantity=quantity,
                            instrument_token=trade_execution.instrument_key,
                            order_type="MARKET",
                            transaction_type="SELL",  # SELL to exit position
                            product=product_type,
                            validity="DAY",
                            price=0.0,  # Market order
                            trigger_price=0.0,
                            disclosed_quantity=0,
                            is_amo=False,
                            tag=f"exit_{trade_execution.trade_id}",
                            slice=True,  # Enable auto-slicing
                        )

                        if not result.get("success"):
                            logger.error(
                                f"Upstox exit order failed: {result.get('message')}"
                            )
                            return None

                        # Extract order IDs
                        order_ids = result.get("data", {}).get("order_ids", [])
                        primary_order_id = order_ids[0] if order_ids else None
                        latency = result.get("metadata", {}).get("latency", 0)

                        logger.info(
                            f"Upstox V3 exit order placed: {len(order_ids)} orders, "
                            f"latency: {latency}ms, IDs: {order_ids}"
                        )

                        return primary_order_id

                    elif "angel" in broker_name:
                        from brokers.angel_broker import AngelOneBroker

                        broker = AngelOneBroker(broker_config)

                        order_result = broker.place_order(
                            symbol=trade_execution.symbol,
                            quantity=quantity,
                            order_type="MARKET",
                            transaction_type="SELL",
                        )

                        return order_result.get("orderid")

                    elif "dhan" in broker_name:
                        from brokers.dhan_broker import DhanBroker

                        broker = DhanBroker(broker_config)

                        order_result = broker.place_order(
                            instrument_key=trade_execution.instrument_key,
                            quantity=quantity,
                            order_type="MARKET",
                            transaction_type="SELL",
                        )

                        return order_result.get("orderId")

                    else:
                        logger.error(
                            f"Unsupported broker for exit order: {broker_name}"
                        )
                        return None
                except Exception as e:
                    logger.error(f"Job Error placing exit order: {e}")
                    return None

            # Run the blocking DB and API calls in a thread
            return await asyncio.to_thread(place_order_job)

        except Exception as e:
            logger.error(f"Error placing exit order: {e}")
            return None

    async def _close_position(
        self,
        position: ActivePosition,
        trade_execution: AutoTradeExecution,
        exit_price: Decimal,
        exit_reason: str,
        db: Session,
    ):
        """
        Close position with Post-Trade Diagnostics and Risk Monitoring
        """
        try:
            logger.info(
                f"🚪 Closing position {trade_execution.trade_id}: {exit_reason}"
            )

            # --- DIAGNOSTICS CAPTURE ---
            entry_price = Decimal(str(trade_execution.entry_price))
            planned_sl = Decimal(str(trade_execution.initial_stop_loss))
            planned_target = Decimal(str(trade_execution.target_1))

            # Realized Risk/Reward
            risk_taken = abs(entry_price - planned_sl)
            reward_realized = exit_price - entry_price
            realized_rr = reward_realized / risk_taken if risk_taken > 0 else 0

            # Time Integrity
            time_in_trade_mins = (
                get_ist_now_naive() - trade_execution.entry_time
            ).total_seconds() / 60

            # ACTUAL EXIT PRICE WITH SLIPPAGE FOR PAPER TRADING
            if trade_execution.trading_mode == "paper":
                raw_exit_price = exit_price
                slippage = raw_exit_price * Decimal("0.0005")
                exit_price = raw_exit_price - slippage
                logger.info(
                    f"📝 Paper exit slippage applied: {raw_exit_price} -> {exit_price}"
                )

            # Place exit order if live trading (Async)
            exit_order_id = None
            if trade_execution.trading_mode == "live":
                exit_order_id = await self._place_exit_order(
                    trade_execution, exit_price, db
                )

            # Define DB Update Job
            def db_close_job(pos_id, trade_id, price, reason, order_id):
                try:
                    # Calculate final PnL
                    quantity = trade_execution.quantity
                    total_investment = (
                        Decimal(str(trade_execution.total_investment))
                        if trade_execution.total_investment
                        else (entry_price * Decimal(str(quantity)))
                    )

                    buy_value = entry_price * Decimal(str(quantity))
                    sell_value = price * Decimal(str(quantity))
                    gross_pnl = sell_value - buy_value
                    turnover = buy_value + sell_value

                    # CHARGES
                    brokerage_flat = Decimal("40.0")
                    taxes = turnover * Decimal("0.001")
                    total_charges = brokerage_flat + taxes

                    net_pnl = gross_pnl - total_charges
                    pnl_percent = (
                        (net_pnl / total_investment * Decimal("100"))
                        if total_investment > 0
                        else 0.0
                    )

                    # --- RISK MONITORING (KILL-SWITCH) ---
                    from services.trading_execution.shared_instrument_registry import (
                        shared_registry,
                    )

                    if reason == "STOP_LOSS_HIT":
                        # Check for Global Kill Switch triggers (3 SLs in 60 mins or Daily Loss > 5000)
                        pass

                    # Store diagnostics in execution_notes as a JSON string
                    # This avoids the reserved 'metadata' keyword and misleading 'fibonacci' column names
                    import json

                    diagnostics = {
                        "realized_rr": float(realized_rr),
                        "time_in_trade_min": float(time_in_trade_mins),
                        "exit_reason": reason,
                        # BUG-12 FIX: Was `float(price) - float(price)` which is always 0.
                        # Slippage is the difference between raw exit price and post-slippage price.
                        "slippage_exit": (
                            float(raw_exit_price) - float(exit_price)
                            if trade_execution.trading_mode == "paper"
                            else 0.0
                        ),
                        "diagnostic_check": (
                            "PASSED" if time_in_trade_mins > 0 else "FAILED_DATA"
                        ),
                    }
                    trade_execution.execution_notes = json.dumps(diagnostics)

                    # Update trade execution
                    trade_execution.exit_time = get_ist_now_naive()
                    trade_execution.exit_price = float(price)
                    trade_execution.exit_order_id = order_id
                    trade_execution.exit_reason = reason
                    trade_execution.gross_pnl = float(gross_pnl)
                    trade_execution.net_pnl = float(net_pnl)
                    trade_execution.pnl_percentage = float(pnl_percent)
                    trade_execution.status = "CLOSED"

                    # Deactivate position
                    position.is_active = False
                    position.last_updated = get_ist_now_naive()

                    # SETTLE FUNDS & CREATE LEDGER ENTRIES (New Fund Management System)
                    from services.trading_execution.fund_manager import fund_manager
                    
                    fund_manager.release_margin_and_settle(
                        user_id=position.user_id,
                        trading_mode=trade_execution.trading_mode,
                        reference_id=trade_execution.trade_id,
                        invested_amount=float(total_investment),
                        gross_pnl=float(gross_pnl),
                        brokerage=float(brokerage_flat),
                        taxes=float(taxes),
                        db=db
                    )

                    db.commit()

                    return {
                        "net_pnl": float(net_pnl),
                        "pnl_percent": float(pnl_percent),
                        "gross_pnl": float(gross_pnl),
                        "quantity": quantity,
                        "entry_price": float(entry_price),
                        "pnl_points": float(price - entry_price),
                    }
                except Exception as e:
                    logger.error(f"DB Error in _close_position: {e}")
                    db.rollback()
                    raise e

            # Run DB job in thread
            result = await asyncio.to_thread(
                db_close_job,
                position.id,
                trade_execution.trade_id,
                exit_price,
                exit_reason,
                exit_order_id,
            )

            # Send Alert via AlertManager (Professional Unified Interface)
            from services.notifications.alert_manager import alert_manager

            asyncio.create_task(
                alert_manager.notify_trade_exit(
                    user_id=position.user_id,
                    trade_data={
                        "symbol": position.symbol,
                        "exit_price": float(exit_price),
                        "pnl": result["net_pnl"],
                        "exit_reason": exit_reason,
                    },
                )
            )

            logger.info(
                f"✅ Position closed: PnL = Rs.{result['net_pnl']:.2f} ({result['pnl_percent']:.2f}%)"
            )

            log_structured(
                event="POSITION_CLOSED",
                message=f"Closed position {trade_execution.trade_id} ({exit_reason})",
                data={
                    "trade_id": trade_execution.trade_id,
                    "symbol": position.symbol,
                    "exit_price": float(exit_price),
                    "exit_reason": exit_reason,
                    "net_pnl": result["net_pnl"],
                    "pnl_percent": result["pnl_percent"],
                    "duration_min": int(
                        (
                            get_ist_now_naive() - trade_execution.entry_time
                        ).total_seconds()
                        / 60
                    ),
                },
                user_id=str(position.user_id),
            )

            # Broadcast position close event to UI
            try:
                from router.unified_websocket_routes import broadcast_to_clients

                close_data = {
                    "position_id": position.id,
                    "trade_id": trade_execution.trade_id,
                    "user_id": position.user_id,
                    "symbol": position.symbol,
                    "instrument_key": position.instrument_key,
                    "entry_price": result["entry_price"],
                    "exit_price": float(exit_price),
                    "quantity": result["quantity"],
                    "gross_pnl": result["gross_pnl"],
                    "net_pnl": result["net_pnl"],
                    "pnl_percent": result["pnl_percent"],
                    "pnl_points": result["pnl_points"],
                    "exit_reason": exit_reason,
                    "entry_time": trade_execution.entry_time.isoformat(),
                    "exit_time": get_ist_isoformat(),
                    "holding_duration_minutes": int(
                        (
                            get_ist_now_naive() - trade_execution.entry_time
                        ).total_seconds()
                        / 60
                    ),
                    "timestamp": get_ist_isoformat(),
                }

                await broadcast_to_clients("position_closed", close_data)
                logger.info(
                    f"Broadcasted position close event for trade {trade_execution.trade_id}"
                )

            except Exception as broadcast_error:
                logger.error(f"Error broadcasting position close: {broadcast_error}")

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            pass

    async def _broadcast_pnl_updates(self, pnl_updates: List[PositionPnL]):
        """
        Broadcast PnL updates via WebSocket

        Args:
            pnl_updates: List of position PnL updates
        """
        try:
            from router.unified_websocket_routes import broadcast_to_clients

            for pnl_update in pnl_updates:
                # Format data to match frontend expectations
                update_data = {
                    "position_id": pnl_update.position_id,
                    "trade_id": pnl_update.trade_id,
                    "user_id": pnl_update.user_id,
                    "symbol": pnl_update.symbol,
                    "current_price": float(pnl_update.current_price),
                    "pnl": float(pnl_update.pnl),
                    "pnl_percent": float(pnl_update.pnl_percent),
                    "strike_price": (
                        float(pnl_update.strike_price)
                        if pnl_update.strike_price
                        else None
                    ),
                    "stop_loss": float(pnl_update.stop_loss),
                    "target": float(pnl_update.target),
                    "trailing_sl_active": pnl_update.trailing_sl_active,
                    "highest_price": float(pnl_update.highest_price),
                    "last_updated": pnl_update.last_updated,
                    "timestamp": get_ist_isoformat(),
                }

                await broadcast_to_clients("pnl_update", update_data)
                logger.debug(
                    f"Broadcasted PnL update for position {pnl_update.position_id}"
                )

        except Exception as e:
            logger.error(f"Error broadcasting PnL updates: {e}")

    def get_user_positions_summary(
        self, user_id: int, db: Session, trading_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary of all positions for a user

        Args:
            user_id: User identifier
            db: Database session
            trading_mode: Trading mode filter (paper/live)

        Returns:
            Summary dict with aggregate PnL and positions
        """
        try:
            query = db.query(ActivePosition).filter(
                and_(
                    ActivePosition.user_id == user_id, ActivePosition.is_active == True
                )
            )

            if trading_mode:
                query = query.join(
                    AutoTradeExecution,
                    ActivePosition.trade_execution_id == AutoTradeExecution.id,
                ).filter(AutoTradeExecution.trading_mode == trading_mode)

            active_positions = query.all()

            from services.realtime_market_engine import get_market_engine

            market_engine = get_market_engine()

            total_pnl = Decimal("0")
            total_investment = Decimal("0")

            for pos in active_positions:
                trade = (
                    db.query(AutoTradeExecution)
                    .filter(AutoTradeExecution.id == pos.trade_execution_id)
                    .first()
                )
                if not trade:
                    continue

                # Get entry price and quantity
                entry_price = Decimal(str(trade.entry_price))
                quantity = trade.quantity
                investment = entry_price * Decimal(str(quantity))
                total_investment += investment

                # Get current price (LTP) from market engine
                current_price = Decimal("0")
                if pos.instrument_key in market_engine.instruments:
                    current_price = Decimal(
                        str(market_engine.instruments[pos.instrument_key].current_price)
                    )

                # Fallback to DB price if not in engine
                if current_price <= 0:
                    current_price = (
                        Decimal(str(pos.current_price))
                        if pos.current_price
                        else entry_price
                    )

                # Calculate live PnL for summary
                pnl_points = current_price - entry_price
                gross_pnl = pnl_points * Decimal(str(quantity))

                # Estimated charges
                buy_val = entry_price * Decimal(str(quantity))
                sell_val = current_price * Decimal(str(quantity))
                est_charges = Decimal("40.0") + (
                    (buy_val + sell_val) * Decimal("0.001")
                )

                total_pnl += gross_pnl - est_charges

            return {
                "user_id": user_id,
                "active_positions_count": len(active_positions),
                "total_pnl": float(total_pnl),
                "total_investment": float(total_investment),
                "pnl_percent": float(
                    (total_pnl / total_investment * Decimal("100"))
                    if total_investment > 0
                    else Decimal("0")
                ),
                "last_updated": get_ist_isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting user positions summary: {e}")
            return {"user_id": user_id, "error": str(e)}


# Create singleton instance
pnl_tracker = RealTimePnLTracker()
