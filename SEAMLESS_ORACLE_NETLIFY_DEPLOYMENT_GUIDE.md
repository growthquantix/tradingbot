# 🚀 Seamless Oracle Cloud & Netlify Deployment Guide
**Complete Architecture, Configuration Reference & One-Click Deployment for Trading Bot (`tradingapp-main`) and Quant Watchlist Service (`ai-quant-watchlist-service`)**

---

## 🏛️ 1. Architecture Overview (No Custom Domain Required!)
If your custom domain (`growthquantix.com`) expired, **you do NOT need to buy another domain**. Your full enterprise quantitative trading architecture runs seamlessly using your **Oracle Cloud Static Public IP** and **Netlify Subdomain**:

```
+-----------------------------------------------------------------------------------+
|                                 USER BROWSER                                      |
|  Opens Netlify UI: https://resplendent-shortbread-e830d3.netlify.app             |
+-----------------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            | (HTTP REST API / WebSocket via REACT_APP_API_URL)
            v
+-----------------------------------------------------------------------------------+
|                   ORACLE CLOUD ALWAYS FREE TIER (ARM 24GB RAM)                    |
|                         Static Public IP: http://x.x.x.x                          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |  Docker Container: tradingapp-main Backend (FastAPI + Socket.IO: Port 8000) |  |
|  |  - CORS dynamically allows your Netlify URL via CORS_ORIGINS                |  |
|  |  - Headless Playwright Chromium handles Upstox Auto-Login internally        |  |
|  +-----------------------------------------------------------------------------+  |
|                                    |                                              |
|            +-----------------------+-----------------------+                      |
|            v                                               v                      |
|  +---------------------------+                   +-----------------------------+  |
|  | Docker: postgres:13-alpine|                   | Docker: redis:6-alpine      |  |
|  | (Trading DB + Watchlist)  |                   | (In-Memory Tick Cache)      |  |
|  +---------------------------+                   +-----------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## ☁️ 2. Step 1: Oracle Cloud Free Tier VPS Setup
1. **Create Instance**: Log in to [Oracle Cloud Console](https://cloud.oracle.com) $\rightarrow$ **Compute** $\rightarrow$ **Instances** $\rightarrow$ **Create Instance**.
2. **Select Image & Shape**:
   - **Image**: `Ubuntu 22.04 LTS` or `Oracle Linux 9`
   - **Shape**: `VM.Standard.A1.Flex` (ARM Ampere: Select **4 OCPUs** and **24 GB RAM** — 100% Always Free).
3. **Open Security Network / Firewall (Port 8000)**:
   - In Oracle Cloud Console $\rightarrow$ **Subnet** $\rightarrow$ **Default Security List**:
     - Add Ingress Rule: **0.0.0.0/0**, Protocol: **TCP**, Destination Port Range: **8000**, Description: `FastAPI Trading Backend`
   - Once inside your VPS terminal (via SSH), open the OS firewall:
     ```bash
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
     sudo netfilter-persistent save
     # (Or if using UFW on Ubuntu: sudo ufw allow 8000/tcp)
     ```

---

## ⚙️ 3. Step 2: Backend Configuration (`.env.production`)
Inside `/Work/P/app/tradingapp-main/tradingapp-main`, create or edit `.env.production`. Below is the **exact, verified production configuration reference**:

```env
# ==============================================================================
# 🌟 TRADINGAPP-MAIN PRODUCTION CONFIGURATION (.env.production)
# ==============================================================================

# 1. Environment & Server
ENVIRONMENT=production
APP_NAME=TradingBot
DEBUG=false
LOG_LEVEL=INFO
PORT=8000
TZ=Asia/Kolkata

# 2. CORS & Allowed Hosts (Allows Netlify & Localhost seamlessly)
# Replace x.x.x.x with your actual Oracle Cloud Static Public IP
ALLOWED_HOSTS=localhost,127.0.0.1,x.x.x.x
CORS_ORIGINS=https://resplendent-shortbread-e830d3.netlify.app,http://x.x.x.x:8000

# 3. Database & Cache (Matches docker-compose.prod.yml exact credentials)
DATABASE_URL=postgresql://trading_user:trading_password@db:5432/trading_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379

# 4. Security Secrets (Generate random 32-char strings)
JWT_SECRET_KEY=Replace_With_Your_Secure_Random_JWT_Secret_32Chars
SECRET_KEY=Replace_With_Your_Secure_Random_App_Secret_32Chars

# 5. Upstox API & Playwright Headless Automation
UPSTOX_API_KEY=your_upstox_api_key_here
UPSTOX_API_SECRET=your_upstox_api_secret_here
# Redirect URI: Put your exact Oracle IP in Upstox Developer Console
UPSTOX_REDIRECT_URI=http://x.x.x.x:8000/api/broker/upstox/callback
UPSTOX_MOBILE=your_10_digit_upstox_mobile_number
UPSTOX_PIN=your_6_digit_upstox_pin
# TOTP Secret: 32-character base32 secret from Upstox 2FA QR code setup
UPSTOX_TOTP_SECRET=your_32_character_totp_secret_from_upstox

