"""
Boundary Tests for Target & Stop-Loss Exit Concurrency to Prevent Accidental Shorting
"""
import pytest

class PositionExitLock:
    def __init__(self, current_qty: int):
        self.current_qty = current_qty
        self.is_closed = False

    def process_exit(self, exit_qty: int) -> int:
        """Enforces invariant: executed_exit_quantity <= current_qty."""
        if self.is_closed or self.current_qty <= 0:
            return 0
        
        actual_exit = min(exit_qty, self.current_qty)
        self.current_qty -= actual_exit
        if self.current_qty == 0:
            self.is_closed = True
        return actual_exit

def test_sl_target_concurrency_no_overexit():
    pos = PositionExitLock(current_qty=500)
    
    # Target trigger attempts to exit 500
    target_exit_qty = pos.process_exit(500)
    assert target_exit_qty == 500
    assert pos.current_qty == 0
    assert pos.is_closed

    # SL trigger fires simultaneously for 500
    sl_exit_qty = pos.process_exit(500)
    assert sl_exit_qty == 0  # Blocked, cannot short
    assert pos.current_qty == 0
