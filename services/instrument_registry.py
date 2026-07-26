"""
Instrument Registry Bridge Module
Centralized instrument registry access for live market analytics, heatmap, and strategy services.
"""
from services.trading_execution.shared_instrument_registry import (
    SharedInstrumentRegistry as InstrumentRegistry,
    shared_instrument_registry as instrument_registry,
)

__all__ = ["InstrumentRegistry", "instrument_registry"]
