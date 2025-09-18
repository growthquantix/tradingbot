"""
Performance Logging System for Trading Operations

This module provides comprehensive performance monitoring and logging
for critical trading system operations including latency tracking,
throughput monitoring, and system performance metrics.
"""

import time
import asyncio
import functools
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager, contextmanager
from core.logging_config import get_performance_logger, get_correlation_id


@dataclass
class PerformanceMetrics:
    """Performance metrics for an operation."""
    operation_name: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: Optional[str] = None
    correlation_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.duration_ms / 1000.0


class PerformanceLogger:
    """Performance logger for trading operations."""

    def __init__(self):
        self.logger = get_performance_logger()
        self.operation_counts = {}
        self.latency_buckets = {
            'sub_1ms': 0,
            '1_10ms': 0,
            '10_100ms': 0,
            '100ms_1s': 0,
            'over_1s': 0
        }

    def _categorize_latency(self, duration_ms: float) -> str:
        """Categorize latency into buckets."""
        if duration_ms < 1:
            return 'sub_1ms'
        elif duration_ms < 10:
            return '1_10ms'
        elif duration_ms < 100:
            return '10_100ms'
        elif duration_ms < 1000:
            return '100ms_1s'
        else:
            return 'over_1s'

    def log_performance(self, metrics: PerformanceMetrics) -> None:
        """Log performance metrics."""
        # Update counters
        self.operation_counts[metrics.operation_name] = (
            self.operation_counts.get(metrics.operation_name, 0) + 1
        )

        latency_bucket = self._categorize_latency(metrics.duration_ms)
        self.latency_buckets[latency_bucket] += 1

        # Prepare log data
        log_data = {
            'operation': metrics.operation_name,
            'duration_ms': round(metrics.duration_ms, 3),
            'duration_seconds': round(metrics.duration_seconds, 6),
            'success': metrics.success,
            'timestamp': datetime.utcnow().isoformat(),
            'latency_bucket': latency_bucket,
        }

        if metrics.correlation_id:
            log_data['correlation_id'] = metrics.correlation_id
        if metrics.error:
            log_data['error'] = metrics.error
        if metrics.additional_data:
            log_data.update(metrics.additional_data)

        # Log with appropriate level based on performance
        if metrics.duration_ms > 1000:  # Over 1 second
            self.logger.warning(
                f"SLOW_OPERATION: {metrics.operation_name} took {metrics.duration_ms:.2f}ms",
                extra=log_data
            )
        elif metrics.duration_ms > 100:  # Over 100ms
            self.logger.info(
                f"PERFORMANCE: {metrics.operation_name} took {metrics.duration_ms:.2f}ms",
                extra=log_data
            )
        else:
            self.logger.debug(
                f"PERFORMANCE: {metrics.operation_name} took {metrics.duration_ms:.2f}ms",
                extra=log_data
            )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        return {
            'operation_counts': self.operation_counts.copy(),
            'latency_distribution': self.latency_buckets.copy(),
            'timestamp': datetime.utcnow().isoformat()
        }

    @contextmanager
    def time_operation(
        self,
        operation_name: str,
        **additional_data
    ):
        """Context manager for timing operations."""
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        success = True
        error = None

        try:
            yield
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                success=success,
                error=error,
                correlation_id=correlation_id,
                additional_data=additional_data
            )
            self.log_performance(metrics)

    @asynccontextmanager
    async def time_async_operation(
        self,
        operation_name: str,
        **additional_data
    ):
        """Async context manager for timing operations."""
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        success = True
        error = None

        try:
            yield
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                success=success,
                error=error,
                correlation_id=correlation_id,
                additional_data=additional_data
            )
            self.log_performance(metrics)

    def performance_decorator(
        self,
        operation_name: Optional[str] = None,
        **additional_data
    ):
        """Decorator for automatic performance logging."""
        def decorator(func: Callable) -> Callable:
            nonlocal operation_name
            if operation_name is None:
                operation_name = f"{func.__module__}.{func.__name__}"

            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    async with self.time_async_operation(operation_name, **additional_data):
                        return await func(*args, **kwargs)
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.time_operation(operation_name, **additional_data):
                        return func(*args, **kwargs)
                return sync_wrapper

        return decorator


