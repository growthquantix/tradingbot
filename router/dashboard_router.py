import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from database.connection import get_db
from services.auth_service import get_current_user
from services.dashboard_ohlc_service import DashboardOHLCService
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Global instances
dashboard_service = DashboardOHLCService()


@router.get("/selected-stocks")
async def get_selected_stocks(current_user: dict = Depends(get_current_user)):
    """Get currently selected stocks for trading"""
    try:
        return {
            "selected_stocks": trading_engine.selected_stocks,
            "count": len(trading_engine.selected_stocks),
            "last_updated": (
                trading_engine.market_scheduler.last_analysis_time
                if hasattr(trading_engine.market_scheduler, "last_analysis_time")
                else None
            ),
        }

    except Exception as e:
        logger.error(f"❌ Failed to get selected stocks: {e}")
        return {"error": str(e)}


@router.get("/ohlc/{symbol}")
async def get_stock_ohlc(symbol: str, current_user: dict = Depends(get_current_user)):
    """Get OHLC data for specific stock"""
    try:
        ohlc_data = dashboard_service.get_ohlc_data(symbol)

        if not ohlc_data:
            return {"error": f"No OHLC data found for {symbol}"}

        return ohlc_data

    except Exception as e:
        logger.error(f"❌ Failed to get OHLC for {symbol}: {e}")
        return {"error": str(e)}


@router.get("/ohlc")
async def get_all_ohlc(current_user: dict = Depends(get_current_user)):
    """Get OHLC data for all selected stocks"""
    try:
        return dashboard_service.get_ohlc_data()

    except Exception as e:
        logger.error(f"❌ Failed to get all OHLC data: {e}")
        return {"error": str(e)}


@router.websocket("/ws/ohlc")
async def ohlc_websocket(websocket: WebSocket):
    """WebSocket for real-time OHLC updates"""
    await websocket.accept()
    logger.info("📊 OHLC WebSocket connected")

    try:
        while True:
            # Send current OHLC data every 30 seconds
            ohlc_data = dashboard_service.get_ohlc_data()

            if ohlc_data:
                await websocket.send_json(
                    {
                        "type": "ohlc_update",
                        "data": ohlc_data,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info("📊 OHLC WebSocket disconnected")
    except Exception as e:
        logger.error(f"❌ OHLC WebSocket error: {e}")
    finally:
        await websocket.close()


@router.post("/start-engine")
async def start_trading_engine(current_user: dict = Depends(get_current_user)):
    """Start the trading engine (admin only)"""
    try:
        if not trading_engine.is_running:
            # Start engine in background
            import asyncio

            asyncio.create_task(trading_engine.start_trading_engine())

            return {"message": "Trading engine started", "status": "running"}
        else:
            return {"message": "Trading engine already running", "status": "running"}

    except Exception as e:
        logger.error(f"❌ Failed to start trading engine: {e}")
        return {"error": str(e)}


@router.post("/stop-engine")
async def stop_trading_engine(current_user: dict = Depends(get_current_user)):
    """Stop the trading engine (admin only)"""
    try:
        trading_engine.stop_engine()
        return {"message": "Trading engine stopped", "status": "stopped"}

    except Exception as e:
        logger.error(f"❌ Failed to stop trading engine: {e}")
        return {"error": str(e)}


@router.get("/engine-status")
async def get_engine_status(current_user: dict = Depends(get_current_user)):
    """Get trading engine status"""
    try:
        return {
            "is_running": trading_engine.is_running,
            "selected_stocks_count": len(trading_engine.selected_stocks),
            "active_users_count": len(trading_engine.active_users),
            "current_phase": (
                trading_engine._get_current_phase()
                if hasattr(trading_engine, "_get_current_phase")
                else "unknown"
            ),
        }

    except Exception as e:
        logger.error(f"❌ Failed to get engine status: {e}")
        return {"error": str(e)}
