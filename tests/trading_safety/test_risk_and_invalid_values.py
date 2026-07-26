"""
Boundary Tests for Risk Invariants and Invalid Value Rejection
"""
import pytest
import math

def validate_risk_parameters(capital: float, entry_price: float, stop_loss: float, lot_size: int) -> bool:
    """Validate risk invariants; fail closed if values are non-positive, NaN, or Inf."""
    if math.isnan(capital) or math.isnan(entry_price) or math.isnan(stop_loss):
        return False
    if math.isinf(capital) or math.isinf(entry_price) or math.isinf(stop_loss):
        return False
    if capital <= 0 or entry_price <= 0 or stop_loss <= 0 or lot_size <= 0:
        return False
    if stop_loss >= entry_price:
        return False  # For long option buy, SL must be below entry price
    return True

def test_risk_invariants_valid():
    assert validate_risk_parameters(capital=100000.0, entry_price=100.0, stop_loss=85.0, lot_size=25)

def test_risk_invariants_invalid_stop():
    assert not validate_risk_parameters(capital=100000.0, entry_price=100.0, stop_loss=105.0, lot_size=25)

def test_risk_invariants_nan():
    assert not validate_risk_parameters(capital=float('nan'), entry_price=100.0, stop_loss=85.0, lot_size=25)
