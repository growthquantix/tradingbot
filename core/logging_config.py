"""
Comprehensive Logging Configuration for Trading System

This module provides enterprise-grade logging with:
- Structured JSON logging
- Correlation IDs for request tracking
- Audit trails for financial operations
- Performance monitoring
- Security logging
- Different log levels for different environments
"""

import asyncio
import logging
import logging.config
import os
import sys
import json
import uuid
import time
import threading
import psutil
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, List, Union
from pathlib import Path
import contextvars
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum

# Context variables for distributed tracing
correlation_id_context: contextvars.ContextVar = contextvars.ContextVar(
    "correlation_id", default=None
)
trace_id_context: contextvars.ContextVar = contextvars.ContextVar(
    "trace_id", default=None
)
span_id_context: contextvars.ContextVar = contextvars.ContextVar(
    "span_id", default=None
)
user_id_context: contextvars.ContextVar = contextvars.ContextVar(
    "user_id", default=None
)
session_id_context: contextvars.ContextVar = contextvars.ContextVar(
    "session_id", default=None
)


class LogLevel(Enum):
    """Enhanced log levels with severity mapping."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class LogCategory(Enum):
    """Log categories for better organization."""
    BUSINESS = "BUSINESS"
    TECHNICAL = "TECHNICAL"
    SECURITY = "SECURITY"
    AUDIT = "AUDIT"
    PERFORMANCE = "PERFORMANCE"
    INTEGRATION = "INTEGRATION"
    USER_ACTIVITY = "USER_ACTIVITY"


@dataclass
class LogContext:
    """Structured log context for consistent logging."""
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    category: Optional[LogCategory] = None
    business_context: Optional[Dict[str, Any]] = None
    technical_context: Optional[Dict[str, Any]] = None
    performance_context: Optional[Dict[str, Any]] = None
    security_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, Enum):
                    result[key] = value.value
                else:
                    result[key] = value
        return result


# Import enhanced formatters
from core.formatters import (
    TradingConsoleFormatter,
    TradingJSONFormatter,
    AuditFormatter,
    PerformanceFormatter,
    get_formatter,
)


class SecurityFilter(logging.Filter):
    """Filter to remove sensitive information from logs."""

    SENSITIVE_FIELDS = {
        "password",
        "token",
        "secret",
        "key",
        "authorization",
        "api_key",
        "access_token",
        "refresh_token",
        "pin",
        "otp",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out sensitive information from log records."""
        message = record.getMessage().lower()

        # Check if message contains sensitive information
        for sensitive_field in self.SENSITIVE_FIELDS:
            if sensitive_field in message:
                # Mask the sensitive information
                record.msg = record.msg.replace(
                    str(getattr(record, "args", []))[1:-1] if record.args else "",
                    "***MASKED***",
                )
                break

        return True


class TradingLoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for trading operations."""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add trading-specific context to log messages."""
        # Add correlation ID to extra if not present
        extra = kwargs.get("extra", {})

        correlation_id = correlation_id_context.get()
        if correlation_id and "correlation_id" not in extra:
            extra["correlation_id"] = correlation_id

        # Add context information
        if self.extra:
            extra.update(self.extra)

        kwargs["extra"] = extra
        return msg, kwargs


