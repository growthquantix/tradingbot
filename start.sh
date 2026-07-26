#!/bin/bash

set -e

# Ensure Playwright knows where to look for browsers in Docker
export PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

PORT=${PORT:-8000}

echo "Running Alembic database migrations..."
alembic upgrade head

echo "Starting FastAPI server on port $PORT..."
exec uvicorn app:sio_app --host 0.0.0.0 --port $PORT --workers 1 --log-level warning
