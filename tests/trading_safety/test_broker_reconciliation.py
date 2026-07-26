"""
Unit & Safety Tests for Broker Reconciliation & Recovery State Machine
"""
import pytest
from services.trading_execution.broker_reconciliation_service import (
    BrokerReconciliationService, RecoveryState, ReconciliationStatus
)

def test_reconciliation_matched_positions():
    service = BrokerReconciliationService()
    local_pos = [{"instrument_key": "NSE_FO|54321", "quantity": 250}]
    broker_pos = [{"instrument_token": "NSE_FO|54321", "quantity": 250}]

    result = service.reconcile_positions(local_pos, broker_pos)
    assert result["matched_count"] == 1
    assert result["broker_only_count"] == 0
    assert result["local_only_count"] == 0
    assert service.recovery_state == RecoveryState.READY

def test_reconciliation_broker_only_position():
    service = BrokerReconciliationService()
    local_pos = []
    broker_pos = [{"instrument_token": "NSE_FO|99999", "quantity": 100}]

    result = service.reconcile_positions(local_pos, broker_pos)
    assert result["broker_only_count"] == 1
    assert result["broker_only"][0]["instrument_key"] == "NSE_FO|99999"
    assert service.recovery_state == RecoveryState.DEGRADED
