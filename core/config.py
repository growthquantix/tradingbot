import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Secret Keys for JWT Tokens
JWT_SECRET = os.getenv("JWT_SECRET", "your-access-secret-key")
REFRESH_SECRET = os.getenv("REFRESH_SECRET", JWT_SECRET)

# Token Expiry Settings
ACCESS_TOKEN_EXPIRE_MINUTES = 36000  # 10 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7

TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"  # User ID or Group ID

# TODO - Add more config variables here
# ✅ 1. Set Up Telegram Bot
# Go to Telegram and search for @BotFather.
# Type /newbot and follow the instructions.
# Copy the bot token and store it in config.py.


# ✅ 2. Get Chat ID
# Search for your bot on Telegram and send a message.

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


# ZeptoMail Configuration
ZEPTOMAIL_HOST = os.getenv("ZEPTOMAIL_HOST", "smtp.zeptomail.in")
ZEPTOMAIL_PORT = int(os.getenv("ZEPTOMAIL_PORT", "587"))
ZEPTOMAIL_USERNAME = os.getenv("ZEPTOMAIL_USERNAME", "emailapikey")
ZEPTOMAIL_PASSWORD = os.getenv("ZEPTOMAIL_PASSWORD", "")
ZEPTOMAIL_FROM_EMAIL = os.getenv("ZEPTOMAIL_FROM_EMAIL", "noreply@growthquantix.com")


# Legacy Email Configuration (for backward compatibility)
EMAIL_HOST = ZEPTOMAIL_HOST
EMAIL_PORT = ZEPTOMAIL_PORT
EMAIL_USERNAME = ZEPTOMAIL_USERNAME
EMAIL_PASSWORD = ZEPTOMAIL_PASSWORD

TWILIO_ACCOUNT_SID = "your-twilio-sid"
TWILIO_AUTH_TOKEN = "your-twilio-auth-token"
TWILIO_PHONE_NUMBER = "+123456789"


# Upstox API Configuration

# Security: Use environment variables instead of hardcoded values
API_KEY = os.getenv("UPSTOX_API_KEY", "REPLACE_WITH_ACTUAL_API_KEY")
API_SECRET = os.getenv("UPSTOX_API_SECRET", "REPLACE_WITH_ACTUAL_API_SECRET")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "REPLACE_WITH_ACTUAL_REDIRECT_URI")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN", "GENERATE_VIA_AUTH_FLOW")
WS_URL = "wss://api.upstox.com/live/market-data"  # Upstox WebSocket URL

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
