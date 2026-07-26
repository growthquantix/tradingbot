"""
Unit & Safety Tests for Instrument Validation & Liquidity Gating
"""
import pytest
from datetime import datetime, timedelta

def validate_instrument_for_trade(instrument: dict) -> bool:
    """
    Validate instrument parameters before order dispatch.
    Returns False if instrument is expired, missing keys, invalid lot size, or has extreme bid/ask spread.
    """
    if not instrument or not instrument.get("instrument_key"):
        return False
    
    # Check lot size
    lot_size = instrument.get("lot_size", 0)
    if lot_size <= 0:
        return False

    # Check expiry
    expiry_str = instrument.get("expiry_date")
    if expiry_str:
        try:
            exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            if exp_date < datetime.now().date():
                return False  # Expired contract
        except ValueError:
            pass

    # Liquidity check (spread)
    bid = instrument.get("bid_price", 0.0)
    ask = instrument.get("ask_price", 0.0)
    if bid > 0 and ask > 0:
        midpoint = (bid + ask) / 2.0
        spread_pct = (ask - bid) / midpoint
        if spread_pct > 0.20:  # > 20% spread is illiquid
            return False

    return True

def test_instrument_validation_valid():
    inst = {
        "instrument_key": "NSE_FO|54321",
        "lot_size": 25,
        "expiry_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
        "bid_price": 100.0,
        "ask_price": 102.0
    }
    assert validate_instrument_for_trade(inst)

def test_instrument_validation_expired():
    inst = {
        "instrument_key": "NSE_FO|54321",
        "lot_size": 25,
        "expiry_date": "2020-01-01",
        "bid_price": 100.0,
        "ask_price": 102.0
    }
    assert not validate_instrument_for_trade(inst)

def test_instrument_validation_extreme_spread():
    inst = {
        "instrument_key": "NSE_FO|54321",
        "lot_size": 25,
        "expiry_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
        "bid_price": 50.0,
        "ask_price": 100.0  # 66.6% spread
    }
    assert not validate_instrument_for_trade(inst)
