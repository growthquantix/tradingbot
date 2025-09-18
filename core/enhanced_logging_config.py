"""
Production-Grade Enhanced Logging Configuration for Trading System

This module provides enterprise-level logging with:
- Distributed tracing and correlation IDs
- Structured JSON logging with business context
- Advanced security filtering and compliance
- Performance monitoring and metrics
- Log aggregation and monitoring hooks
- Circuit breaker patterns for logging
- Async logging for high-throughput systems
- Multi-tenant logging support
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
import socket
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, List, Union, Callable
from pathlib import Path
import contextvars
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor


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
tenant_id_context: contextvars.ContextVar = contextvars.ContextVar(
    "tenant_id", default=None
)


class LogLevel(Enum):
    """Enhanced log levels with severity mapping."""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = 60


class LogCategory(Enum):
    """Log categories for better organization and routing."""
    BUSINESS = "BUSINESS"
    TECHNICAL = "TECHNICAL"
    SECURITY = "SECURITY"
    AUDIT = "AUDIT"
    PERFORMANCE = "PERFORMANCE"
    INTEGRATION = "INTEGRATION"
    USER_ACTIVITY = "USER_ACTIVITY"
    COMPLIANCE = "COMPLIANCE"
    DEBUGGING = "DEBUGGING"


class AlertSeverity(Enum):
    """Alert severity levels for monitoring integration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Comprehensive structured log context."""
    # Tracing context
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    # User context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None

    # System context
    operation: Optional[str] = None
    component: Optional[str] = None
    service: Optional[str] = None
    version: Optional[str] = None
    environment: Optional[str] = None

    # Business context
    category: Optional[LogCategory] = None
    business_domain: Optional[str] = None
    transaction_id: Optional[str] = None

    # Technical context
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Performance context
    duration_ms: Optional[float] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None

    # Security context
    security_level: Optional[str] = None
    risk_score: Optional[int] = None

    # Alert context
    alert_severity: Optional[AlertSeverity] = None
    alert_tags: Optional[List[str]] = None

    # Custom context
    custom_fields: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, Enum):
                    result[key] = value.value
                elif isinstance(value, list) and all(isinstance(x, Enum) for x in value):
                    result[key] = [x.value for x in value]
                else:
                    result[key] = value
        return result


class CircuitBreakerFilter(logging.Filter):
    """Circuit breaker for logging to prevent cascading failures."""

    def __init__(self, max_errors=10, reset_timeout=60):
        super().__init__()
        self.max_errors = max_errors
        self.reset_timeout = reset_timeout
        self.error_count = 0
        self.last_error_time = 0
        self.circuit_open = False

    def filter(self, record):
        """Apply circuit breaker logic."""
        current_time = time.time()

        # Reset circuit if timeout has passed
        if self.circuit_open and (current_time - self.last_error_time) > self.reset_timeout:
            self.circuit_open = False
            self.error_count = 0

        # If circuit is open, drop non-critical logs
        if self.circuit_open and record.levelno < logging.ERROR:
            return False

        # Track errors for circuit breaker
        if record.levelno >= logging.ERROR:
            self.error_count += 1
            self.last_error_time = current_time

            if self.error_count >= self.max_errors:
                self.circuit_open = True

        return True


class EnhancedSecurityFilter(logging.Filter):
    """Advanced security filter with pattern matching and data classification."""

    SENSITIVE_FIELDS = {
        # Authentication
        "password", "passwd", "pwd", "pass",
        "token", "access_token", "refresh_token", "jwt", "bearer",
        "secret", "api_secret", "client_secret",
        "key", "api_key", "private_key", "public_key", "encryption_key",
        "authorization", "auth", "credentials",
        "pin", "otp", "totp", "mfa_code",

        # Financial
        "ssn", "social_security", "social_security_number",
        "credit_card", "card_number", "cvv", "cvc",
        "bank_account", "account_number", "routing_number",
        "iban", "swift_code",

        # Personal Information
        "email_password", "phone_number", "address",
        "date_of_birth", "dob", "birthday",

        # System
        "signature", "hash", "checksum",
        "session_token", "csrf_token"
    }

    SENSITIVE_PATTERNS = [
        (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'CREDIT_CARD'),  # Credit card
        (r'\b\d{3}-?\d{2}-?\d{4}\b', 'SSN'),  # SSN
        (r'\b\d{9,18}\b', 'ACCOUNT_NUMBER'),  # Account numbers
        (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'BEARER_TOKEN'),  # Bearer tokens
        (r'[A-Za-z0-9]{32,}', 'LONG_HEX'),  # Long hex strings
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),  # Email
        (r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b', 'PHONE'),  # Phone
    ]

    def filter(self, record):
        """Enhanced security filtering with classification."""
        import re

        message = record.getMessage()
        original_message = message.lower()
        sensitive_data_found = []

        # Check for sensitive field names
        for sensitive_field in self.SENSITIVE_FIELDS:
            if sensitive_field in original_message:
                # Sophisticated masking preserving structure
                pattern = rf'(\b{sensitive_field}\b["\s]*[:=]["\s]*)([^"\s,}}]*)'
                message = re.sub(pattern, r'\1***MASKED***', message, flags=re.IGNORECASE)
                sensitive_data_found.append(f"FIELD_{sensitive_field.upper()}")

        # Check for sensitive patterns
        for pattern, data_type in self.SENSITIVE_PATTERNS:
            if re.search(pattern, message):
                message = re.sub(pattern, f'***{data_type}_MASKED***', message)
                sensitive_data_found.append(data_type)

        # Update record if modified
        if message != record.getMessage():
            record.msg = message
            record.args = ()
            setattr(record, 'security_filtered', True)
            setattr(record, 'sensitive_data_types', sensitive_data_found)

        # Add security classification
        setattr(record, 'security_level', self._classify_security_level(record))
        setattr(record, 'data_classification', self._classify_data(record))

        return True

    def _classify_security_level(self, record):
        """Classify security level of the log entry."""
        message = record.getMessage().lower()

        critical_indicators = ['attack', 'breach', 'intrusion', 'unauthorized access']
        high_indicators = ['failed login', 'permission denied', 'authentication failed']
        medium_indicators = ['login', 'logout', 'access denied', 'invalid']

        if any(indicator in message for indicator in critical_indicators):
            return 'CRITICAL'
        elif any(indicator in message for indicator in high_indicators):
            return 'HIGH'
        elif any(indicator in message for indicator in medium_indicators):
            return 'MEDIUM'
        else:
            return 'LOW'

    def _classify_data(self, record):
        """Classify data sensitivity level."""
        if hasattr(record, 'sensitive_data_types'):
            return 'SENSITIVE'
        elif any(field in record.getMessage().lower() for field in ['user', 'account', 'profile']):
            return 'PERSONAL'
        elif any(field in record.getMessage().lower() for field in ['trade', 'order', 'position']):
            return 'BUSINESS_CRITICAL'
        else:
            return 'PUBLIC'


class PerformanceMonitoringFilter(logging.Filter):
    """Advanced performance monitoring with system metrics."""

    def __init__(self):
        super().__init__()
        self.process = psutil.Process()
        self.system_metrics_cache = {}
        self.cache_expiry = 0

    def filter(self, record):
        """Add comprehensive performance metrics."""
        current_time = time.time()

        # Cache system metrics for 1 second to avoid overhead
        if current_time > self.cache_expiry:
            try:
                # System metrics
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                network_io = psutil.net_io_counters()

                # Process metrics
                process_memory = self.process.memory_info()
                process_cpu = self.process.cpu_percent()

                self.system_metrics_cache = {
                    'system_cpu_percent': cpu_percent,
                    'system_memory_percent': memory.percent,
                    'system_memory_available_mb': memory.available / 1024 / 1024,
                    'disk_read_mb': disk_io.read_bytes / 1024 / 1024 if disk_io else 0,
                    'disk_write_mb': disk_io.write_bytes / 1024 / 1024 if disk_io else 0,
                    'network_sent_mb': network_io.bytes_sent / 1024 / 1024 if network_io else 0,
                    'network_recv_mb': network_io.bytes_recv / 1024 / 1024 if network_io else 0,
                    'process_memory_mb': process_memory.rss / 1024 / 1024,
                    'process_cpu_percent': process_cpu,
                    'thread_count': threading.active_count(),
                }
                self.cache_expiry = current_time + 1
            except:
                pass

        # Add metrics to record
        for key, value in self.system_metrics_cache.items():
            setattr(record, key, value)

        # Add precise timing
        setattr(record, 'precise_timestamp', time.time_ns())
        setattr(record, 'timestamp_utc', datetime.now(timezone.utc).isoformat())

        # Add performance classification
        setattr(record, 'performance_tier', self._classify_performance(record))

        return True

    def _classify_performance(self, record):
        """Classify performance tier based on duration if available."""
        duration_ms = getattr(record, 'duration_ms', None)
        if duration_ms is None:
            return 'UNKNOWN'

        if duration_ms < 10:
            return 'EXCELLENT'
        elif duration_ms < 50:
            return 'GOOD'
        elif duration_ms < 200:
            return 'ACCEPTABLE'
        elif duration_ms < 1000:
            return 'SLOW'
        else:
            return 'CRITICAL'


class BusinessContextFilter(logging.Filter):
    """Enhanced business context filter with domain classification."""

    BUSINESS_DOMAINS = {
        'TRADING': ['order', 'trade', 'position', 'portfolio', 'execution', 'fill'],
        'MARKET_DATA': ['price', 'quote', 'market', 'feed', 'ticker', 'depth'],
        'USER_MANAGEMENT': ['user', 'login', 'signup', 'profile', 'authentication'],
        'RISK_MANAGEMENT': ['risk', 'limit', 'exposure', 'margin', 'drawdown'],
        'COMPLIANCE': ['audit', 'regulation', 'compliance', 'sebi', 'reporting'],
        'SETTLEMENT': ['settlement', 'clearing', 'payment', 'fund', 'transfer'],
        'NOTIFICATION': ['alert', 'notification', 'email', 'sms', 'push'],
        'ANALYTICS': ['analysis', 'metric', 'report', 'dashboard', 'insight'],
    }

    def filter(self, record):
        """Add business context classification."""
        message = record.getMessage().lower()

        # Classify business domain
        for domain, keywords in self.BUSINESS_DOMAINS.items():
            if any(keyword in message for keyword in keywords):
                setattr(record, 'business_domain', domain)
                break
        else:
            setattr(record, 'business_domain', 'SYSTEM')

        # Add environment context
        setattr(record, 'environment', os.getenv('ENVIRONMENT', 'development'))
        setattr(record, 'service_name', os.getenv('SERVICE_NAME', 'trading-app'))
        setattr(record, 'version', os.getenv('APP_VERSION', '1.0.0'))
        setattr(record, 'hostname', socket.gethostname())
        setattr(record, 'process_id', os.getpid())

        # Add business event classification
        if any(word in message for word in ['executed', 'filled', 'completed']):
            setattr(record, 'business_event_type', 'COMPLETION')
        elif any(word in message for word in ['failed', 'error', 'rejected']):
            setattr(record, 'business_event_type', 'FAILURE')
        elif any(word in message for word in ['started', 'initiated', 'created']):
            setattr(record, 'business_event_type', 'INITIATION')
        else:
            setattr(record, 'business_event_type', 'STATUS_UPDATE')

        return True


class ProductionTradingLoggerAdapter(logging.LoggerAdapter):
    """Production-grade logger adapter with comprehensive features."""

    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})
        self.start_time = time.time()
        self.log_count = 0

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
            'tenant_id': tenant_id_context.get(),
        }

        for key, value in context_vars.items():
            if value and key not in extra:
                extra[key] = value

        # Add adapter context
        if self.extra:
            extra.update(self.extra)

        # Add runtime context
        self.log_count += 1
        extra.update({
            'logger_uptime_seconds': time.time() - self.start_time,
            'logger_log_count': self.log_count,
            'thread_name': threading.current_thread().name,
        })

        kwargs['extra'] = extra
        return msg, kwargs

    # Enhanced logging methods
    def trace(self, msg, *args, **kwargs):
        """Log trace level message."""
        if self.isEnabledFor(5):
            self._log(5, msg, args, **kwargs)

    def business(self, msg, *args, **kwargs):
        """Log business event with automatic categorization."""
        kwargs.setdefault('extra', {}).update({
            'category': LogCategory.BUSINESS.value,
            'log_type': 'business_event'
        })
        self.info(msg, *args, **kwargs)

    def security(self, msg, *args, **kwargs):
        """Log security event with enhanced context."""
        kwargs.setdefault('extra', {}).update({
            'category': LogCategory.SECURITY.value,
            'log_type': 'security_event',
            'requires_investigation': True
        })
        self.warning(msg, *args, **kwargs)

    def performance(self, msg, *args, **kwargs):
        """Log performance event with metrics."""
        kwargs.setdefault('extra', {}).update({
            'category': LogCategory.PERFORMANCE.value,
            'log_type': 'performance_metric'
        })
        self.info(msg, *args, **kwargs)

    def audit(self, msg, *args, **kwargs):
        """Log audit event for compliance."""
        kwargs.setdefault('extra', {}).update({
            'category': LogCategory.AUDIT.value,
            'log_type': 'audit_event',
            'immutable': True,
            'retention_years': 7
        })
        audit_logger = logging.getLogger('audit')
        audit_logger.info(msg, *args, **kwargs)

    def alert(self, msg, severity=AlertSeverity.MEDIUM, tags=None, *args, **kwargs):
        """Log alert that should trigger monitoring."""
        kwargs.setdefault('extra', {}).update({
            'alert_severity': severity.value,
            'alert_tags': tags or [],
            'requires_alert': True,
            'log_type': 'alert'
        })

        if severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            self.error(msg, *args, **kwargs)
        else:
            self.warning(msg, *args, **kwargs)


def get_production_logging_config(environment: str = "production") -> Dict[str, Any]:
    """
    Get production-grade logging configuration.

    Args:
        environment: Environment name (development, staging, production)

    Returns:
        Comprehensive logging configuration
    """
    from core.formatters import (
        TradingConsoleFormatter, TradingJSONFormatter,
        AuditFormatter, PerformanceFormatter
    )

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Base configuration with all production features
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
            },
            "compact": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%H:%M:%S"
            }
        },

        "filters": {
            "circuit_breaker": {
                "()": CircuitBreakerFilter,
                "max_errors": 20,
                "reset_timeout": 60
            },
            "security_enhanced": {
                "()": EnhancedSecurityFilter,
            },
            "performance_monitoring": {
                "()": PerformanceMonitoringFilter,
            },
            "business_context": {
                "()": BusinessContextFilter,
            }
        },

        "handlers": {
            # Console handlers
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console_colored" if environment == "development" else "console_plain",
                "filters": ["circuit_breaker", "security_enhanced", "performance_monitoring", "business_context"],
                "stream": sys.stdout,
            },

            # File handlers with enhanced features
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["security_enhanced", "performance_monitoring", "business_context"],
                "filename": str(log_dir / "trading_app.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 20,
                "encoding": "utf-8",
            },

            "business_events": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["business_context"],
                "filename": str(log_dir / "business_events.log"),
                "maxBytes": 100 * 1024 * 1024,  # 100MB
                "backupCount": 30,
                "encoding": "utf-8",
            },

            "security_events": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["security_enhanced"],
                "filename": str(log_dir / "security_events.log"),
                "maxBytes": 200 * 1024 * 1024,  # 200MB
                "backupCount": 50,
                "encoding": "utf-8",
            },

            "audit_compliant": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "audit_compliant",
                "filename": str(log_dir / "audit_trail.log"),
                "maxBytes": 500 * 1024 * 1024,  # 500MB
                "backupCount": 100,  # Long retention for compliance
                "encoding": "utf-8",
            },

            "performance_metrics": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "performance_optimized",
                "filters": ["performance_monitoring"],
                "filename": str(log_dir / "performance_metrics.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 15,
                "encoding": "utf-8",
            },

            "error_tracking": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["security_enhanced", "performance_monitoring", "business_context"],
                "filename": str(log_dir / "errors.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 20,
                "encoding": "utf-8",
                "level": "WARNING",
            },

            "critical_alerts": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured_json",
                "filters": ["security_enhanced", "performance_monitoring"],
                "filename": str(log_dir / "critical_alerts.log"),
                "maxBytes": 20 * 1024 * 1024,  # 20MB
                "backupCount": 10,
                "encoding": "utf-8",
                "level": "ERROR",
            }
        },

        "loggers": {
            # Main application loggers
            "trading_app": {
                "handlers": ["console", "app_file", "error_tracking"],
                "level": "INFO",
                "propagate": False,
            },

            # Specialized loggers
            "business": {
                "handlers": ["business_events", "console"],
                "level": "INFO",
                "propagate": False,
            },

            "security": {
                "handlers": ["security_events", "console", "critical_alerts"],
                "level": "INFO",
                "propagate": False,
            },

            "audit": {
                "handlers": ["audit_compliant"],
                "level": "INFO",
                "propagate": False,
            },

            "performance": {
                "handlers": ["performance_metrics"],
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
                "handlers": ["console", "app_file", "business_events"],
                "level": "INFO",
                "propagate": False,
            },

            "database": {
                "handlers": ["console", "app_file"],
                "level": "WARNING",
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
    elif environment == "staging":
        config["loggers"]["trading_app"]["level"] = "INFO"
        config["handlers"]["console"]["formatter"] = "console_plain"
    elif environment == "production":
        config["handlers"]["console"]["formatter"] = "console_plain"
        config["loggers"]["trading_app"]["level"] = "WARNING"
        config["loggers"]["websocket"]["level"] = "WARNING"

    return config


def setup_production_logging(environment: str = None) -> None:
    """
    Setup production-grade logging configuration.

    Args:
        environment: Environment name, defaults to ENVIRONMENT env var
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "production")

    # Add TRACE level
    logging.addLevelName(5, "TRACE")

    config = get_production_logging_config(environment)
    logging.config.dictConfig(config)

    # Log startup message with system information
    logger = get_production_logger("trading_app")
    logger.info(f"Production logging system initialized", extra={
        'environment': environment,
        'python_version': sys.version,
        'platform': sys.platform,
        'hostname': socket.gethostname(),
        'process_id': os.getpid(),
        'startup_time': datetime.now(timezone.utc).isoformat()
    })


