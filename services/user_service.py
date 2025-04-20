from fastapi import HTTPException
import logging
from sqlalchemy.orm import Session
from database.models import User
from database.schemas import UserResponse, UserProfileUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_user_profile(db: Session, user_id: int):
    try:
        logger.info(f"🔍 Fetching user profile for user_id={user_id}")

        # Performance optimized: preload broker configs
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning(f"❌ User not found for user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        if not user.full_name:
            logger.warning(f"❌ Full name missing for user_id={user_id}")
            raise HTTPException(status_code=404, detail="User name not found")
        if not user.email:
            logger.warning(f"❌ Email missing for user_id={user_id}")
            raise HTTPException(status_code=404, detail="User email not found")
        if not user.phone_number:
            logger.warning(f"❌ Phone number missing for user_id={user_id}")
            raise HTTPException(status_code=404, detail="User phone number not found")
        if not user.broker_configs or len(user.broker_configs) == 0:
            logger.warning(f"❌ Broker account missing for user_id={user_id}")
            raise HTTPException(status_code=404, detail="Broker account not found")

        broker_accounts = []
        for broker in user.broker_configs:
            if not broker.broker_name:
                logger.warning(
                    f"❌ Broker name missing in broker config for user_id={user_id}"
                )
                raise HTTPException(status_code=404, detail="Broker name not found")

            broker_accounts.append(
                {
                    "id": broker.id,
                    "broker_name": broker.broker_name,
                    # Add more fields here if needed like `api_key`, `connected`, etc.
                }
            )

        logger.info(f"✅ Successfully fetched profile for user_id={user_id}")
        return {
            "name": user.full_name,
            "email": user.email,
            "phone": user.phone_number,
            "brokerAccounts": broker_accounts,
        }

    except HTTPException as http_err:
        logger.error(f"⚠️ HTTPException while fetching user profile: {http_err.detail}")
        raise http_err

    except Exception as e:
        logger.exception(
            f"🔥 Unhandled exception while fetching user profile for user_id={user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


def update_user_profile(db: Session, user_id: int, data: UserProfileUpdate):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.name = data.name
    db.commit()
    return {"message": "Profile updated successfully"}
