"""
Unit & Safety Tests for Lot-Aware Partial Profit Booking Allocation
"""
import pytest

def calculate_lot_aware_partial_booking(total_lots: int) -> tuple[int, int]:
    """
    Calculate integer lot allocation for Target 1 (80% target) vs Runner (20%).
    Guarantees target_lots + runner_lots == total_lots and target_lots >= 0, runner_lots >= 0.
    """
    if total_lots <= 0:
        return (0, 0)
    if total_lots == 1:
        # Policy for 1 lot: Cannot divide integer lots; keep 1 lot for full runner/target
        return (1, 0)
    
    target_lots = int(round(total_lots * 0.8))
    # Safety bounds
    if target_lots >= total_lots:
        target_lots = total_lots - 1
    if target_lots < 1:
        target_lots = 1
        
    runner_lots = total_lots - target_lots
    return (target_lots, runner_lots)

def test_lot_aware_partial_booking_cases():
    test_cases = [1, 2, 3, 4, 5, 10, 17]
    for total in test_cases:
        target_lots, runner_lots = calculate_lot_aware_partial_booking(total)
        assert target_lots + runner_lots == total
        assert target_lots >= 1 or total == 1
        assert runner_lots >= 0
        print(f"Total Lots: {total} -> Target Lots: {target_lots}, Runner Lots: {runner_lots}")
