"""
Centralized Trading Kill Switch & Safety Controller
Blocks new trade entries and handles emergency safety actions upon risk trigger detection.
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class KillSwitchTrigger(Enum):
    """Kill Switch Trigger Types"""
    BROKER_DISCONNECTED = "BROKER_DISCONNECTED"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    PROTECTIVE_ORDER_FAILED = "PROTECTIVE_ORDER_FAILED"
    ORDER_STATE_UNKNOWN = "ORDER_STATE_UNKNOWN"
    MAX_DAILY_LOSS = "MAX_DAILY_LOSS"
    SYSTEM_EXCEPTION = "SYSTEM_EXCEPTION"


class KillSwitchAction(Enum):
    """Kill Switch Safety Action Types"""
    BLOCK_NEW_ENTRIES = "BLOCK_NEW_ENTRIES"
    MANAGE_POSITIONS_ONLY = "MANAGE_POSITIONS_ONLY"
    EMERGENCY_FLATTEN = "EMERGENCY_FLATTEN"
    HALT_SYSTEM = "HALT_SYSTEM"


class TradingKillSwitch:
    """
    Centralized Trading Safety Controller.
    Blocks new entries and coordinates emergency mitigation.
    """

    def __init__(self):
        self.is_active: bool = False
        self.active_triggers: List[Dict[str, Any]] = []
        self.current_action: KillSwitchAction = KillSwitchAction.BLOCK_NEW_ENTRIES

    def activate(self, trigger: KillSwitchTrigger, reason: str, action: KillSwitchAction = KillSwitchAction.BLOCK_NEW_ENTRIES):
        """Activate kill switch to block trade execution."""
        self.is_active = True
        self.current_action = action
        trigger_record = {
            "trigger": trigger.value,
            "reason": reason,
            "action": action.value,
            "timestamp": datetime.now().isoformat()
        }
        self.active_triggers.append(trigger_record)
        logger.error(f"🚨 KILL SWITCH ACTIVATED [{trigger.value}]: {reason} (Action: {action.value})")

    def deactivate(self, user_id: str = "admin"):
        """Deactivate kill switch (manual reset)."""
        self.is_active = False
        self.active_triggers.clear()
        logger.info(f"🟢 Kill Switch Deactivated by {user_id}")

    def can_execute_new_trade(self) -> bool:
        """Check whether new trades are allowed to enter."""
        if self.is_active:
            logger.warning("🛡️ Trade Blocked by Active Kill Switch")
            return False
        return True


# Singleton instance
trading_kill_switch = TradingKillSwitch()
