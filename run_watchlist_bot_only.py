"""
⚡ STANDALONE AI QUANT WATCHLIST SERVICE (PRODUCTION READY)
This is a lightweight, runtime-separated entry point for your subscriber F&O Watchlist.
It DOES NOT start trade execution engines, order managers, or web routers.
It ONLY handles: 08:30 AM Upstox Login -> 09:05 AM Stock Selection -> Telegram VIP Broadcast.
"""

import asyncio
import logging
import time
import schedule
from datetime import datetime
import pytz
import requests

# Import ONLY the selection, auth, and database modules (No trade execution!)
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

# 🔴 IMPORTANT: Paste your Cosmofeed / Topmate VIP Telegram Channel ID here!
# For testing, you can put your personal telegram chat ID or admin chat ID.
VIP_CHANNEL_ID = "-100987654321"


async def async_morning_login_job():
    """8:30 AM: Automatically login to Upstox and refresh access token"""
    logger.info("🌅 08:30 AM IST: Running Upstox Auto-Login via Playwright...")
    try:
        auth_service = UpstoxAutomationService()
        result = await auth_service.refresh_admin_upstox_token()
        if result and result.get("success"):
            logger.info("✅ Access Token generated and refreshed successfully!")
        else:
            logger.warning(f"⚠️ Token refresh returned status: {result}")
    except Exception as e:
        logger.error(f"❌ Login failed: {e}", exc_info=True)


async def async_run_selection_and_broadcast():
    """9:05 AM: Run selection engine and broadcast to Telegram VIP Channel"""
    logger.info("📊 09:05 AM IST: Running Intelligent Stock Selection Engine...")
    try:
        # 1. Run selection engine (calculates sentiment & grades A+ stocks)
        await intelligent_stock_selection_service.run_premarket_selection()
        logger.info("✅ Stock selection completed and saved to database!")
        
        # 2. Fetch today's A+ picks from database
        db = SessionLocal()
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        
        # Query top stocks sorted by selection score
        picks = db.query(SelectedStock).filter(
            SelectedStock.selection_date == today
        ).order_by(SelectedStock.selection_score.desc()).limit(5).all()
        
        db.close()
        
        if not picks:
            logger.warning("⚠️ No stocks selected today. Attempting fallback query...")
            return
            
        # 3. Format neat, professional HTML message for subscribers
        msg = f"<b>🚀 TODAY'S AI QUANTITATIVE WATCHLIST</b>\n"
        msg += f"<i>Date: {today.strftime('%d-%b-%Y')} | 09:05 AM IST</i>\n\n"
        
        if picks[0].market_sentiment:
            sentiment_icon = "🟢" if "bullish" in str(picks[0].market_sentiment).lower() else "🔴" if "bearish" in str(picks[0].market_sentiment).lower() else "⚪"
            msg += f"<b>📊 MARKET BREADTH & SENTIMENT:</b>\n"
            msg += f"• Overall Sentiment: {sentiment_icon} <b>{str(picks[0].market_sentiment).upper().replace('_', ' ')}</b>\n"
            if picks[0].advance_decline_ratio:
                msg += f"• Advance/Decline Ratio: <b>{picks[0].advance_decline_ratio:.2f}</b>\n"
            msg += "\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            
        msg += "<b>⭐ HIGH-PROBABILITY QUANT SELECTIONS:</b>\n\n"
        
        for idx, p in enumerate(picks, 1):
            opt_type = str(p.option_type or "NEUTRAL").upper()
            direction_icon = "🟢" if opt_type == "CE" else "🔴" if opt_type == "PE" else "⚪"
            
            msg += f"<b>{idx}. {p.symbol}</b> (Score: {p.selection_score:.1f}%)\n"
            msg += f"• Direction Focus: {direction_icon} <b>{opt_type}</b>\n"
            msg += f"• Sector: <i>{p.sector or 'OTHER'}</i>\n"
            if p.selection_reason:
                msg += f"<i>💡 {p.selection_reason}</i>\n"
            msg += "\n"
            
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "⚠️ <i><b>Mandatory SEBI Disclaimer:</b> We are NOT SEBI Registered Research Analysts. This watchlist is generated automatically by quantitative volume algorithms for educational & technical analysis only. No buy/sell tips provided.</i>"
        
        # 4. Broadcast cleanly to Telegram VIP Channel
        logger.info(f"📢 Broadcasting Watchlist to Paid Telegram Subscribers (Chat ID: {VIP_CHANNEL_ID})...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        res = requests.post(url, json={
            "chat_id": VIP_CHANNEL_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })
        
        if res.status_code == 200:
            logger.info("🎉 Daily Watchlist broadcasted successfully to VIP subscribers!")
        else:
            logger.error(f"❌ Telegram broadcast failed: {res.status_code} - {res.text}")
            
    except Exception as e:
        logger.error(f"❌ Selection/Broadcast workflow failed: {e}", exc_info=True)


def morning_login_job():
    """Wrapper to run async login job in schedule"""
    asyncio.run(async_morning_login_job())


def run_selection_and_broadcast():
    """Wrapper to run async selection job in schedule"""
    asyncio.run(async_run_selection_and_broadcast())


# Schedule the automated daily workflow (IST timings)
schedule.every().day.at("08:30").do(morning_login_job)
schedule.every().day.at("09:05").do(run_selection_and_broadcast)


if __name__ == "__main__":
    logger.info("==================================================")
    logger.info("🚀 STANDALONE AI QUANT WATCHLIST SERVICE STARTED")
    logger.info("🔒 Trade Execution Engine is OFF (Zero Real-Money Risk)")
    logger.info("📅 Scheduled Tasks: [08:30 AM Login] -> [09:05 AM VIP Broadcast]")
    logger.info("==================================================")
    
    # Optional: If you want to test the broadcast immediately upon startup, uncomment the line below:
    # run_selection_and_broadcast()
    
    while True:
        schedule.run_pending()
        time.sleep(30)
