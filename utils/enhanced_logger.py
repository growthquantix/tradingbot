"""
Enhanced Production-Grade Logger Utilities for Trading System

This module provides high-level utilities and convenience functions for
production logging with comprehensive features:
- Trading-specific logging functions
- Business event tracking
- Performance monitoring helpers
- Security event logging
- Compliance audit trails
- Error tracking and alerting
"""

import asyncio
import time
import traceback
import functools
from typing import Any, Dict, Optional, List, Union, Callable
from decimal import Decimal
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from core.enhanced_logging_config import (
    get_production_logger,
    set_distributed_trace_context,
    LogContext,
    LogCategory,
    AlertSeverity,
    timed_operation,
    structured_log
)


class TradingEventType(Enum):
    """Trading-specific event types for structured logging."""
    ORDER_PLACED = "order_placed"
    ORDER_MODIFIED = "order_modified"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_EXECUTED = "order_executed"
    ORDER_REJECTED = "order_rejected"

    TRADE_EXECUTED = "trade_executed"
    TRADE_SETTLED = "trade_settled"

    POSITION_OPENED = "position_opened"
    POSITION_MODIFIED = "position_modified"
    POSITION_CLOSED = "position_closed"

    PORTFOLIO_UPDATED = "portfolio_updated"
    BALANCE_UPDATED = "balance_updated"

    MARKET_DATA_RECEIVED = "market_data_received"
    MARKET_DATA_PROCESSED = "market_data_processed"

    RISK_LIMIT_CHECKED = "risk_limit_checked"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"

    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_ACTION = "user_action"

    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"

    COMPLIANCE_CHECK = "compliance_check"
    COMPLIANCE_VIOLATION = "compliance_violation"


@dataclass
class TradingContext:
    """Comprehensive trading context for logging."""
    # Trading identifiers
    user_id: Optional[str] = None
    account_id: Optional[str] = None
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    position_id: Optional[str] = None

    # Financial data
    symbol: Optional[str] = None
    side: Optional[str] = None  # BUY/SELL
    quantity: Optional[Union[int, Decimal]] = None
    price: Optional[Union[float, Decimal]] = None
    amount: Optional[Union[float, Decimal]] = None

    # Broker context
    broker: Optional[str] = None
    exchange: Optional[str] = None
    product_type: Optional[str] = None
    order_type: Optional[str] = None

    # Risk context
    available_margin: Optional[Union[float, Decimal]] = None
    used_margin: Optional[Union[float, Decimal]] = None
    risk_score: Optional[float] = None

    # Performance context
    latency_ms: Optional[float] = None
    throughput: Optional[float] = None

    # Market context
    market_price: Optional[Union[float, Decimal]] = None
    market_time: Optional[datetime] = None

    # Additional context
    strategy: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_log_context(self) -> LogContext:
        """Convert to LogContext for structured logging."""
        business_context = {}
        technical_context = {}
        performance_context = {}

        # Business context
        for field_name in ['user_id', 'account_id', 'symbol', 'side', 'quantity',
                          'price', 'amount', 'broker', 'exchange', 'strategy']:
            value = getattr(self, field_name)
            if value is not None:
                if isinstance(value, Decimal):
                    business_context[field_name] = str(value)
                else:
                    business_context[field_name] = value

        # Technical context
        for field_name in ['order_id', 'trade_id', 'position_id', 'product_type',
                          'order_type', 'market_time', 'reason']:
            value = getattr(self, field_name)
            if value is not None:
                if isinstance(value, datetime):
                    technical_context[field_name] = value.isoformat()
                else:
                    technical_context[field_name] = value

        # Performance context
        for field_name in ['latency_ms', 'throughput']:
            value = getattr(self, field_name)
            if value is not None:
                performance_context[field_name] = value

        # Risk context
        risk_context = {}
        for field_name in ['available_margin', 'used_margin', 'risk_score']:
            value = getattr(self, field_name)
            if value is not None:
                if isinstance(value, Decimal):
                    risk_context[field_name] = str(value)
                else:
                    risk_context[field_name] = value

        return LogContext(
            business_context=business_context if business_context else None,
            technical_context=technical_context if technical_context else None,
            performance_context=performance_context if performance_context else None,
            security_context=risk_context if risk_context else None,
            custom_fields=self.metadata if self.metadata else None
        )


