"""
Auto Trading API Routes
Provides endpoints for auto stock selection and trade execution
"""

import asyncio
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Database imports
from database.connection import get_db
from database.models import SelectedStock, AutoTradingSession, TradeExecution, User, BrokerConfig
from router.auth_router import get_current_user

# Service imports
from services.auto_stock_selection_service import auto_stock_selection_service
from services.execution.auto_trade_execution_service import auto_trade_execution_service
from services.auto_trading_coordinator import AutoTradingCoordinator
from services.unified_trading_executor import unified_trading_executor, UnifiedTradeSignal, TradingMode
from services.paper_trading_account import PaperTradingAccountService
from services.websocket.auto_trading_websocket import AutoTradingWebSocketService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auto-trading", tags=["Auto Trading"])

# Global instances
auto_trading_coordinator = None
paper_trading_service = PaperTradingAccountService()
websocket_service = AutoTradingWebSocketService()

# Initialize coordinator if not exists
async def get_coordinator():
    global auto_trading_coordinator
    if auto_trading_coordinator is None:
        config = {
            'max_positions': 5,
            'max_daily_loss': 50000,
            'risk_per_trade': 0.02
        }
        auto_trading_coordinator = AutoTradingCoordinator(config)
        await auto_trading_coordinator.initialize_system()
    return auto_trading_coordinator

# Pydantic models for request/response
class TradingSessionConfig(BaseModel):
    mode: str = "PAPER_TRADING"  # PAPER_TRADING or LIVE_TRADING
    selected_stocks: List[Dict[str, Any]] = []
    risk_parameters: Dict[str, Any] = {
        "max_risk_per_trade": 0.02,
        "max_daily_loss": 50000
    }
    strategy_config: Dict[str, Any] = {
        "min_signal_strength": 70
    }
    max_positions: int = 5
    max_daily_loss: float = 50000

class TradingSessionResponse(BaseModel):
    is_active: bool
    active_trades: int
    trades_executed_today: int
    daily_pnl: float
    session_date: str
    selected_stocks_count: int
    trading_mode: str = "PAPER_TRADING"
    session_id: Optional[str] = None

class SelectedStockResponse(BaseModel):
    symbol: str
    sector: str
    selection_score: float
    selection_reason: str
    price_at_selection: float
    option_type: str
    atm_strike: float
    adr_score: float
    sector_momentum: float
    volume_score: float
    technical_score: float
    expiry_date: str
    market_sentiment_alignment: bool
    selection_date: str

class MarketSentimentResponse(BaseModel):
    sentiment: str
    confidence: float
    option_bias: str
    factors: Dict[str, Any]

class AutoTradingStatusResponse(BaseModel):
    market_sentiment: MarketSentimentResponse
    stocks: List[SelectedStockResponse]
    trading_session: TradingSessionResponse

@router.get("/selected-stocks")
async def get_selected_stocks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get today's selected stocks with market sentiment"""
    try:
        # Get selected stocks from database
        selected_records = db.query(SelectedStock).filter(
            SelectedStock.selection_date == date.today(),
            SelectedStock.is_active == True
        ).all()
        
        # Convert to response format
        stocks = []
        for record in selected_records:
            try:
                import json
                score_breakdown = {}
                if record.score_breakdown:
                    score_breakdown = json.loads(record.score_breakdown)
                
                stock_data = {
                    "id": record.id,
                    "symbol": record.symbol,
                    "sector": record.sector,
                    "selection_score": record.selection_score,
                    "selection_reason": record.selection_reason,
                    "price_at_selection": record.price_at_selection,
                    "option_type": record.option_type or "NEUTRAL",
                    "atm_strike": score_breakdown.get("atm_strike", 0.0),
                    "adr_score": score_breakdown.get("adr_score", 0.5),
                    "sector_momentum": score_breakdown.get("sector_momentum", 0.0),
                    "volume_score": score_breakdown.get("volume_score", 0.5),
                    "technical_score": score_breakdown.get("technical_score", 0.5),
                    "expiry_date": record.option_expiry_date or "",
                    "market_sentiment_alignment": record.option_type in ["CE", "PE"],
                    "selection_date": record.selection_date.isoformat(),
                    "change_percent": 0.0  # Will be updated with real-time data
                }
                stocks.append(stock_data)
            except Exception as e:
                logger.error(f"Error processing stock {record.symbol}: {e}")
                continue
        
        # Get market sentiment
        market_sentiment = {
            "sentiment": "bullish",
            "confidence": 0.75,
            "option_bias": "CE",
            "factors": {
                "nifty_trend": "positive",
                "vix_level": "normal",
                "institutional_flow": {"fii_flow": 100}
            }
        }
        
        # Get trading session status
        try:
            trading_stats = auto_trade_execution_service.get_trading_stats()
        except:
            trading_stats = {
                "is_active": False,
                "active_trades": 0,
                "trades_executed_today": 0,
                "daily_pnl": 0.0
            }
        
        trading_session = {
            "is_active": trading_stats["is_active"],
            "active_trades": trading_stats["active_trades"],
            "trades_executed_today": trading_stats["trades_executed_today"],
            "daily_pnl": trading_stats["daily_pnl"],
            "session_date": date.today().isoformat(),
            "selected_stocks_count": len(stocks),
            "trading_mode": "PAPER_TRADING"
        }
        
        return {
            "success": True,
            "stocks": stocks,
            "market_sentiment": market_sentiment,
            "trading_session": trading_session
        }
        
    except Exception as e:
        logger.error(f"Error getting selected stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session-status")
