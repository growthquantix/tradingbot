"""
Order Lifecycle & Idempotency Management Service
Enforces strict state transitions and verifies execution fill confirmation before position entry.
"""

import logging
import uuid
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class OrderState(Enum):
    """Strict Order State Machine Types"""
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXIT_PENDING = "EXIT_PENDING"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class ProtectionState(Enum):
    """Broker-Side Stop Loss Protection State Types"""
    UNPROTECTED = "UNPROTECTED"
    PROTECTION_PENDING = "PROTECTION_PENDING"
    PROTECTED = "PROTECTED"
    PROTECTION_FAILED = "PROTECTION_FAILED"


class OrderLifecycleService:
    """
    Manages order states, idempotency keys, fill confirmation, and transition validation.
    """

    VALID_TRANSITIONS = {
        OrderState.CREATED: {OrderState.VALIDATED, OrderState.REJECTED},
        OrderState.VALIDATED: {OrderState.SUBMITTING, OrderState.REJECTED},
        OrderState.SUBMITTING: {OrderState.SUBMITTED, OrderState.REJECTED, OrderState.UNKNOWN},
        OrderState.SUBMITTED: {OrderState.ACKNOWLEDGED, OrderState.REJECTED, OrderState.CANCELLED},
        OrderState.ACKNOWLEDGED: {OrderState.OPEN, OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED},
        OrderState.OPEN: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCEL_PENDING, OrderState.CANCELLED},
        OrderState.PARTIALLY_FILLED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED},
        OrderState.FILLED: {OrderState.EXIT_PENDING, OrderState.CLOSED},
        OrderState.EXIT_PENDING: {OrderState.CLOSED, OrderState.UNKNOWN},
        OrderState.CLOSED: set(),
        OrderState.REJECTED: set(),
        OrderState.CANCELLED: set(),
        OrderState.UNKNOWN: {OrderState.ACKNOWLEDGED, OrderState.FILLED, OrderState.REJECTED, OrderState.CLOSED}
    }

    def __init__(self):
        self.trade_intents: Dict[str, Dict[str, Any]] = {}
        self.order_states: Dict[str, OrderState] = {}
        self.order_fills: Dict[str, Dict[str, Any]] = {}

    def create_trade_intent(self, user_id: int, symbol: str, option_type: str, quantity: int) -> str:
        """Generate persistent unique trade intent ID for idempotent execution."""
        intent_id = f"INTENT_{uuid.uuid4().hex[:12].upper()}"
        self.trade_intents[intent_id] = {
            "intent_id": intent_id,
            "user_id": user_id,
            "symbol": symbol,
            "option_type": option_type,
            "quantity": quantity,
            "state": OrderState.CREATED,
            "created_at": datetime.now().isoformat(),
            "broker_order_id": None
        }
        self.order_states[intent_id] = OrderState.CREATED
        logger.info(f"🆔 Created Trade Intent: {intent_id} for {symbol} ({quantity} units)")
        return intent_id

    def transition_state(self, intent_id: str, new_state: OrderState, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Validate and apply state machine transition."""
        current_state = self.order_states.get(intent_id, OrderState.UNKNOWN)
        
        # Check transition validity
        if current_state != OrderState.UNKNOWN and new_state not in self.VALID_TRANSITIONS.get(current_state, set()):
            logger.error(f"❌ Illegal State Transition for {intent_id}: {current_state.value} -> {new_state.value}")
            return False

        self.order_states[intent_id] = new_state
        if intent_id in self.trade_intents:
            self.trade_intents[intent_id]["state"] = new_state
            if metadata:
                self.trade_intents[intent_id].update(metadata)

        logger.info(f"🔄 State Transition for {intent_id}: {current_state.value} -> {new_state.value}")
        return True

    def is_fill_confirmed(self, intent_id: str) -> bool:
        """Verify whether an order has explicit confirmed fills (FILLED or PARTIALLY_FILLED)."""
        state = self.order_states.get(intent_id, OrderState.UNKNOWN)
        return state in (OrderState.FILLED, OrderState.PARTIALLY_FILLED)

    def record_fill(self, intent_id: str, broker_order_id: str, filled_qty: int, fill_price: Decimal) -> Dict[str, Any]:
        """Record fill confirmation details from broker response or callback."""
        fill_record = {
            "intent_id": intent_id,
            "broker_order_id": broker_order_id,
            "filled_qty": filled_qty,
            "fill_price": float(fill_price),
            "timestamp": datetime.now().isoformat()
        }
        self.order_fills[intent_id] = fill_record
        logger.info(f"✅ Executed Fill Confirmed for {intent_id}: {filled_qty} units @ ₹{fill_price}")
        return fill_record


# Singleton instance
order_lifecycle_service = OrderLifecycleService()
