"""
Stock Selection Module

Modular stock selection services with Kafka integration.
Implements clean separation of concerns for stock screening and selection.

Author: Trading System
Created: 2025-01-11
"""

from .real_time_stock_selector import (
    RealTimeStockSelector, 
    SelectionCriteria, 
    StockScore,
    get_stock_selector
)

__all__ = [
    "RealTimeStockSelector",
    "SelectionCriteria", 
    "StockScore",
    "get_stock_selector"
]