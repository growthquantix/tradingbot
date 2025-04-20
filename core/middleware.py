import logging
import os
import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# ✅ Configure Logger (Console Only)
logger = logging.getLogger("middleware_logger")
logger.setLevel(logging.DEBUG)

# ✅ Console Handler (Logs to Terminal)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

# ✅ Add Console Handler (No File Logging)
logger.addHandler(console_handler)

# ✅ Load Secret Keys
SECRET_KEY = os.getenv("JWT_SECRET", "your-access-secret-key")
ALGORITHM = "HS256"

# ✅ Allowed Origins (Frontend URLs)
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # ✅ Local Dev (React Frontend)
    "https://resplendent-shortbread-e830d3.netlify.app",  # ✅ Production Frontend
    "http://localhost:8000",  # ✅ Local Backend (FastAPI)
    "https://tradingbot-ttys.onrender.com",  # ✅ Production Backend
    "https://growthquantix.com",  # ✅ Production Frontend
    "https://www.growthquantix.com",  # ✅ Production Frontend
    "https://api.growthquantix.com",  # ✅ Production Backend
    "https://api.growthquantix.com/v1",  # ✅ Production Backend (API Version)
]


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware to detect expired tokens, refresh them, and log requests"""

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("Origin", "")
        logger.info(
            f"📌 Incoming request: {request.method} {request.url.path} from {origin}"
        )

        # ✅ Handle CORS Preflight (OPTIONS Request)
        if request.method == "OPTIONS":
            logger.info(f"🔍 Handling CORS Preflight request from {origin}")
            response = JSONResponse(status_code=200, content={})
            if origin in ALLOWED_ORIGINS:
                response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            return response

        access_token = request.headers.get("Authorization")

        if access_token and "Bearer" in access_token:
            access_token = access_token.split("Bearer ")[-1]
            try:
                jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
                logger.info(
                    f"✅ Token successfully validated for request: {request.url.path}"
                )
            except jwt.ExpiredSignatureError:
                logger.warning(f"⚠️ Token expired for request: {request.url.path}")
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Access token expired", "code": "token_expired"},
                )
                if origin in ALLOWED_ORIGINS:
                    response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Headers"] = (
                    "Authorization, Content-Type"
                )
                response.headers["Access-Control-Allow-Methods"] = (
                    "GET, POST, PUT, DELETE"
                )
                return response
            except jwt.PyJWTError as e:
                logger.error(
                    f"❌ Invalid Token Error: {str(e)} for request: {request.url.path}"
                )
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token"},
                )
                if origin in ALLOWED_ORIGINS:
                    response.headers["Access-Control-Allow-Origin"] = origin
                return response

        response = await call_next(request)

        # ✅ Log Response Status
        logger.info(
            f"📤 Response {response.status_code} for {request.method} {request.url.path}"
        )

        # ✅ Set Correct CORS Headers on Response
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
