"""
Trading Execution API Router
API endpoints for automated trading with paper/live modes, real-time PnL, and position management
"""

import asyncio
from datetime import date
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from decimal import Decimal

from database.connection import get_db
from database.models import (
    BrokerConfig,
    SelectedStock,
    User,
    ActivePosition,
    AutoTradeExecution,
    UserTradingConfig,
)
from router.auth_router import get_current_user
from utils.timezone_utils import get_ist_now_naive, get_ist_isoformat
from services.trading_execution import (
    trade_prep_service,
    execution_handler,
    pnl_tracker,
    TradingMode,
    TradeStatus,
)
from services.enhanced_intelligent_options_selection import enhanced_options_service
from services.trading_execution.multi_demat_capital_service import (
    multi_demat_capital_service,
)
from services.trading_execution.fund_manager import fund_manager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/trading/execution", tags=["Trading Execution"])


# ==================== Request Models ====================


class ExecuteTradeRequest(BaseModel):
    """Request model for trade execution"""

    stock_symbol: str = Field(..., description="Stock symbol")
    option_instrument_key: str = Field(..., description="Option instrument key")
    option_type: str = Field(..., description="CE or PE")
    strike_price: Decimal = Field(..., description="Strike price")
    expiry_date: str = Field(..., description="Expiry date (YYYY-MM-DD)")
    lot_size: Optional[int] = Field(None, description="Lot size (optional, will be fetched if not provided)")
    trading_mode: str = Field("paper", description="Trading mode: paper or live")


class TradingModeConfig(BaseModel):
    """Trading mode configuration"""

    mode: str = Field(..., description="paper or live")
    auto_execute: bool = Field(False, description="Auto-execute trades")


# ==================== Endpoints ====================


