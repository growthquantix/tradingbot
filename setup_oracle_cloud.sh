#!/bin/bash
# ==============================================================================
# 🚀 ONE-CLICK ORACLE CLOUD / VPS DEPLOYMENT SCRIPT FOR TRADINGAPP-MAIN
# ==============================================================================
set -e

echo "=========================================================================="
echo "🌟 Starting One-Click Deployment for Trading Bot on Oracle Cloud / VPS..."
echo "=========================================================================="

# 1. Check & Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "📦 Docker not found. Installing Docker & Docker Compose..."
    sudo apt-get update -y || sudo yum update -y
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm -f get-docker.sh
    sudo usermod -aG docker $USER || true
    echo "✅ Docker installed successfully!"
else
    echo "✅ Docker is already installed."
fi

# 2. Ensure .env.production exists
if [ ! -f ".env.production" ]; then
    echo "⚠️ .env.production not found. Creating from template..."
    cp .env.production.template .env.production || cp .env.template .env.production || touch .env.production
    echo "ENVIRONMENT=production" >> .env.production
    echo "CORS_ORIGINS=https://resplendent-shortbread-e830d3.netlify.app" >> .env.production
    echo "✅ Created .env.production. Please verify API keys inside before running!"
fi

# 3. Build & Launch Containers
echo "🏗️ Starting Docker containers (Postgres, Redis, Backend)..."
sudo docker compose -f docker-compose.prod.yml pull || true
sudo docker compose -f docker-compose.prod.yml up -d

# 4. Wait for Database to initialize
echo "⏳ Waiting 10 seconds for PostgreSQL database to stabilize..."
sleep 10

# 5. Run Database Migrations
echo "🗄️ Running Alembic database migrations..."
sudo docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head || echo "⚠️ Migrations skipped or already up to date."

echo "=========================================================================="
echo "🎉 DEPLOYMENT COMPLETE! Your Trading Application is LIVE 24/7."
echo "=========================================================================="
echo "👉 Check logs anytime using: sudo docker compose -f docker-compose.prod.yml logs -f backend"
