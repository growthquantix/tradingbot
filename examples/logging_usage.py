"""
Logging Usage Examples for Trading System

This file demonstrates how to use the comprehensive logging system
in your trading application with real-world examples.
"""

import asyncio
from decimal import Decimal
from datetime import datetime
from utils.logger import (
    get_trading_logger,
    log_trade_execution,
    log_market_data_update,
    log_user_activity,
    log_system_error,
    log_performance_metric,
    audit_logger,
    performance_logger,
    time_trading_operation,
    set_correlation_id,
    AuditEventType
)


# Example 1: Basic logging with context
def example_basic_logging():
    """Demonstrate basic logging with trading context."""
    # Get specialized loggers
    broker_logger = get_trading_logger('broker', broker='upstox')
    websocket_logger = get_trading_logger('websocket')
    database_logger = get_trading_logger('database')

    # Log different types of events
    broker_logger.info("Connected to Upstox API", extra={'connection_status': 'active'})
    websocket_logger.info("Market data stream started", extra={'symbol_count': 50})
    database_logger.warning("Slow query detected", extra={'query_time_ms': 1500})


# Example 2: Trade execution logging with audit trail
def example_trade_logging():
    """Demonstrate trade execution logging."""
    # Set correlation ID for request tracking
    correlation_id = set_correlation_id("trade_req_001")

    # Log trade execution (automatically creates audit trail)
    log_trade_execution(
        user_id="user123",
        order_id="ORD_001",
        symbol="RELIANCE",
        side="buy",
        quantity=100,
        price=2450.50,
        broker="upstox"
    )

    # Manual audit logging for complex scenarios
    audit_logger.log_order_placed(
        user_id="user123",
        order_id="ORD_002",
        symbol="TCS",
        side="sell",
        quantity=Decimal('50'),
        price=Decimal('3200.00'),
        order_type="limit",
        broker="upstox",
        strategy_name="momentum_breakout"
    )


# Example 3: Performance monitoring
@time_trading_operation('order_placement')
async def place_order_with_monitoring(symbol: str, quantity: int, price: float):
    """Example function with automatic performance monitoring."""
    # Simulate order placement
    await asyncio.sleep(0.1)  # Simulate API call

    # Manual performance logging
    start_time = datetime.now()

    # Simulate database operation
    await asyncio.sleep(0.05)

    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
    log_performance_metric(
        operation='database_insert',
        duration_ms=duration_ms,
        table='orders',
        record_count=1
    )

    return {"status": "success", "order_id": "ORD_003"}


# Example 4: Market data logging
def example_market_data_logging():
    """Demonstrate market data logging."""
    # Log market data updates
    symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK"]

    for symbol in symbols:
        log_market_data_update(
            symbol=symbol,
            price=2450.50,
            volume=150000,
            broker="upstox"
        )


# Example 5: Error handling with proper logging
async def example_error_handling():
    """Demonstrate error handling with comprehensive logging."""
    try:
        # Simulate an operation that might fail
        result = await risky_trading_operation()
        return result
    except ValueError as e:
        log_system_error(
            error=e,
            context={
                'operation': 'risk_calculation',
                'symbol': 'RELIANCE',
                'user_id': 'user123'
            }
        )
        raise
    except Exception as e:
        log_system_error(
            error=e,
            context={'operation': 'unknown_trading_operation'}
        )
        raise


async def risky_trading_operation():
    """Simulate a risky operation that might fail."""
    # Simulate random failure
    import random
    if random.random() < 0.3:
        raise ValueError("Invalid trading parameters")
    return {"status": "success"}


# Example 6: User activity logging
def example_user_activity():
    """Demonstrate user activity logging."""
    # Log user login
    log_user_activity(
        user_id="user123",
        activity="login",
        details={
            'login_method': 'password',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0...'
        }
    )

    # Log trading activity
    log_user_activity(
        user_id="user123",
        activity="portfolio_view",
        details={'symbols_viewed': ['RELIANCE', 'TCS']}
    )

    # Log security-sensitive activity
    log_user_activity(
        user_id="user123",
        activity="api_key_generated",
        details={'key_permissions': ['read_portfolio', 'place_orders']}
    )