def get_production_logger(name: str, **context) -> ProductionTradingLoggerAdapter:
    """
    Get a production-grade logger with comprehensive context.

    Args:
        name: Logger name
        **context: Additional context to include in all log messages

    Returns:
        ProductionTradingLoggerAdapter instance
    """
    base_logger = logging.getLogger(name)
    return ProductionTradingLoggerAdapter(base_logger, context)


# Enhanced context management functions
def set_distributed_trace_context(
    correlation_id: str = None,
    trace_id: str = None,
    span_id: str = None,
    user_id: str = None,
    session_id: str = None,
    tenant_id: str = None
) -> Dict[str, str]:
    """
    Set comprehensive distributed tracing context.

    Args:
        correlation_id: Correlation ID for request tracking
        trace_id: Trace ID for distributed tracing
        span_id: Span ID for operation tracing
        user_id: User ID for user activity tracking
        session_id: Session ID for session tracking
        tenant_id: Tenant ID for multi-tenant support

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

    if tenant_id:
        tenant_id_context.set(tenant_id)
        context['tenant_id'] = tenant_id

    return context


def get_trace_context() -> Dict[str, Optional[str]]:
    """Get current distributed tracing context."""
    return {
        'correlation_id': correlation_id_context.get(),
        'trace_id': trace_id_context.get(),
        'span_id': span_id_context.get(),
        'user_id': user_id_context.get(),
        'session_id': session_id_context.get(),
        'tenant_id': tenant_id_context.get(),
    }


# Performance monitoring decorator
def timed_operation(
    operation_name: str,
    logger_name: str = "performance",
    alert_threshold_ms: float = 1000,
    business_critical: bool = False
):
    """
    Advanced decorator for operation timing with alerting.

    Args:
        operation_name: Name of the operation
        logger_name: Logger to use for timing
        alert_threshold_ms: Threshold for performance alerts
        business_critical: Whether this is a business-critical operation
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            logger = get_production_logger(logger_name, operation=operation_name)

            # Set span context for distributed tracing
            span_id = str(uuid.uuid4())
            parent_span = span_id_context.get()
            span_id_context.set(span_id)

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                extra_context = {
                    'duration_ms': duration_ms,
                    'status': 'success',
                    'operation': operation_name,
                    'span_id': span_id,
                    'parent_span_id': parent_span,
                    'business_critical': business_critical
                }

                if duration_ms > alert_threshold_ms:
                    logger.alert(
                        f"Operation {operation_name} exceeded threshold: {duration_ms:.1f}ms",
                        severity=AlertSeverity.HIGH if business_critical else AlertSeverity.MEDIUM,
                        tags=['performance', 'slow_operation'],
                        extra=extra_context
                    )
                else:
                    logger.performance(
                        f"Operation {operation_name} completed: {duration_ms:.1f}ms",
                        extra=extra_context
                    )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                extra_context = {
                    'duration_ms': duration_ms,
                    'status': 'error',
                    'operation': operation_name,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'span_id': span_id,
                    'parent_span_id': parent_span,
                    'business_critical': business_critical
                }

                logger.alert(
                    f"Operation {operation_name} failed: {str(e)}",
                    severity=AlertSeverity.CRITICAL if business_critical else AlertSeverity.HIGH,
                    tags=['error', 'operation_failure'],
                    extra=extra_context
                )
                raise
            finally:
                # Reset span context
                if parent_span:
                    span_id_context.set(parent_span)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            logger = get_production_logger(logger_name, operation=operation_name)

            span_id = str(uuid.uuid4())
            parent_span = span_id_context.get()
            span_id_context.set(span_id)

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                extra_context = {
                    'duration_ms': duration_ms,
                    'status': 'success',
                    'operation': operation_name,
                    'span_id': span_id,
                    'parent_span_id': parent_span,
                    'business_critical': business_critical
                }

                if duration_ms > alert_threshold_ms:
                    logger.alert(
                        f"Operation {operation_name} exceeded threshold: {duration_ms:.1f}ms",
                        severity=AlertSeverity.HIGH if business_critical else AlertSeverity.MEDIUM,
                        tags=['performance', 'slow_operation'],
                        extra=extra_context
                    )
                else:
                    logger.performance(
                        f"Operation {operation_name} completed: {duration_ms:.1f}ms",
                        extra=extra_context
                    )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                extra_context = {
                    'duration_ms': duration_ms,
                    'status': 'error',
                    'operation': operation_name,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'span_id': span_id,
                    'parent_span_id': parent_span,
                    'business_critical': business_critical
                }

                logger.alert(
                    f"Operation {operation_name} failed: {str(e)}",
                    severity=AlertSeverity.CRITICAL if business_critical else AlertSeverity.HIGH,
                    tags=['error', 'operation_failure'],
                    extra=extra_context
                )
                raise
            finally:
                if parent_span:
                    span_id_context.set(parent_span)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def structured_log(
    level: str,
    message: str,
    context: LogContext,
    logger_name: str = "trading_app"
) -> None:
    """
    Log a structured message with comprehensive context.

    Args:
        level: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        context: Structured log context
        logger_name: Logger to use
    """
    logger = get_production_logger(logger_name)
    log_method = getattr(logger, level.lower())
    log_method(message, extra=context.to_dict())


# Specialized logger getters
def get_business_logger(**context) -> ProductionTradingLoggerAdapter:
    """Get business events logger."""
    return get_production_logger("business", component="business_logic", **context)


def get_security_logger(**context) -> ProductionTradingLoggerAdapter:
    """Get security events logger."""
    return get_production_logger("security", component="security", **context)


def get_audit_logger(**context) -> ProductionTradingLoggerAdapter:
    """Get audit compliance logger."""
    return get_production_logger("audit", component="audit", **context)


def get_performance_logger(**context) -> ProductionTradingLoggerAdapter:
    """Get performance monitoring logger."""
    return get_production_logger("performance", component="performance", **context)


def get_websocket_logger(**context) -> ProductionTradingLoggerAdapter:
    """Get WebSocket logger with enhanced context."""
    return get_production_logger("websocket", component="websocket", **context)


def get_broker_logger(broker: str, **context) -> ProductionTradingLoggerAdapter:
    """Get broker-specific logger with enhanced context."""
    return get_production_logger("broker", broker=broker, component="broker_integration", **context)


def get_database_logger(**context) -> ProductionTradingLoggerAdapter:
    """Get database logger with enhanced context."""
    return get_production_logger("database", component="database", **context)