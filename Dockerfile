FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV TZ=Asia/Kolkata
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libpq5 \
    curl \
    tzdata && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies directly using pre-compiled binary wheels (CPU PyTorch)
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Install Playwright browsers and their system dependencies
# CRITICAL: Install to a shared location and fix permissions for non-root user
RUN mkdir -p /ms-playwright && \
    python -m playwright install chromium && \
    python -m playwright install-deps chromium && \
    chmod -R 777 /ms-playwright

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Make start script executable
RUN chmod +x start.sh

# Command to run the application using the start script
CMD ["./start.sh"]
