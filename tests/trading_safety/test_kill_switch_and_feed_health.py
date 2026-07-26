"""
Unit & Safety Tests for Kill Switch and Feed Health Monitor
"""
import pytest
import time
from services.trading_execution.trading_kill_switch import (
    TradingKillSwitch, KillSwitchTrigger, KillSwitchAction
)
from services.trading_execution.feed_health_monitor import (
    FeedHealthMonitor, FeedHealthStatus
)

def test_kill_switch_blocks_new_trades():
    kill_switch = TradingKillSwitch()
    assert kill_switch.can_execute_new_trade()

    kill_switch.activate(
        trigger=KillSwitchTrigger.BROKER_DISCONNECTED,
        reason="Upstox WebSocket Disconnected",
        action=KillSwitchAction.BLOCK_NEW_ENTRIES
    )

    assert not kill_switch.can_execute_new_trade()
    
    kill_switch.deactivate("admin")
    assert kill_switch.can_execute_new_trade()

def test_feed_health_monitor_staleness():
    monitor = FeedHealthMonitor(stale_threshold_ms=100, critical_threshold_ms=300)
    key = "NSE_FO|54321"

    monitor.record_tick(key)
    assert monitor.evaluate_feed_health(key) == FeedHealthStatus.HEALTHY

    time.sleep(0.15)  # 150ms -> Stale
    assert monitor.evaluate_feed_health(key) == FeedHealthStatus.STALE

    time.sleep(0.20)  # 350ms -> Critical
    assert monitor.evaluate_feed_health(key) == FeedHealthStatus.CRITICAL
