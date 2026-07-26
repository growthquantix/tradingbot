"""
Boundary Tests for Order Fills, Weighted Average Entry Price, and ACK vs FILL Gating
"""
import pytest
from decimal import Decimal
from services.trading_execution.order_lifecycle_service import (
    OrderLifecycleService, OrderState
)

def test_ack_is_not_fill():
    service = OrderLifecycleService()
    intent_id = service.create_trade_intent(user_id=1, symbol="RELIANCE", option_type="CE", quantity=500)
    
    # Valid transition path: CREATED -> VALIDATED -> SUBMITTING -> SUBMITTED -> ACKNOWLEDGED
    assert service.transition_state(intent_id, OrderState.VALIDATED)
    assert service.transition_state(intent_id, OrderState.SUBMITTING)
    assert service.transition_state(intent_id, OrderState.SUBMITTED)
    assert service.transition_state(intent_id, OrderState.ACKNOWLEDGED)
    
    # ACKNOWLEDGED state must NOT be treated as confirmed fill
    assert not service.is_fill_confirmed(intent_id)
    assert service.order_states[intent_id] == OrderState.ACKNOWLEDGED

def test_multiple_partial_fills_and_weighted_average():
    service = OrderLifecycleService()
    intent_id = service.create_trade_intent(user_id=1, symbol="RELIANCE", option_type="CE", quantity=500)
    
    # Valid transition path to ACKNOWLEDGED
    service.transition_state(intent_id, OrderState.VALIDATED)
    service.transition_state(intent_id, OrderState.SUBMITTING)
    service.transition_state(intent_id, OrderState.SUBMITTED)
    service.transition_state(intent_id, OrderState.ACKNOWLEDGED)

    # Fill #1: 100 @ ₹100
    fill1 = {"qty": 100, "price": Decimal("100.00")}
    # Fill #2: 150 @ ₹101
    fill2 = {"qty": 150, "price": Decimal("101.00")}
    # Fill #3: 250 @ ₹102
    fill3 = {"qty": 250, "price": Decimal("102.00")}

    fills = [fill1, fill2, fill3]
    total_qty = sum(f["qty"] for f in fills)
    total_cost = sum(f["qty"] * f["price"] for f in fills)
    weighted_avg_price = total_cost / Decimal(str(total_qty))

    assert total_qty == 500
    assert weighted_avg_price == Decimal("101.30")  # (10000 + 15150 + 25500) / 500 = 50650 / 500 = 101.30

    service.transition_state(intent_id, OrderState.FILLED)
    service.record_fill(intent_id, "BROKER_ORDER_500", total_qty, weighted_avg_price)

    assert service.is_fill_confirmed(intent_id)
    recorded = service.order_fills[intent_id]
    assert recorded["filled_qty"] == 500
    assert recorded["fill_price"] == 101.30
