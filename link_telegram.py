
import os
from database.connection import SessionLocal
from database.models import User

def link_account(email, chat_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.telegram_chat_id = str(chat_id)
            db.commit()
            print(f"✅ Successfully linked Telegram ID {chat_id} to user {email}")
        else:
            print(f"❌ User with email {email} not found.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # REPLACE with your login email
    MY_EMAIL = "your_email@example.com" 
    MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
    
    link_account(MY_EMAIL, MY_CHAT_ID)
