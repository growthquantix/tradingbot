"""
Production-Grade Logging Configuration for Trading Application
Includes structured logging, error tracking, audit trails, and compliance logging
"""
import logging
import logging.handlers
import time
import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from contextlib import contextmanager

# Optional: Try to import concurrent-log-handler for safe multi-process logging
try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
    HAS_CONCURRENT_LOG = True
except ImportError:
    HAS_CONCURRENT_LOG = False

class ThrottledFilter(logging.Filter):
    """
    Filter that silences noisy logs by default in production.
    - Completely silences common "noise" patterns (INFO level)
    - Throttles REPETITIVE errors to prevent log floods (ERROR level)
    """
    def __init__(self, name="", interval=60, max_cache_size=1000):
        super().__init__(name)
        self.interval = interval
        self.max_cache_size = max_cache_size
        self.last_logged = {}
        self.error_counts = {}
        # Check if noisy logs are explicitly enabled
        self.show_noisy = os.getenv('ENABLE_NOISY_LOGS', 'false').lower() == 'true'

    def filter(self, record):
        # Handle ERROR/WARNING throttling
        if record.levelno >= logging.WARNING:
            msg_key = f"{record.levelno}:{record.name}:{record.getMessage()[:100]}"
            now = time.time()
            
            # If we've seen this exact error recently, throttle it
            if msg_key in self.last_logged:
                if now - self.last_logged[msg_key] < self.interval:
                    self.error_counts[msg_key] = self.error_counts.get(msg_key, 0) + 1
                    return False
                else:
                    # Log the summary of missed errors if any
                    missed = self.error_counts.get(msg_key, 0)
                    if missed > 0:
                        record.msg = f"{record.msg} (Suppressed {missed} similar logs in last {self.interval}s)"
                        self.error_counts[msg_key] = 0
            
            self.last_logged[msg_key] = now
            return True
            
        # If noisy logs are enabled, allow them
        if self.show_noisy:
            return True

        # logic to identify and SILENCE noisy logs (INFO/DEBUG)
        msg_key = record.getMessage()
        
        # Extended patterns that should be hidden in production by default
        is_noisy = any(pattern.lower() in msg_key.lower() for pattern in [
            "Received data", "PnL Update", "Heartbeat", "Broadcast", "tick data", 
            "ltp update", "Processed", "Instrument", "Analytics", "Engine", "Socket",
            "WebSocket", "Connecting", "Disconnecting", "Sentiment", "Heatmap",
            "Updating", "Calculating", "Fetching", "Cached", "Market Data"
        ])
        
        if is_noisy:
            return False
            
        return True

class ProductionFormatter(logging.Formatter):
    """Extremely compact string-based formatter for production to minimize cost/overhead"""
    def format(self, record: logging.LogRecord) -> str:
        # Ultra compact format: [L][HH:MM:SS] Name: Msg
        level = record.levelname[0]
        # Use simple HH:MM:SS to save bytes
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime('%H:%M:%S')
        # Limit message length to prevent massive cost spikes from large JSON objects
        msg = record.getMessage()
        if len(msg) > 500:
            msg = msg[:497] + "..."
            
        return f"[{level}][{timestamp}] {record.name}: {msg}"

