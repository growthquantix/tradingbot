"""
Enhanced Log Formatters for Trading System

This module provides specialized formatters for different types of logs
with improved readability, color coding, and trading-specific formatting.
"""

import json
import logging
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Check if colorama is available for colored output
try:
    from colorama import Fore, Back, Style, init
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback color constants
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Back:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""


class TradingConsoleFormatter(logging.Formatter):
    """Enhanced console formatter with colors and better readability for trading logs."""

    # Color scheme for different log levels
    LEVEL_COLORS = {
        'DEBUG': Fore.CYAN + Style.DIM,
        'INFO': Fore.GREEN + Style.BRIGHT,
        'WARNING': Fore.YELLOW + Style.BRIGHT,
        'ERROR': Fore.RED + Style.BRIGHT,
        'CRITICAL': Fore.MAGENTA + Style.BRIGHT + Back.RED,
    }

    # Color scheme for different components
    COMPONENT_COLORS = {
        'trading_app': Fore.BLUE + Style.BRIGHT,
        'broker': Fore.MAGENTA + Style.BRIGHT,
        'websocket': Fore.CYAN + Style.BRIGHT,
        'database': Fore.YELLOW + Style.DIM,
        'audit': Fore.RED + Style.BRIGHT,
        'performance': Fore.GREEN + Style.DIM,
        'security': Fore.RED + Style.BRIGHT + Back.BLACK,
        'market_data': Fore.CYAN + Style.NORMAL,
        'order_management': Fore.BLUE + Style.NORMAL,
        'risk_management': Fore.YELLOW + Style.BRIGHT,
        'upstox': Fore.MAGENTA + Style.DIM,
        'angel': Fore.BLUE + Style.DIM,
        'zerodha': Fore.GREEN + Style.DIM,
    }

    # Trading-specific icons with colors (Windows-safe)
    TRADING_ICONS = {
        'order_placed': {'icon': '[ORD]', 'color': Fore.BLUE + Style.BRIGHT},
        'order_executed': {'icon': '[EXE]', 'color': Fore.GREEN + Style.BRIGHT},
        'order_cancelled': {'icon': '[CXL]', 'color': Fore.RED + Style.BRIGHT},
        'trade_execution': {'icon': '[TRD]', 'color': Fore.GREEN + Style.BRIGHT},
        'market_data_update': {'icon': '[MKT]', 'color': Fore.CYAN + Style.BRIGHT},
        'user_activity': {'icon': '[USR]', 'color': Fore.YELLOW + Style.BRIGHT},
        'system_error': {'icon': '[ERR]', 'color': Fore.RED + Style.BRIGHT + Back.BLACK},
        'performance': {'icon': '[PRF]', 'color': Fore.GREEN + Style.DIM},
        'audit': {'icon': '[AUD]', 'color': Fore.RED + Style.BRIGHT},
        'security': {'icon': '[SEC]', 'color': Fore.RED + Style.BRIGHT + Back.BLACK},
        'websocket': {'icon': '[WS]', 'color': Fore.CYAN + Style.BRIGHT},
        'database': {'icon': '[DB]', 'color': Fore.YELLOW + Style.DIM},
        'broker': {'icon': '[BRK]', 'color': Fore.MAGENTA + Style.BRIGHT},
    }

    def __init__(self, use_colors: bool = None):
        super().__init__()
        self.use_colors = use_colors if use_colors is not None else (COLORAMA_AVAILABLE and sys.stdout.isatty())

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with enhanced readability."""
        # Get timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]

        # Get component name and color
        component = self._get_component_name(record.name)
        component_color = self.COMPONENT_COLORS.get(component, Fore.WHITE) if self.use_colors else ""

        # Get level color
        level_color = self.LEVEL_COLORS.get(record.levelname, Fore.WHITE) if self.use_colors else ""

        # Get icon for event type with color
        event_type = getattr(record, 'event_type', None)
        icon_data = self.TRADING_ICONS.get(event_type, {'icon': '', 'color': ''}) if event_type else {'icon': '', 'color': ''}

        if self.use_colors and icon_data['icon']:
            icon = f"{icon_data['color']}{icon_data['icon']}{Style.RESET_ALL}"
        else:
            icon = icon_data['icon']

        # Format correlation ID
        correlation_id = getattr(record, 'correlation_id', None)
        correlation_part = f" [{correlation_id[:8]}]" if correlation_id else ""

        # Format trading-specific data
        trading_data = self._format_trading_data(record)
        trading_part = f" {trading_data}" if trading_data else ""

        # Build the formatted message with enhanced colors
        if self.use_colors:
            # Color the correlation ID
            correlation_color = Fore.BLUE + Style.DIM if correlation_id else ""
            correlation_reset = Style.RESET_ALL if correlation_id else ""

            # Color the message based on level
            message_color = ""
            if record.levelname == 'ERROR':
                message_color = Fore.RED + Style.BRIGHT
            elif record.levelname == 'WARNING':
                message_color = Fore.YELLOW + Style.BRIGHT
            elif record.levelname == 'CRITICAL':
                message_color = Fore.MAGENTA + Style.BRIGHT
            else:
                message_color = Fore.WHITE

            formatted_msg = (
                f"{Fore.WHITE + Style.DIM}{timestamp}{Style.RESET_ALL} "
                f"{level_color}{record.levelname:<8}{Style.RESET_ALL} "
                f"{component_color}{component:<15}{Style.RESET_ALL} "
                f"{icon} {message_color}{record.getMessage()}{Style.RESET_ALL}"
                f"{correlation_color}{correlation_part}{correlation_reset}{trading_part}"
            )
        else:
            formatted_msg = (
                f"{timestamp} {record.levelname:<8} {component:<15} "
                f"{icon} {record.getMessage()}{correlation_part}{trading_part}"
            )

        # Add exception info if present
        if record.exc_info:
            formatted_msg += "\n" + self.formatException(record.exc_info)

        return formatted_msg

    def _get_component_name(self, logger_name: str) -> str:
        """Extract component name from logger name."""
        parts = logger_name.split('.')
        if len(parts) > 1:
            return parts[-1]
        return logger_name

    def _format_trading_data(self, record: logging.LogRecord) -> str:
        """Format trading-specific data from log record."""
        parts = []

        # User information with color
        if hasattr(record, 'user_id'):
            color = Fore.CYAN + Style.BRIGHT if self.use_colors else ""
            reset = Style.RESET_ALL if self.use_colors else ""
            parts.append(f"{color}USR:{record.user_id}{reset}")

        # Trading symbols with color
        if hasattr(record, 'symbol'):
            color = Fore.MAGENTA + Style.BRIGHT if self.use_colors else ""
            reset = Style.RESET_ALL if self.use_colors else ""
            parts.append(f"{color}SYM:{record.symbol}{reset}")

        # Order information with color
        if hasattr(record, 'order_id'):
            color = Fore.BLUE + Style.BRIGHT if self.use_colors else ""
            reset = Style.RESET_ALL if self.use_colors else ""
            parts.append(f"{color}ORD:{record.order_id}{reset}")

        # Financial amounts with color
        if hasattr(record, 'amount'):
            amount = record.amount
            if isinstance(amount, (Decimal, float)):
                color = Fore.GREEN + Style.BRIGHT if self.use_colors else ""
                reset = Style.RESET_ALL if self.use_colors else ""
                parts.append(f"{color}AMT:INR{amount:,.2f}{reset}")

        # Performance data with colored latency
        if hasattr(record, 'duration_ms'):
            duration = record.duration_ms
            color = ""
            if self.use_colors:
                if duration > 1000:
                    color = Fore.RED + Style.BRIGHT + Back.BLACK
                elif duration > 100:
                    color = Fore.YELLOW + Style.BRIGHT
                elif duration > 50:
                    color = Fore.YELLOW + Style.DIM
                else:
                    color = Fore.GREEN + Style.BRIGHT
            reset = Style.RESET_ALL if self.use_colors else ""
            parts.append(f"{color}LAT:{duration:.1f}ms{reset}")

        # Broker information with color
        if hasattr(record, 'broker'):
            broker_color = self.COMPONENT_COLORS.get(record.broker.lower(), Fore.MAGENTA + Style.BRIGHT) if self.use_colors else ""
            reset = Style.RESET_ALL if self.use_colors else ""
            parts.append(f"{broker_color}BRK:{record.broker}{reset}")

        return " ".join(parts)

    def _colorize_trading_context(self, message: str, context: dict) -> str:
        """
        Apply trading-specific colorization to message content.

        Args:
            message: The formatted message
            context: Trading context data

        Returns:
            Message with trading context colorized
        """
        if not self.use_colors:
            return message

        # Trading data colors
        TRADING_COLORS = {
            'user': Fore.BLUE + Style.BRIGHT,
            'symbol': Fore.CYAN + Style.BRIGHT,
            'order': Fore.MAGENTA + Style.BRIGHT,
            'amount': Fore.GREEN + Style.BRIGHT,
            'latency': Fore.YELLOW + Style.BRIGHT,
            'broker': Fore.WHITE + Style.BRIGHT,
        }

        # Performance-based colors
        PERFORMANCE_COLORS = {
            'fast': Fore.GREEN + Style.BRIGHT,
            'normal': Fore.YELLOW,
            'slow': Fore.RED + Style.BRIGHT,
            'critical': Fore.RED + Style.BRIGHT + Back.YELLOW,
        }

        colored_msg = message

        # Colorize user references (USR:xxx)
        if 'user_id' in context:
            user_pattern = f"USR:{context['user_id']}"
            if user_pattern in colored_msg:
                colored_msg = colored_msg.replace(
                    user_pattern,
                    TRADING_COLORS['user'] + user_pattern + Style.RESET_ALL
                )

        # Colorize symbol references (SYM:xxx)
        if 'symbol' in context:
            symbol_pattern = f"SYM:{context['symbol']}"
            if symbol_pattern in colored_msg:
                colored_msg = colored_msg.replace(
                    symbol_pattern,
                    TRADING_COLORS['symbol'] + symbol_pattern + Style.RESET_ALL
                )

        # Colorize order references (ORD:xxx)
        if 'order_id' in context:
            order_pattern = f"ORD:{context['order_id']}"
            if order_pattern in colored_msg:
                colored_msg = colored_msg.replace(
                    order_pattern,
                    TRADING_COLORS['order'] + order_pattern + Style.RESET_ALL
                )

        # Colorize amount references (AMT:xxx)
        if 'amount' in context:
            amount_pattern = f"AMT:INR{context['amount']}"
            if amount_pattern in colored_msg:
                colored_msg = colored_msg.replace(
                    amount_pattern,
                    TRADING_COLORS['amount'] + amount_pattern + Style.RESET_ALL
                )

        # Colorize broker references (BRK:xxx)
        if 'broker' in context:
            broker_pattern = f"BRK:{context['broker']}"
            if broker_pattern in colored_msg:
                colored_msg = colored_msg.replace(
                    broker_pattern,
                    TRADING_COLORS['broker'] + broker_pattern + Style.RESET_ALL
                )

        # Colorize latency based on performance
        if 'latency' in context:
            try:
                latency_ms = float(context['latency'])
                latency_pattern = f"LAT:{latency_ms}ms"

                if latency_pattern in colored_msg:
                    if latency_ms > 1000:
                        latency_color = PERFORMANCE_COLORS['critical']
                    elif latency_ms > 100:
                        latency_color = PERFORMANCE_COLORS['slow']
                    elif latency_ms > 50:
                        latency_color = PERFORMANCE_COLORS['normal']
                    else:
                        latency_color = PERFORMANCE_COLORS['fast']

                    colored_msg = colored_msg.replace(
                        latency_pattern,
                        latency_color + latency_pattern + Style.RESET_ALL
                    )
            except (ValueError, TypeError):
                pass

        return colored_msg

    def _get_icon_color(self, icon: str) -> str:
        """
        Get color for trading operation icons.

        Args:
            icon: The operation icon

        Returns:
            ANSI color code for the icon
        """
        ICON_COLORS = {
            '[ORD]': Fore.BLUE + Style.BRIGHT,      # Order operations - Blue
            '[EXE]': Fore.GREEN + Style.BRIGHT,     # Executions - Green
            '[CXL]': Fore.RED + Style.BRIGHT,       # Cancellations - Red
            '[TRD]': Fore.CYAN + Style.BRIGHT,      # Trades - Cyan
            '[MKT]': Fore.MAGENTA + Style.BRIGHT,   # Market data - Magenta
            '[USR]': Fore.YELLOW + Style.BRIGHT,    # User activities - Yellow
            '[SEC]': Fore.RED + Back.YELLOW,        # Security events - Red on Yellow
            '[PRF]': Fore.GREEN + Style.DIM,        # Performance - Dim Green
            '[BRK]': Fore.WHITE + Style.BRIGHT,     # Broker operations - Bright White
            '[DB]': Fore.CYAN + Style.DIM,          # Database - Dim Cyan
            '[WS]': Fore.MAGENTA + Style.DIM,       # WebSocket - Dim Magenta
        }

        return ICON_COLORS.get(icon, Fore.WHITE)


class TradingJSONFormatter(logging.Formatter):
    """Enhanced JSON formatter with better structure and trading-specific fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON with enhanced fields."""
        # Base log structure
        log_entry = {
            '@timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process,
        }

        # Add correlation ID if available
        correlation_id = getattr(record, 'correlation_id', None)
        if correlation_id:
            log_entry['correlation_id'] = correlation_id

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'stack_trace': self.formatException(record.exc_info)
            }

        # Add trading-specific fields
        trading_fields = self._extract_trading_fields(record)
        if trading_fields:
            log_entry['trading'] = trading_fields

        # Add performance fields
        performance_fields = self._extract_performance_fields(record)
        if performance_fields:
            log_entry['performance'] = performance_fields

        # Add security fields
        security_fields = self._extract_security_fields(record)
        if security_fields:
            log_entry['security'] = security_fields

        # Add extra fields from record
        extra_fields = self._extract_extra_fields(record)
        if extra_fields:
            log_entry['extra'] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False, default=self._json_serializer)

    def _extract_trading_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract trading-specific fields."""
        trading_fields = {}

        trading_attrs = [
            'user_id', 'order_id', 'trade_id', 'symbol', 'side', 'quantity',
            'price', 'amount', 'broker', 'order_type', 'strategy_name'
        ]

        for attr in trading_attrs:
            if hasattr(record, attr):
                value = getattr(record, attr)
                if isinstance(value, Decimal):
                    trading_fields[attr] = str(value)
                else:
                    trading_fields[attr] = value

        return trading_fields

    def _extract_performance_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract performance-related fields."""
        performance_fields = {}

        performance_attrs = [
            'duration_ms', 'latency_ms', 'throughput', 'memory_usage',
            'cpu_usage', 'operation_count', 'error_count', 'success_count'
        ]

        for attr in performance_attrs:
            if hasattr(record, attr):
                performance_fields[attr] = getattr(record, attr)

        return performance_fields

    def _extract_security_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract security-related fields."""
        security_fields = {}

        security_attrs = [
            'ip_address', 'user_agent', 'session_id', 'auth_method',
            'permissions', 'risk_score', 'threat_level'
        ]

        for attr in security_attrs:
            if hasattr(record, attr):
                security_fields[attr] = getattr(record, attr)

        return security_fields

    def _extract_extra_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract any additional fields."""
        # Standard logging record attributes to exclude
        excluded_attrs = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
            'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'message', 'correlation_id'
        }

        # Trading fields already extracted
        trading_attrs = {
            'user_id', 'order_id', 'trade_id', 'symbol', 'side', 'quantity',
            'price', 'amount', 'broker', 'order_type', 'strategy_name'
        }

        # Performance fields already extracted
        performance_attrs = {
            'duration_ms', 'latency_ms', 'throughput', 'memory_usage',
            'cpu_usage', 'operation_count', 'error_count', 'success_count'
        }

        # Security fields already extracted
        security_attrs = {
            'ip_address', 'user_agent', 'session_id', 'auth_method',
            'permissions', 'risk_score', 'threat_level'
        }

        all_excluded = excluded_attrs | trading_attrs | performance_attrs | security_attrs

        extra_fields = {}
        for attr_name in dir(record):
            if (not attr_name.startswith('_') and
                attr_name not in all_excluded and
                not callable(getattr(record, attr_name))):

                value = getattr(record, attr_name)
                if value is not None:
                    extra_fields[attr_name] = value

        return extra_fields

    def _json_serializer(self, obj: Any) -> str:
        """Custom JSON serializer for special types."""
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return str(obj)


class AuditFormatter(logging.Formatter):
    """Specialized formatter for audit logs with compliance-ready format."""

    def format(self, record: logging.LogRecord) -> str:
        """Format audit record with compliance structure."""
        timestamp = datetime.utcnow().isoformat() + 'Z'

        audit_entry = {
            '@timestamp': timestamp,
            'audit_type': 'TRADING_AUDIT',
            'event_type': getattr(record, 'event_type', 'unknown'),
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None),
            'compliance': {
                'regulation': 'SEBI',
                'retention_years': 7,
                'immutable': True
            }
        }

        # Extract audit event data if present
        if hasattr(record, 'audit_event'):
            audit_event = getattr(record, 'audit_event')
            if isinstance(audit_event, dict):
                audit_entry.update(audit_event)

        return json.dumps(audit_entry, ensure_ascii=False, default=str)


class PerformanceFormatter(logging.Formatter):
    """Specialized formatter for performance logs with metrics structure."""

    def format(self, record: logging.LogRecord) -> str:
        """Format performance record with metrics structure."""
        timestamp = datetime.utcnow().isoformat() + 'Z'

        perf_entry = {
            '@timestamp': timestamp,
            'metric_type': 'PERFORMANCE',
            'operation': getattr(record, 'operation', 'unknown'),
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None),
            'metrics': {}
        }

        # Extract performance metrics
        performance_attrs = [
            'duration_ms', 'latency_ms', 'throughput', 'memory_mb',
            'cpu_percent', 'operations_per_second', 'error_rate'
        ]

        for attr in performance_attrs:
            if hasattr(record, attr):
                perf_entry['metrics'][attr] = getattr(record, attr)

        # Add categorization
        duration_ms = getattr(record, 'duration_ms', 0)
        if duration_ms > 1000:
            perf_entry['performance_category'] = 'SLOW'
        elif duration_ms > 100:
            perf_entry['performance_category'] = 'MEDIUM'
        else:
            perf_entry['performance_category'] = 'FAST'

        return json.dumps(perf_entry, ensure_ascii=False, default=str)


class CompactConsoleFormatter(logging.Formatter):
    """Compact console formatter for production monitoring."""

    def format(self, record: logging.LogRecord) -> str:
        """Format record in compact, readable format."""
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

        # Get component
        component = record.name.split('.')[-1][:10]

        # Build compact message
        message_parts = [
            f"{timestamp}",
            f"{record.levelname[0]}",  # Just first letter (I, W, E, etc.)
            f"{component}",
            record.getMessage()
        ]

        # Add key trading info
        if hasattr(record, 'symbol'):
            message_parts.append(f"[{record.symbol}]")

        if hasattr(record, 'duration_ms'):
            message_parts.append(f"({record.duration_ms:.0f}ms)")

        return " ".join(message_parts)


# Factory function to get appropriate formatter
def get_formatter(formatter_type: str, **kwargs) -> logging.Formatter:
    """
    Get appropriate formatter based on type.

    Args:
        formatter_type: Type of formatter ('console', 'json', 'audit', 'performance', 'compact')
        **kwargs: Additional arguments for formatter

    Returns:
        Logging formatter instance
    """
    formatters = {
        'console': TradingConsoleFormatter,
        'json': TradingJSONFormatter,
        'audit': AuditFormatter,
        'performance': PerformanceFormatter,
        'compact': CompactConsoleFormatter,
    }

    formatter_class = formatters.get(formatter_type, TradingConsoleFormatter)
    return formatter_class(**kwargs)