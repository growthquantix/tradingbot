"""
Improved Security Filter that doesn't interfere with trading data.

This filter is designed to only mask actual sensitive data while preserving
all legitimate trading information like symbols, prices, quantities, etc.
"""

import logging
import re
from typing import List


class TradingSafeSecurityFilter(logging.Filter):
    """Security filter that preserves trading data while masking sensitive information."""

    # Only mask clearly sensitive authentication data
    SENSITIVE_PATTERNS = [
        # Passwords
        (r'(password\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'PASSWORD'),

        # API keys and tokens - any value after these keywords
        (r'(api_key\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'API_KEY'),
        (r'(access_token\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'TOKEN'),
        (r'(refresh_token\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'REFRESH_TOKEN'),
        (r'(token\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'TOKEN'),
        (r'(Bearer\s+)([A-Za-z0-9._-]{10,})', r'\1***MASKED***', 'BEARER_TOKEN'),

        # Security codes and PINs
        (r'(pin\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'PIN'),
        (r'(otp\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'OTP'),
        (r'(secret\s*[:=]\s*)["\']?([^"\'\s,}]+)["\']?', r'\1***MASKED***', 'SECRET'),
        (r'(key\s*[:=]\s*)["\']?([A-Za-z0-9._-]{16,})["\']?', r'\1***MASKED***', 'SECRET_KEY'),

        # Credit card numbers (16 digits with separators)
        (r'\b(\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4})\b', r'****-****-****-****', 'CREDIT_CARD'),

        # SSN format
        (r'\b(\d{3}-\d{2}-\d{4})\b', r'***-**-****', 'SSN'),

        # JWT tokens (three parts with dots)
        (r'\b(eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b', r'***JWT_TOKEN***', 'JWT'),
    ]

    # Trading terms that should NEVER be masked
    TRADING_SAFE_KEYWORDS = {
        'symbol', 'price', 'quantity', 'amount', 'volume',
        'user_id', 'order_id', 'trade_id', 'position_id', 'portfolio_id',
        'broker', 'exchange', 'side', 'buy', 'sell', 'limit', 'market',
        'nifty', 'sensex', 'reliance', 'infy', 'tcs', 'hdfc', 'icici',
        'nse', 'bse', 'upstox', 'zerodha', 'angel', 'dhan', 'kotak',
        'margin', 'exposure', 'pnl', 'profit', 'loss', 'risk',
        'equity', 'futures', 'options', 'commodity', 'currency',
        'inr', 'rupees', 'ltp', 'bid', 'ask', 'open', 'high', 'low', 'close'
    }

    def filter(self, record):
        """Apply security filtering while preserving trading data."""
        message = record.getMessage()
        original_message = message

        # Check if this is trading-related data
        message_lower = message.lower()
        is_trading_data = any(keyword in message_lower for keyword in self.TRADING_SAFE_KEYWORDS)

        if is_trading_data:
            # For trading data, only apply very specific security patterns
            # and avoid general masking that might affect trading information

            # Only mask clearly sensitive patterns like actual passwords/tokens
            for pattern, replacement, data_type in self.SENSITIVE_PATTERNS:
                if data_type in ['PASSWORD', 'API_KEY', 'TOKEN', 'BEARER_TOKEN', 'JWT']:
                    # Only mask authentication-related sensitive data
                    if re.search(pattern, message, re.IGNORECASE):
                        message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
                        setattr(record, 'security_filtered', True)
        else:
            # For non-trading data, apply all security patterns
            for pattern, replacement, data_type in self.SENSITIVE_PATTERNS:
                if re.search(pattern, message, re.IGNORECASE):
                    message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
                    setattr(record, 'security_filtered', True)

        # Update message if it was modified
        if message != original_message:
            record.msg = message
            record.args = ()

        # Add basic security classification without interfering with data
        setattr(record, 'data_classification', self._classify_data_safely(record))

        return True

    def _classify_data_safely(self, record):
        """Classify data type without masking legitimate information."""
        message = record.getMessage().lower()

        # Safe classification that won't trigger masking
        if any(word in message for word in ['password', 'token', 'secret', 'credential']):
            return 'AUTHENTICATION'
        elif any(word in message for word in ['order', 'trade', 'position', 'portfolio']):
            return 'TRADING_DATA'
        elif any(word in message for word in ['user', 'login', 'session']):
            return 'USER_ACTIVITY'
        elif any(word in message for word in ['market', 'price', 'quote']):
            return 'MARKET_DATA'
        else:
            return 'SYSTEM'


class MinimalSecurityFilter(logging.Filter):
    """Minimal security filter that only masks obvious sensitive data."""

    def filter(self, record):
        """Apply minimal security filtering."""
        message = record.getMessage()
        original_message = message

        # Only mask very obvious sensitive patterns
        sensitive_patterns = [
            # Clear password assignments
            (r'(password\s*=\s*)["\']([^"\']+)["\']', r'\1"***MASKED***"'),
            (r'(pwd\s*=\s*)["\']([^"\']+)["\']', r'\1"***MASKED***"'),

            # API key assignments
            (r'(api_key\s*=\s*)["\']([^"\']+)["\']', r'\1"***MASKED***"'),
            (r'(secret\s*=\s*)["\']([^"\']+)["\']', r'\1"***MASKED***"'),

            # Authorization headers
            (r'(Authorization:\s*Bearer\s+)([A-Za-z0-9._-]+)', r'\1***MASKED***'),
        ]

        for pattern, replacement in sensitive_patterns:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

        # Update message if modified
        if message != original_message:
            record.msg = message
            record.args = ()
            setattr(record, 'security_filtered', True)

        return True


class NoSecurityFilter(logging.Filter):
    """Pass-through filter that doesn't mask anything - for development use."""

    def filter(self, record):
        """No filtering - pass everything through."""
        return True