# Trading-specific performance logging functions
class TradingPerformanceLogger(PerformanceLogger):
    """Enhanced performance logger for trading operations."""

    def log_order_latency(
        self,
        operation: str,
        duration_ms: float,
        symbol: str,
        order_type: str,
        broker: str = None,
        success: bool = True,
        error: str = None
    ) -> None:
        """Log order-related operation latency."""
        additional_data = {
            'symbol': symbol,
            'order_type': order_type,
            'category': 'order_management'
        }

        if broker:
            additional_data['broker'] = broker

        metrics = PerformanceMetrics(
            operation_name=f"order.{operation}",
            start_time=0,  # Not used for manual logging
            end_time=0,    # Not used for manual logging
            duration_ms=duration_ms,
            success=success,
            error=error,
            correlation_id=get_correlation_id(),
            additional_data=additional_data
        )

        self.log_performance(metrics)

        # Alert on high-latency order operations
        if duration_ms > 500:  # 500ms threshold for order operations
            self.logger.warning(
                f"HIGH_LATENCY_ORDER: {operation} for {symbol} took {duration_ms:.2f}ms",
                extra={
                    'operation': operation,
                    'symbol': symbol,
                    'duration_ms': duration_ms,
                    'threshold_exceeded': True,
                    'category': 'order_management'
                }
            )

    def log_market_data_latency(
        self,
        operation: str,
        duration_ms: float,
        symbol_count: int = None,
        data_size_bytes: int = None,
        broker: str = None
    ) -> None:
        """Log market data processing latency."""
        additional_data = {
            'category': 'market_data'
        }

        if symbol_count:
            additional_data['symbol_count'] = symbol_count
        if data_size_bytes:
            additional_data['data_size_bytes'] = data_size_bytes
        if broker:
            additional_data['broker'] = broker

        metrics = PerformanceMetrics(
            operation_name=f"market_data.{operation}",
            start_time=0,
            end_time=0,
            duration_ms=duration_ms,
            success=True,
            correlation_id=get_correlation_id(),
            additional_data=additional_data
        )

        self.log_performance(metrics)

        # Alert on high-latency market data operations
        if duration_ms > 50:  # 50ms threshold for market data
            self.logger.warning(
                f"HIGH_LATENCY_MARKET_DATA: {operation} took {duration_ms:.2f}ms",
                extra={
                    'operation': operation,
                    'duration_ms': duration_ms,
                    'threshold_exceeded': True,
                    'category': 'market_data'
                }
            )

    def log_database_query(
        self,
        query_type: str,
        duration_ms: float,
        table_name: str = None,
        row_count: int = None,
        success: bool = True,
        error: str = None
    ) -> None:
        """Log database query performance."""
        additional_data = {
            'category': 'database'
        }

        if table_name:
            additional_data['table_name'] = table_name
        if row_count:
            additional_data['row_count'] = row_count

        metrics = PerformanceMetrics(
            operation_name=f"database.{query_type}",
            start_time=0,
            end_time=0,
            duration_ms=duration_ms,
            success=success,
            error=error,
            correlation_id=get_correlation_id(),
            additional_data=additional_data
        )

        self.log_performance(metrics)

        # Alert on slow database queries
        if duration_ms > 1000:  # 1 second threshold
            self.logger.warning(
                f"SLOW_DATABASE_QUERY: {query_type} took {duration_ms:.2f}ms",
                extra={
                    'query_type': query_type,
                    'table_name': table_name,
                    'duration_ms': duration_ms,
                    'threshold_exceeded': True,
                    'category': 'database'
                }
            )

    def log_websocket_latency(
        self,
        operation: str,
        duration_ms: float,
        message_size: int = None,
        connection_count: int = None,
        broker: str = None
    ) -> None:
        """Log WebSocket operation latency."""
        additional_data = {
            'category': 'websocket'
        }

        if message_size:
            additional_data['message_size'] = message_size
        if connection_count:
            additional_data['connection_count'] = connection_count
        if broker:
            additional_data['broker'] = broker

        metrics = PerformanceMetrics(
            operation_name=f"websocket.{operation}",
            start_time=0,
            end_time=0,
            duration_ms=duration_ms,
            success=True,
            correlation_id=get_correlation_id(),
            additional_data=additional_data
        )

        self.log_performance(metrics)

    def log_api_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
        user_id: str = None,
        request_size: int = None,
        response_size: int = None
    ) -> None:
        """Log API request performance."""
        additional_data = {
            'category': 'api',
            'method': method,
            'status_code': status_code
        }

        if user_id:
            additional_data['user_id'] = user_id
        if request_size:
            additional_data['request_size'] = request_size
        if response_size:
            additional_data['response_size'] = response_size

        success = 200 <= status_code < 400

        metrics = PerformanceMetrics(
            operation_name=f"api.{endpoint}",
            start_time=0,
            end_time=0,
            duration_ms=duration_ms,
            success=success,
            correlation_id=get_correlation_id(),
            additional_data=additional_data
        )

        self.log_performance(metrics)

        # Alert on slow API requests
        if duration_ms > 2000:  # 2 second threshold
            self.logger.warning(
                f"SLOW_API_REQUEST: {method} {endpoint} took {duration_ms:.2f}ms",
                extra={
                    'endpoint': endpoint,
                    'method': method,
                    'duration_ms': duration_ms,
                    'status_code': status_code,
                    'threshold_exceeded': True,
                    'category': 'api'
                }
            )


# Global performance logger instance
performance_logger = TradingPerformanceLogger()

# Convenience decorators
def time_trading_operation(operation_name: str = None, **additional_data):
    """Decorator for timing trading operations."""
    return performance_logger.performance_decorator(operation_name, **additional_data)


def log_order_latency(operation: str, **kwargs):
    """Log order operation latency."""
    return performance_logger.log_order_latency(operation, **kwargs)


def log_market_data_latency(operation: str, **kwargs):
    """Log market data operation latency."""
    return performance_logger.log_market_data_latency(operation, **kwargs)