class EnhancedTradingLogger:
    """High-level trading logger with convenience methods."""

    def __init__(self, component: str, logger_name: str = "trading_app"):
        self.component = component
        self.logger = get_production_logger(logger_name, component=component)

    def log_trading_event(self,
                         event_type: TradingEventType,
                         message: str,
                         context: TradingContext,
                         level: str = "INFO",
                         alert_severity: Optional[AlertSeverity] = None):
        """
        Log a trading event with full context.

        Args:
            event_type: Type of trading event
            message: Human-readable message
            context: Trading context data
            level: Log level
            alert_severity: Alert severity if this should trigger alerts
        """
        log_context = context.to_log_context()
        log_context.category = LogCategory.BUSINESS
        log_context.business_context = log_context.business_context or {}
        log_context.business_context['event_type'] = event_type.value

        if alert_severity:
            self.logger.alert(
                message,
                severity=alert_severity,
                tags=[event_type.value, 'trading_event'],
                extra=log_context.to_dict()
            )
        else:
            structured_log(level, message, log_context, self.logger.logger.name)

    def log_order_placed(self, context: TradingContext, message: str = None):
        """Log order placement event."""
        default_msg = f"Order placed: {context.symbol} {context.side} {context.quantity} @ {context.price}"
        self.log_trading_event(
            TradingEventType.ORDER_PLACED,
            message or default_msg,
            context,
            level="INFO"
        )

    def log_order_executed(self, context: TradingContext, message: str = None):
        """Log order execution event."""
        default_msg = f"Order executed: {context.symbol} {context.side} {context.quantity} @ {context.price}"
        self.log_trading_event(
            TradingEventType.ORDER_EXECUTED,
            message or default_msg,
            context,
            level="INFO"
        )

    def log_order_rejected(self, context: TradingContext, reason: str, message: str = None):
        """Log order rejection event."""
        context.reason = reason
        default_msg = f"Order rejected: {context.symbol} {context.side} {context.quantity} - {reason}"
        self.log_trading_event(
            TradingEventType.ORDER_REJECTED,
            message or default_msg,
            context,
            level="WARNING",
            alert_severity=AlertSeverity.MEDIUM
        )

    def log_trade_executed(self, context: TradingContext, message: str = None):
        """Log trade execution event."""
        default_msg = f"Trade executed: {context.symbol} {context.quantity} @ {context.price}"
        self.log_trading_event(
            TradingEventType.TRADE_EXECUTED,
            message or default_msg,
            context,
            level="INFO"
        )

    def log_position_update(self, context: TradingContext, action: str, message: str = None):
        """Log position update event."""
        event_map = {
            'opened': TradingEventType.POSITION_OPENED,
            'modified': TradingEventType.POSITION_MODIFIED,
            'closed': TradingEventType.POSITION_CLOSED
        }

        event_type = event_map.get(action.lower(), TradingEventType.POSITION_MODIFIED)
        default_msg = f"Position {action}: {context.symbol} {context.quantity}"

        self.log_trading_event(
            event_type,
            message or default_msg,
            context,
            level="INFO"
        )

    def log_risk_event(self, context: TradingContext, risk_type: str, severity: AlertSeverity, message: str = None):
        """Log risk management event."""
        context.reason = risk_type
        default_msg = f"Risk event: {risk_type} for {context.symbol}"

        event_type = (TradingEventType.RISK_LIMIT_EXCEEDED
                     if 'exceeded' in risk_type.lower()
                     else TradingEventType.RISK_LIMIT_CHECKED)

        self.log_trading_event(
            event_type,
            message or default_msg,
            context,
            level="WARNING" if severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM] else "ERROR",
            alert_severity=severity
        )

    def log_market_data_event(self, context: TradingContext, event_type: str, message: str = None):
        """Log market data event."""
        event_map = {
            'received': TradingEventType.MARKET_DATA_RECEIVED,
            'processed': TradingEventType.MARKET_DATA_PROCESSED
        }

        trading_event = event_map.get(event_type.lower(), TradingEventType.MARKET_DATA_PROCESSED)
        default_msg = f"Market data {event_type}: {context.symbol}"

        self.log_trading_event(
            trading_event,
            message or default_msg,
            context,
            level="DEBUG"
        )

    def log_user_activity(self, context: TradingContext, activity: str, message: str = None):
        """Log user activity event."""
        context.reason = activity
        default_msg = f"User activity: {activity} for user {context.user_id}"

        event_type = {
            'login': TradingEventType.USER_LOGIN,
            'logout': TradingEventType.USER_LOGOUT
        }.get(activity.lower(), TradingEventType.USER_ACTION)

        self.log_trading_event(
            event_type,
            message or default_msg,
            context,
            level="INFO"
        )

    def log_system_event(self, event_type: str, message: str,
                        alert_severity: Optional[AlertSeverity] = None,
                        context: Optional[TradingContext] = None):
        """Log system event."""
        trading_context = context or TradingContext()
        trading_context.reason = event_type

        event_map = {
            'startup': TradingEventType.SYSTEM_STARTUP,
            'shutdown': TradingEventType.SYSTEM_SHUTDOWN,
            'error': TradingEventType.SYSTEM_ERROR
        }

        trading_event = event_map.get(event_type.lower(), TradingEventType.SYSTEM_ERROR)

        self.log_trading_event(
            trading_event,
            message,
            trading_context,
            level="INFO" if event_type in ['startup', 'shutdown'] else "ERROR",
            alert_severity=alert_severity
        )

    def log_performance_metric(self, operation: str, duration_ms: float,
                              context: Optional[TradingContext] = None,
                              threshold_ms: float = 1000):
        """Log performance metric with automatic alerting."""
        trading_context = context or TradingContext()
        trading_context.latency_ms = duration_ms
        trading_context.reason = f"performance_metric_{operation}"

        log_context = trading_context.to_log_context()
        log_context.category = LogCategory.PERFORMANCE
        log_context.operation = operation
        log_context.performance_context = log_context.performance_context or {}
        log_context.performance_context.update({
            'duration_ms': duration_ms,
            'threshold_ms': threshold_ms,
            'operation': operation
        })

        if duration_ms > threshold_ms:
            self.logger.alert(
                f"Performance threshold exceeded for {operation}: {duration_ms:.1f}ms",
                severity=AlertSeverity.HIGH if duration_ms > threshold_ms * 2 else AlertSeverity.MEDIUM,
                tags=['performance', 'slow_operation', operation],
                extra=log_context.to_dict()
            )
        else:
            self.logger.performance(
                f"Operation {operation} completed in {duration_ms:.1f}ms",
                extra=log_context.to_dict()
            )

    def log_security_event(self, event_type: str, message: str,
                          severity: AlertSeverity,
                          context: Optional[TradingContext] = None):
        """Log security event with automatic alerting."""
        trading_context = context or TradingContext()
        trading_context.reason = event_type

        log_context = trading_context.to_log_context()
        log_context.category = LogCategory.SECURITY
        log_context.security_context = log_context.security_context or {}
        log_context.security_context.update({
            'event_type': event_type,
            'severity': severity.value
        })

        self.logger.alert(
            message,
            severity=severity,
            tags=['security', event_type],
            extra=log_context.to_dict()
        )

    def log_compliance_event(self, event_type: str, message: str,
                           context: Optional[TradingContext] = None,
                           violation: bool = False):
        """Log compliance event for audit trails."""
        trading_context = context or TradingContext()
        trading_context.reason = event_type

        log_context = trading_context.to_log_context()
        log_context.category = LogCategory.COMPLIANCE

        compliance_event = (TradingEventType.COMPLIANCE_VIOLATION
                          if violation
                          else TradingEventType.COMPLIANCE_CHECK)

        log_context.business_context = log_context.business_context or {}
        log_context.business_context.update({
            'event_type': compliance_event.value,
            'compliance_type': event_type,
            'violation': violation
        })

        if violation:
            self.logger.alert(
                message,
                severity=AlertSeverity.HIGH,
                tags=['compliance', 'violation', event_type],
                extra=log_context.to_dict()
            )
        else:
            self.logger.audit(message, extra=log_context.to_dict())


