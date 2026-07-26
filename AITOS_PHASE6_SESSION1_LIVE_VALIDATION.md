# AITOS Phase-6 — Session 1 Live Market Runtime Validation

**SESSION_DATE:** 2026-07-25  
**BASELINE_SESSION_NUMBER:** DO NOT COUNT (Session Invalid)  
**STRATEGY_VERSION:** AITOS_BASELINE_V1  
**MODEL_VERSION:** AITOS_TRANSFORMER_V1  
**CONFIG_VERSION:** PRODUCTION_SAFETY_V3  
**TRADING_MODE:** SHADOW  
**NSE_EQ_STATUS:** CLOSED  
**NSE_FO_STATUS:** CLOSED  
**MARKET_STATUS_SOURCE:** Upstox Market Feed V3 `market_info`  
**MARKET_OPEN_GATE:** SESSION_INVALID_MARKET_CLOSED  
**FIRST_RAW_TICK:** N/A (Market Closed)  
**LAST_RAW_TICK:** N/A (Market Closed)  
**RAW_TICKS_RECEIVED:** 0  
**UNIQUE_INSTRUMENTS:** 0  
**SELECTION_CYCLES:** 0  
**CANDIDATES_EVALUATED:** 0  
**CE_SIGNALS:** 0  
**PE_SIGNALS:** 0  
**NO_TRADE_DECISIONS:** 0  
**BROKER_ORDER_ATTEMPTS:** 0  
**BROKER_ORDERS_CREATED:** 0  
**MOCK_DATA_DETECTED:** NO  
**REPLAY_DATA_DETECTED:** NO  
**DATA_QUALITY_CRITICAL_ERRORS:** 0  
**SESSION_VALID:** False  

---

## 1. Session Activation Gates Audit

| Gate ID | Description | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **G1** | WebSocket Connected | OFF-MARKET | Upstox WS Client State |
| **G2** | Market Info Received | PASS | Upstox Market Feed V3 payload |
| **G3** | NSE_EQ Status Open | FAIL (CLOSED) | `NSE_EQ` Segment Status = CLOSED |
| **G4** | NSE_FO Status Open | FAIL (CLOSED) | `NSE_FO` Segment Status = CLOSED |
| **G5** | Trading Date Verified | FAIL (WEEKEND) | IST Calendar Check (Saturday) |
| **G6** | Current Session Ticks | FAIL (0 TICKS) | Raw Tick Stream Count |
| **G7** | Timestamps Current | FAIL | `ltt <= local_receive_ts <= decision_ts` |
| **G8** | Instruments Resolved | **PASS** | `InstrumentRegistry` DB Verification |
| **G9** | Tick Freshness OK | FAIL | `data_age_ms` < 500ms |
| **G10**| No Mock Data | **PASS** | Zero test fixtures in live pipeline |
| **G11**| No Replay Data | **PASS** | Live WebSocket stream required |
| **G12**| SHADOW Safety Active | **PASS** | Hard safety check in `execution_handler.py:183` |
| **G13**| Zero Broker Orders | **PASS** | `broker_order_attempt_count == 0` |

---

## 2. Session 1 Validation Decision

- **DATA PROVENANCE**: **FAIL (MARKET CLOSED)**
- **SHADOW SAFETY**: **PASS (`broker_order_attempt_count == 0`)**
- **DATA INTEGRITY**: **PASS**
- **SESSION VALID**: **False**
- **BASELINE SESSION**: **DO NOT COUNT**
- **CONTINUE TO SESSION 2**: **NO — WAIT FOR NEXT NSE MARKET OPEN (MONDAY 09:15 AM IST)**
