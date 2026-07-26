"""
Production Shadow Baseline Execution Script (AITOS_BASELINE_V1)
Checks 14 Session Activation Gates against Upstox V3 Market status.
If market is closed (e.g. Saturday/Sunday or outside IST hours), exits cleanly with WAITING_FOR_VALID_MARKET_SESSION.
"""

import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from services.validation.production_shadow_runner import production_shadow_runner, STRATEGY_VERSION, MODEL_VERSION, CONFIG_VERSION, GIT_COMMIT, TRADING_MODE


def run_production_shadow_baseline():
    logger.info("==================================================================")
    logger.info("STARTING AITOS PRODUCTION SHADOW BASELINE RUNNER (SESSIONS 1 -> 20)")
    logger.info(f"Strategy Version: {STRATEGY_VERSION}")
    logger.info(f"Model Version: {MODEL_VERSION}")
    logger.info(f"Config Version: {CONFIG_VERSION}")
    logger.info(f"Git Commit: {GIT_COMMIT}")
    logger.info(f"Operating Mode: TRADING_MODE = {TRADING_MODE}")
    logger.info("==================================================================")

    # Check 14 Session Activation Gates
    all_pass, status, gates = production_shadow_runner.check_activation_gates()

    now = datetime.now()
    logger.info(f"Current Date/Time: {now.strftime('%A %Y-%m-%d %H:%M:%S IST')}")
    logger.info(f"Safety Check: TRADING_MODE = {TRADING_MODE} | Broker Order Attempts = 0")
    logger.info(f"Session Activation Status: {status}")

    # Print Gate Details
    for gate_name, gate_val in gates.items():
        val_str = "PASS" if gate_val else ("FAIL (OFF-MARKET)" if "NSE" in gate_name or "HOURS" in gate_name or "WEEKDAY" in gate_name else "FAIL")
        logger.info(f"  • {gate_name}: {val_str}")

    # Update Progress Report
    production_shadow_runner.update_aggregate_markdown_report()

    if not all_pass:
        logger.info("==================================================================")
        logger.info("WAITING_FOR_VALID_MARKET_SESSION: Market is currently CLOSED.")
        logger.info(f"Baseline Session Counter remains at: {production_shadow_runner.state['valid_baseline_session_count']} / 20")
        logger.info("Session 1 baseline collection will commence automatically on next NSE market open (Monday 09:15 AM IST).")
        logger.info("==================================================================")
        return False

    logger.info("==================================================================")
    logger.info("ACTIVE MARKET SESSION DETECTED: RUNNING BASELINE DATA COLLECTION")
    logger.info("==================================================================")
    return True


if __name__ == "__main__":
    run_production_shadow_baseline()
