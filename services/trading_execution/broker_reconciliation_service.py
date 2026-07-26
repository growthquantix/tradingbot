"""
Broker Position Reconciliation & Recovery Service
Reconciles local database state against live broker demat portfolio and manages recovery lifecycle.
"""

import logging
from enum import Enum
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)


class RecoveryState(Enum):
    """System Recovery Lifecycle States"""
    STARTING = "STARTING"
    RECONCILING = "RECONCILING"
    RECOVERING = "RECOVERING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


class ReconciliationStatus(Enum):
    """Discrepancy Category Types"""
    MATCHED = "MATCHED"
    LOCAL_ONLY = "LOCAL_ONLY"
    BROKER_ONLY = "BROKER_ONLY"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    UNPROTECTED_POSITION = "UNPROTECTED_POSITION"


class BrokerReconciliationService:
    """
    Broker Reconciliation Service.
    Enforces broker demat portfolio as authoritative source of truth over local database.
    """

    def __init__(self):
        self.recovery_state: RecoveryState = RecoveryState.STARTING
        self.reconciliation_history: List[Dict[str, Any]] = []

    def set_state(self, state: RecoveryState, reason: str = ""):
        """Update system recovery state."""
        old_state = self.recovery_state
        self.recovery_state = state
        logger.info(f"🔄 System Recovery State Changed: {old_state.value} -> {state.value} ({reason})")

    def reconcile_positions(self, local_positions: List[Dict[str, Any]], broker_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reconcile local active positions against broker demat portfolio.

        Args:
            local_positions: List of position dicts from local DB (`ActivePosition`)
            broker_positions: List of position dicts fetched from Upstox portfolio API

        Returns:
            Dict containing matched, broker_only, local_only, and quantity_mismatch items.
        """
        self.set_state(RecoveryState.RECONCILING, "Starting reconciliation scan")

        broker_map = {p.get("instrument_token") or p.get("instrument_key"): p for p in broker_positions}
        local_map = {p.get("instrument_key"): p for p in local_positions}

        matched = []
        broker_only = []
        local_only = []
        quantity_mismatch = []

        # 1. Inspect Local Positions vs Broker Portfolio
        for key, local_p in local_map.items():
            if key in broker_map:
                broker_p = broker_map[key]
                local_qty = int(local_p.get("quantity", 0))
                broker_qty = int(broker_p.get("quantity", 0))

                if local_qty == broker_qty:
                    matched.append({"instrument_key": key, "status": ReconciliationStatus.MATCHED, "quantity": local_qty})
                else:
                    quantity_mismatch.append({
                        "instrument_key": key,
                        "status": ReconciliationStatus.QUANTITY_MISMATCH,
                        "local_qty": local_qty,
                        "broker_qty": broker_qty
                    })
            else:
                # Ghost position in DB with no broker position
                local_only.append({"instrument_key": key, "status": ReconciliationStatus.LOCAL_ONLY, "local_data": local_p})

        # 2. Inspect Orphan Broker Positions not in Local DB
        for key, broker_p in broker_map.items():
            if key not in local_map:
                broker_only.append({"instrument_key": key, "status": ReconciliationStatus.BROKER_ONLY, "broker_data": broker_p})

        result = {
            "matched_count": len(matched),
            "broker_only_count": len(broker_only),
            "local_only_count": len(local_only),
            "quantity_mismatch_count": len(quantity_mismatch),
            "matched": matched,
            "broker_only": broker_only,
            "local_only": local_only,
            "quantity_mismatch": quantity_mismatch,
            "timestamp": datetime.now().isoformat()
        }

        self.reconciliation_history.append(result)

        # Determine System State post-reconciliation
        if broker_only or quantity_mismatch or local_only:
            self.set_state(RecoveryState.DEGRADED, f"Discrepancies found: {len(broker_only)} broker-only, {len(local_only)} local-only")
        else:
            self.set_state(RecoveryState.READY, "Reconciliation successful - 100% matched")

        return result


# Singleton instance
broker_reconciliation_service = BrokerReconciliationService()
