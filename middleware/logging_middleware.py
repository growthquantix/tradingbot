"""
Logging Middleware for Trading Application

This middleware adds comprehensive logging for all HTTP requests and responses,
including correlation ID tracking, performance monitoring, and audit logging.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from core.logging_config import get_logger, set_correlation_id, get_correlation_id
from core.performance_logger import performance_logger
from core.audit_logger import audit_logger


class LoggingMiddleware:
    """Middleware for comprehensive request/response logging."""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger('trading_app.middleware')

    async def __call__(self, scope, receive, send):
        """Process request with comprehensive logging."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create correlation ID for this request
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Extract request information
        request = Request(scope, receive)
        start_time = time.perf_counter()

        # Log request start
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                'method': request.method,
                'path': request.url.path,
                'query_params': str(request.query_params),
                'user_agent': request.headers.get('user-agent'),
                'client_ip': self._get_client_ip(request),
                'request_id': correlation_id,
                'event': 'request_start'
            }
        )

        # Process response
        response_body = b""
        status_code = 500

        async def send_wrapper(message):
            nonlocal response_body, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # Log unhandled exceptions
            self.logger.error(
                f"Unhandled exception in request: {str(e)}",
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'error': str(e),
                    'request_id': correlation_id,
                    'event': 'request_error'
                },
                exc_info=True
            )

            # Send error response
            error_response = JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": correlation_id
                }
            )
            await error_response(scope, receive, send)
            return

        # Calculate duration
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        # Log request completion
        self.logger.info(
            f"Request completed: {request.method} {request.url.path} - {status_code} - {duration_ms:.2f}ms",
            extra={
                'method': request.method,
                'path': request.url.path,
                'status_code': status_code,
                'duration_ms': round(duration_ms, 3),
                'response_size': len(response_body),
                'request_id': correlation_id,
                'event': 'request_complete'
            }
        )

        # Log API performance
        performance_logger.log_api_request(
            endpoint=request.url.path,
            method=request.method,
            duration_ms=duration_ms,
            status_code=status_code,
            request_size=int(request.headers.get('content-length', 0)),
            response_size=len(response_body)
        )

        # Log security events for authentication endpoints
        if self._is_auth_endpoint(request.url.path):
            user_id = await self._extract_user_id(request)
            success = 200 <= status_code < 400

            if request.url.path.endswith('/login'):
                audit_logger.log_user_login(
                    user_id=user_id or 'unknown',
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get('user-agent'),
                    success=success
                )
            elif request.url.path.endswith('/logout'):
                audit_logger.log_user_logout(user_id=user_id or 'unknown')

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded header first (proxy/load balancer)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        # Check for real IP header
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip

        # Fall back to direct client
        if hasattr(request, 'client') and request.client:
            return request.client.host

        return 'unknown'

    def _is_auth_endpoint(self, path: str) -> bool:
        """Check if path is an authentication endpoint."""
        auth_paths = ['/login', '/logout', '/register', '/auth/', '/token/']
        return any(auth_path in path for auth_path in auth_paths)

    async def _extract_user_id(self, request: Request) -> str:
        """Extract user ID from request if available."""
        # Try to get from JWT token
        auth_header = request.headers.get('authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                import jwt
                from core.config import JWT_SECRET_KEY

                token = auth_header.split(' ')[1]
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
                return payload.get('user_id')
            except:
                pass

        # Try to get from form data for login requests
        if request.method == 'POST':
            try:
                form_data = await request.form()
                return form_data.get('username') or form_data.get('email')
            except:
                pass

        return None


def add_logging_middleware(app):
    """Add logging middleware to FastAPI app."""
    app.add_middleware(LoggingMiddleware)