import asyncio
import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager
import threading
import time
import schedule
import uvicorn
import socketio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import database and models
from core.middleware import TokenRefreshMiddleware
from database.connection import SessionLocal, get_db
from database.init_db import init_db
from database.models import TradePerformance, TradeSignal
from router import analytics_router, order_router
from router.user_router import router as user_router
from router.auth_router import auth_router
from router.broker_router import broker_router
from router.stock_list_router import stock_list_router
from router.dhan_router import dhan_router
from router.upstox_router import upstox_router
from router.fyers_router import fyers_router
from router.market_data_router import market_data_router
from services import stop_loss_router
from services.auto_trade_execution import auto_execute_trades
from services.dynamic_stop_loss import calculate_dynamic_stop_loss
from services.trailing_stop_loss import update_trailing_stop_loss
from ws_router.upstox_ltp_ws import ws_upstox_router
from router.market_ws import router as market_ws_router
from router.backtest_router import backtesting_router
from router.stock_router import router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("Starting Trading Application...")

    try:
        # Initialize database connection
        db = next(get_db())
        logger.info("Trading bot initialized successfully.")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise

    yield
    logger.info("Shutting down application...")


# Initialize FastAPI App
app = FastAPI(
    title="Trading Bot API",
    description="AI-powered automated trading system",
    version="1.0.0",
    lifespan=lifespan,
)

# ✅ Secure CORS Middleware Setup
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Allow local development frontend
    "https://resplendent-shortbread-e830d3.netlify.app",
    "https://growthquantix.com",  # frontend
    "https://www.growthquantix.com",
    "https://api.growthquantix.com",  # Allow Netlify-hosted frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ✅ Use specific origins instead of "*"
    allow_credentials=True,  # ✅ Required for sending cookies & Authorization headers
    allow_methods=["*"],  # ✅ Allow all methods (GET, POST, PUT, DELETE, OPTIONS)
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Refresh-Token",
        "X-CSRFToken",
    ],  # ✅ Include Refresh-Token
    expose_headers=[
        "Content-Disposition",
        "Authorization",
    ],  # ✅ Expose required headers for downloads & auth
)

# ✅ Register FastAPI Routes Before Initializing SocketIO
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(broker_router, prefix="/api/broker", tags=["Broker API"])
app.include_router(user_router, prefix="/api/user", tags=["User Profile"])
app.include_router(stock_list_router, prefix="/api/stocks", tags=["Stock Data"])
app.include_router(upstox_router, prefix="/api/broker/upstox", tags=["Upstox API"])
app.include_router(fyers_router, prefix="/api/broker/fyers", tags=["Fyers API"])
app.add_middleware(TokenRefreshMiddleware)
app.include_router(dhan_router, prefix="/api/dhan", tags=["Dhan API"])
app.include_router(market_data_router)
app.include_router(analytics_router.router)
app.include_router(order_router.router)
app.include_router(stop_loss_router.router)
app.include_router(ws_upstox_router)
app.include_router(market_ws_router)
app.include_router(backtesting_router, prefix="/api/backtesting")
app.include_router(router)
app.include_router(router)


# ✅ Background task for AI stop-loss updates
def update_all_stop_losses():
    """Update AI stop-loss dynamically every minute for open trades."""
    db = SessionLocal()
    users = db.query(TradePerformance.user_id).distinct().all()

    for user in users:
        trades = (
            db.query(TradePerformance)
            .filter(
                TradePerformance.user_id == user[0], TradePerformance.status == "OPEN"
            )
            .all()
        )
        for trade in trades:
            calculate_dynamic_stop_loss(user[0], trade.symbol, db)

    db.close()


# ✅ Schedule stop-loss updates every minute
def run_scheduler():
    """Runs the scheduler in a separate thread."""
    schedule.every(1).minutes.do(update_all_stop_losses)
    while True:
        schedule.run_pending()
        time.sleep(1)


# ✅ Start background scheduler when the server starts
@app.on_event("startup")
def start_background_scheduler():
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()


# ✅ Run AI-Based Trailing Stop-Loss Update
def run_trailing_stop_loss_updates():
    """Updates trailing stop-loss every minute for all trades."""
    db = SessionLocal()
    users = db.query(TradePerformance.user_id).distinct().all()

    for user in users:
        trades = (
            db.query(TradePerformance)
            .filter(
                TradePerformance.user_id == user[0], TradePerformance.status == "OPEN"
            )
            .all()
        )
        for trade in trades:
            update_trailing_stop_loss(user[0], trade.symbol, db)

    db.close()


def start_trailing_stop_task():
    schedule.every(1).minutes.do(run_trailing_stop_loss_updates)
    while True:
        schedule.run_pending()


thread = threading.Thread(target=start_trailing_stop_task, daemon=True)
thread.start()


# ✅ Background Auto-Trade Execution Task
def run_auto_trading():
    db = SessionLocal()
    users = db.query(TradeSignal.user_id).distinct().all()

    for user in users:
        auto_execute_trades(user[0], db)

    db.close()


# ✅ Run every minute
def start_auto_trading():
    schedule.every(1).minutes.do(run_auto_trading)
    while True:
        schedule.run_pending()


thread = threading.Thread(target=start_auto_trading, daemon=True)
thread.start()


# ✅ Debug Preflight Requests
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return JSONResponse(content={"message": "Preflight OK"}, status_code=200)


# ✅ Initialize SocketIO separately
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS)
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)


# ✅ Root API Endpoint
@app.get("/")
async def root():
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


# ✅ API Health Check
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


# ✅ Improved Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "message": "An internal server error occurred. Please check the logs.",
        },
    )


# ✅ Start FastAPI Server
if __name__ == "__main__":
    logger.info("Starting FastAPI Trading Bot Server...")
    uvicorn.run(
        "app:sio_app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
