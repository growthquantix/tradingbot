from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import BrokerConfig, Trade, User
from pydantic import BaseModel
import jwt
import os
import requests
import logging
from database.models import BrokerConfig
from services.upstox_service import generate_upstox_auth_url, exchange_upstox_token

# ✅ Configure Logging
logger = logging.getLogger(__name__)

# Load JWT Secret Key
SECRET_KEY = os.getenv("JWT_SECRET")
# API Router
broker_router = APIRouter()

# ✅ Broker API URLs
BROKER_API_URLS = {
    "Dhan": "https://api.dhan.co/v2",
    "Zerodha": "https://kite.zerodha.com/connect/login",
    "Upstox": "https://api.upstox.com/login",
    "Angel One": "https://smartapi.angelbroking.com/authenticate",
    "Fyers": "https://api.fyers.in/api/v2/validate-token",
}


# ✅ Schema for Broker Request
class BrokerAuthRequest(BaseModel):
    broker_name: str
    credentials: dict


# ✅ Helper Function to Get User ID from JWT
def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract user_id from JWT token"""
    if not authorization:
        logger.warning("🔴 No Authorization header received!")
        raise HTTPException(status_code=401, detail="Missing Authorization Token")

    if "Bearer " not in authorization:
        logger.error(f"🔴 Invalid Authorization header format: {authorization}")
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format"
        )

    token = authorization.split("Bearer ")[-1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")  # Extract email

        if not email:
            raise HTTPException(status_code=401, detail="Invalid token: No user found")

        # ✅ Fetch user ID from the database using the email
        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        logger.info(
            f"🟢 Token decoded successfully for user: {user.id} (email: {email})"
        )
        return user.id  # Return integer user ID instead of email

    except jwt.ExpiredSignatureError:
        logger.warning("🔴 Token expired!")
        raise HTTPException(
            status_code=401, detail="Token expired. Please log in again."
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"🔴 Invalid token error: {str(e)}")
        raise HTTPException(
            status_code=401, detail="Invalid token. Please log in again."
        )


# ✅ Function to Verify Broker Credentials with Error Handling
def verify_broker_credentials(broker_name: str, credentials: dict):
    """Verify broker credentials dynamically based on the selected broker."""
    if broker_name not in BROKER_API_URLS:
        logger.error(f"🔴 Unsupported broker: {broker_name}")
        raise HTTPException(status_code=400, detail="Unsupported broker")

    try:
        if broker_name == "Dhan":
            headers = {"access-token": credentials["access_token"]}
            response = requests.get(f"https://api.dhan.co/v2/profile", headers=headers)

        elif broker_name == "Zerodha":
            response = requests.post(BROKER_API_URLS[broker_name], json=credentials)

        elif broker_name == "Upstox":
            api_key = credentials.get("api_key")
            api_secret = credentials.get("api_secret")
            if not api_key or not api_secret:
                raise HTTPException(status_code=400, detail="Missing API key or secret")
            # Return auth URL to frontend
            auth_url = generate_upstox_auth_url(api_key)
            return {
                "auth_url": auth_url,
                "client_id": api_key,
                "api_secret": api_secret,
            }

        elif broker_name == "Angel One":
            response = requests.post(BROKER_API_URLS[broker_name], json=credentials)

        elif broker_name == "Fyers":
            response = requests.post(BROKER_API_URLS[broker_name], json=credentials)

        else:
            raise HTTPException(status_code=400, detail="Invalid broker")

        if response.status_code == 200:
            logger.info(f"🟢 Credentials verified for {broker_name}")
            return response.json()
        else:
            logger.error(
                f"🔴 Invalid credentials for {broker_name}. Response: {response.text}"
            )
            raise HTTPException(
                status_code=400, detail=f"Invalid {broker_name} credentials"
            )

    except requests.RequestException as e:
        logger.error(f"🔴 Broker API error for {broker_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Broker API error: {str(e)}")


# ✅ Authenticate Broker API
@broker_router.post("/authenticate")
def authenticate_broker(
    request: BrokerAuthRequest, user_id: int = Depends(get_current_user)
):
    """Verify credentials with broker API"""
    try:
        response = verify_broker_credentials(request.broker_name, request.credentials)
        return {"message": "Broker authenticated successfully", "broker_data": response}
    except Exception as e:
        logger.error(f"🔴 Authentication failed for {request.broker_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Add Broker API (After Authentication)
@broker_router.post("/add")
def add_broker(
    request: BrokerAuthRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """First verifies the broker, then adds it to the database"""
    try:
        # ✅ Step 1: Verify broker credentials dynamically
        broker_data = verify_broker_credentials(
            request.broker_name, request.credentials
        )

        expiry_str = broker_data.get("tokenValidity")  # Example: '29/03/2025 22:21'
        expiry_datetime = None  # Default value

        if expiry_str:
            try:
                # Convert from 'DD/MM/YYYY HH:MM' → 'YYYY-MM-DD HH:MM:SS'
                expiry_datetime = datetime.strptime(expiry_str, "%d/%m/%Y %H:%M")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Expected 'DD/MM/YYYY HH:MM'.",
                )

        # ✅ Step 2: Save broker details in the database
        new_broker = BrokerConfig(
            user_id=user_id,
            broker_name=request.broker_name,
            access_token=request.credentials.get("access_token"),  # ✅ Store securely
            client_id=request.credentials.get("client_id"),  # ✅ Store securely
            access_token_expiry=expiry_datetime,  # ✅ Store securely # ✅ Store securely
            is_active=True,
        )
        db.add(new_broker)
        db.commit()

        logger.info(f"🟢 {request.broker_name} added successfully for user {user_id}")
        return {
            "message": f"{request.broker_name} added successfully",
            "broker_data": broker_data,
        }
    except Exception as e:
        logger.error(f"🔴 Failed to add broker {request.broker_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Get All Brokers API
@broker_router.get("/list")
def get_brokers(
    user_id: int = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Fetch all brokers linked to a user"""
    try:
        brokers = db.query(BrokerConfig).filter(BrokerConfig.user_id == user_id).all()
        logger.info(f"🟢 Retrieved {len(brokers)} brokers for user {user_id}")
        return {"brokers": brokers}
    except Exception as e:
        logger.error(f"🔴 Failed to fetch brokers for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Delete Broker API
@broker_router.delete("/delete/{broker_id}")
def delete_broker(
    broker_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a broker from the user's account"""
    try:
        broker = (
            db.query(BrokerConfig)
            .filter(BrokerConfig.id == broker_id, BrokerConfig.user_id == user_id)
            .first()
        )
        if not broker:
            logger.warning(f"🔴 Broker {broker_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Broker not found")

        db.delete(broker)
        db.commit()
        logger.info(f"🟢 Deleted broker {broker_id} for user {user_id}")
        return {"message": "Broker deleted successfully"}
    except Exception as e:
        logger.error(f"🔴 Failed to delete broker {broker_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@broker_router.post("/execute-trade")
async def execute_trade(
    user_id: int,
    symbol: str,
    trade_type: str,  # BUY or SELL
    quantity: int,
    price: float,
    db: Session = Depends(get_db),
):
    """Execute a trade and send a real-time WebSocket update."""
    try:
        # ✅ Store Trade in Database
        new_trade = Trade(
            user_id=user_id,
            symbol=symbol,
            trade_type=trade_type,
            entry_price=price,
            quantity=quantity,
            status="OPEN",
            created_at=datetime.now(),
        )
        db.add(new_trade)
        db.commit()

        # ✅ Prepare Real-Time Update Data
        trade_data = {
            "trade_id": new_trade.id,
            "symbol": symbol,
            "trade_type": trade_type,
            "quantity": quantity,
            "price": price,
            "status": "OPEN",
            "timestamp": datetime.now().isoformat(),
        }

        # ✅ Send WebSocket Update to Frontend
        await send_trade_update(str(user_id), trade_data)

        return {"message": "Trade executed successfully", "trade": trade_data}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))




@broker_router.get("/callback")
def upstox_callback(code: str, state: str = None, db: Session = Depends(get_db)):
    """Handle OAuth callback from Upstox."""
    try:
        # Retrieve user's pending Upstox config (based on saved client_id or state)
        client_id = state  # Optional if using state
        user = db.query(User).filter(User.email == state).first() if state else None

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get temp credentials stored before redirect (you can also use Redis, etc.)
        config = db.query(BrokerConfig).filter(BrokerConfig.client_id == client_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Pending broker config not found")

        # Exchange code for token
        tokens = exchange_upstox_token(code, config.client_id, config.api_key)

        # Save access token and expiry
        config.access_token = tokens["access_token"]
        config.refresh_token = tokens.get("refresh_token")
        config.access_token_expiry = datetime.now() + timedelta(seconds=tokens.get("expires_in", 0))
        config.is_active = True
        db.commit()

        return {"message": "Upstox linked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
