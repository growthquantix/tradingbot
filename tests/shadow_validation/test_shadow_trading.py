"""
Unit & Safety Tests for Phase-6 Real-Market Shadow Trading Service
"""
import pytest
from datetime import datetime
from decimal import Decimal
from services.trading_execution.capital_manager import TradingMode
from services.trading_execution.trade_prep import PreparedTrade, TradeStatus
from services.trading_execution.execution_handler import TradeExecutionHandler
from services.validation.shadow_trading_service import shadow_trading_service, BASELINE_VERSION

def test_shadow_mode_order_interception_safety():
    """Verify that SHADOW mode blocks broker order placement with 0 real orders dispatched."""
    handler = TradeExecutionHandler()
    
    prep_trade = PreparedTrade(
        status=TradeStatus.READY,
        stock_symbol="RELIANCE",
        option_instrument_key="NSE_FO|54321",
        option_type="CE",
        strike_price=Decimal("2850.0"),
        expiry_date="2026-07-30",
        current_premium=Decimal("120.50"),
        lot_size=25,
        signal={"signal_type": "BUY"},
        capital_allocation=None,
        risk_reward_ratio=Decimal("2.0"),
        entry_price=Decimal("2850.0"),
        stop_loss=Decimal("100.0"),
        target_price=Decimal("150.0"),
        trailing_stop_config={},
        position_size_lots=2,
        total_investment=Decimal("6025.0"),
        max_loss_amount=Decimal("1025.0"),
        trading_mode="shadow",
        broker_name="Upstox",
        user_id=1,
        prepared_at="2026-07-25T12:00:00",
        valid_until="2026-07-25T12:15:00",
        metadata={"signal_confidence": 0.85}
    )

    result = handler.execute_trade(prep_trade, db=None)
    assert result.success
    assert result.status == "SHADOW_RECORDED"
    assert result.order_id is None  # Zero broker orders placed

def test_market_open_gate_off_market_invalidation():
    """Verify that off-market execution marks session_valid = False and SESSION_INVALID_MARKET_CLOSED."""
    is_open, status = shadow_trading_service.check_market_open_gate()
    now = datetime.now()
    if now.weekday() >= 5 or now.hour < 9 or now.hour >= 16:
        assert not is_open
        assert status == "SESSION_INVALID_MARKET_CLOSED"
        assert not shadow_trading_service.session_valid

def test_transaction_cost_calculation():
    """Verify Indian F&O option trading cost calculations."""
    costs = shadow_trading_service.calculate_transaction_costs(entry_price=100.0, exit_price=120.0, quantity=250)
    assert costs["gross_pnl"] == 5000.0
    assert costs["brokerage"] == 40.0
    assert costs["stt"] == 30.0  # 0.1% of 30,000 sell val = 30
    assert costs["net_pnl"] < 5000.0

def test_forward_outcomes_and_mfe_mae():
    """Verify forward return horizons (+1m to +30m) and MFE/MAE calculations."""
    future_prices = [100.0, 105.0, 110.0, 108.0, 115.0, 120.0]
    outcomes = shadow_trading_service.evaluate_forward_outcomes("SHADOW_TEST_1", future_prices)

    assert outcomes["mfe_pct"] == 20.0  # max 120 vs entry 100 -> +20%
    assert outcomes["mae_pct"] == 0.0   # min 100 vs entry 100 -> 0%
    assert outcomes["forward_returns"]["1m"] == 5.0
    assert outcomes["baseline_version"] == BASELINE_VERSION
