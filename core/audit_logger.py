"""
Audit Logging System for Trading Operations

This module provides comprehensive audit logging for all financial operations
including trades, orders, portfolio changes, and security events.
Maintains immutable audit trails for regulatory compliance.
"""

import json
import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
from core.logging_config import get_audit_logger, get_correlation_id


class AuditEventType(Enum):
    """Types of audit events."""
    # Trading operations
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_MODIFIED = "order_modified"
    ORDER_EXECUTED = "order_executed"
    ORDER_REJECTED = "order_rejected"

    # Portfolio operations
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_MODIFIED = "position_modified"

    # Account operations
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    MARGIN_CALL = "margin_call"

    # Authentication & Security
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    API_KEY_GENERATED = "api_key_generated"
    API_KEY_REVOKED = "api_key_revoked"

    # System operations
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGED = "config_changed"
    BACKUP_CREATED = "backup_created"

    # Compliance & Risk
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    COMPLIANCE_VIOLATION = "compliance_violation"

    # Data operations
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_DELETION = "data_deletion"


@dataclass
class AuditEvent:
    """Structured audit event."""
    event_type: AuditEventType
    user_id: Optional[str]
    timestamp: datetime
    correlation_id: Optional[str]
    event_data: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    source_system: str = "trading_app"

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()

        # Convert Decimal values to strings
        def convert_decimals(obj):
            if isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimals(item) for item in obj]
            elif isinstance(obj, Decimal):
                return str(obj)
            return obj

        data['event_data'] = convert_decimals(data['event_data'])
        return data


