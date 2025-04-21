from datetime import datetime, timedelta
import os
import logging
from sqlalchemy.orm import Session
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Dict, Optional
import requests
from database.connection import SessionLocal, get_db
from database.models import BrokerConfig, User
from services.auth_service import get_current_user
from services.upstox_service import (
    calculate_upstox_expiry,
    exchange_code_for_token,
    generate_upstox_auth_url,
)
from services.upstox_temp_store import (
    store_upstox_credentials_temp,
    get_upstox_credentials_temp,
    clear_upstox_credentials_temp,
)

logger = logging.getLogger(__name__)
db = SessionLocal()

# Initialize router without prefix
upstox_router = APIRouter()
UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")


class UpstoxConfiguration(BaseModel):
    broker: str
    config: Dict[str, str]


@upstox_router.get("/status")
async def check_status():
    """
    Check Upstox connection status
    """
    # TODO: Implement status check logic
    return {"status": "operational"}


@upstox_router.post("/init-auth")
def initiate_upstox_auth(data: dict, user_id: int = Depends(get_current_user)):
    client_id = data.get("api_key")
    api_secret = data.get("api_secret")
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing api_key")
    state = str(user_id.id)
    store_upstox_credentials_temp(state, client_id, api_secret)
    auth_url = generate_upstox_auth_url(client_id, user_id.id)
    return {"auth_url": auth_url}


# OAuth Callback Endpoint
@upstox_router.get("/callback")
def upstox_callback(code: str, state: str = None, db: Session = Depends(get_db)):
    try:
        user_id = int(state)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # ✅ Retrieve existing broker config if present
        existing_config = (
            db.query(BrokerConfig)
            .filter(
                BrokerConfig.user_id == user_id,
                BrokerConfig.broker_name.ilike("upstox"),
            )
            .first()
        )

        # ✅ Retrieve credentials: from DB or temp store
        if existing_config:
            creds = {
                "client_id": existing_config.api_key,
                "client_secret": existing_config.api_secret,
            }
        else:
            creds = get_upstox_credentials_temp(user_id)

        if not creds:
            raise HTTPException(status_code=400, detail="Missing temporary credentials")

        # ✅ Exchange code for tokens
        token_response = exchange_code_for_token(
            code, creds["client_id"], creds["client_secret"]
        )
        access_token_expiry = calculate_upstox_expiry()

        if existing_config:
            # 🔄 Update existing config
            existing_config.access_token = token_response["access_token"]
            existing_config.api_key = creds["client_id"]
            existing_config.api_secret = creds["client_secret"]
            existing_config.access_token_expiry = access_token_expiry
            existing_config.additional_params = token_response
            existing_config.is_active = token_response.get("is_active", True)
            existing_config.config = {
                "email": token_response.get("email"),
                "user_name": token_response.get("user_name"),
                "user_type": token_response.get("user_type"),
                "poa": token_response.get("poa"),
                "ddpi": token_response.get("ddpi"),
                "exchanges": token_response.get("exchanges"),
                "products": token_response.get("products"),
                "order_types": token_response.get("order_types"),
                "extended_token": token_response.get("extended_token"),
            }
        else:
            # 🆕 Create new config
            new_config = BrokerConfig(
                user_id=user_id,
                client_id=token_response["user_id"],
                broker_name=token_response["broker"],
                api_key=creds["client_id"],
                api_secret=creds["client_secret"],
                access_token=token_response["access_token"],
                access_token_expiry=access_token_expiry,
                created_at=datetime.now(),
                is_active=token_response.get("is_active", True),
                additional_params=token_response,
                config={
                    "email": token_response.get("email"),
                    "user_name": token_response.get("user_name"),
                    "user_type": token_response.get("user_type"),
                    "poa": token_response.get("poa"),
                    "ddpi": token_response.get("ddpi"),
                    "exchanges": token_response.get("exchanges"),
                    "products": token_response.get("products"),
                    "order_types": token_response.get("order_types"),
                    "extended_token": token_response.get("extended_token"),
                },
            )
            db.add(new_config)

        db.commit()
        clear_upstox_credentials_temp(user_id)

        logger.info(f"✅ Upstox linked successfully for user_id={user_id}")
        return {"message": "Upstox broker linked successfully."}

    except Exception as e:
        logger.exception(f"❌ Upstox callback failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@upstox_router.get("/token")
def get_upstox_token(current_user: User = Depends(get_current_user)):
    upstox_token = None

    for broker in current_user.brokers:
        if broker.broker_name.lower() == "upstox":
            upstox_token = broker.access_token  # or broker.upstox_access_token
            break

    if not upstox_token:
        return {"error": "No Upstox token found"}

    return {"access_token": upstox_token}


@upstox_router.post("/refresh/{broker_id}")
def refresh_upstox_token(broker_id: int, db: Session = Depends(get_db)):
    broker = db.query(BrokerConfig).filter(BrokerConfig.id == broker_id).first()

    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    if broker.broker_name.lower() != "upstox":
        raise HTTPException(
            status_code=400, detail="Token refresh only supported for Upstox"
        )

    if not broker.api_key or not broker.api_secret:
        raise HTTPException(status_code=400, detail="Missing Upstox credentials")

    # Generate OAuth2 auth URL again
    auth_url = generate_upstox_auth_url(api_key=broker.api_key, user_id=broker.user_id)

    # Return auth_url so frontend can open it in a popup
    return {"auth_url": auth_url}
