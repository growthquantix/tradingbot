"""
Auto Trading Module

Modular auto trading system with complete Kafka integration.
Implements clean architecture principles with proper separation of concerns.

Author: Trading System
Created: 2025-01-11
"""

from .kafka_strategy_executor import (
    KafkaStrategyExecutor,
    AutoTradingMode,
    ExecutionPhase,
    TradingSession,
    get_kafka_strategy_executor
)

from .modular_stock_selector import (
    get_modular_stock_selector,
    StockSelectionConfig,
    MarketCondition
)

from .execution_engine import (
    get_auto_trade_execution_engine,
    TradeDirection,
    PositionStatus
)

from .position_monitor import (
    AutoTradingPositionMonitor,
    get_position_monitor
)

from .pnl_calculator import (
    PnLCalculator,
    get_pnl_calculator
)

from .risk_manager import (
    AutoTradingRiskManager,
    get_risk_manager
)

__all__ = [
    "KafkaStrategyExecutor",
    "AutoTradingMode",
    "ExecutionPhase", 
    "TradingSession",
    "get_kafka_strategy_executor",
    "get_modular_stock_selector",
    "StockSelectionConfig",
    "MarketCondition",
    "get_auto_trade_execution_engine",
    "TradeDirection",
    "PositionStatus",
    "AutoTradingPositionMonitor",
    "get_position_monitor",
    "PnLCalculator",
    "get_pnl_calculator", 
    "AutoTradingRiskManager",
    "get_risk_manager"
]