# Example 7: Advanced audit logging
def example_advanced_audit():
    """Demonstrate advanced audit logging scenarios."""
    # Log risk limit exceeded
    audit_logger.log_risk_limit_exceeded(
        user_id="user123",
        limit_type="daily_loss",
        limit_value=Decimal('10000'),
        current_value=Decimal('12000'),
        action_taken="trading_disabled"
    )

    # Log suspicious activity
    audit_logger.log_suspicious_activity(
        user_id="user456",
        activity_type="rapid_trading",
        description="100+ orders in 5 minutes",
        risk_score=85
    )

    # Log system events
    audit_logger.log_system_event(
        event_type=AuditEventType.SYSTEM_START,
        description="Trading system startup completed",
        startup_duration_seconds=45
    )


# Example 8: WebSocket performance monitoring
async def example_websocket_performance():
    """Demonstrate WebSocket-specific performance monitoring."""
    # Monitor WebSocket operations
    async with performance_logger.time_async_operation(
        'websocket_message_processing',
        message_type='market_data',
        symbol_count=100
    ):
        # Simulate message processing
        await asyncio.sleep(0.02)  # 20ms processing time

    # Log WebSocket latency
    performance_logger.log_websocket_latency(
        operation='market_data_broadcast',
        duration_ms=15.5,
        message_size=2048,
        connection_count=50,
        broker='upstox'
    )


# Example 9: Database operation logging
def example_database_logging():
    """Demonstrate database operation logging."""
    db_logger = get_trading_logger('database', table='trades')

    # Log database operations
    db_logger.info(
        "Executing trade query",
        extra={
            'query_type': 'SELECT',
            'table': 'trades',
            'user_id': 'user123',
            'filter_criteria': {'symbol': 'RELIANCE', 'date': '2025-01-15'}
        }
    )

    # Log slow query
    performance_logger.log_database_query(
        query_type='complex_join',
        duration_ms=1250,
        table_name='trades_with_portfolio',
        row_count=5000,
        success=True
    )


# Example 10: Correlation ID tracking across services
async def example_correlation_tracking():
    """Demonstrate correlation ID tracking across multiple operations."""
    # Set correlation ID at the start of request
    correlation_id = set_correlation_id("user_trade_flow_001")

    # All subsequent logging will include this correlation ID
    logger = get_trading_logger('general')
    logger.info("Starting trade flow", extra={'user_id': 'user123'})

    # Call multiple services
    await validate_order()
    await execute_trade()
    await update_portfolio()

    logger.info("Trade flow completed")


async def validate_order():
    """Simulate order validation."""
    logger = get_trading_logger('general')
    logger.info("Order validation started")
    await asyncio.sleep(0.1)
    logger.info("Order validation completed")


async def execute_trade():
    """Simulate trade execution."""
    logger = get_trading_logger('broker', broker='upstox')
    logger.info("Trade execution started")
    await asyncio.sleep(0.2)
    logger.info("Trade execution completed")


async def update_portfolio():
    """Simulate portfolio update."""
    logger = get_trading_logger('database')
    logger.info("Portfolio update started")
    await asyncio.sleep(0.05)
    logger.info("Portfolio update completed")


# Main execution
async def main():
    """Run all logging examples."""
    print("🚀 Trading System Logging Examples")
    print("=" * 50)

    # Run examples
    example_basic_logging()
    example_trade_logging()
    await place_order_with_monitoring("RELIANCE", 100, 2450.50)
    example_market_data_logging()
    example_user_activity()
    example_advanced_audit()
    await example_websocket_performance()
    example_database_logging()
    await example_correlation_tracking()

    # Show performance summary
    summary = performance_logger.get_performance_summary()
    print(f"\n📊 Performance Summary: {summary}")

    print("\n✅ All logging examples completed!")
    print("Check the logs/ directory for generated log files:")
    print("  - trading_app.log (Main application logs)")
    print("  - audit.log (Financial audit trail)")
    print("  - performance.log (Performance metrics)")
    print("  - errors.log (Error logs)")


if __name__ == "__main__":
    asyncio.run(main())