def get_logging_config(environment: str = "development") -> Dict[str, Any]:
    """
    Get logging configuration based on environment.

    Args:
        environment: Environment name (development, staging, production)

    Returns:
        Logging configuration dictionary
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    base_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {"()": TradingConsoleFormatter, "use_colors": True},
            "console_plain": {"()": TradingConsoleFormatter, "use_colors": False},
            "json": {
                "()": TradingJSONFormatter,
            },
            "audit": {
                "()": AuditFormatter,
            },
            "performance": {
                "()": PerformanceFormatter,
            },
            "compact": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "filters": {
            "security": {
                "()": SecurityFilter,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
                "filters": ["security"],
                "stream": sys.stdout,
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filters": ["security"],
                "filename": str(log_dir / "trading_app.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "audit_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "audit",
                "filename": str(log_dir / "audit.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filters": ["security"],
                "filename": str(log_dir / "errors.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
                "level": "ERROR",
            },
            "performance_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "performance",
                "filename": str(log_dir / "performance.log"),
                "maxBytes": 20 * 1024 * 1024,  # 20MB
                "backupCount": 7,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # Main application logger
            "trading_app": {
                "handlers": ["console", "app_file", "error_file"],
                "level": "INFO",
                "propagate": False,
            },
            # Audit logger for financial operations
            "audit": {"handlers": ["audit_file"], "level": "INFO", "propagate": False},
            # Performance logger
            "performance": {
                "handlers": ["performance_file"],
                "level": "INFO",
                "propagate": False,
            },
            # WebSocket logger
            "websocket": {
                "handlers": ["console", "app_file"],
                "level": "INFO",
                "propagate": False,
            },
            # Database logger
            "database": {
                "handlers": ["console", "app_file"],
                "level": "WARNING",
                "propagate": False,
            },
            # Broker integration logger
            "broker": {
                "handlers": ["console", "app_file"],
                "level": "INFO",
                "propagate": False,
            },
            # Security logger
            "security": {
                "handlers": ["console", "app_file", "audit_file"],
                "level": "INFO",
                "propagate": False,
            },
            # Third-party libraries
            "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "sqlalchemy": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
            "aiohttp": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
        },
        "root": {"handlers": ["console", "app_file"], "level": "INFO"},
    }

    # Environment-specific configurations
    if environment == "development":
        base_config["loggers"]["trading_app"]["level"] = "DEBUG"
        base_config["loggers"]["websocket"]["level"] = "DEBUG"
        base_config["loggers"]["broker"]["level"] = "DEBUG"
        base_config["root"]["level"] = "DEBUG"
    elif environment == "production":
        # Use plain console formatter in production (no colors)
        base_config["handlers"]["console"]["formatter"] = "console_plain"
        # Reduce log levels in production
        base_config["loggers"]["trading_app"]["level"] = "INFO"
        base_config["loggers"]["websocket"]["level"] = "WARNING"
        base_config["loggers"]["broker"]["level"] = "INFO"
    elif environment == "testing":
        # Compact format for testing
        base_config["handlers"]["console"]["formatter"] = "compact"
        base_config["loggers"]["trading_app"]["level"] = "WARNING"

    return base_config


def setup_logging(environment: str = None) -> None:
    """
    Setup logging configuration for the trading application.

    Args:
        environment: Environment name, defaults to value from ENVIRONMENT env var
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    config = get_logging_config(environment)
    logging.config.dictConfig(config)

    # Log startup message
    logger = logging.getLogger("trading_app")
    logger.info(f"Logging system initialized for {environment} environment")


def get_logger(name: str, **context) -> TradingLoggerAdapter:
    """
    Get a logger with trading context.

    Args:
        name: Logger name
        **context: Additional context to include in all log messages

    Returns:
        TradingLoggerAdapter instance
    """
    base_logger = logging.getLogger(name)
    return TradingLoggerAdapter(base_logger, context)


def set_correlation_id(correlation_id: str = None) -> str:
    """
    Set correlation ID for current context.

    Args:
        correlation_id: Correlation ID, generates one if not provided

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    correlation_id_context.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context."""
    return correlation_id_context.get()


def with_correlation_id(func):
    """Decorator to automatically set correlation ID for functions."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not get_correlation_id():
            set_correlation_id()
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not get_correlation_id():
            set_correlation_id()
        return func(*args, **kwargs)

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


# Specialized loggers for different components
def get_audit_logger() -> logging.Logger:
    """Get audit logger for financial operations."""
    return logging.getLogger("audit")


def get_performance_logger() -> logging.Logger:
    """Get performance logger."""
    return logging.getLogger("performance")


def get_security_logger() -> logging.Logger:
    """Get security logger."""
    return logging.getLogger("security")


def get_websocket_logger(**context) -> TradingLoggerAdapter:
    """Get WebSocket logger with context."""
    return get_logger("websocket", **context)


def get_broker_logger(broker: str, **context) -> TradingLoggerAdapter:
    """Get broker-specific logger."""
    return get_logger("broker", broker=broker, **context)


def get_database_logger(**context) -> TradingLoggerAdapter:
    """Get database logger with context."""
    return get_logger("database", **context)