# Convenience functions for common logging patterns
def log_trade_execution(user_id: str, symbol: str, side: str, quantity: Union[int, Decimal],
                       price: Union[float, Decimal], broker: str, order_id: str = None,
                       trade_id: str = None, component: str = "trading_engine"):
    """Convenience function to log trade execution."""
    logger = EnhancedTradingLogger(component)
    context = TradingContext(
        user_id=user_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        broker=broker,
        order_id=order_id,
        trade_id=trade_id,
        amount=Decimal(str(quantity)) * Decimal(str(price)) if quantity and price else None
    )
    logger.log_trade_executed(context)


def log_order_placement(user_id: str, symbol: str, side: str, quantity: Union[int, Decimal],
                       price: Union[float, Decimal], broker: str, order_id: str,
                       order_type: str = "LIMIT", component: str = "order_management"):
    """Convenience function to log order placement."""
    logger = EnhancedTradingLogger(component)
    context = TradingContext(
        user_id=user_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        broker=broker,
        order_id=order_id,
        order_type=order_type,
        amount=Decimal(str(quantity)) * Decimal(str(price)) if quantity and price else None
    )
    logger.log_order_placed(context)


def log_risk_violation(user_id: str, risk_type: str, details: str,
                      symbol: str = None, amount: Union[float, Decimal] = None,
                      component: str = "risk_management"):
    """Convenience function to log risk violations."""
    logger = EnhancedTradingLogger(component)
    context = TradingContext(
        user_id=user_id,
        symbol=symbol,
        amount=amount,
    )
    logger.log_risk_event(context, risk_type, AlertSeverity.HIGH, details)