@router.post("/emergency-exit-all")
async def emergency_exit_all(
    confirm: bool = Query(..., description="Confirmation flag to proceed"),
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Emergency Exit: Close ALL active positions immediately

    **Process:**
    - Live: Uses Broker's 'Exit All Positions' API for fastest execution.
    - Paper: Closes all virtual positions.
    - Updates database state.

    **Requires:** confirm=True
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required for emergency exit")

    try:
        from services.trading_execution.execution_handler import execution_handler
        mode = TradingMode(trading_mode)

        result = execution_handler.exit_all_positions(
            user_id=current_user.id,
            db=db,
            trading_mode=mode
        )

        return {
            "success": result.get("success", False),
            "message": result.get("message", "Emergency exit initiated"),
            "details": result
        }

    except Exception as e:
        logger.error(f"Error in emergency exit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare-trade")
async def prepare_trade(
    request: ExecuteTradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Prepare trade with validation, capital check, and strategy signal

    **Process:**
    1. Validates user's broker configuration
    2. Checks available capital
    3. Fetches live option premium
    4. Generates SuperTrend + EMA trading signal
    5. Calculates position size and risk
    6. Returns prepared trade ready for execution

    **Returns:** PreparedTrade with complete execution details
    """
    try:
        # Get correct lot size
        lot_size = request.lot_size
        if not lot_size:
            # Fetch from database
            from services.upstox_option_service import upstox_option_service
            instrument_details = upstox_option_service.get_instrument_details(request.option_instrument_key, db)
            if instrument_details and instrument_details.get("lot_size"):
                lot_size = instrument_details["lot_size"]
            else:
                raise HTTPException(status_code=400, detail="Lot size not provided and could not be fetched.")
        
        trading_mode = TradingMode(request.trading_mode)
        prepared_trade = await trade_prep_service.prepare_trade(
            user_id=current_user.id,
            stock_symbol=request.stock_symbol,
            option_instrument_key=request.option_instrument_key,
            option_type=request.option_type,
            strike_price=request.strike_price,
            expiry_date=request.expiry_date,
            lot_size=lot_size,
            db=db,
            trading_mode=trading_mode,
        )

        return {
            "success": prepared_trade.status == TradeStatus.READY,
            "status": prepared_trade.status.value,
            "prepared_trade": {
                "stock_symbol": prepared_trade.stock_symbol,
                "option_type": prepared_trade.option_type,
                "strike_price": float(prepared_trade.strike_price),
                "expiry_date": prepared_trade.expiry_date,
                "current_premium": float(prepared_trade.current_premium),
                "entry_price": float(prepared_trade.entry_price),
                "stop_loss": float(prepared_trade.stop_loss),
                "target_price": float(prepared_trade.target_price),
                "position_size_lots": prepared_trade.position_size_lots,
                "total_investment": float(prepared_trade.total_investment),
                "max_loss_amount": float(prepared_trade.max_loss_amount),
                "risk_reward_ratio": float(prepared_trade.risk_reward_ratio),
                "trading_mode": prepared_trade.trading_mode,
                "broker_name": prepared_trade.broker_name,
                "signal": prepared_trade.signal,
                "capital_allocation": prepared_trade.capital_allocation,
                "metadata": prepared_trade.metadata,
            },
        }

    except Exception as e:
        logger.error(f"Error preparing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-trade")
async def execute_trade(
    request: ExecuteTradeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute trade (paper or live) after preparation

    **Process:**
    1. Prepares trade with full validation
    2. Executes via broker API (live) or mock execution (paper)
    3. Creates trade execution record
    4. Creates active position for PnL tracking
    5. Starts real-time monitoring

    **Returns:** Execution result with trade ID and position details
    """
    try:
        # Prepare trade
        trading_mode = TradingMode(request.trading_mode)
        # Get correct lot size
        lot_size = request.lot_size
        if not lot_size:
            # Fetch from database
            from services.upstox_option_service import upstox_option_service
            instrument_details = upstox_option_service.get_instrument_details(request.option_instrument_key, db)
            if instrument_details and instrument_details.get("lot_size"):
                lot_size = instrument_details["lot_size"]
            else:
                raise HTTPException(status_code=400, detail="Lot size not provided and could not be fetched.")

        prepared_trade = await trade_prep_service.prepare_trade(
            user_id=current_user.id,
            stock_symbol=request.stock_symbol,
            option_instrument_key=request.option_instrument_key,
            option_type=request.option_type,
            strike_price=request.strike_price,
            expiry_date=request.expiry_date,
            lot_size=lot_size,
            db=db,
            trading_mode=trading_mode,
        )

        if prepared_trade.status != TradeStatus.READY:
            raise HTTPException(
                status_code=400,
                detail=f"Trade not ready: {prepared_trade.metadata.get('error', 'Unknown error')}",
            )

        # Execute trade
        execution_result = execution_handler.execute_trade(prepared_trade, db)

        if not execution_result.success:
            raise HTTPException(status_code=400, detail=execution_result.message)

        return {
            "success": True,
            "message": "Trade executed successfully",
            "trade_id": execution_result.trade_id,
            "order_id": execution_result.order_id,
            "entry_price": float(execution_result.entry_price),
            "quantity": execution_result.quantity,
            "status": execution_result.status,
            "trade_execution_id": execution_result.trade_execution_id,
            "active_position_id": execution_result.active_position_id,
            "metadata": execution_result.metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-execute-selected-stocks")
async def auto_execute_selected_stocks(
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    execution_mode: str = Query(
        "multi_demat", description="Execution mode: single_demat or multi_demat"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Auto-execute trades for all final selected stocks with options

    **Execution Modes:**
    - single_demat: Execute on default/first active broker only
    - multi_demat: Execute across ALL active brokers with proportional allocation

    **Process:**
    1. Gets final selected stocks with option contracts
    2. Prepares and executes trade for each stock
    3. Creates active positions for monitoring
    4. Returns summary of executions

    **Use Case:** Automated trading after stock selection completes
    """
    try:
        mode = TradingMode(trading_mode)

        # Get final options selections from database
        final_selections = enhanced_options_service.get_final_options_selections(db)

        if not final_selections:
            return {
                "success": False,
                "message": "No final stock selections with option contracts available",
                "executions": [],
                "total_selections": 0,
                "successful_executions": 0,
            }

        executions = []
        successful_executions = 0
        total_allocated_capital = 0
        total_quantity = 0

        # Multi-demat execution mode
        if execution_mode == "multi_demat":
            from services.trading_execution.multi_demat_executor import (
                multi_demat_executor,
            )

            logger.info(
                f"🚀 Multi-demat execution mode for {len(final_selections)} stocks"
            )

            for selection in final_selections:
                if not selection.get("option_instrument_key"):
                    continue

                try:
                    # Execute across all demats
                    multi_result = await multi_demat_executor.execute_across_all_demats(
                        user_id=current_user.id,
                        stock_symbol=selection["symbol"],
                        option_instrument_key=selection["option_instrument_key"],
                        option_type=selection["option_type"],
                        strike_price=Decimal(str(selection["strike_price"])),
                        expiry_date=selection["expiry_date"],
                        lot_size=selection["lot_size"],
                        premium_per_lot=Decimal(str(selection.get("premium", 0))),
                        db=db,
                        trading_mode=mode,
                    )

                    if multi_result.success:
                        successful_executions += multi_result.successful_executions
                        total_allocated_capital += float(
                            multi_result.total_allocated_capital
                        )
                        total_quantity += multi_result.total_quantity

                    executions.append(
                        {
                            "symbol": selection["symbol"],
                            "success": multi_result.success,
                            "parent_trade_id": multi_result.parent_trade_id,
                            "total_demats": multi_result.total_demats,
                            "successful_executions": multi_result.successful_executions,
                            "failed_executions": multi_result.failed_executions,
                            "total_allocated_capital": float(
                                multi_result.total_allocated_capital
                            ),
                            "total_quantity": multi_result.total_quantity,
                            "demat_executions": multi_result.executions,
                            "message": (
                                multi_result.error_message
                                if not multi_result.success
                                else "Success"
                            ),
                        }
                    )

                except Exception as e:
                    logger.error(
                        f"Error in multi-demat execution for {selection['symbol']}: {e}"
                    )
                    executions.append(
                        {
                            "symbol": selection["symbol"],
                            "success": False,
                            "message": str(e),
                        }
                    )

            return {
                "success": successful_executions > 0,
                "execution_mode": "multi_demat",
                "message": f"Multi-demat execution: {successful_executions} total trades executed",
                "total_selections": len(final_selections),
                "total_allocated_capital": total_allocated_capital,
                "total_quantity": total_quantity,
                "successful_executions": successful_executions,
                "executions": executions,
            }

        # Single demat execution mode (legacy)
        else:
            logger.info(
                f"📝 Single-demat execution mode for {len(final_selections)} stocks"
            )

            for selection in final_selections:
                if not selection.get("option_instrument_key"):
                    continue

                try:
                    # Prepare trade
                    prepared_trade = await trade_prep_service.prepare_trade(
                        user_id=current_user.id,
                        stock_symbol=selection["symbol"],
                        option_instrument_key=selection["option_instrument_key"],
                        option_type=selection["option_type"],
                        strike_price=Decimal(str(selection["strike_price"])),
                        expiry_date=selection["expiry_date"],
                        lot_size=selection["lot_size"],
                        db=db,
                        trading_mode=mode,
                    )

                    if prepared_trade.status == TradeStatus.READY:
                        # Execute trade
                        result = execution_handler.execute_trade(prepared_trade, db)

                        if result.success:
                            successful_executions += 1

                        executions.append(
                            {
                                "symbol": selection["symbol"],
                                "success": result.success,
                                "trade_id": result.trade_id,
                                "message": result.message,
                                "entry_price": float(result.entry_price),
                                "quantity": result.quantity,
                            }
                        )
                    else:
                        executions.append(
                            {
                                "symbol": selection["symbol"],
                                "success": False,
                                "message": f"Trade not ready: {prepared_trade.status.value}",
                            }
                        )

                except Exception as e:
                    logger.error(
                        f"Error executing trade for {selection['symbol']}: {e}"
                    )
                    executions.append(
                        {
                            "symbol": selection["symbol"],
                            "success": False,
                            "message": str(e),
                        }
                    )

            return {
                "success": successful_executions > 0,
                "execution_mode": "single_demat",
                "message": f"Executed {successful_executions}/{len(final_selections)} trades",
                "total_selections": len(final_selections),
                "successful_executions": successful_executions,
                "executions": executions,
            }

    except Exception as e:
        logger.error(f"Error in auto-execute: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active-positions")
def get_active_positions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get all active positions with real-time PnL

    **Returns:** List of active positions with current PnL, SL, targets
    """
    try:
        # Optimized query: Use JOIN instead of N+1 queries
        results = (
            db.query(ActivePosition, AutoTradeExecution)
            .join(
                AutoTradeExecution,
                ActivePosition.trade_execution_id == AutoTradeExecution.id
            )
            .filter(
                ActivePosition.user_id == current_user.id,
                ActivePosition.is_active == True,
            )
            .all()
        )

        active_positions = []

        for position, trade in results:
            # Calculate total investment
            total_investment = float(trade.total_investment) if trade.total_investment else (float(trade.entry_price) * trade.quantity)
            lots_traded = trade.lots_traded if trade.lots_traded else (trade.quantity // trade.lot_size if trade.lot_size > 0 else 1)

            # Calculate holding duration
            duration_minutes = 0
            if trade.entry_time:
                from datetime import datetime
                duration_minutes = int((datetime.now() - trade.entry_time).total_seconds() / 60)

            active_positions.append(
                {
                    "position_id": position.id,
                    "trade_id": trade.trade_id,
                    "symbol": position.symbol,
                    "signal_type": trade.signal_type,
                    "instrument_key": position.instrument_key,
                    "entry_price": float(trade.entry_price),
                    "strike_price": float(trade.strike_price) if trade.strike_price else None,
                    "expiry_date": trade.expiry_date,
                    "current_price": (
                        float(position.current_price)
                        if position.current_price
                        else 0
                    ),
                    "quantity": trade.quantity,
                    "lot_size": trade.lot_size,
                    "lots_traded": lots_traded,
                    "total_investment": total_investment,
                    "current_pnl": (
                        float(position.current_pnl) if position.current_pnl else 0
                    ),
                    "current_pnl_percentage": (
                        float(position.current_pnl_percentage)
                        if position.current_pnl_percentage
                        else 0
                    ),
                    "stop_loss": (
                        float(position.current_stop_loss)
                        if position.current_stop_loss
                        else 0
                    ),
                    "target": float(trade.target_1) if trade.target_1 else 0,
                    "highest_price_reached": (
                        float(position.highest_price_reached)
                        if position.highest_price_reached
                        else 0
                    ),
                    "trailing_stop_active": position.trailing_stop_triggered,
                    "entry_time": (
                        trade.entry_time.isoformat() if trade.entry_time else None
                    ),
                    "duration_minutes": duration_minutes,
                    "last_updated": (
                        position.last_updated.isoformat()
                        if position.last_updated
                        else None
                    ),
                    "broker_name": trade.broker_name or "N/A",
                    "trading_mode": trade.trading_mode or "paper",
                    "strategy_name": trade.strategy_name or "fibonacci_ema",
                    "entry_order_id": trade.entry_order_id,
                    "status": "ACTIVE",
                }
            )

        # ADDED: Include recently FAILED trades (last 15 minutes) for UI visibility
        from datetime import timedelta
        recent_cutoff = get_ist_now_naive() - timedelta(minutes=15)
        
        failed_trades = db.query(AutoTradeExecution).filter(
            AutoTradeExecution.user_id == current_user.id,
            AutoTradeExecution.status == "FAILED",
            AutoTradeExecution.entry_time >= recent_cutoff
        ).order_by(AutoTradeExecution.entry_time.desc()).all()

        for trade in failed_trades:
            active_positions.append({
                "position_id": f"FAILED_{trade.id}",
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "signal_type": trade.signal_type,
                "instrument_key": trade.instrument_key,
                "entry_price": float(trade.entry_price),
                "strike_price": float(trade.strike_price) if trade.strike_price else None,
                "expiry_date": trade.expiry_date,
                "current_price": float(trade.entry_price),
                "quantity": trade.quantity,
                "lot_size": trade.lot_size,
                "lots_traded": 0,
                "total_investment": 0,
                "current_pnl": 0,
                "current_pnl_percentage": 0,
                "stop_loss": 0,
                "target": 0,
                "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                "status": "FAILED",
                "error_reason": trade.execution_notes,
                "broker_name": trade.broker_name or "N/A",
                "trading_mode": trade.trading_mode or "paper",
            })

        return {
            "success": True,
            "active_positions_count": len(active_positions),
            "active_positions": active_positions,
        }

    except Exception as e:
        logger.error(f"Error getting active positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pnl-summary")
def get_pnl_summary(
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):


    """


    Get aggregate PnL summary for user





    **Returns:** Total PnL, investment, win rate, and position counts


    """


    try:


        summary = pnl_tracker.get_user_positions_summary(current_user.id, db, trading_mode)


        return {"success": True, "summary": summary}





    except Exception as e:


        logger.error(f"Error getting PnL summary: {e}")


        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-auto-trading")
async def start_auto_trading(
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start auto-trading for selected stocks

    **Process:**
    1. Loads user's selected stocks from database
    2. Subscribes to live feed for spot + option instruments
    3. Runs strategy on real-time data
    4. Auto-executes trades on valid signals
    5. Manages positions with trailing SL

    **Returns:** Auto-trading session details
    """
    try:
        from services.trading_execution.auto_trade_live_feed import auto_trade_live_feed

        # Get active broker for access token
        broker_config = (
            db.query(BrokerConfig)
            .filter(
                BrokerConfig.user_id == current_user.id,
                BrokerConfig.is_active == True,
                BrokerConfig.access_token.isnot(None),
            )
            .first()
        )

        if not broker_config:
            raise HTTPException(
                status_code=400,
                detail="No active broker configuration found. Please configure broker first.",
            )

        # Validate token expiry
        from datetime import datetime

        if (
            broker_config.access_token_expiry
            and broker_config.access_token_expiry < datetime.now()
        ):
            raise HTTPException(
                status_code=400, detail="Broker token expired. Please refresh token."
            )

        # Start auto-trading in background
        mode = TradingMode(trading_mode)
        asyncio.create_task(
            auto_trade_live_feed.start_auto_trading(
                trading_mode=mode,
            )
        )

        from services.trading_execution.shared_instrument_registry import shared_registry

        return {
            "success": True,
            "message": "Auto-trading started successfully",
            "trading_mode": trading_mode,
            "broker": broker_config.broker_name,
            "monitored_stocks": len(shared_registry.instruments),
            "stats": auto_trade_live_feed.stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting auto-trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-auto-trading")
async def stop_auto_trading(current_user: User = Depends(get_current_user)):
    """
    Stop auto-trading

    **Process:**
    1. Stops WebSocket connection
    2. Stops strategy monitoring
    3. Does NOT close open positions

    **Returns:** Stop confirmation
    """
    try:
        from services.trading_execution.auto_trade_live_feed import auto_trade_live_feed

        await auto_trade_live_feed.stop()

        return {
            "success": True,
            "message": "Auto-trading stopped successfully",
            "final_stats": auto_trade_live_feed.stats,
        }

    except Exception as e:
        logger.error(f"Error stopping auto-trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable-auto-mode")
async def enable_auto_mode(
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
):
    """
    Enable auto-mode: WebSocket starts automatically when stocks selected at 9:15 AM

    **Process:**
    1. Starts scheduler service
    2. Monitors stock selection
    3. Auto-starts WebSocket at 9:15 AM when stocks are selected
    4. Auto-stops when all positions closed

    **Returns:** Scheduler status
    """
    try:
        from services.trading_execution.auto_trade_scheduler import auto_trade_scheduler

        # Start scheduler in background
        mode = TradingMode(trading_mode)
        asyncio.create_task(
            auto_trade_scheduler.start_scheduler(
                user_id=current_user.id, trading_mode=mode
            )
        )

        return {
            "success": True,
            "message": "Auto-mode enabled - WebSocket will start automatically at 9:15 AM when stocks are selected",
            "trading_mode": trading_mode,
            "auto_start_time": "09:15 AM",
            "auto_stop": "When all positions closed",
        }

    except Exception as e:
        logger.error(f"Error enabling auto-mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable-auto-mode")
async def disable_auto_mode(current_user: User = Depends(get_current_user)):
    """
    Disable auto-mode and stop scheduler

    **Returns:** Disable confirmation
    """
    try:
        from services.trading_execution.auto_trade_scheduler import auto_trade_scheduler
        from services.trading_execution.auto_trade_live_feed import auto_trade_live_feed

        # Stop scheduler
        await auto_trade_scheduler.stop_scheduler()

        # Stop auto-trading if running
        if auto_trade_live_feed.is_running:
            await auto_trade_live_feed.stop()

        return {"success": True, "message": "Auto-mode disabled successfully"}

    except Exception as e:
        logger.error(f"Error disabling auto-mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto-trading-status")
async def get_auto_trading_status(current_user: User = Depends(get_current_user)):
    """
    Get auto-trading status

    **Returns:** Current auto-trading state and monitored instruments
    """
    try:
        from services.trading_execution.auto_trade_live_feed import auto_trade_live_feed
        from services.trading_execution.auto_trade_scheduler import auto_trade_scheduler
        from services.trading_execution.shared_instrument_registry import shared_registry

        monitored = []
        for inst_key, inst in shared_registry.instruments.items():
            monitored.append(
                {
                    "symbol": inst.stock_symbol,
                    "option_type": inst.option_type,
                    "strike_price": float(inst.strike_price),
                    "state": inst.state.value,
                    "live_spot_price": float(inst.live_spot_price),
                    "live_option_premium": float(inst.live_option_premium),
                    "last_signal": (
                        inst.last_signal.signal_type.value if inst.last_signal else None
                    ),
                }
            )

        return {
            "success": True,
            "auto_mode_enabled": auto_trade_scheduler.is_running,
            "websocket_running": auto_trade_live_feed.is_running,
            "auto_started_today": auto_trade_scheduler.auto_started_users.get(current_user.id, False),
            "monitored_stocks_count": len(shared_registry.instruments),
            "monitored_stocks": monitored,
            "stats": auto_trade_live_feed.stats,
        }

    except Exception as e:
        logger.error(f"Error getting auto-trading status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/selected-stocks")
def get_selected_stock(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get Auto selected stock for trading (OPTIMIZED)

    Performance optimizations:
    - Database-level DISTINCT query to eliminate duplicates
    - Bulk JSON parsing outside loop
    - Cached helper functions
    - Early validation to skip invalid records
    """
    try:
        # OPTIMIZATION 1: Use DISTINCT at database level and order by ID (keep latest)
        # This eliminates duplicate processing entirely
        from sqlalchemy import func

        subquery = (
            db.query(
                SelectedStock.symbol,
                func.max(SelectedStock.id).label('max_id')
            )
            .filter(
                SelectedStock.selection_date == get_ist_now_naive().date(),
                SelectedStock.is_active == True,
            )
            .group_by(SelectedStock.symbol)
            .subquery()
        )

        selected_records = (
            db.query(SelectedStock)
            .join(subquery, SelectedStock.id == subquery.c.max_id)
            .all()
        )

        # DEBUG: Log what we found
        logger.info(f"Found {len(selected_records)} selected stocks for today")

        if not selected_records:
            return {
                "success": True,
                "stocks": [],
                "market_sentiment": {},
                "debug_info": {
                    "query_date": get_ist_now_naive().date().isoformat(),
                    "total_records": 0
                }
            }

        # OPTIMIZATION 2: Define JSON parser once (no function calls in loop)
        def safe_parse_json(maybe_json):
            if not maybe_json:
                return {}
            if isinstance(maybe_json, dict):
                return maybe_json
            if isinstance(maybe_json, str):
                s = maybe_json.strip()
                if not s:
                    return {}
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    try:
                        import ast
                        return ast.literal_eval(s)
                    except Exception:
                        return {}
            return {}

        # OPTIMIZATION 3: Pre-validate and parse all records
        # CRITICAL FIX: Show stocks even WITHOUT option contracts for visibility!
        valid_records = []
        stocks_without_options = 0

        for record in selected_records:
            try:
                option_contract = safe_parse_json(getattr(record, "option_contract", None))
                score_breakdown = safe_parse_json(getattr(record, "score_breakdown", None))

                # NEW: Accept stocks even without option contracts
                # This allows users to see what was selected, even if options aren't ready yet
                if not option_contract or not option_contract.get("option_instrument_key"):
                    stocks_without_options += 1
                    # Use empty option contract as placeholder
                    option_contract = {
                        "option_instrument_key": "",
                        "strike_price": 0,
                        "lot_size": 0,
                        "premium": 0,
                        "option_type": record.option_type or "N/A",
                        "expiry_date": ""
                    }

                valid_records.append((record, option_contract, score_breakdown))
            except Exception as e:
                logger.warning(f"Failed to parse record {record.id}: {e}")
                continue

        # DEBUG: Log parsing results
        logger.info(f"Parsed {len(valid_records)} valid stocks ({stocks_without_options} without option contracts)")

        # OPTIMIZATION 4: Bulk process valid records with optimized data extraction
        stocks = []
        for record, option_contract, score_breakdown in valid_records:
            try:
                # Extract numeric values with single operation (no repeated .get() calls)
                strike_price = float(option_contract.get("strike_price", 0) or 0)
                lot_size = int(option_contract.get("lot_size", 0) or 0)
                premium = float(option_contract.get("premium", 0) or 0)
                option_instrument_key = option_contract.get("option_instrument_key", "")

                # Build normalized score dict in one operation
                capital_allocation = float(score_breakdown.get("capital_allocation", 0) or 0)
                position_size_lots = int(score_breakdown.get("position_size_lots", 0) or 0)
                max_loss = float(score_breakdown.get("max_loss", 0) or 0)
                target_profit = float(score_breakdown.get("target_profit", 0) or 0)

                # Build stock data dict with all fields at once
                stock_data = {
                    "id": record.id,
                    "symbol": record.symbol,
                    "sector": record.sector,
                    "selection_score": record.selection_score,
                    "selection_reason": record.selection_reason,
                    "price_at_selection": float(record.price_at_selection or 0),
                    "option_type": record.option_type or "NEUTRAL",
                    "strike_price": strike_price,
                    "lot_size": lot_size,
                    "premium": premium,
                    "option_instrument_key": option_instrument_key,
                    "expiry_date": record.option_expiry_date or "",
                    "atm_strike": score_breakdown.get("atm_strike", strike_price),
                    "adr_score": score_breakdown.get("adr_score", 0.5),
                    "sector_momentum": score_breakdown.get("sector_momentum", 0.0),
                    "volume_score": score_breakdown.get("volume_score", 0.5),
                    "technical_score": score_breakdown.get("technical_score", 0.5),
                    "capital_allocation": capital_allocation,
                    "position_size_lots": position_size_lots,
                    "max_loss": max_loss,
                    "target_profit": target_profit,
                    "market_sentiment_alignment": record.option_type in ["CE", "PE"],
                    "selection_date": record.selection_date.isoformat(),
                    "change_percent": 0.0,
                    "live_price": 0.0,
                    "unrealized_pnl": 0.0,
                }
                stocks.append(stock_data)
            except Exception as e:
                logger.warning(f"Skipping stock {record.symbol}: {e}")
                continue

        # Add debug info to response
        logger.info(f"Returning {len(stocks)} stocks to frontend")

        return {
            "success": True,
            "stocks": stocks,
            "market_sentiment": {},
            "debug_info": {
                "query_date": get_ist_now_naive().date().isoformat(),
                "total_records_found": len(selected_records),
                "valid_records_parsed": len(valid_records),
                "stocks_returned": len(stocks),
                "stocks_without_options": stocks_without_options
            }
        }

    except Exception as e:
        logger.exception(f"Error getting selected stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/selected-stocks-live-prices")
async def get_selected_stocks_live_prices(
    current_user: User = Depends(get_current_user),
):
    """
    Get live prices for selected stocks from auto-trading WebSocket

    **Returns:**
    - Live spot prices
    - Live option premiums
    - Price changes from selection
    - Unrealized PnL (hypothetical if not in position, actual if in position)
    - State (monitoring, position_open, etc.)

    **Use Case:** Display live prices in Selected Stocks table with real-time updates
    """
    try:
        from services.trading_execution.auto_trade_live_feed import auto_trade_live_feed

        if not auto_trade_live_feed.is_running:
            return {
                "success": False,
                "message": "Auto-trading WebSocket not running. Start auto-trading first.",
                "live_prices": [],
            }

        live_prices = auto_trade_live_feed.get_live_prices()

        return {
            "success": True,
            "live_prices": live_prices,
            "count": len(live_prices),
            "websocket_running": auto_trade_live_feed.is_running,
        }

    except Exception as e:
        logger.error(f"Error getting live prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-history")
def get_trade_history(
    limit: int = Query(50, description="Number of trades to fetch"),
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    start_date: Optional[date] = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter by end date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get trade execution history with optional date filtering

    **Returns:** List of closed trades with PnL details
    """
    try:
        query = db.query(AutoTradeExecution).filter(
            AutoTradeExecution.user_id == current_user.id,
            AutoTradeExecution.status.in_(["CLOSED", "FAILED"]),
        )

        if trading_mode:
            query = query.filter(AutoTradeExecution.trading_mode == trading_mode)

        if start_date:
            query = query.filter(func.date(AutoTradeExecution.entry_time) >= start_date)
        
        if end_date:
            query = query.filter(func.date(AutoTradeExecution.entry_time) <= end_date)

        # If date range is provided, we might want to ignore the limit or increase it
        # But keeping limit is safer for pagination. 
        # For export, the frontend might request a large limit.
        # Use entry_time for sorting as FAILED trades won't have exit_time
        trades = query.order_by(AutoTradeExecution.entry_time.desc()).limit(limit).all()

        trade_history = []

        for trade in trades:
            is_failed = trade.status == "FAILED"
            # Calculate duration in minutes
            duration_minutes = 0
            if trade.entry_time and trade.exit_time:
                duration_minutes = int((trade.exit_time - trade.entry_time).total_seconds() / 60)

            # Format dates and times (Stored as Naive IST in DB)
            if trade.entry_time:
                # DB stores Naive IST, so no conversion needed
                entry_time_ist = trade.entry_time
                entry_date = entry_time_ist.strftime("%d-%b-%Y")  # e.g., 14-Nov-2025
                entry_time_str = entry_time_ist.strftime("%I:%M:%S %p")  # e.g., 02:30:45 PM
            else:
                entry_date = None
                entry_time_str = None

            if trade.exit_time:
                # DB stores Naive IST
                exit_time_ist = trade.exit_time
                exit_date = exit_time_ist.strftime("%d-%b-%Y")
                exit_time_str = exit_time_ist.strftime("%I:%M:%S %p")
            else:
                exit_date = None
                exit_time_str = None

            # Calculate total investment
            total_investment = float(trade.total_investment) if trade.total_investment else (float(trade.entry_price) * trade.quantity)
            lots_traded = trade.lots_traded if trade.lots_traded else (trade.quantity // trade.lot_size if trade.lot_size > 0 else 1)

            # Determine status tag
            net_pnl = float(trade.net_pnl) if trade.net_pnl else 0
            status_tag = "WIN" if net_pnl > 0 else "LOSS"
            if is_failed: status_tag = "FAILED"

            # Determine exit type (SL Hit / Target Hit / Manual)
            exit_type = "MANUAL"
            exit_reason = trade.exit_reason
            
            if is_failed:
                exit_type = "FAILED"
                exit_reason = trade.execution_notes or "Preparation failed"
            elif trade.exit_reason:
                reason = trade.exit_reason.upper()
                if "STOP_LOSS" in reason or "SL" in reason:
                    exit_type = "SL_HIT"
                elif "TARGET" in reason or "PROFIT" in reason:
                    exit_type = "TARGET_HIT"
                elif "TIME" in reason:
                    exit_type = "TIME_EXIT"

            trade_history.append(
                {
                    "trade_id": trade.trade_id,
                    "symbol": trade.symbol,
                    "signal_type": trade.signal_type,
                    "strike_price": float(trade.strike_price) if trade.strike_price else 0,
                    "expiry_date": trade.expiry_date,
                    "entry_time": (
                        trade.entry_time.isoformat() if trade.entry_time else None
                    ),
                    "exit_time": (
                        trade.exit_time.isoformat() if trade.exit_time else None
                    ),
                    "entry_date": entry_date,
                    "entry_time_str": entry_time_str,
                    "exit_date": exit_date,
                    "exit_time_str": exit_time_str,
                    "entry_price": float(trade.entry_price),
                    "exit_price": float(trade.exit_price) if trade.exit_price else 0,
                    "stop_loss": float(trade.initial_stop_loss) if trade.initial_stop_loss else 0,
                    "target": float(trade.target_1) if trade.target_1 else 0,
                    "quantity": trade.quantity,
                    "lot_size": trade.lot_size,
                    "lots_traded": lots_traded,
                    "total_investment": total_investment,
                    "gross_pnl": float(trade.gross_pnl) if trade.gross_pnl else 0,
                    "net_pnl": net_pnl,
                    "pnl_percentage": (
                        float(trade.pnl_percentage) if trade.pnl_percentage else 0
                    ),
                    "exit_reason": exit_reason,
                    "exit_type": exit_type,
                    "status_tag": status_tag,
                    "strategy_name": trade.strategy_name,
                    "duration_minutes": duration_minutes,
                    "broker_name": trade.broker_name or "N/A",
                    "trading_mode": trade.trading_mode or "paper",
                    "instrument_key": trade.instrument_key,
                    "entry_order_id": trade.entry_order_id,
                    "exit_order_id": trade.exit_order_id,
                    "status": trade.status,
                }
            )

        return {
            "success": True,
            "trade_count": len(trade_history),
            "trades": trade_history,
        }

    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-trading-preferences")
async def get_user_trading_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get user's trading mode and execution mode preferences

    Returns:
        trading_mode: "paper" or "live"
        execution_mode: "single_demat" or "multi_demat"
    """
    try:
        # Get or create user trading config
        trading_config = (
            db.query(UserTradingConfig)
            .filter(UserTradingConfig.user_id == current_user.id)
            .first()
        )

        if not trading_config:
            # Create default config
            trading_config = UserTradingConfig(
                user_id=current_user.id,
                trading_mode="paper",
                execution_mode="multi_demat",
            )
            db.add(trading_config)
            db.commit()
            db.refresh(trading_config)

        return {
            "success": True,
            "trading_mode": trading_config.trading_mode or "paper",
            "execution_mode": trading_config.execution_mode or "multi_demat",
        }

    except Exception as e:
        logger.error(f"Error getting user trading preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-trading-preferences")
async def update_user_trading_preferences(
    trading_mode: str = Query(..., description="Trading mode: paper or live"),
    execution_mode: str = Query(
        ..., description="Execution mode: single_demat or multi_demat"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user's trading mode and execution mode preferences

    Args:
        trading_mode: "paper" or "live"
        execution_mode: "single_demat" or "multi_demat"
    """
    try:
        # Validate inputs
        if trading_mode not in ["paper", "live"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid trading_mode. Must be 'paper' or 'live'",
            )

        if execution_mode not in ["single_demat", "multi_demat"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid execution_mode. Must be 'single_demat' or 'multi_demat'",
            )

        # Get or create user trading config
        trading_config = (
            db.query(UserTradingConfig)
            .filter(UserTradingConfig.user_id == current_user.id)
            .first()
        )

        if not trading_config:
            # Create new config
            trading_config = UserTradingConfig(
                user_id=current_user.id,
                trading_mode=trading_mode,
                execution_mode=execution_mode,
            )
            db.add(trading_config)
        else:
            # Update existing config
            trading_config.trading_mode = trading_mode
            trading_config.execution_mode = execution_mode

        db.commit()
        db.refresh(trading_config)

        logger.info(
            f"Updated trading preferences for user {current_user.id}: mode={trading_mode}, execution={execution_mode}"
        )

        return {
            "success": True,
            "message": "Trading preferences updated successfully",
            "trading_mode": trading_config.trading_mode,
            "execution_mode": trading_config.execution_mode,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user trading preferences: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-position/{position_id}")
async def close_position_manually(
    position_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually close an active position

    **Args:** position_id - Active position ID to close

    **Returns:** Closure confirmation with final PnL
    """
    try:
        position = (
            db.query(ActivePosition)
            .filter(
                ActivePosition.id == position_id,
                ActivePosition.user_id == current_user.id,
                ActivePosition.is_active == True,
            )
            .first()
        )

        if not position:
            raise HTTPException(status_code=404, detail="Active position not found")

        trade_execution = (
            db.query(AutoTradeExecution)
            .filter(AutoTradeExecution.id == position.trade_execution_id)
            .first()
        )

        if not trade_execution:
            raise HTTPException(status_code=404, detail="Trade execution not found")

        # Get current price
        from services.realtime_market_engine import get_market_engine

        market_engine = get_market_engine()

        current_price = Decimal("0")
        if position.instrument_key in market_engine.instruments:
            current_price = Decimal(
                str(market_engine.instruments[position.instrument_key].current_price)
            )
        else:
            current_price = Decimal(str(position.current_price))

        # Close position
        await pnl_tracker._close_position(
            position, trade_execution, current_price, "MANUAL_EXIT", db
        )

        return {
            "success": True,
            "message": "Position closed successfully",
            "trade_id": trade_execution.trade_id,
            "exit_price": float(current_price),
            "pnl": float(trade_execution.net_pnl) if trade_execution.net_pnl else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-capital-overview")
async def get_user_capital_overview(
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get aggregated capital overview from all user's demat accounts

    **Returns:**
    - Total available capital across all demats
    - Per-demat capital breakdown
    - Capital utilization percentage
    - Max trade allocation allowed
    - Token validity status per demat

    **Use Case:** Display capital dashboard in UI before trade execution
    """
    try:
        capital_overview = await multi_demat_capital_service.get_user_total_capital(
            user_id=current_user.id, db=db, trading_mode=trading_mode
        )

        return {"success": True, "capital_overview": capital_overview}

    except Exception as e:
        logger.error(f"Error getting capital overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/capital-allocation-plan")
async def get_capital_allocation_plan(
    required_capital: float = Query(..., description="Required capital for trade"),
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get capital allocation plan across demats for a trade

    **Returns:**
    - Whether trade can be executed
    - Proportional allocation across demats
    - Per-demat allocation details
    - Rejection reason if trade cannot be executed

    **Use Case:** Validate and plan trade before execution
    """
    try:
        required_decimal = Decimal(str(required_capital))

        allocation_plan = multi_demat_capital_service.get_capital_summary_for_trade(
            user_id=current_user.id,
            required_capital=required_decimal,
            db=db,
            trading_mode=trading_mode,
        )

        return {"success": True, "allocation_plan": allocation_plan}

    except Exception as e:
        logger.error(f"Error getting allocation plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio-summary")
async def get_portfolio_summary(
    trading_mode: str = Query("paper", description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive portfolio summary with real-time P&L and investments

    **Returns:**
    - Total P&L (realized + unrealized)
    - Active positions count
    - Total investment in active positions
    - Available capital
    - Today's P&L
    - Overall portfolio performance

    **Use Case:** Display portfolio dashboard with complete financial overview
    """
    try:
        from sqlalchemy import and_, func
        from datetime import datetime, date

        # Get active positions with real-time PnL
        active_positions = db.query(ActivePosition).filter(
            and_(
                ActivePosition.user_id == current_user.id,
                ActivePosition.is_active == True
            )
        ).all()

        # Calculate total investment and unrealized P&L from active positions
        total_investment = Decimal('0')
        total_unrealized_pnl = Decimal('0')
        active_positions_data = []

        for pos in active_positions:
            trade = db.query(AutoTradeExecution).filter(
                AutoTradeExecution.id == pos.trade_execution_id
            ).first()

            if trade:
                investment = Decimal(str(trade.total_investment)) if trade.total_investment else (Decimal(str(trade.entry_price)) * Decimal(str(trade.quantity)))
                total_investment += investment
                total_unrealized_pnl += Decimal(str(pos.current_pnl))

                active_positions_data.append({
                    "symbol": pos.symbol,
                    "investment": float(investment),
                    "current_pnl": float(pos.current_pnl),
                    "pnl_percent": float(pos.current_pnl_percentage)
                })

        # Get realized P&L from closed trades
        today = get_ist_now_naive().date()

        # Today's closed trades
        todays_closed_trades = db.query(AutoTradeExecution).filter(
            and_(
                AutoTradeExecution.user_id == current_user.id,
                AutoTradeExecution.status == "CLOSED",
                func.date(AutoTradeExecution.exit_time) == today
            )
        ).all()

        todays_realized_pnl = sum(
            Decimal(str(trade.net_pnl)) for trade in todays_closed_trades if trade.net_pnl
        )

        # All time closed trades
        all_closed_trades = db.query(AutoTradeExecution).filter(
            and_(
                AutoTradeExecution.user_id == current_user.id,
                AutoTradeExecution.status == "CLOSED"
            )
        ).all()

        total_realized_pnl = sum(
            Decimal(str(trade.net_pnl)) for trade in all_closed_trades if trade.net_pnl
        )

        # Total P&L = Realized + Unrealized
        total_pnl = total_realized_pnl + total_unrealized_pnl

        # Get capital information
        from services.trading_execution.capital_manager import capital_manager

        if trading_mode == "paper":
            total_capital = capital_manager.paper_trading_capital
        else:
            broker_config = capital_manager.get_active_broker_config(current_user.id, db)
            if broker_config:
                total_capital = capital_manager._fetch_funds_from_broker(broker_config)
            else:
                total_capital = Decimal('0')

        # Calculate available capital
        available_capital = total_capital - total_investment + total_realized_pnl

        # Calculate portfolio metrics
        total_pnl_percent = (total_pnl / total_capital * Decimal('100')) if total_capital > 0 else Decimal('0')
        todays_pnl_percent = ((todays_realized_pnl + total_unrealized_pnl) / total_capital * Decimal('100')) if total_capital > 0 else Decimal('0')

        portfolio_summary = {
            "total_capital": float(total_capital),
            "available_capital": float(available_capital),
            "total_investment": float(total_investment),
            "active_positions_count": len(active_positions),
            "total_pnl": float(total_pnl),
            "total_pnl_percent": float(total_pnl_percent),
            "unrealized_pnl": float(total_unrealized_pnl),
            "realized_pnl": float(total_realized_pnl),
            "todays_pnl": float(todays_realized_pnl + total_unrealized_pnl),
            "todays_pnl_percent": float(todays_pnl_percent),
            "used_margin": float(total_investment),
            "free_margin": float(available_capital),
            "margin_utilization_percent": float((total_investment / total_capital * Decimal('100')) if total_capital > 0 else Decimal('0')),
            "active_positions": active_positions_data,
            "total_trades_today": len(todays_closed_trades),
            "total_trades_all_time": len(all_closed_trades),
            "timestamp": datetime.now().isoformat()
        }

        return {"success": True, "portfolio_summary": portfolio_summary}

    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PERFORMANCE ANALYTICS ENDPOINTS ====================


@router.get("/performance/daily")
async def get_daily_performance(
    target_date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD), default: today"),
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get daily trading performance metrics

    **Returns:**
    - Total trades for the day
    - Win ratio and profit factor
    - Total P&L and ROI
    - Average profit/loss per trade
    - Maximum drawdown
    - Sharpe ratio
    - Detailed trade list

    **Use Case:** Daily performance review and analysis
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service
        from datetime import date as date_obj

        # Parse target date
        if target_date:
            target = date_obj.fromisoformat(target_date)
        else:
            target = None

        performance = trade_analytics_service.get_daily_performance(
            user_id=current_user.id,
            db=db,
            target_date=target,
            trading_mode=trading_mode
        )

        return performance

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting daily performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/weekly")
async def get_weekly_performance(
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get weekly trading performance metrics (last 7 days)

    **Returns:**
    - All daily metrics aggregated for the week
    - Daily breakdown of performance
    - Week-over-week comparison (if available)

    **Use Case:** Weekly performance review
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        performance = trade_analytics_service.get_weekly_performance(
            user_id=current_user.id,
            db=db,
            trading_mode=trading_mode
        )

        return performance

    except Exception as e:
        logger.error(f"Error getting weekly performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/monthly")
async def get_monthly_performance(
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get monthly trading performance metrics (last 30 days)

    **Returns:**
    - All daily metrics aggregated for the month
    - Daily breakdown of performance
    - Month-over-month comparison (if available)

    **Use Case:** Monthly performance review
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        performance = trade_analytics_service.get_monthly_performance(
            user_id=current_user.id,
            db=db,
            trading_mode=trading_mode
        )

        return performance

    except Exception as e:
        logger.error(f"Error getting monthly performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/six-month")
async def get_six_month_performance(
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get 6-month trading performance metrics (last 180 days)

    **Returns:**
    - All daily metrics aggregated for 6 months
    - Weekly breakdown of performance
    - Trend analysis

    **Use Case:** Long-term performance review
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        performance = trade_analytics_service.get_six_month_performance(
            user_id=current_user.id,
            db=db,
            trading_mode=trading_mode
        )

        return performance

    except Exception as e:
        logger.error(f"Error getting 6-month performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/yearly")
async def get_yearly_performance(
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get 1-year trading performance metrics (last 365 days)

    **Returns:**
    - All daily metrics aggregated for the year
    - Monthly breakdown of performance
    - Year-over-year comparison (if available)

    **Use Case:** Annual performance review
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        performance = trade_analytics_service.get_yearly_performance(
            user_id=current_user.id,
            db=db,
            trading_mode=trading_mode
        )

        return performance

    except Exception as e:
        logger.error(f"Error getting yearly performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/summary")
async def get_performance_summary(
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get overall all-time performance summary

    **Returns:**
    - Total trades count
    - Overall win ratio
    - Overall profit factor
    - Total P&L and ROI
    - Average profit/loss per trade
    - Maximum drawdown
    - Sharpe ratio
    - Trading statistics (symbols traded, strategies used)

    **Use Case:** Complete trading performance overview
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        performance = trade_analytics_service.get_overall_performance(
            user_id=current_user.id,
            db=db,
            trading_mode=trading_mode
        )

        return performance

    except Exception as e:
        logger.error(f"Error getting overall performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/system-health")
async def get_system_health_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get system health and operational analytics

    **Returns:**
    - Latency metrics (signal generation, execution)
    - Hourly trade distribution
    - Broker-wise performance breakdown

    **Use Case:** Monitoring system efficiency and operational patterns
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        analytics = trade_analytics_service.get_system_health_analytics(
            user_id=current_user.id,
            db=db
        )

        return analytics

    except Exception as e:
        logger.error(f"Error getting system health performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/detailed")
async def get_detailed_performance(
    limit: int = Query(100, description="Number of trades to fetch (max 500)"),
    trading_mode: Optional[str] = Query(None, description="Trading mode: paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed trade-by-trade analysis

    **Args:**
    - limit: Number of recent trades to return (default: 100, max: 500)
    - trading_mode: Filter by paper or live mode

    **Returns:**
    - Detailed list of all closed trades
    - Trade-by-trade P&L breakdown
    - Entry/exit details for each trade
    - Duration and exit reason

    **Use Case:** Detailed trade review and analysis
    """
    try:
        from services.trading_execution.trade_analytics_service import trade_analytics_service

        # Validate limit
        if limit > 500:
            limit = 500
        elif limit < 1:
            limit = 100

        performance = trade_analytics_service.get_detailed_performance(
            user_id=current_user.id,
            db=db,
            limit=limit,
            trading_mode=trading_mode
        )

        return performance

    except Exception as e:
        logger.error(f"Error getting detailed performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FUND MANAGEMENT ENDPOINTS ====================

@router.get("/funds/balance")
async def get_fund_balances(
    trading_mode: str = Query("paper", description="paper or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available, used and total balance"""
    try:
        balances = fund_manager.get_balances(current_user.id, db, trading_mode)
        return {"success": True, "balances": balances}
    except Exception as e:
        logger.error(f"Error fetching balances: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/funds/add-paper-funds")
async def add_paper_funds(
    amount: float = Query(..., gt=0, description="Amount to add"),
    description: str = Query("Manual top-up", description="Transaction description"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add virtual funds to paper trading account"""
    try:
        result = fund_manager.add_paper_funds(current_user.id, amount, db, description)
        return result
    except Exception as e:
        logger.error(f"Error adding funds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/funds/statement")
async def get_fund_statement(
    trading_mode: str = Query("paper", description="paper or live"),
    limit: int = Query(50, description="Max entries to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transaction ledger/statement"""
    try:
        statement = fund_manager.get_statement(current_user.id, db, trading_mode, limit)
        return {"success": True, "statement": statement}
    except Exception as e:
        logger.error(f"Error fetching statement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/eod-report")
async def get_eod_report(
    target_date: Optional[date] = Query(None, description="Report date YYYY-MM-DD"),
    trading_mode: Optional[str] = Query(None, description="paper or live or ALL"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate End-Of-Day performance summary report"""
    try:
        from services.eod_report_service import eod_report_service
        report = eod_report_service.generate_eod_report(
            db=db,
            user_id=current_user.id,
            target_date=target_date,
            trading_mode=trading_mode
        )
        return {"success": True, "report": report}
    except Exception as e:
        logger.error(f"Error generating EOD report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/eod-report/send-telegram")
async def send_eod_telegram_report(
    target_date: Optional[date] = Query(None, description="Report date YYYY-MM-DD"),
    trading_mode: Optional[str] = Query(None, description="paper or live or ALL"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate and dispatch EOD performance summary to Telegram"""
    try:
        from services.eod_report_service import eod_report_service
        success = await eod_report_service.send_eod_telegram_report(
            db=db,
            user_id=current_user.id,
            target_date=target_date,
            trading_mode=trading_mode
        )
        return {"success": success, "message": "EOD report dispatched to Telegram" if success else "Failed to dispatch Telegram report"}
    except Exception as e:
        logger.error(f"Error sending EOD report to Telegram: {e}")
        raise HTTPException(status_code=500, detail=str(e))