# 6. Telegram Watchlist & Alerts Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
VIP_CHANNEL_ID=834049680
FREE_CHANNEL_ID=
TELEGRAM_CHAT_ID=834049680

# 7. Risk Management Safeguards
MAX_POSITION_SIZE=100000
MAX_DAILY_LOSS=50000
```

---

## 🔨 4. Step 3: One-Click Backend Deployment on Oracle Cloud
We have provided an automated deployment script [`setup_oracle_cloud.sh`](file:///C:/Work/P/app/tradingapp-main/tradingapp-main/setup_oracle_cloud.sh) that installs Docker, checks configuration, launches PostgreSQL/Redis/FastAPI, and applies Alembic migrations automatically.

Run this single command on your Oracle VPS terminal:
```bash
cd /Work/P/app/tradingapp-main/tradingapp-main
bash setup_oracle_cloud.sh
```

### Verification & Useful Docker Commands:
* **Check Running Containers**:
  ```bash
  sudo docker compose -f docker-compose.prod.yml ps
  ```
* **View Live Backend / Playwright Auto-Login Logs**:
  ```bash
  sudo docker compose -f docker-compose.prod.yml logs -f backend
  ```
* **Verify Health Check Endpoint**:
  ```bash
  curl http://localhost:8000/health
  # Expected response: {"status":"healthy",...}
  ```

---

## 🌐 5. Step 4: Netlify Frontend Configuration & Deployment
Your React frontend (`ui/trading-bot-ui`) is deployed automatically on Netlify via `netlify.toml`.

### 1. Configure Environment Variables in Netlify
Log inside [Netlify Dashboard](https://app.netlify.com) $\rightarrow$ Select your Site (`resplendent-shortbread-e830d3`) $\rightarrow$ **Site Configuration** $\rightarrow$ **Environment Variables**:

| Variable Name | Exact Value to Enter |
| :--- | :--- |
| `REACT_APP_API_URL` | `http://YOUR_ORACLE_PUBLIC_IP:8000` *(e.g. `http://144.24.120.85:8000`)* |
| `REACT_APP_WS_URL` | `ws://YOUR_ORACLE_PUBLIC_IP:8000` *(e.g. `ws://144.24.120.85:8000`)* |
| `REACT_APP_ENV` | `production` |
| `REACT_APP_WEBSOCKET_BASE_URL` | `ws://YOUR_ORACLE_PUBLIC_IP:8000` |

### 2. Trigger Frontend Build
After saving the variables, go to **Deploys** $\rightarrow$ **Trigger Deploy** $\rightarrow$ **Deploy Site**.
When finished, open your Netlify URL and your frontend will instantly connect and display live data from your Oracle Cloud backend!

---

## 🔐 6. Step 5: Upstox API Callback & Headless Auto-Login
Because of how Playwright is configured in `services/upstox_automation_service.py`:
1. **Upstox Developer Console Setting**:
   Go to [Upstox Developer Portal](https://developer.upstox.com) $\rightarrow$ **My Apps** $\rightarrow$ **Redirect URI**.
   Set the Redirect URI to your exact Oracle Public IP:
   👉 `http://YOUR_ORACLE_PUBLIC_IP:8000/api/broker/upstox/callback`
2. **How Token Exchange Works Automatically Every Morning (`08:30 AM IST`)**:
   - Playwright opens headless Chromium inside the Oracle container and logs into Upstox using your `UPSTOX_MOBILE`, `UPSTOX_PIN`, and `UPSTOX_TOTP_SECRET`.
   - When Upstox redirects the page to `http://YOUR_ORACLE_PUBLIC_IP:8000/api/broker/upstox/callback?code=XXXXX...`, **Playwright intercepts the URL bar directly inside the container before any network packet leaves**.
   - It captures `code=XXXXX` and exchanges it for your daily Upstox Access Token immediately, saving it to PostgreSQL (`BrokerConfig`). **Zero manual login needed!**

---

## 💡 7. Quick Troubleshooting Reference
| Issue / Symptom | Likely Cause | Exact Solution / Command |
| :--- | :--- | :--- |
| **CORS Error in Browser Console** | Netlify URL not in `CORS_ORIGINS` | Add your exact `https://...netlify.app` URL to `CORS_ORIGINS` inside `.env.production` and restart `docker compose restart backend`. |
| **Frontend shows "Cannot connect to server"** | Port 8000 blocked by Oracle Firewall | Run `sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT` on your Oracle VPS. |
| **Upstox Auto-Login stuck or failed** | Incorrect `UPSTOX_TOTP_SECRET` or `PIN` | Check real-time login logs: `sudo docker compose -f docker-compose.prod.yml logs -f backend \| grep -i upstox` |
| **Alembic Table Missing Error** | Database migrations didn't finish | Run manually inside container: `sudo docker compose -f docker-compose.prod.yml exec backend alembic upgrade head` |