class TradingFormatter(logging.Formatter):
    """Custom formatter for trading application with structured logging (Development)"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Create optimized structured log entry
        log_entry = {
            't': datetime.fromtimestamp(record.created, tz=timezone.utc).strftime('%H:%M:%S'),
            'l': record.levelname[:1],
            'n': record.name,
            'm': record.getMessage(),
        }
        
        if record.exc_info:
            log_entry['ex'] = str(record.exc_info[1])
            
        return json.dumps(log_entry, ensure_ascii=False)

class AuditLogger:
    """Dedicated audit logger for compliance and regulatory requirements"""
    
    def __init__(self, log_dir: str = "logs/audit", silent: bool = False):
        self._is_production = (
            os.getenv('ENVIRONMENT') == 'production' or os.getenv('RAILWAY_ENVIRONMENT')
        )
        self.log_dir = Path(log_dir)
        if not self._is_production:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create audit logger
        self.logger = logging.getLogger('audit')
        
        # If silent mode, set to a level that won't log anything
        if silent and self._is_production:
            self.logger.setLevel(logging.CRITICAL + 1)
            self.logger.addHandler(logging.NullHandler())
            self.logger.propagate = False
            return
            
        self.logger.setLevel(logging.INFO)
        
        # Remove default handlers to avoid duplication
        self.logger.handlers.clear()
        
        if self._is_production:
            # In production, use compact string logging to save costs
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ProductionFormatter())
            self.logger.addHandler(console_handler)
        else:
            # File handler for audit logs (concurrent-safe rotation)
            if HAS_CONCURRENT_LOG:
                audit_handler = ConcurrentRotatingFileHandler(
                    filename=self.log_dir / 'audit.log',
                    mode='a',
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=365,
                    encoding='utf-8'
                )
            else:
                audit_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_dir / 'audit.log',
                    maxBytes=10 * 1024 * 1024,
                    backupCount=365,
                    encoding='utf-8'
                )
            audit_handler.setFormatter(TradingFormatter())
            self.logger.addHandler(audit_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
        
    def log_trade_execution(self, user_id: str, broker: str, symbol: str, 
                          order_type: str, quantity: int, price: float, 
                          order_id: str, trade_id: Optional[str] = None):
        """Log trade execution for audit trail"""
        self.logger.info(
            f"TRADE_EXECUTED: {order_type} {quantity} {symbol} @ {price}",
            extra={
                'user_id': user_id,
                'broker': broker,
                'symbol': symbol,
                'order_type': order_type,
                'quantity': quantity,
                'price': price,
                'order_id': order_id,
                'trade_id': trade_id,
                'event_type': 'TRADE_EXECUTION'
            }
        )
    
    def log_login(self, user_id: str, ip_address: str, user_agent: str, success: bool):
        """Log user login attempts"""
        event = "LOGIN_SUCCESS" if success else "LOGIN_FAILED"
        self.logger.info(
            f"{event}: User {user_id} from {ip_address}",
            extra={
                'user_id': user_id,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'event_type': event
            }
        )
    
    def log_configuration_change(self, user_id: str, component: str, 
                                old_value: Any, new_value: Any):
        """Log configuration changes"""
        self.logger.info(
            f"CONFIG_CHANGE: {component} changed by {user_id}",
            extra={
                'user_id': user_id,
                'component': component,
                'old_value': str(old_value),
                'new_value': str(new_value),
                'event_type': 'CONFIG_CHANGE'
            }
        )
    
    def log_api_access(self, user_id: str, endpoint: str, method: str, 
                      status_code: int, request_id: str):
        """Log API access for security monitoring"""
        self.logger.info(
            f"API_ACCESS: {method} {endpoint} - {status_code}",
            extra={
                'user_id': user_id,
                'endpoint': endpoint,
                'method': method,
                'status_code': status_code,
                'request_id': request_id,
                'event_type': 'API_ACCESS'
            }
        )

class TradingLogger:
    """Main production logging setup for trading application"""
    
    def __init__(self, app_name: str = "TradingBot", log_level: str = "WARNING"):
        self.app_name = app_name
        # Enhanced production detection
        self._is_production = (
            os.getenv('ENVIRONMENT') == 'production' or 
            os.getenv('RAILWAY_ENVIRONMENT') is not None or
            os.getenv('RAILWAY_STATIC_URL') is not None
        )
        
        # Check for absolute silence mode (to save costs in production)
        self._silent_mode = log_level.upper() in ('SILENT', 'NONE', 'OFF')
        if self._silent_mode:
            log_level = "CRITICAL"
            
        self.log_dir = Path("logs")
        
        # Only create directories if NOT in production
        if not self._is_production:
            self.log_dir.mkdir(exist_ok=True)
            (self.log_dir / "application").mkdir(exist_ok=True)
            (self.log_dir / "trading").mkdir(exist_ok=True)
            (self.log_dir / "errors").mkdir(exist_ok=True)
            (self.log_dir / "performance").mkdir(exist_ok=True)
        
        # Silence noisy third-party loggers in production
        if self._is_production:
            for noisy_logger in [
                'urllib3', 'apscheduler', 'matplotlib', 'playwright', 
                'uvicorn.access', 'engineio', 'socketio', 'tensorflow',
                'h11', 'httpcore', 'httpx', 'asyncio', 'sqlalchemy',
                'pydantic', 'fastapi', 'selenium', 'multiprocessing'
            ]:
                logging.getLogger(noisy_logger).setLevel(logging.CRITICAL if self._silent_mode else logging.WARNING)

        # Force WARNING level in production if not explicitly set to something else
        if self._is_production and os.getenv('LOG_LEVEL') is None and not self._silent_mode:
            log_level = "WARNING"

        # If in production and silent mode, monkey-patch print to stop the flood
        if self._is_production and self._silent_mode:
            # This completely stops all 'print()' calls from emitting anything to stdout
            # without refactoring hundreds of files.
            import builtins
            builtins.print = lambda *args, **kwargs: None

        # Set up loggers
        self.setup_application_logger(log_level)
        self.setup_trading_logger(log_level)
        self.setup_error_logger()
        self.setup_performance_logger(log_level)
        
        # Initialize audit logger
        self.audit = AuditLogger(silent=self._silent_mode)
        
    def setup_application_logger(self, log_level: str):
        """Set up main application logger"""
        logger = logging.getLogger()
        
        # Map 'SILENT' or invalid levels to CRITICAL or WARNING
        level_map = {'SILENT': logging.CRITICAL, 'NONE': logging.CRITICAL, 'OFF': logging.CRITICAL}
        level = level_map.get(log_level.upper(), getattr(logging, log_level.upper(), logging.WARNING))
        logger.setLevel(level)
        
        # Remove default handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        # If silent mode, we don't even add a console handler
        if self._is_production and self._silent_mode:
            logger.addHandler(logging.NullHandler())
            return

        # Console handler - ALWAYS ENABLED FOR CLOUD PLATFORMS (Railway, Render, etc.)
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Apply ThrottledFilter to prevent cost spikes from ticks/pnl updates
        # Still allows all WARNING and ERROR logs through immediately
        console_handler.addFilter(ThrottledFilter(interval=60))
        
        # In production, use compact string logging to save costs
        if os.getenv('ENVIRONMENT') == 'production' or os.getenv('RAILWAY_ENVIRONMENT'):
            console_handler.setFormatter(ProductionFormatter())
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            
        logger.addHandler(console_handler)
        
    def setup_trading_logger(self, log_level: Optional[str] = None):
        """Set up dedicated trading operations logger"""
        trading_logger = logging.getLogger('trading')
        
        # Use provided level, or current instance level, or default to WARNING
        effective_level = log_level or os.getenv('LOG_LEVEL', 'WARNING')
        
        # Map 'SILENT' or invalid levels to CRITICAL or WARNING
        level_map = {'SILENT': logging.CRITICAL, 'NONE': logging.CRITICAL, 'OFF': logging.CRITICAL}
        level = level_map.get(effective_level.upper(), getattr(logging, effective_level.upper(), logging.WARNING))
        trading_logger.setLevel(level)
        
        # Trading operations log (non-production only)
        if not self._is_production:
            if HAS_CONCURRENT_LOG:
                trading_handler = ConcurrentRotatingFileHandler(
                    filename=self.log_dir / "trading" / "trading.log",
                    mode='a',
                    maxBytes=20 * 1024 * 1024, # 20MB
                    backupCount=90,
                    encoding='utf-8'
                )
            else:
                trading_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_dir / "trading" / "trading.log",
                    maxBytes=20 * 1024 * 1024,
                    backupCount=90,
                    encoding='utf-8'
                )
            trading_handler.setFormatter(TradingFormatter())
            trading_logger.addHandler(trading_handler)
        
        # In production, propagate trading logs to root (stdout handler)
        trading_logger.propagate = True if self._is_production else False
        
    def setup_error_logger(self):
        """Set up dedicated error logger with immediate notification"""
        error_logger = logging.getLogger('errors')
        error_logger.setLevel(logging.ERROR)
        
        # Error log file (non-production only)
        if not self._is_production:
            if HAS_CONCURRENT_LOG:
                error_handler = ConcurrentRotatingFileHandler(
                    filename=self.log_dir / "errors" / "errors.log",
                    mode='a',
                    maxBytes=10 * 1024 * 1024,
                    backupCount=365,
                    encoding='utf-8'
                )
            else:
                error_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_dir / "errors" / "errors.log",
                    maxBytes=10 * 1024 * 1024,
                    backupCount=365,
                    encoding='utf-8'
                )
            error_handler.setFormatter(TradingFormatter())
            error_logger.addHandler(error_handler)
        
        # Email handler for critical errors (if configured)
        if os.getenv('SMTP_HOST') and os.getenv('ERROR_EMAIL_TO'):
            smtp_handler = logging.handlers.SMTPHandler(
                mailhost=(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT', '587'))),
                fromaddr=os.getenv('ERROR_EMAIL_FROM'),
                toaddrs=[os.getenv('ERROR_EMAIL_TO')],
                subject=f"[CRITICAL] {self.app_name} Error",
                credentials=(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD')),
                secure=()
            )
            smtp_handler.setLevel(logging.CRITICAL)
            error_logger.addHandler(smtp_handler)
            
        error_logger.propagate = False
        
    def setup_performance_logger(self, log_level: Optional[str] = None):
        """Set up performance monitoring logger"""
        perf_logger = logging.getLogger('performance')
        
        # Use provided level, or current instance level, or default to WARNING
        effective_level = log_level or os.getenv('LOG_LEVEL', 'WARNING')
        
        # Map 'SILENT' or invalid levels to CRITICAL or WARNING
        level_map = {'SILENT': logging.CRITICAL, 'NONE': logging.CRITICAL, 'OFF': logging.CRITICAL}
        level = level_map.get(effective_level.upper(), getattr(logging, effective_level.upper(), logging.WARNING))
        perf_logger.setLevel(level)

        
        # Performance log file (non-production only)
        if not self._is_production:
            if HAS_CONCURRENT_LOG:
                perf_handler = ConcurrentRotatingFileHandler(
                    filename=self.log_dir / "performance" / "performance.log",
                    mode='a',
                    maxBytes=10 * 1024 * 1024,
                    backupCount=30,
                    encoding='utf-8'
                )
            else:
                perf_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_dir / "performance" / "performance.log",
                    maxBytes=10 * 1024 * 1024,
                    backupCount=30,
                    encoding='utf-8'
                )
            perf_handler.setFormatter(TradingFormatter())
            perf_logger.addHandler(perf_handler)
        perf_logger.propagate = False

# Global logger instances
_trading_logger = None
_audit_logger = None

def get_trading_logger() -> TradingLogger:
    """Get or create the global trading logger instance"""
    global _trading_logger
    if _trading_logger is None:
        log_level = os.getenv('LOG_LEVEL', 'WARNING')
        _trading_logger = TradingLogger(log_level=log_level)
    return _trading_logger


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        log_level = os.getenv('LOG_LEVEL', 'WARNING')
        silent = log_level.upper() in ('SILENT', 'NONE', 'OFF')
        _audit_logger = AuditLogger(silent=silent)
    return _audit_logger

@contextmanager
def log_execution_time(operation_name: str, logger_name: str = 'performance'):
    """Context manager to log operation execution time"""
    logger = logging.getLogger(logger_name)
    start_time = datetime.now()
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(
            f"OPERATION_START: {operation_name}",
            extra={'operation': operation_name, 'request_id': request_id}
        )
        yield request_id
        
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.error(
            f"OPERATION_FAILED: {operation_name} after {execution_time:.3f}s",
            extra={
                'operation': operation_name,
                'request_id': request_id,
                'execution_time': execution_time,
                'error': str(e)
            },
            exc_info=True
        )
        raise
        
    else:
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"OPERATION_COMPLETE: {operation_name} in {execution_time:.3f}s",
            extra={
                'operation': operation_name,
                'request_id': request_id,
                'execution_time': execution_time
            }
        )

# Initialize logging on import
get_trading_logger()
