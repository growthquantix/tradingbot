"""
Fixed Logging Configuration with Improved Security Filtering

This configuration uses the improved security filter that doesn't interfere
with legitimate trading data while still protecting sensitive information.
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
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, List, Union
from pathlib import Path
import contextvars
from functools import wraps

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

# Import formatters
from core.formatters import (
    TradingConsoleFormatter,
    TradingJSONFormatter,
    AuditFormatter,
    PerformanceFormatter
)

# Import improved security filter
from core.improved_security_filter import TradingSafeSecurityFilter


class EnhancedTradingLoggerAdapter(logging.LoggerAdapter):
    """Enhanced logger adapter with distributed tracing."""

    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})
        self.start_time = time.time()

    def process(self, msg, kwargs):
        """Add comprehensive context to log messages."""
        extra = kwargs.get('extra', {})

        # Add distributed tracing context
        context_vars = {
            'correlation_id': correlation_id_context.get(),
            'trace_id': trace_id_context.get(),
            'span_id': span_id_context.get(),
            'user_id': user_id_context.get(),
            'session_id': session_id_context.get(),
        }

        for key, value in context_vars.items():
            if value and key not in extra:
                extra[key] = value

        # Add adapter context
        if self.extra:
            extra.update(self.extra)

        # Add runtime context
        extra.update({
            'logger_uptime_seconds': time.time() - self.start_time,
            'thread_name': threading.current_thread().name,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        })

        kwargs['extra'] = extra
        return msg, kwargs

    def trace(self, msg, *args, **kwargs):
        """Log trace level message."""
        if self.isEnabledFor(5):
            self._log(5, msg, args, **kwargs)

    def business(self, msg, *args, **kwargs):
        """Log business event."""
        kwargs.setdefault('extra', {})['log_type'] = 'business_event'
        self.info(msg, *args, **kwargs)

    def security(self, msg, *args, **kwargs):
        """Log security event."""
        kwargs.setdefault('extra', {})['log_type'] = 'security_event'
        self.warning(msg, *args, **kwargs)

    def performance(self, msg, *args, **kwargs):
        """Log performance event."""
        kwargs.setdefault('extra', {})['log_type'] = 'performance_metric'
        self.info(msg, *args, **kwargs)

    def audit(self, msg, *args, **kwargs):
        """Log audit event."""
        kwargs.setdefault('extra', {})['log_type'] = 'audit_event'
        audit_logger = logging.getLogger('audit')
        audit_logger.info(msg, *args, **kwargs)


def get_fixed_logging_config(environment: str = "development") -> Dict[str, Any]:
    """
    Get fixed logging configuration that doesn't interfere with trading data.

    Args:
        environment: Environment name (development, staging, production)

    Returns:
        Logging configuration dictionary
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,

        "formatters": {
            "console_colored": {
                "()": TradingConsoleFormatter,
                "use_colors": True
            },
            "console_plain": {
                "()": TradingConsoleFormatter,
                "use_colors": False
            },
            "structured_json": {
                "()": TradingJSONFormatter,
            },
            "audit_compliant": {
                "()": AuditFormatter,
            },
            "performance_optimized": {
                "()": PerformanceFormatter,
            }
        },

        "filters": {
            "trading_safe_security": {
                "()": TradingSafeSecurityFilter,
            }
        },

        "handlers": {
            # Console handler with improved security filter
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console_colored" if environment == "development" else "console_plain",
                "filters": ["trading_safe_security"],
                "stream": sys.stdout,
            },

            # File handlers
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["trading_safe_security"],
                "filename": str(log_dir / "trading_app.log"),
                "maxBytes": 20 * 1024 * 1024,  # 20MB
                "backupCount": 10,
                "encoding": "utf-8",
            },

            "audit_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "audit_compliant",
                "filename": str(log_dir / "audit.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 20,
                "encoding": "utf-8",
            },

            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["trading_safe_security"],
                "filename": str(log_dir / "errors.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
                "level": "ERROR",
            },

            "performance_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "performance_optimized",
                "filename": str(log_dir / "performance.log"),
                "maxBytes": 20 * 1024 * 1024,  # 20MB
                "backupCount": 15,
                "encoding": "utf-8",
            },
        },

        "loggers": {
            # Main application loggers
            "trading_app": {
                "handlers": ["console", "app_file", "error_file"],
                "level": "INFO",
                "propagate": False,
            },

            # Audit logger
            "audit": {
                "handlers": ["audit_file"],
                "level": "INFO",
                "propagate": False,
            },

            # Performance logger
            "performance": {
                "handlers": ["performance_file"],
                "level": "INFO",
                "propagate": False,
            },

            # Component loggers
            "websocket": {
                "handlers": ["console", "app_file"],
                "level": "INFO",
                "propagate": False,
            },

            "broker": {
                "handlers": ["console", "app_file"],
                "level": "INFO",
                "propagate": False,
            },

            "database": {
                "handlers": ["console", "app_file"],
                "level": "WARNING",
                "propagate": False,
            },

            "security": {
                "handlers": ["console", "app_file", "audit_file"],
                "level": "INFO",
                "propagate": False,
            },

            # Third-party library loggers
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },

            "sqlalchemy": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            }
        },

        "root": {
            "handlers": ["console", "app_file"],
            "level": "INFO"
        }
    }

    # Environment-specific adjustments
    if environment == "development":
        config["loggers"]["trading_app"]["level"] = "DEBUG"
        config["loggers"]["websocket"]["level"] = "DEBUG"
        config["loggers"]["broker"]["level"] = "DEBUG"
        config["root"]["level"] = "DEBUG"
    elif environment == "production":
        config["handlers"]["console"]["formatter"] = "console_plain"
        config["loggers"]["trading_app"]["level"] = "INFO"

    return config


