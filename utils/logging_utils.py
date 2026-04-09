import logging
import uuid
import threading
from typing import Any, Dict, Optional
from core.production_logging import get_trading_logger, get_audit_logger

# Initialize logging (singleton handles multiple calls)
get_trading_logger()

# Use the named logger 'trading' which is setup in production_logging
trading_logger = logging.getLogger('trading')
audit_logger = get_audit_logger()

# Thread-local storage for recursion protection
_local = threading.local()

def generate_trace_id() -> str:
    """Generate a unique trace ID for tracking request flows"""
    return str(uuid.uuid4())

def log_structured(
    event: str, 
    level: str = "INFO", 
    message: str = "", 
    data: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    Log a structured event with standardized fields.
    
    Args:
        event: The event name (e.g., "STOCK_SELECTION", "TRADE_SIGNAL")
        level: Log level ("INFO", "WARNING", "ERROR")
        message: Human readable message
        data: Dictionary of structured data
        trace_id: Correlation ID
        user_id: User identifier
    """
    if data is None:
        data = {}
    
    # Sanitize data to avoid LogRecord conflicts
    safe_data = {k: v for k, v in data.items() if k not in ['message', 'asctime', 'levelname', 'levelno']}
    if 'message' in data:
        safe_data['original_message'] = data['message']
        
    extra = {
        'event_type': event,
        'trace_id': trace_id,
        'user_id': user_id,
        **safe_data
    }
    
    log_func = getattr(trading_logger, level.lower(), trading_logger.info)
    log_func(f"{event}: {message}", extra=extra)

def log_stock_selection(
    symbol: str, 
    score: float, 
    sentiment: str, 
    status: str, 
    reasons: list, 
    meta: Dict = None
):
    """Log stock selection results"""
    log_structured(
        event="STOCK_SELECTION",
        message=f"{symbol} {status} (Score: {score})",
        data={
            "symbol": symbol,
            "score": score,
            "sentiment": sentiment,
            "status": status,
            "reasons": reasons,
            **(meta or {})
        }
    )

def log_signal_generation(
    symbol: str,
    signal_type: str,
    confidence: float,
    strategy: str,
    price: float,
    trace_id: str = None
):
    """Log trading signal generation"""
    log_structured(
        event="SIGNAL_GENERATION",
        message=f"{signal_type} signal for {symbol} (Conf: {confidence})",
        data={
            "symbol": symbol,
            "signal_type": signal_type,
            "confidence": confidence,
            "strategy": strategy,
            "price": price
        },
        trace_id=trace_id
    )

def log_trade_prep(
    user_id: str,
    symbol: str,
    status: str,
    error: str = None,
    data: Dict = None
):
    """Log trade preparation results"""
    level = "ERROR" if status != "ready" else "INFO"
    log_structured(
        event="TRADE_PREPARATION",
        level=level,
        message=f"Prep {status} for {symbol}" + (f": {error}" if error else ""),
        data={
            "symbol": symbol,
            "status": status,
            "error": error,
            **(data or {})
        },
        user_id=user_id
    )

def log_trailing_update(
    symbol: str,
    old_sl: float,
    new_sl: float,
    reason: str,
    current_price: float
):
    """Log trailing stop loss update"""
    log_structured(
        event="TRAILING_STOP_UPDATE",
        message=f"SL updated for {symbol}: {old_sl} -> {new_sl} ({reason})",
        data={
            "symbol": symbol,
            "old_sl": old_sl,
            "new_sl": new_sl,
            "reason": reason,
            "current_price": current_price
        }
    )

def log_trade_attempt(
    user_id: str,
    symbol: str,
    side: str,
    qty: int,
    price: float,
    reason: str,
    trace_id: str = None
):
    """Log a trade execution attempt"""
    log_structured(
        event="TRADE_ATTEMPT",
        message=f"Attempting {side} {qty} {symbol} @ {price}",
        data={
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "price": price,
            "reason": reason
        },
        user_id=user_id,
        trace_id=trace_id
    )

def log_trade_result(
    user_id: str,
    trade_id: str,
    status: str,
    error: str = None,
    trace_id: str = None
):
    """Log the result of a trade execution"""
    level = "ERROR" if status == "FAILED" else "INFO"
    log_structured(
        event="TRADE_RESULT",
        level=level,
        message=f"Trade {trade_id} {status}",
        data={
            "trade_id": trade_id,
            "status": status,
            "error": error
        },
        user_id=user_id,
        trace_id=trace_id
    )
    
    # If successful, also log to audit trail
    if status == "SUCCESS":
        # We need to fetch details or pass them in. 
        # For now, we assume the AuditLogger is handled separately or we enhance this.
        pass
