"""
Enhanced Logger Utilities for Trading System

This module provides enhanced logging utilities with proper configuration,
structured logging, correlation IDs, and trading-specific logging patterns.

REPLACED: Basic console-only logging
ADDED: Comprehensive enterprise-grade logging system
"""

import logging
import os
from core.fixed_logging_config import (
    setup_fixed_logging,
    get_fixed_logger,
    set_trace_context,
    get_trace_context,
    timed_operation
)
from core.audit_logger import audit_logger, AuditEventType
from core.performance_logger import performance_logger, time_trading_operation

# Initialize fixed logging system
setup_fixed_logging(os.getenv('ENVIRONMENT', 'development'))

# Main application logger
main_logger = get_fixed_logger('trading_app')

# Specialized loggers
websocket_logger = get_fixed_logger('websocket', component='websocket')
database_logger = get_fixed_logger('database', component='database')
security_logger = get_fixed_logger('security', component='security')
audit_log = get_fixed_logger('audit', component='audit')
performance_log = get_fixed_logger('performance', component='performance')


def get_trading_logger(component: str = 'general', **context):
    """
    Get a trading-specific logger with context.

    Args:
        component: Component name (broker, websocket, database, etc.)
        **context: Additional context to include in logs

    Returns:
        Logger instance with trading context
    """
    return get_fixed_logger(component, component=component, **context)


def log_trade_execution(
    user_id: str,
    order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    broker: str = None
):
    """
    Log trade execution with proper audit trail.

    Args:
        user_id: User identifier
        order_id: Order identifier
        symbol: Trading symbol
        side: buy/sell
        quantity: Quantity traded
        price: Execution price
        broker: Broker name
    """
    from decimal import Decimal

    # Log to audit trail
    audit_logger.log_order_executed(
        user_id=user_id,
        order_id=order_id,
        trade_id=f"trade_{order_id}",
        symbol=symbol,
        side=side,
        quantity=Decimal(str(quantity)),
        executed_price=Decimal(str(price)),
        commission=Decimal('0'),  # Should be calculated
        broker=broker
    )

    # Log to main logger
    main_logger.info(
        f"Trade executed: {side} {quantity} {symbol} @ {price}",
        extra={
            'user_id': user_id,
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'broker': broker,
            'event_type': 'trade_execution'
        }
    )


def log_market_data_update(symbol: str, price: float, volume: int = None, broker: str = None):
    """
    Log market data updates with proper context.

    Args:
        symbol: Trading symbol
        price: Current price
        volume: Trading volume
        broker: Data source broker
    """
    websocket_logger.debug(
        f"Market data update: {symbol} @ {price}",
        extra={
            'symbol': symbol,
            'price': price,
            'volume': volume,
            'broker': broker,
            'event_type': 'market_data_update'
        }
    )


def log_user_activity(user_id: str, activity: str, details: dict = None):
    """
    Log user activity with security context.

    Args:
        user_id: User identifier
        activity: Activity description
        details: Additional activity details
    """
    security_logger.info(
        f"User activity: {activity}",
        extra={
            'user_id': user_id,
            'activity': activity,
            'details': details or {},
            'event_type': 'user_activity'
        }
    )


def log_system_error(error: Exception, context: dict = None):
    """
    Log system errors with proper context and error tracking.

    Args:
        error: Exception object
        context: Additional error context
    """
    main_logger.error(
        f"System error: {str(error)}",
        extra={
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'event_type': 'system_error'
        },
        exc_info=True
    )


def log_performance_metric(operation: str, duration_ms: float, success: bool = True, **kwargs):
    """
    Log performance metrics.

    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        success: Whether operation was successful
        **kwargs: Additional performance data
    """
    performance_logger.log_performance(
        operation_name=operation,
        duration_ms=duration_ms,
        success=success,
        additional_data=kwargs
    )


# Backward compatibility
def setup_console_logging():
    """Backward compatibility - now uses comprehensive logging."""
    main_logger.info("✅ Comprehensive logging system active")


# Export commonly used functions and classes
__all__ = [
    'get_trading_logger',
    'log_trade_execution',
    'log_market_data_update',
    'log_user_activity',
    'log_system_error',
    'log_performance_metric',
    'main_logger',
    'websocket_logger',
    'database_logger',
    'security_logger',
    'audit_log',
    'performance_log',
    'audit_logger',
    'performance_logger',
    'time_trading_operation',
    'set_correlation_id',
    'get_correlation_id',
    'with_correlation_id',
    'AuditEventType'
]