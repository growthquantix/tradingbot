"""
Unit & Safety Tests for Order Lifecycle & State Machine
"""
import pytest
from decimal import Decimal
from services.trading_execution.order_lifecycle_service import (
    OrderLifecycleService, OrderState
)

def test_order_state_machine_valid_flow():
    service = OrderLifecycleService()
    intent_id = service.create_trade_intent(user_id=1, symbol="RELIANCE", option_type="CE", quantity=250)
    
    assert service.order_states[intent_id] == OrderState.CREATED
    assert not service.is_fill_confirmed(intent_id)

    assert service.transition_state(intent_id, OrderState.VALIDATED)
    assert service.transition_state(intent_id, OrderState.SUBMITTING)
    assert service.transition_state(intent_id, OrderState.SUBMITTED)
    assert service.transition_state(intent_id, OrderState.ACKNOWLEDGED)
    
    # ACKNOWLEDGED is not a confirmed fill
    assert not service.is_fill_confirmed(intent_id)

    # Record fill
    service.transition_state(intent_id, OrderState.FILLED)
    service.record_fill(intent_id, broker_order_id="2407250001", filled_qty=250, fill_price=Decimal("120.50"))
    
    assert service.is_fill_confirmed(intent_id)

def test_order_state_machine_illegal_transition():
    service = OrderLifecycleService()
    intent_id = service.create_trade_intent(user_id=1, symbol="RELIANCE", option_type="CE", quantity=250)
    
    # Attempt illegal transition CREATED -> CLOSED directly
    result = service.transition_state(intent_id, OrderState.CLOSED)
    assert not result
    assert service.order_states[intent_id] == OrderState.CREATED
