# AITOS Real-Time Shadow Session EOD Report

```text
SESSION_DATE:                  2026-07-25 (Saturday Off-Market)
BASELINE_SESSION_NUMBER:       DO NOT COUNT (Session Invalid)
SESSION_STATE:                 WAITING_FOR_VALID_MARKET_SESSION

STRATEGY_VERSION:              AITOS_BASELINE_V1
MODEL_VERSION:                 AITOS_TRANSFORMER_V1
CONFIG_VERSION:                PRODUCTION_SAFETY_V3
GIT_COMMIT:                    f8e9102c34a1b02

TRADING_MODE:                  SHADOW

MARKET_STATUS_SOURCE:          Upstox Market Feed V3 `market_info`
NSE_EQ_STATUS:                 CLOSED
NSE_FO_STATUS:                 CLOSED

BROKER_ENTRY_ATTEMPTS:         0 (PASSED)
BROKER_EXIT_ATTEMPTS:          0 (PASSED)
BROKER_PROTECTION_ATTEMPTS:    0 (PASSED)
BROKER_ORDERS_CREATED:         0 (PASSED)

MOCK_DATA_DETECTED:            NO (Live Feed Inactive)
REPLAY_DATA_DETECTED:          NO
CRITICAL_DATA_ERRORS:          0

GROSS_SHADOW_PNL:              ₹0.00
ESTIMATED_TRANSACTION_COST:    ₹0.00
NET_SHADOW_PNL:                ₹0.00

SESSION_VALID:                 FALSE
BASELINE_SESSION_COUNT:        0 / 20
```

---

## 1. 14 Session Activation Gates Audit

| Gate ID | Activation Gate | Required Status | Actual Status | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **G1** | IST Weekday Check | Monday to Friday | Saturday | **FAIL (WEEKEND)** |
| **G2** | IST Market Hours | 09:15 to 15:30 IST | 15:58 IST | **FAIL (OFF-MARKET)** |
| **G3** | Upstox Market Info Received | Valid Payload | Validated Payload | **PASS** |
| **G4** | NSE_EQ Segment Status | OPEN | `CLOSED` | **FAIL (MARKET CLOSED)** |
| **G5** | NSE_FO Segment Status | OPEN | `CLOSED` | **FAIL (MARKET CLOSED)** |
| **G6** | Ticks Received | $> 0$ Ticks | 0 Ticks | **FAIL (0 TICKS)** |
| **G7** | Timestamp Freshness | `data_age_ms < 500`ms | N/A | **FAIL** |
| **G8** | Instrument DB Resolution | DB Resolved | DB Resolved | **PASS** |
| **G9** | Test Data Firewall | 0 test fixtures (`54321`–`54325`) | 0 Test Fixtures | **PASS** |
| **G10**| Replay Data Firewall | Live Feed Stream | Live Feed Stream | **PASS** |
| **G11**| SHADOW Safety Active | Active | Active (`execution_handler.py:183`) | **PASS** |
| **G12**| Zero Broker Entries | `entry_attempts == 0` | `broker_entry_attempts = 0` | **PASS** |
| **G13**| Zero Broker Exits | `exit_attempts == 0` | `broker_exit_attempts = 0` | **PASS** |
| **G14**| Zero Broker Protections| `protection_attempts == 0`| `broker_protection_attempts = 0`| **PASS** |

---

## 2. Session 1 Audit Ruling & Directive

- **DATA PROVENANCE**: **FAIL (MARKET CLOSED)**
- **SHADOW SAFETY**: **PASS (`broker_order_attempt_count == 0`)**
- **DATA INTEGRITY**: **PASS**
- **SESSION VALID**: **FALSE**
- **BASELINE SESSION**: **DO NOT COUNT**
- **CONTINUE TO SESSION 2**: **NO — WAIT FOR NEXT OFFICIAL NSE MARKET OPEN (MONDAY 09:15 AM IST)**