def log_user_login(user_id: str, ip_address: str = None, user_agent: str = None,
                  success: bool = True, component: str = "authentication"):
    """Convenience function to log user login events."""
    logger = EnhancedTradingLogger(component)
    context = TradingContext(
        user_id=user_id,
        metadata={
            'ip_address': ip_address,
            'user_agent': user_agent,
            'success': success
        }
    )

    if success:
        logger.log_user_activity(context, 'login', f"User {user_id} logged in successfully")
    else:
        logger.log_security_event(
            'failed_login',
            f"Failed login attempt for user {user_id}",
            AlertSeverity.MEDIUM,
            context
        )


def log_market_data_processing(symbol: str, latency_ms: float, records_processed: int,
                              component: str = "market_data"):
    """Convenience function to log market data processing."""
    logger = EnhancedTradingLogger(component)
    context = TradingContext(
        symbol=symbol,
        latency_ms=latency_ms,
        throughput=records_processed / (latency_ms / 1000) if latency_ms > 0 else 0,
        metadata={'records_processed': records_processed}
    )

    logger.log_market_data_event(context, 'processed')
    logger.log_performance_metric(
        f"market_data_processing_{symbol}",
        latency_ms,
        context,
        threshold_ms=100  # Market data should be fast
    )


# Decorator for automatic trading operation logging
def log_trading_operation(event_type: TradingEventType, component: str = "trading_app"):
    """Decorator to automatically log trading operations."""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = EnhancedTradingLogger(component)
            start_time = time.perf_counter()

            # Extract trading context from function arguments if available
            context = TradingContext()

            # Try to extract common parameters
            if 'user_id' in kwargs:
                context.user_id = kwargs['user_id']
            if 'symbol' in kwargs:
                context.symbol = kwargs['symbol']
            if 'order_id' in kwargs:
                context.order_id = kwargs['order_id']

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                context.latency_ms = duration_ms

                logger.log_trading_event(
                    event_type,
                    f"Operation {func.__name__} completed successfully",
                    context,
                    level="INFO"
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                context.latency_ms = duration_ms
                context.reason = f"error_{type(e).__name__}"

                logger.log_trading_event(
                    TradingEventType.SYSTEM_ERROR,
                    f"Operation {func.__name__} failed: {str(e)}",
                    context,
                    level="ERROR",
                    alert_severity=AlertSeverity.HIGH
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = EnhancedTradingLogger(component)
            start_time = time.perf_counter()

            context = TradingContext()

            if 'user_id' in kwargs:
                context.user_id = kwargs['user_id']
            if 'symbol' in kwargs:
                context.symbol = kwargs['symbol']
            if 'order_id' in kwargs:
                context.order_id = kwargs['order_id']

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                context.latency_ms = duration_ms

                logger.log_trading_event(
                    event_type,
                    f"Operation {func.__name__} completed successfully",
                    context,
                    level="INFO"
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                context.latency_ms = duration_ms
                context.reason = f"error_{type(e).__name__}"

                logger.log_trading_event(
                    TradingEventType.SYSTEM_ERROR,
                    f"Operation {func.__name__} failed: {str(e)}",
                    context,
                    level="ERROR",
                    alert_severity=AlertSeverity.HIGH
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Context manager for automatic trace context management
class TradingOperationContext:
    """Context manager for trading operations with automatic tracing."""

    def __init__(self, operation_name: str, user_id: str = None,
                 correlation_id: str = None, component: str = "trading_app"):
        self.operation_name = operation_name
        self.user_id = user_id
        self.correlation_id = correlation_id
        self.component = component
        self.logger = EnhancedTradingLogger(component)
        self.start_time = None
        self.trace_context = None

    def __enter__(self):
        self.start_time = time.perf_counter()

        # Set distributed trace context
        self.trace_context = set_distributed_trace_context(
            correlation_id=self.correlation_id,
            user_id=self.user_id
        )

        # Log operation start
        context = TradingContext(
            user_id=self.user_id,
            reason=f"operation_started_{self.operation_name}"
        )

        self.logger.log_system_event(
            'operation_start',
            f"Started operation: {self.operation_name}",
            context=context
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000

        context = TradingContext(
            user_id=self.user_id,
            latency_ms=duration_ms,
            reason=f"operation_completed_{self.operation_name}"
        )

        if exc_type is None:
            # Operation completed successfully
            self.logger.log_system_event(
                'operation_complete',
                f"Completed operation: {self.operation_name} in {duration_ms:.1f}ms",
                context=context
            )
        else:
            # Operation failed
            context.reason = f"operation_failed_{self.operation_name}_{exc_type.__name__}"
            context.metadata = {
                'error_type': exc_type.__name__,
                'error_message': str(exc_val),
                'traceback': traceback.format_exc()
            }

            self.logger.log_system_event(
                'error',
                f"Operation {self.operation_name} failed: {str(exc_val)}",
                alert_severity=AlertSeverity.HIGH,
                context=context
            )


# Global logger instances for common use cases
trading_logger = EnhancedTradingLogger("trading_engine")
order_logger = EnhancedTradingLogger("order_management")
risk_logger = EnhancedTradingLogger("risk_management")
market_data_logger = EnhancedTradingLogger("market_data")
user_logger = EnhancedTradingLogger("user_management")
system_logger = EnhancedTradingLogger("system")