class TradingAuditLogger:
    """Audit logger for trading operations."""

    def __init__(self):
        self.logger = get_audit_logger()

    def _log_event(self, event: AuditEvent) -> None:
        """Log audit event."""
        event_dict = event.to_dict()
        self.logger.info(
            f"AUDIT: {event.event_type.value}",
            extra={'audit_event': event_dict}
        )

    # Trading Operations
    def log_order_placed(
        self,
        user_id: str,
        order_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "market",
        broker: str = None,
        **kwargs
    ) -> None:
        """Log order placement."""
        event_data = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': str(quantity),
            'order_type': order_type,
        }

        if price is not None:
            event_data['price'] = str(price)
        if broker:
            event_data['broker'] = broker

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.ORDER_PLACED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    def log_order_executed(
        self,
        user_id: str,
        order_id: str,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        executed_price: Decimal,
        commission: Decimal,
        broker: str = None,
        **kwargs
    ) -> None:
        """Log order execution."""
        event_data = {
            'order_id': order_id,
            'trade_id': trade_id,
            'symbol': symbol,
            'side': side,
            'quantity': str(quantity),
            'executed_price': str(executed_price),
            'commission': str(commission),
            'total_value': str(quantity * executed_price)
        }

        if broker:
            event_data['broker'] = broker

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.ORDER_EXECUTED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    def log_order_cancelled(
        self,
        user_id: str,
        order_id: str,
        symbol: str,
        reason: str = None,
        **kwargs
    ) -> None:
        """Log order cancellation."""
        event_data = {
            'order_id': order_id,
            'symbol': symbol,
        }

        if reason:
            event_data['reason'] = reason

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.ORDER_CANCELLED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    def log_order_rejected(
        self,
        user_id: str,
        order_id: str,
        symbol: str,
        rejection_reason: str,
        **kwargs
    ) -> None:
        """Log order rejection."""
        event_data = {
            'order_id': order_id,
            'symbol': symbol,
            'rejection_reason': rejection_reason,
        }

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.ORDER_REJECTED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    # Portfolio Operations
    def log_position_change(
        self,
        user_id: str,
        symbol: str,
        old_quantity: Decimal,
        new_quantity: Decimal,
        avg_price: Decimal,
        change_reason: str,
        **kwargs
    ) -> None:
        """Log position change."""
        if old_quantity == Decimal('0') and new_quantity > Decimal('0'):
            event_type = AuditEventType.POSITION_OPENED
        elif new_quantity == Decimal('0') and old_quantity != Decimal('0'):
            event_type = AuditEventType.POSITION_CLOSED
        else:
            event_type = AuditEventType.POSITION_MODIFIED

        event_data = {
            'symbol': symbol,
            'old_quantity': str(old_quantity),
            'new_quantity': str(new_quantity),
            'quantity_change': str(new_quantity - old_quantity),
            'avg_price': str(avg_price),
            'change_reason': change_reason,
        }

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    # Account Operations
    def log_deposit(
        self,
        user_id: str,
        amount: Decimal,
        currency: str = "INR",
        method: str = None,
        reference: str = None,
        **kwargs
    ) -> None:
        """Log fund deposit."""
        event_data = {
            'amount': str(amount),
            'currency': currency,
        }

        if method:
            event_data['method'] = method
        if reference:
            event_data['reference'] = reference

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.DEPOSIT,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    def log_withdrawal(
        self,
        user_id: str,
        amount: Decimal,
        currency: str = "INR",
        method: str = None,
        reference: str = None,
        **kwargs
    ) -> None:
        """Log fund withdrawal."""
        event_data = {
            'amount': str(amount),
            'currency': currency,
        }

        if method:
            event_data['method'] = method
        if reference:
            event_data['reference'] = reference

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.WITHDRAWAL,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    # Security Operations
    def log_user_login(
        self,
        user_id: str,
        ip_address: str = None,
        user_agent: str = None,
        success: bool = True,
        login_method: str = "password",
        **kwargs
    ) -> None:
        """Log user login attempt."""
        event_type = AuditEventType.USER_LOGIN if success else AuditEventType.LOGIN_FAILED

        event_data = {
            'login_method': login_method,
            'success': success,
        }

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self._log_event(event)

    def log_user_logout(
        self,
        user_id: str,
        session_duration_seconds: int = None,
        **kwargs
    ) -> None:
        """Log user logout."""
        event_data = {}

        if session_duration_seconds:
            event_data['session_duration_seconds'] = session_duration_seconds

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.USER_LOGOUT,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    # Risk & Compliance
    def log_risk_limit_exceeded(
        self,
        user_id: str,
        limit_type: str,
        limit_value: Decimal,
        current_value: Decimal,
        action_taken: str = None,
        **kwargs
    ) -> None:
        """Log risk limit exceeded."""
        event_data = {
            'limit_type': limit_type,
            'limit_value': str(limit_value),
            'current_value': str(current_value),
            'excess_amount': str(current_value - limit_value),
        }

        if action_taken:
            event_data['action_taken'] = action_taken

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.RISK_LIMIT_EXCEEDED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    def log_suspicious_activity(
        self,
        user_id: str,
        activity_type: str,
        description: str,
        risk_score: int = None,
        **kwargs
    ) -> None:
        """Log suspicious activity."""
        event_data = {
            'activity_type': activity_type,
            'description': description,
        }

        if risk_score:
            event_data['risk_score'] = risk_score

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    # System Operations
    def log_system_event(
        self,
        event_type: AuditEventType,
        description: str,
        user_id: str = None,
        **kwargs
    ) -> None:
        """Log system-level event."""
        event_data = {
            'description': description,
        }

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)

    # Data Operations
    def log_data_operation(
        self,
        operation_type: AuditEventType,
        user_id: str,
        data_type: str,
        record_count: int = None,
        file_name: str = None,
        **kwargs
    ) -> None:
        """Log data operation (export, import, deletion)."""
        event_data = {
            'data_type': data_type,
        }

        if record_count:
            event_data['record_count'] = record_count
        if file_name:
            event_data['file_name'] = file_name

        event_data.update(kwargs)

        event = AuditEvent(
            event_type=operation_type,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            correlation_id=get_correlation_id(),
            event_data=event_data
        )
        self._log_event(event)


# Global audit logger instance
audit_logger = TradingAuditLogger()