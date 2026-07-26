# AITOS Baseline V1 — Running Aggregate Progress Report

**STRATEGY_VERSION:** AITOS_BASELINE_V1  
**MODEL_VERSION:** AITOS_TRANSFORMER_V1  
**CONFIG_VERSION:** PRODUCTION_SAFETY_V3  
**GIT_COMMIT:** f8e9102c34a1b02  
**TRADING_MODE:** SHADOW  
**TARGET_VALID_SESSIONS:** 20  
**CURRENT_VALID_SESSIONS:** 0  
**RUNNER_STATUS:** WAITING_FOR_VALID_MARKET_SESSION  
**LAST_UPDATED:** 2026-07-25T15:58:38.900132  

---

## 1. Cumulative Baseline Performance Summary

| Metric Name | Cumulative Baseline Value |
| :--- | :--- |
| **Valid Sessions Collected** | **0 / 20** |
| **Total Selection Cycles** | 0 |
| **Total Candidates Evaluated** | 0 |
| **Total CE Signals** | 0 |
| **Total PE Signals** | 0 |
| **Total NO_TRADE Decisions** | 0 |
| **Total Completed Shadow Trades** | 0 |
| **Cumulative Gross Shadow PnL** | ₹0.00 |
| **Cumulative Estimated Costs** | ₹0.00 |
| **Cumulative Net Shadow PnL** | **₹0.00** |

---

## 2. Baseline Protocol Guidelines

1. **Frozen Parameters**: No ranking weights, AI thresholds, OI rules, or SL/target parameters may be altered during the 20-session baseline.
2. **Session Validity Rule**: Invalid sessions (off-market, feed outages, gate failures) do NOT increment `valid_baseline_session_count`.
3. **Zero Broker Call Assertion**: `broker_entry_attempts == 0`, `broker_exit_attempts == 0`, `broker_protection_attempts == 0` strictly enforced.