def setup_fixed_logging(environment: str = None) -> None:
    """
    Setup fixed logging configuration that preserves trading data.

    Args:
        environment: Environment name, defaults to ENVIRONMENT env var
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    # Add TRACE level
    logging.addLevelName(5, "TRACE")

    config = get_fixed_logging_config(environment)
    logging.config.dictConfig(config)

    # Log startup message
    logger = logging.getLogger("trading_app")
    logger.info(f"Fixed logging system initialized for {environment} environment")


def get_fixed_logger(name: str, **context) -> EnhancedTradingLoggerAdapter:
    """
    Get a fixed logger that won't mask trading data.

    Args:
        name: Logger name
        **context: Additional context to include in all log messages

    Returns:
        EnhancedTradingLoggerAdapter instance
    """
    base_logger = logging.getLogger(name)
    return EnhancedTradingLoggerAdapter(base_logger, context)


def set_trace_context(
    correlation_id: str = None,
    trace_id: str = None,
    span_id: str = None,
    user_id: str = None,
    session_id: str = None
) -> Dict[str, str]:
    """
    Set distributed tracing context.

    Args:
        correlation_id: Correlation ID for request tracking
        trace_id: Trace ID for distributed tracing
        span_id: Span ID for operation tracing
        user_id: User ID for user activity tracking
        session_id: Session ID for session tracking

    Returns:
        Dictionary of set context values
    """
    context = {}

    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_context.set(correlation_id)
    context['correlation_id'] = correlation_id

    if trace_id is None:
        trace_id = str(uuid.uuid4())
    trace_id_context.set(trace_id)
    context['trace_id'] = trace_id

    if span_id is None:
        span_id = str(uuid.uuid4())
    span_id_context.set(span_id)
    context['span_id'] = span_id

    if user_id:
        user_id_context.set(user_id)
        context['user_id'] = user_id

    if session_id:
        session_id_context.set(session_id)
        context['session_id'] = session_id

    return context


def get_trace_context() -> Dict[str, Optional[str]]:
    """Get current distributed tracing context."""
    return {
        'correlation_id': correlation_id_context.get(),
        'trace_id': trace_id_context.get(),
        'span_id': span_id_context.get(),
        'user_id': user_id_context.get(),
        'session_id': session_id_context.get(),
    }


# Performance timing decorator
def timed_operation(operation_name: str, logger_name: str = "performance"):
    """Decorator to automatically log operation timing."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            logger = get_fixed_logger(logger_name, operation=operation_name)

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.performance(f"Operation {operation_name} completed in {duration_ms:.1f}ms")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"Operation {operation_name} failed after {duration_ms:.1f}ms: {str(e)}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            logger = get_fixed_logger(logger_name, operation=operation_name)

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.performance(f"Operation {operation_name} completed in {duration_ms:.1f}ms")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"Operation {operation_name} failed after {duration_ms:.1f}ms: {str(e)}")
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator