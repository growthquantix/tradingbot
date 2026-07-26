"""
Builds a completely independent, standalone repository at C:/Work/P/app/ai-quant-watchlist-service
with all required folders, database models, services, and a clean asyncio main.py.
Also strips out unnecessary trade execution, backtesting, and strategy folders!
"""

import os
import sys
import shutil
from pathlib import Path

# Ensure UTF-8 output on Windows console if possible
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SOURCE_ROOT = Path("C:/Work/P/app/tradingapp-main/tradingapp-main")
DEST_ROOT = Path("C:/Work/P/app/ai-quant-watchlist-service")

print("==================================================")
print(f"[START] BUILDING STANDALONE SERVICE AT: {DEST_ROOT}")
print("==================================================")

DEST_ROOT.mkdir(parents=True, exist_ok=True)

# 1. Copy essential folders completely so there are ZERO missing import errors!
FOLDERS_TO_COPY = ["data", "database", "services", "utils", "core", "config"]

for folder in FOLDERS_TO_COPY:
    src_dir = SOURCE_ROOT / folder
    dest_dir = DEST_ROOT / folder
    if src_dir.exists():
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)
        print(f"[SUCCESS] Copied folder: {folder}/")
    else:
        print(f"[WARN] Folder not found: {folder}")

# 2. PRUNE UNNECESSARY THINGS (Trade Execution, Backtesting, UI WebSockets, Strategies)
UNNECESSARY_DIRS = [
    "trading_execution", "auto_trading", "backtester", "backtesting", 
    "strategies", "strategies_registry", "angel", "websocket", "hft", "sse"
]

for u_dir in UNNECESSARY_DIRS:
    p = DEST_ROOT / "services" / u_dir
    if p.exists():
        shutil.rmtree(p)
        print(f"[CLEANUP] Removed unnecessary folder: services/{u_dir}")

# Remove unnecessary trade execution and UI files in services/
for file_path in (DEST_ROOT / "services").glob("*.py"):
    name = file_path.name
    if name.startswith("trade_") or name.startswith("paper_") or "supertrend" in name or "socketio_" in name:
        try:
            file_path.unlink()
            print(f"[CLEANUP] Removed unnecessary file: services/{name}")
        except Exception:
            pass

# 3. Copy environment files
for env_file in [".env", ".env.production", ".env.template"]:
    src_env = SOURCE_ROOT / env_file
    if src_env.exists():
        shutil.copy2(src_env, DEST_ROOT / env_file)
        print(f"[SUCCESS] Copied config file: {env_file}")

# 4. Create clean requirements.txt (No external scheduler needed; uses native asyncio!)
requirements_content = """playwright>=1.40.0
pyotp>=2.9.0
requests>=2.31.0
httpx>=0.25.0
sqlalchemy>=2.0.0
pandas>=2.1.0
numpy>=1.26.0
websockets>=12.0
pytz>=2023.3
python-dotenv>=1.0.0
psycopg2-binary>=2.9.0
"""

with open(DEST_ROOT / "requirements.txt", "w", encoding="utf-8") as f:
    f.write(requirements_content)
print("[SUCCESS] Created lightweight requirements.txt (pure asyncio)")

# 5. Create clean README.md
readme_content = """# AI Quant Watchlist Service (Standalone & Pruned)

This is a completely standalone, lightweight Algotrading Screener service.
It connects to Upstox, calculates real-time Advance/Decline market sentiment, selects Grade A+ F&O momentum stocks, and broadcasts them to a VIP Telegram Channel.
All unnecessary trade execution, backtesting, and UI socket engines have been removed!

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Configure your Telegram Channel ID in `main.py` (line 28).
3. Run the service:
   ```bash
   python main.py
   ```

## Schedule (Pure Asyncio Loop)
- **08:30 AM IST:** Automated Upstox Login via Playwright & Token Generation.
- **09:05 AM IST:** Quantitative Stock Selection & VIP Telegram Broadcast.
"""

with open(DEST_ROOT / "README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)
print("[SUCCESS] Created README.md")

# 6. Create clean main.py (Pure Asyncio Master Entry Point!)
main_py_content = """# C:/Work/P/app/ai-quant-watchlist-service/main.py
\"\"\"
STANDALONE AI QUANT WATCHLIST SERVICE (PRODUCTION READY & PRUNED)
This is an independent, lightweight entry point for your subscriber F&O Watchlist.
It DOES NOT start trade execution engines, order managers, or web routers.
It ONLY handles: 08:30 AM Upstox Login -> 09:05 AM Stock Selection -> Telegram VIP Broadcast.
Uses native Python asyncio loop (Zero external scheduler dependencies).
\"\"\"

import asyncio
import logging
from datetime import datetime, time as dt_time, timedelta
import pytz
import requests

# Import ONLY the selection, auth, and database modules
from services.upstox_automation_service import UpstoxAutomationService
from services.intelligent_stock_selection_service import intelligent_stock_selection_service
from database.connection import SessionLocal
from database.models import SelectedStock
from core.config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("Standalone-Watchlist-Bot")

# IMPORTANT: Paste your new Telegram VIP Channel ID here!
VIP_CHANNEL_ID = "-100987654321"


async def async_morning_login_job():
    \"\"\"8:30 AM: Automatically login to Upstox and refresh access token\"\"\"
    logger.info("08:30 AM IST: Running Upstox Auto-Login via Playwright...")
    try:
        auth_service = UpstoxAutomationService()
        result = await auth_service.refresh_admin_upstox_token()
        if result and result.get("success"):
            logger.info("Access Token generated and refreshed successfully!")
        else:
            logger.warning(f"Token refresh returned status: {result}")
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)


async def async_run_selection_and_broadcast():
    \"\"\"9:05 AM: Run selection engine and broadcast to Telegram VIP Channel\"\"\"
    logger.info("09:05 AM IST: Running Intelligent Stock Selection Engine...")
    try:
        # 1. Run selection engine (calculates sentiment & grades A+ stocks)
        await intelligent_stock_selection_service.run_premarket_selection()
        logger.info("Stock selection completed and saved to database!")
        
        # 2. Fetch today's A+ picks from database
        db = SessionLocal()
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        
        picks = db.query(SelectedStock).filter(
            SelectedStock.selection_date == today
        ).order_by(SelectedStock.selection_score.desc()).limit(5).all()
        
        db.close()
        
        if not picks:
            logger.warning("No stocks selected today.")
            return
            
        # 3. Format neat, professional HTML message for subscribers
        msg = f"<b>TODAY'S AI QUANTITATIVE WATCHLIST</b>\\n"
        msg += f"<i>Date: {today.strftime('%d-%b-%Y')} | 09:05 AM IST</i>\\n\\n"
        
        if picks[0].market_sentiment:
            sentiment_icon = "🟢" if "bullish" in str(picks[0].market_sentiment).lower() else "🔴" if "bearish" in str(picks[0].market_sentiment).lower() else "⚪"
            msg += f"<b>MARKET BREADTH & SENTIMENT:</b>\\n"
            msg += f"• Overall Sentiment: {sentiment_icon} <b>{str(picks[0].market_sentiment).upper().replace('_', ' ')}</b>\\n"
            if picks[0].advance_decline_ratio:
                msg += f"• Advance/Decline Ratio: <b>{picks[0].advance_decline_ratio:.2f}</b>\\n"
            msg += "\\n━━━━━━━━━━━━━━━━━━━━━\\n\\n"
            
        msg += "<b>HIGH-PROBABILITY QUANT SELECTIONS:</b>\\n\\n"
        
        for idx, p in enumerate(picks, 1):
            opt_type = str(p.option_type or "NEUTRAL").upper()
            direction_icon = "🟢" if opt_type == "CE" else "🔴" if opt_type == "PE" else "⚪"
            
            msg += f"<b>{idx}. {p.symbol}</b> (Score: {p.selection_score:.1f}%)\\n"
            msg += f"• Direction Focus: {direction_icon} <b>{opt_type}</b>\\n"
            msg += f"• Sector: <i>{p.sector or 'OTHER'}</i>\\n"
            if p.selection_reason:
                msg += f"<i>{p.selection_reason}</i>\\n"
            msg += "\\n"
            
        msg += "━━━━━━━━━━━━━━━━━━━━━\\n"
        msg += "<i><b>Mandatory SEBI Disclaimer:</b> We are NOT SEBI Registered Research Analysts. This watchlist is generated automatically by quantitative algorithms for educational & technical analysis only. No buy/sell tips provided.</i>"
        
        # 4. Broadcast cleanly to Telegram VIP Channel
        logger.info(f"Broadcasting Watchlist to Paid Telegram Subscribers (Chat ID: {VIP_CHANNEL_ID})...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        res = requests.post(url, json={
            "chat_id": VIP_CHANNEL_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })
        
        if res.status_code == 200:
            logger.info("Daily Watchlist broadcasted successfully to VIP subscribers!")
        else:
            logger.error(f"Telegram broadcast failed: {res.status_code} - {res.text}")
            
    except Exception as e:
        logger.error(f"Selection/Broadcast workflow failed: {e}", exc_info=True)


async def scheduler_loop():
    \"\"\"Native asyncio daily loop for 08:30 AM login and 09:05 AM selection\"\"\"
    ist = pytz.timezone("Asia/Kolkata")
    logger.info("📅 Native Asyncio Scheduler Loop Started (IST Timezone)")
    
    while True:
        now = datetime.now(ist)
        # Calculate seconds until next 08:30 AM
        target_login = now.replace(hour=8, minute=30, second=0, microsecond=0)
        if now >= target_login:
            target_login += timedelta(days=1)
            
        # Calculate seconds until next 09:05 AM
        target_select = now.replace(hour=9, minute=5, second=0, microsecond=0)
        if now >= target_select:
            target_select += timedelta(days=1)
            
        # Check if we are currently within the execution window (within 30 seconds of target time)
        if now.hour == 8 and now.minute == 30 and now.second < 30:
            await async_morning_login_job()
            await asyncio.sleep(60) # Sleep 60s to avoid double execution
        elif now.hour == 9 and now.minute == 5 and now.second < 30:
            await async_run_selection_and_broadcast()
            await asyncio.sleep(60)
        else:
            # Sleep for 15 seconds before checking time again
            await asyncio.sleep(15)


if __name__ == "__main__":
    logger.info("==================================================")
    logger.info("STANDALONE AI QUANT WATCHLIST SERVICE STARTED")
    logger.info("Trade Execution Engine is OFF (Zero Real-Money Risk)")
    logger.info("Scheduled Tasks: [08:30 AM Login] -> [09:05 AM VIP Broadcast]")
    logger.info("==================================================")
    
    # Optional: To test immediate broadcast on startup, uncomment below:
    # asyncio.run(async_run_selection_and_broadcast())
    
    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
"""

with open(DEST_ROOT / "main.py", "w", encoding="utf-8") as f:
    f.write(main_py_content)
print("[SUCCESS] Created standalone main.py (pure asyncio)")

print("\n[SUCCESS] COMPLETE STANDALONE PROJECT READY AT:")
print(f"-> {DEST_ROOT}")
print("==================================================")
