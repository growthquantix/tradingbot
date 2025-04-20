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
from ws_router.upstox_ltp_ws import ws_upstox_router
from router.market_ws import router as market_ws_router
from router.backtest_router import backtesting_router
from router.stock_router import router as stock_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Trading Application...")

    try:
        # DB initialization
        db = next(get_db())
        logger.info("✅ DB session initialized.")

        # Optional: start any background jobs here
        logger.info("🟢 Background schedulers started.")
        yield
    except Exception as e:
        logger.exception("🔥 Lifespan startup failed.")
        raise e
    finally:
        logger.info("🛑 Lifespan shutdown complete.")


# Initialize FastAPI App
app = FastAPI(
    title="Trading Bot API",
    description="AI-powered automated trading system",
    version="1.0.0",
    lifespan=lifespan,
)

# ✅ CORS Middleware
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://resplendent-shortbread-e830d3.netlify.app",
    "https://growthquantix.com",
    "https://www.growthquantix.com",
    "https://api.growthquantix.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Refresh-Token",
        "X-CSRFToken",
    ],
    expose_headers=["Content-Disposition", "Authorization"],
)

# ✅ Include Routes
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
app.include_router(stock_router)


# ✅ Preflight handler for OPTIONS
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return JSONResponse(content={"message": "Preflight OK"}, status_code=200)


# ✅ SocketIO Initialization
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=ALLOWED_ORIGINS)
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)


# ✅ Root + Health
@app.get("/")
async def root():
    return {"status": "running", "timestamp": datetime.now().isoformat()}


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ✅ Global Error Handler
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


# ✅ Run App
if __name__ == "__main__":
    logger.info("🚀 Launching Trading Bot Server...")
    uvicorn.run(
        "app:sio_app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