async def get_trading_session_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current trading session status from coordinator"""
    try:
        coordinator = await get_coordinator()
        
        # Get active session from database
        active_session = db.query(AutoTradingSession).filter(
            AutoTradingSession.user_id == current_user.id,
            AutoTradingSession.status == "ACTIVE"
        ).first()
        
        # Get selected stocks count
        selected_count = db.query(SelectedStock).filter(
            SelectedStock.selection_date == date.today(),
            SelectedStock.is_active == True
        ).count()
        
        return {
            "is_active": coordinator.system_state.value == "ACTIVE",
            "active_trades": coordinator.system_metrics.get('active_positions', 0),
            "trades_executed_today": coordinator.system_metrics.get('total_trades_today', 0),
            "daily_pnl": coordinator.system_metrics.get('total_pnl_today', 0),
            "session_date": date.today().isoformat(),
            "selected_stocks_count": selected_count,
            "trading_mode": "LIVE_TRADING" if (active_session and active_session.session_type and "LIVE" in active_session.session_type.upper()) else "PAPER_TRADING",
            "session_id": f"auto_session_{active_session.id}" if active_session else None,
            "session_start_time": active_session.created_at.isoformat() if active_session else None,
            "system_health": coordinator.system_health.overall_status
        }
        
    except Exception as e:
        logger.error(f"Error getting trading session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start-session")
async def start_trading_session(
    session_config: TradingSessionConfig,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start automated trading session with unified paper/live trading architecture"""
    try:
        # Get coordinator instance
        coordinator = await get_coordinator()
        
        # Check if already active
        if coordinator.system_state.value == "ACTIVE":
            raise HTTPException(
                status_code=400, 
                detail="Trading session is already active"
            )
        
        # Validate trading mode
        if session_config.mode not in ["PAPER_TRADING", "LIVE_TRADING"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid trading mode. Use PAPER_TRADING or LIVE_TRADING"
            )
        
        # Log trading mode selection
        logger.info(f"🎯 Starting {session_config.mode} session for user {current_user.id}")
        
        # Initialize paper trading account if needed
        if session_config.mode == "PAPER_TRADING":
            await paper_trading_service.create_paper_account(
                user_id=current_user.id,
                initial_capital=500000  # Default ₹5 lakhs
            )
        
        # Create trading session in database
        session_id = f"session_{current_user.id}_{int(datetime.now().timestamp())}"
        auto_session = AutoTradingSession(
            user_id=current_user.id,
            session_id=session_id,
            session_type=f"AUTO_{session_config.mode}",
            trade_mode=session_config.mode,
            config=session_config.dict(),
            created_at=datetime.utcnow(),
            is_active=True
        )
        db.add(auto_session)
        db.commit()
        
        # Create trading session via coordinator
        from services.auto_trading_coordinator import TradingSession, SystemMode
        trading_session = TradingSession(
            session_id=session_id,
            user_id=current_user.id,
            mode=SystemMode.PAPER_TRADING if session_config.mode == "PAPER_TRADING" else SystemMode.LIVE_TRADING,
            selected_stocks=session_config.selected_stocks,
            risk_parameters=session_config.risk_parameters,
            strategy_config=session_config.strategy_config,
            max_positions=session_config.max_positions,
            max_daily_loss=session_config.max_daily_loss,
            session_start_time=datetime.now()
        )
        
        # Start trading session via coordinator
        background_tasks.add_task(
            coordinator.start_trading_session,
            trading_session
        )
        
        # Get current statistics
        selected_count = db.query(SelectedStock).filter(
            SelectedStock.selection_date == date.today(),
            SelectedStock.is_active == True
        ).count()
        
        # Broadcast session start via WebSocket
        await websocket_service.broadcast_session_started({
            "session_id": session_id,
            "user_id": current_user.id,
            "mode": session_config.mode,
            "selected_stocks_count": selected_count,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "message": "Trading session started successfully",
            "session_id": session_id,
            "is_active": True,
            "active_trades": 0,
            "trades_executed_today": 0,
            "daily_pnl": 0.0,
            "session_date": date.today().isoformat(),
            "selected_stocks_count": selected_count,
            "trading_mode": session_config.mode
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting trading session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-session")
async def stop_trading_session(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop automated trading session via coordinator"""
    try:
        # Get coordinator instance
        coordinator = await get_coordinator()
        
        # Check if session is active
        if coordinator.system_state.value != "ACTIVE":
            raise HTTPException(
                status_code=400, 
                detail="No active trading session to stop"
            )
        
        # Stop trading session via coordinator
        background_tasks.add_task(coordinator.stop_all_sessions)
        
        # Update database session status
        active_session = db.query(AutoTradingSession).filter(
            AutoTradingSession.user_id == current_user.id,
            AutoTradingSession.status == "ACTIVE"
        ).first()
        
        if active_session:
            active_session.status = "COMPLETED"
            active_session.completed_at = datetime.utcnow()
            db.commit()
        
        # Get current statistics
        selected_count = db.query(SelectedStock).filter(
            SelectedStock.selection_date == date.today(),
            SelectedStock.is_active == True
        ).count()
        
        # Broadcast session stop via WebSocket
        await websocket_service.broadcast_session_stopped({
            "session_id": active_session.session_id if active_session else "unknown",
            "user_id": current_user.id,
            "final_pnl": coordinator.system_metrics.get('total_pnl_today', 0),
            "total_trades": coordinator.system_metrics.get('total_trades_today', 0),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "message": "Trading session stopped successfully",
            "is_active": False,
            "active_trades": coordinator.system_metrics.get('active_positions', 0),
            "trades_executed_today": coordinator.system_metrics.get('total_trades_today', 0),
            "daily_pnl": coordinator.system_metrics.get('total_pnl_today', 0),
            "session_date": date.today().isoformat(),
            "selected_stocks_count": selected_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping trading session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-stock-selection")
async def run_stock_selection(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Manually trigger stock selection process via coordinator"""
    try:
        coordinator = await get_coordinator()
        
        # Use coordinator's stock selection service if available
        if coordinator.stock_selection_service:
            background_tasks.add_task(
                coordinator.stock_selection_service.run_daily_selection
            )
        else:
            # Fallback to existing service
            background_tasks.add_task(auto_stock_selection_service.run_premarket_selection)
        
        # Broadcast stock selection started
        await websocket_service.broadcast_stock_selection_started({
            "user_id": current_user.id,
            "timestamp": datetime.now().isoformat(),
            "triggered_by": "manual"
        })
        
        return {
            "success": True,
            "message": "Stock selection process started",
            "status": "running",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running stock selection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-trades")
async def get_active_trades(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current active trades from coordinator and unified trading executor"""
    try:
        coordinator = await get_coordinator()
        
        if not coordinator:
            logger.error("Coordinator not initialized")
            return {
                "active_trades": [],
                "total_active": 0,
                "daily_pnl": 0,
                "error": "Coordinator not available"
            }
        
        # Get active positions from coordinator
        active_positions = []
        
        if coordinator.position_monitor:
            try:
                position_summary = coordinator.position_monitor.get_position_summary()
                positions = position_summary.get('positions', [])
                
                for position in positions:
                    if position.get("position_type"):  # Only include active positions
                        position_data = {
                            "id": position.get("position_id"),
                            "symbol": position.get("symbol"),
                            "option_type": "CE",  # Default, could be enhanced
                            "entry_price": position.get("entry_price", 0),
                            "current_price": position.get("current_price", 0),
                            "quantity": position.get("quantity", 0),
                            "lot_size": 1,  # Default, could be enhanced
                            "pnl": position.get("unrealized_pnl", 0),
                            "pnl_percentage": 0,  # Calculate if needed
                            "stop_loss": 0,  # Could be enhanced with actual stop loss data
                            "target": 0,     # Could be enhanced with actual target data
                            "entry_time": datetime.now().isoformat(),  # Could be enhanced
                            "status": "ACTIVE"
                        }
                        active_positions.append(position_data)
            except Exception as position_error:
                logger.error(f"Error getting positions from coordinator: {position_error}")
                # Continue to check paper trading positions
        
        # Also check paper trading service if in paper mode
        try:
            user_session = db.query(AutoTradingSession).filter(
                AutoTradingSession.user_id == current_user.id,
                AutoTradingSession.status == "ACTIVE"
            ).first()
            
            if user_session and ("PAPER" in user_session.session_type.upper() if user_session.session_type else True):
                try:
                    paper_account = await paper_trading_service.get_account(current_user.id)
                    if paper_account:
                        paper_positions = paper_trading_service.positions.get(current_user.id, [])
                        for position in paper_positions:
                            if hasattr(position, 'status') and position.status == "ACTIVE":
                                active_positions.append({
                                    "id": getattr(position, 'position_id', f"paper_{len(active_positions)}"),
                                    "symbol": getattr(position, 'symbol', 'UNKNOWN'),
                                    "option_type": getattr(position, 'option_type', 'CE'),
                                    "entry_price": getattr(position, 'entry_price', 0),
                                    "current_price": getattr(position, 'current_price', 0),
                                    "quantity": getattr(position, 'quantity', 0),
                                    "lot_size": getattr(position, 'lot_size', 1),
                                    "pnl": getattr(position, 'pnl', 0),
                                    "pnl_percentage": getattr(position, 'pnl_percentage', 0),
                                    "stop_loss": getattr(position, 'stop_loss', 0),
                                    "target": getattr(position, 'target', 0),
                                    "entry_time": getattr(position, 'entry_time', datetime.now()).isoformat() if hasattr(position, 'entry_time') else datetime.now().isoformat(),
                                    "status": getattr(position, 'status', 'ACTIVE')
                                })
                except Exception as paper_error:
                    logger.error(f"Error getting paper trading positions: {paper_error}")
        except Exception as session_error:
            logger.error(f"Error getting user session: {session_error}")
        
        # Get daily PnL safely
        daily_pnl = 0
        try:
            if coordinator and hasattr(coordinator, 'system_metrics'):
                daily_pnl = coordinator.system_metrics.get('total_pnl_today', 0)
        except Exception as pnl_error:
            logger.error(f"Error getting daily PnL: {pnl_error}")
        
        return {
            "active_trades": active_positions,
            "total_active": len(active_positions),
            "daily_pnl": daily_pnl,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error getting active trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trading-history")
async def get_trading_history(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trading history for specified days"""
    try:
        from datetime import timedelta
        
        start_date = date.today() - timedelta(days=days)
        
        # Get trade executions
        trades = db.query(TradeExecution).filter(
            TradeExecution.user_id == current_user.id,
            TradeExecution.entry_time >= start_date
        ).order_by(TradeExecution.entry_time.desc()).all()
        
        # Format response
        trade_history = []
        for trade in trades:
            trade_data = {
                "symbol": trade.symbol,
                "trade_type": trade.trade_type,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "quantity": trade.quantity,
                "pnl": trade.pnl,
                "pnl_percentage": trade.pnl_percentage,
                "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                "status": trade.status,
                "exit_reason": trade.exit_reason
            }
            
            # Parse technical indicators if available
            if trade.technical_indicators:
                try:
                    import json
                    indicators = json.loads(trade.technical_indicators)
                    trade_data.update({
                        "option_type": indicators.get("option_type"),
                        "strike_price": indicators.get("strike_price"),
                        "stop_loss": indicators.get("stop_loss"),
                        "target": indicators.get("target")
                    })
                except:
                    pass
            
            trade_history.append(trade_data)
        
        return {
            "trades": trade_history,
            "total_trades": len(trade_history),
            "date_range": {
                "start": start_date.isoformat(),
                "end": date.today().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting trading history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance-summary")
async def get_performance_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trading performance summary"""
    try:
        from datetime import timedelta
        from sqlalchemy import func
        
        # Today's performance
        today_trades = db.query(TradeExecution).filter(
            TradeExecution.user_id == current_user.id,
            TradeExecution.entry_time >= date.today()
        ).all()
        
        # This week's performance
        week_start = date.today() - timedelta(days=7)
        week_trades = db.query(TradeExecution).filter(
            TradeExecution.user_id == current_user.id,
            TradeExecution.entry_time >= week_start
        ).all()
        
        # This month's performance
        month_start = date.today().replace(day=1)
        month_trades = db.query(TradeExecution).filter(
            TradeExecution.user_id == current_user.id,
            TradeExecution.entry_time >= month_start
        ).all()
        
        def calculate_stats(trades):
            if not trades:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "avg_pnl": 0.0,
                    "best_trade": 0.0,
                    "worst_trade": 0.0
                }
            
            completed_trades = [t for t in trades if t.status == "CLOSED" and t.pnl is not None]
            if not completed_trades:
                return {
                    "total_trades": len(trades),
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "avg_pnl": 0.0,
                    "best_trade": 0.0,
                    "worst_trade": 0.0
                }
            
            winning_trades = [t for t in completed_trades if t.pnl > 0]
            losing_trades = [t for t in completed_trades if t.pnl <= 0]
            total_pnl = sum(t.pnl for t in completed_trades)
            
            return {
                "total_trades": len(trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate": len(winning_trades) / len(completed_trades) * 100,
                "total_pnl": total_pnl,
                "avg_pnl": total_pnl / len(completed_trades),
                "best_trade": max(t.pnl for t in completed_trades),
                "worst_trade": min(t.pnl for t in completed_trades)
            }
        
        return {
            "today": calculate_stats(today_trades),
            "week": calculate_stats(week_trades),
            "month": calculate_stats(month_trades),
            "current_session": auto_trade_execution_service.get_trading_stats()
        }
        
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ADDITIONAL MISSING API ENDPOINTS FOR UI INTEGRATION
# ============================================================================

@router.get("/system-stats")
async def get_system_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive system statistics from coordinator and unified trading system"""
    try:
        coordinator = await get_coordinator()
        
        # Get today's completed trades for calculations
        today_trades = db.query(TradeExecution).filter(
            TradeExecution.user_id == current_user.id,
            TradeExecution.entry_time >= date.today(),
            TradeExecution.status == "CLOSED"
        ).all()
        
        # Calculate success rate
        successful_trades = [t for t in today_trades if t.pnl and t.pnl > 0]
        success_rate = (len(successful_trades) / len(today_trades) * 100) if today_trades else 0
        
        # Calculate average return
        avg_return = (sum(t.pnl for t in today_trades if t.pnl) / len(today_trades)) if today_trades else 0
        
        # Get selected stocks count
        selected_stocks_count = db.query(SelectedStock).filter(
            SelectedStock.selection_date == date.today(),
            SelectedStock.is_active == True
        ).count()
        
        # Get portfolio value (paper trading vs live)
        portfolio_value = 100000  # Default
        user_session = db.query(AutoTradingSession).filter(
            AutoTradingSession.user_id == current_user.id,
            AutoTradingSession.is_active == True
        ).first()
        
        if user_session and ("PAPER" in user_session.session_type.upper() if user_session.session_type else True):
            paper_account = await paper_trading_service.get_account(current_user.id)
            if paper_account:
                portfolio_value = paper_account.current_balance
        
        # Get system metrics from coordinator
        system_metrics = coordinator.system_metrics
        
        return {
            "success": True,
            "data": {
                "totalTrades": system_metrics.get('total_trades_today', len(today_trades)),
                "successRate": round(success_rate, 1),
                "avgReturn": round(avg_return, 2),
                "activeStrategies": 2,  # Fibonacci + NIFTY strategies
                "portfolioValue": portfolio_value,
                "dailyPnL": system_metrics.get('total_pnl_today', 0),
                "monthlyReturn": 0.0,  # Calculate from monthly data
                "totalReturn": system_metrics.get('total_pnl_today', 0),
                "activeTrades": system_metrics.get('active_positions', 0),
                "selectedStocksCount": selected_stocks_count,
                "systemStatus": coordinator.system_state.value,
                "winRate": round(success_rate, 1),
                "signalsGenerated": system_metrics.get('signals_generated', 0),
                "signalsExecuted": system_metrics.get('signals_executed', 0),
                "avgExecutionTime": system_metrics.get('avg_execution_time_ms', 0),
                "systemUptime": system_metrics.get('uptime_percentage', 100),
                "lastUpdated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        # Return fallback stats on error
        return {
            "success": False,
            "error": str(e),
            "data": {
                "totalTrades": 0,
                "successRate": 0,
                "avgReturn": 0,
                "activeStrategies": 0,
                "portfolioValue": 100000,
                "dailyPnL": 0,
                "monthlyReturn": 0,
                "totalReturn": 0,
                "activeTrades": 0,
                "selectedStocksCount": 0,
                "systemStatus": "INACTIVE",
                "winRate": 0,
                "signalsGenerated": 0,
                "signalsExecuted": 0,
                "avgExecutionTime": 0,
                "systemUptime": 0,
                "lastUpdated": datetime.now().isoformat()
            }
        }

class EmergencyStopRequest(BaseModel):
    reason: str = "Manual emergency stop"
    force_close_positions: bool = True

@router.post("/emergency-stop")
async def emergency_stop(
    request: EmergencyStopRequest,
    current_user: User = Depends(get_current_user)
):
    """Trigger emergency stop of auto-trading system"""
    try:
        # Only admin users can trigger emergency stop
        if current_user.role != "Admin":
            raise HTTPException(status_code=403, detail="Only admin users can trigger emergency stop")
        
        # Stop trading session if active
        if auto_trade_execution_service.is_trading_active:
            await auto_trade_execution_service.stop_trading_session()
        
        logger.critical(f"EMERGENCY STOP triggered by {current_user.email}: {request.reason}")
        
        # Emit emergency alert via Socket.IO if available
        try:
            from services.socketio_manager import emit_emergency_alert
            await emit_emergency_alert({
                "type": "EMERGENCY_STOP",
                "reason": request.reason,
                "triggered_by": current_user.email,
                "timestamp": datetime.now().isoformat(),
                "force_close": request.force_close_positions
            })
        except ImportError:
            logger.warning("Socket.IO manager not available for emergency alert")
        
        return {
            "success": True,
            "message": "Emergency stop activated successfully",
            "reason": request.reason,
            "triggered_by": current_user.email,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error triggering emergency stop: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger emergency stop: {str(e)}")

@router.get("/position-summary")
async def get_position_summary(
    current_user: User = Depends(get_current_user)
):
    """Get current position summary"""
    try:
        trading_stats = auto_trade_execution_service.get_trading_stats()
        
        return {
            "success": True,
            "data": {
                "active_positions": trading_stats.get("active_positions", []),
                "total_positions": trading_stats.get("active_trades", 0),
                "unrealized_pnl": trading_stats.get("unrealized_pnl", 0),
                "realized_pnl": trading_stats.get("realized_pnl", 0),
                "daily_pnl": trading_stats.get("daily_pnl", 0),
                "portfolio_value": 100000,  # Should come from user config
                "margin_used": trading_stats.get("margin_used", 0),
                "buying_power": trading_stats.get("buying_power", 100000),
                "last_updated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting position summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get position summary: {str(e)}")

@router.post("/pause-trading")
async def pause_trading(
    current_user: User = Depends(get_current_user)
):
    """Pause auto-trading operations (admin only)"""
    try:
        if current_user.role != "Admin":
            raise HTTPException(status_code=403, detail="Only admin users can pause trading")
        
        # This would integrate with auto-trading coordinator when available
        # For now, we'll work with the existing service
        if auto_trade_execution_service.is_trading_active:
            await auto_trade_execution_service.pause_trading()
        
        return {
            "success": True,
            "message": "Trading operations paused",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error pausing trading: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause trading: {str(e)}")

@router.post("/resume-trading") 
async def resume_trading(
    current_user: User = Depends(get_current_user)
):
    """Resume auto-trading operations (admin only)"""
    try:
        if current_user.role != "Admin":
            raise HTTPException(status_code=403, detail="Only admin users can resume trading")
        
        coordinator = await get_coordinator()
        await coordinator.resume_system()
        
        return {
            "success": True,
            "message": "Trading operations resumed",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resuming trading: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume trading: {str(e)}")

@router.get("/real-time-metrics")
async def get_real_time_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get real-time trading metrics for WebSocket broadcasting"""
    try:
        coordinator = await get_coordinator()
        
        # Get real-time metrics
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system_status": coordinator.system_state.value,
            "active_positions": coordinator.system_metrics.get('active_positions', 0),
            "daily_pnl": coordinator.system_metrics.get('total_pnl_today', 0),
            "total_trades": coordinator.system_metrics.get('total_trades_today', 0),
            "successful_trades": coordinator.system_metrics.get('successful_trades', 0),
            "signals_generated": coordinator.system_metrics.get('signals_generated', 0),
            "avg_execution_time": coordinator.system_metrics.get('avg_execution_time_ms', 0),
            "system_uptime": coordinator.system_metrics.get('uptime_percentage', 100)
        }
        
        # Broadcast to WebSocket clients
        await websocket_service.broadcast_real_time_metrics(metrics)
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"Error getting real-time metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/force-stock-selection")
async def force_stock_selection(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Force run stock selection algorithm immediately"""
    try:
        coordinator = await get_coordinator()
        
        if coordinator.stock_selection_service:
            # Run stock selection via coordinator
            background_tasks.add_task(
                coordinator.stock_selection_service.run_daily_selection
            )
            
            return {
                "success": True,
                "message": "Stock selection process initiated",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Fallback to existing service
            background_tasks.add_task(auto_stock_selection_service.run_premarket_selection)
            return {
                "success": True,
                "message": "Stock selection process started (fallback mode)",
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error forcing stock selection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trading-signals")
async def get_recent_trading_signals(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent trading signals generated by the system"""
    try:
        coordinator = await get_coordinator()
        
        # Get recent signals from coordinator if available
        signals = []
        
        if coordinator.fibonacci_strategy:
            # This would get recent signals from strategy cache
            recent_signals = getattr(coordinator.fibonacci_strategy, 'recent_signals', [])
            for signal in recent_signals[-limit:]:
                signals.append({
                    "symbol": signal.get("symbol"),
                    "signal_type": signal.get("signal_type"),
                    "strength": signal.get("strength", 0),
                    "entry_price": signal.get("entry_price"),
                    "stop_loss": signal.get("stop_loss"),
                    "target": signal.get("target"),
                    "fibonacci_levels": signal.get("fibonacci_levels", {}),
                    "timestamp": signal.get("timestamp", datetime.now().isoformat()),
                    "executed": signal.get("executed", False)
                })
        
        # Also get from database if no signals from coordinator
        if not signals:
            # Get recent trade executions as proxy for signals
            recent_trades = db.query(TradeExecution).filter(
                TradeExecution.user_id == current_user.id,
                TradeExecution.entry_time >= datetime.now().date()
            ).order_by(TradeExecution.entry_time.desc()).limit(limit).all()
            
            for trade in recent_trades:
                signals.append({
                    "symbol": trade.symbol,
                    "signal_type": trade.trade_type,
                    "strength": 75,  # Default strength
                    "entry_price": trade.entry_price,
                    "stop_loss": trade.stop_loss,
                    "target": trade.target,
                    "fibonacci_levels": {},
                    "timestamp": trade.entry_time.isoformat() if trade.entry_time else datetime.now().isoformat(),
                    "executed": True
                })
        
        return {
            "success": True,
            "signals": signals,
            "total_count": len(signals)
        }
        
    except Exception as e:
        logger.error(f"Error getting trading signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/selected-stocks/{stock_id}")
async def remove_selected_stock(
    stock_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a stock from selected stocks list"""
    try:
        # Get the selected stock
        selected_stock = db.query(SelectedStock).filter(
            SelectedStock.id == stock_id,
            SelectedStock.selection_date == date.today()
        ).first()
        
        if not selected_stock:
            raise HTTPException(status_code=404, detail="Selected stock not found")
        
        # Mark as inactive instead of deleting
        selected_stock.is_active = False
        db.commit()
        
        # Broadcast the removal via WebSocket
        await websocket_service.broadcast_stock_removed({
            "stock_id": stock_id,
            "symbol": selected_stock.symbol,
            "user_id": current_user.id,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "message": f"Stock {selected_stock.symbol} removed from selection"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing selected stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/kill-switch/{symbol}")
async def kill_switch_stock(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Emergency kill switch for individual stock - immediately exit all positions"""
    try:
        coordinator = await get_coordinator()
        
        # Get user's trading mode
        user_session = db.query(AutoTradingSession).filter(
            AutoTradingSession.user_id == current_user.id,
            AutoTradingSession.status == "ACTIVE"
        ).first()
        
        if not user_session:
            raise HTTPException(status_code=400, detail="No active trading session found")
        
        trading_mode = "LIVE_TRADING" if (user_session.session_type and "LIVE" in user_session.session_type.upper()) else "PAPER_TRADING"
        logger.critical(f"🚨 KILL SWITCH activated for {symbol} by user {current_user.id} (Mode: {trading_mode})")
        
        positions_closed = 0
        total_pnl = 0.0
        
        if trading_mode == "PAPER_TRADING":
            # Close paper trading positions immediately
            paper_positions = paper_trading_service.positions.get(current_user.id, [])
            for position in paper_positions:
                if position.symbol == symbol and position.status == "ACTIVE":
                    # Calculate current P&L and close position
                    current_pnl = position.pnl
                    position.status = "CLOSED"
                    position.exit_time = datetime.now()
                    position.exit_reason = "KILL_SWITCH_ACTIVATED"
                    
                    # Update paper account
                    paper_account = await paper_trading_service.get_account(current_user.id)
                    if paper_account:
                        paper_account.current_balance += position.invested_amount + current_pnl
                        paper_account.used_margin -= position.invested_amount
                        paper_account.available_margin = paper_account.current_balance - paper_account.used_margin
                        paper_account.total_pnl += current_pnl
                        paper_account.daily_pnl += current_pnl
                    
                    positions_closed += 1
                    total_pnl += current_pnl
                    
                    logger.info(f"📈 Paper position closed: {symbol} P&L: ₹{current_pnl:.2f}")
        
        else:  # LIVE_TRADING
            # Get active positions from coordinator
            if coordinator.position_monitor:
                active_positions = await coordinator.position_monitor.get_active_positions()
                for position in active_positions:
                    if position.get("symbol") == symbol:
                        # Execute live exit via broker
                        try:
                            # Get broker configuration for user
                            broker_config = db.query(BrokerConfig).filter(
                                BrokerConfig.user_id == current_user.id,
                                BrokerConfig.is_active == True
                            ).first()
                            
                            if broker_config:
                                # Use unified trading executor to exit position
                                exit_signal = UnifiedTradeSignal(
                                    user_id=current_user.id,
                                    symbol=symbol,
                                    instrument_key=position.get("instrument_key"),
                                    option_type=position.get("option_type"),
                                    signal_type="SELL",  # Exit position
                                    entry_price=position.get("current_price", 0),
                                    quantity=position.get("quantity", 0),
                                    lot_size=position.get("lot_size", 1),
                                    stop_loss=0,  # Emergency exit - no stop loss
                                    target=0,     # Emergency exit - no target
                                    confidence_score=100,  # Max confidence for kill switch
                                    strategy_name="kill_switch_emergency",
                                    trading_mode=TradingMode.LIVE,
                                    exit_reason="KILL_SWITCH_ACTIVATED"
                                )
                                
                                result = await unified_trading_executor.execute_trade_signal(exit_signal)
                                
                                if result.get("status") == "success":
                                    positions_closed += 1
                                    total_pnl += result.get("pnl", 0)
                                    logger.info(f"🔴 Live position closed via broker: {symbol}")
                                else:
                                    logger.error(f"❌ Failed to close live position: {symbol} - {result.get('message')}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error closing live position for {symbol}: {e}")
                            # Continue to try closing other positions
        
        # Deactivate the stock from selection to prevent new trades
        selected_stock = db.query(SelectedStock).filter(
            SelectedStock.symbol == symbol,
            SelectedStock.selection_date == date.today(),
            SelectedStock.is_active == True
        ).first()
        
        if selected_stock:
            selected_stock.is_active = False
            selected_stock.selection_reason += " [KILL_SWITCH_DEACTIVATED]"
            db.commit()
            logger.info(f"🛑 Stock {symbol} deactivated from selection")
        
        # Broadcast kill switch activation via WebSocket
        await websocket_service.broadcast_kill_switch_activated({
            "symbol": symbol,
            "user_id": current_user.id,
            "trading_mode": trading_mode,
            "positions_closed": positions_closed,
            "total_pnl": total_pnl,
            "timestamp": datetime.now().isoformat(),
            "triggered_by": current_user.email
        })
        
        return {
            "success": True,
            "message": f"Kill switch activated for {symbol}",
            "positions_closed": positions_closed,
            "total_pnl": total_pnl,
            "trading_mode": trading_mode,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Kill switch failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Kill switch failed: {str(e)}")

@router.get("/user-capital")
async def get_user_capital(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's available capital based on trading mode"""
    try:
        # Get user's active trading session
        user_session = db.query(AutoTradingSession).filter(
            AutoTradingSession.user_id == current_user.id,
            AutoTradingSession.status == "ACTIVE"
        ).first()
        
        # Default to PAPER_TRADING mode (most sessions are paper trading)
        trading_mode = "PAPER_TRADING"
        if user_session:
            # Try to get trading mode from session_type or default to paper
            session_type = user_session.session_type or ""
            if "LIVE" in session_type.upper():
                trading_mode = "LIVE_TRADING"
        
        if trading_mode == "PAPER_TRADING":
            # Get paper trading account
            paper_account = await paper_trading_service.get_account(current_user.id)
            if paper_account:
                return {
                    "success": True,
                    "trading_mode": trading_mode,
                    "total_capital": paper_account.initial_capital,
                    "available_capital": paper_account.available_margin,
                    "used_capital": paper_account.used_margin,
                    "current_balance": paper_account.current_balance,
                    "daily_pnl": paper_account.daily_pnl,
                    "total_pnl": paper_account.total_pnl
                }
            else:
                return {
                    "success": True,
                    "trading_mode": trading_mode,
                    "total_capital": 500000,  # Default
                    "available_capital": 500000,
                    "used_capital": 0,
                    "current_balance": 500000,
                    "daily_pnl": 0,
                    "total_pnl": 0
                }
        else:  # LIVE_TRADING
            # Get live capital from broker
            broker_config = db.query(BrokerConfig).filter(
                BrokerConfig.user_id == current_user.id,
                BrokerConfig.is_active == True
            ).first()
            
            if broker_config:
                try:
                    # This would call the actual broker API to get funds
                    # For now, return mock data - replace with actual broker integration
                    broker_name = broker_config.broker_name.lower()
                    
                    # Mock broker fund data - replace with actual API calls
                    mock_funds = {
                        "upstox": {"total": 100000, "available": 85000, "used": 15000},
                        "dhan": {"total": 150000, "available": 120000, "used": 30000},
                        "angel": {"total": 200000, "available": 180000, "used": 20000}
                    }
                    
                    funds = mock_funds.get(broker_name, {"total": 100000, "available": 100000, "used": 0})
                    
                    return {
                        "success": True,
                        "trading_mode": trading_mode,
                        "broker_name": broker_config.broker_name,
                        "total_capital": funds["total"],
                        "available_capital": funds["available"],
                        "used_capital": funds["used"],
                        "current_balance": funds["available"],
                        "daily_pnl": 0,  # Would come from broker
                        "total_pnl": 0   # Would come from broker
                    }
                    
                except Exception as e:
                    logger.error(f"Error fetching live capital: {e}")
                    return {
                        "success": False,
                        "error": "Failed to fetch live capital from broker",
                        "trading_mode": trading_mode
                    }
            else:
                return {
                    "success": False,
                    "error": "No active broker configuration found",
                    "trading_mode": trading_mode
                }
        
    except Exception as e:
        logger.error(f"Error getting user capital: {e}")
        raise HTTPException(status_code=500, detail=str(e))