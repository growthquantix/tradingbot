import os
import google.generativeai as genai
from database.connection import SessionLocal
from database.models import TradeHistory, User
from sqlalchemy.orm import Session

class AISupportService:
    def __init__(self, gemini_api_key: str):
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.docs_cache = self._load_docs()

    def _load_docs(self):
        """Load project documentation into memory as a knowledge base."""
        docs_content = ""
        docs_dir = "docs/"
        if os.path.exists(docs_dir):
            for root, dirs, files in os.walk(docs_dir):
                for file in files:
                    if file.endswith(".md"):
                        try:
                            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                                docs_content += f"\n--- {file} ---\n" + f.read()
                        except:
                            pass
        return docs_content[:20000] # Limit for Gemini context window

    def _get_user_context(self, db: Session, user_email: str):
        """Fetch recent trades to provide context for 'Why did my trade close?' questions."""
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return "User not found."
            
        trades = db.query(TradeHistory).filter(TradeHistory.user_id == user.id).order_by(TradeHistory.exit_time.desc()).limit(3).all()
        context = f"User Email: {user_email}\nRecent Trades:\n"
        for t in trades:
            context += f"- {t.symbol}: Side={t.signal}, Entry={t.entry_price}, Exit={t.exit_price}, PnL={t.pnl}, Reason={t.exit_reason}\n"
        return context

    def answer_query(self, query: str, user_email: str = None):
        """Main entry point to answer a support query."""
        db = SessionLocal()
        try:
            user_context = self._get_user_context(db, user_email) if user_email else "No user logged in."
            
            prompt = f"""
            You are 'GrowthQuantix AI Support', an assistant for a specialized Indian Algorithmic Trading Platform.
            
            Platform Documentation (Knowledge Base):
            {self.docs_cache}
            
            Current User Context:
            {user_context}
            
            User Question: {query}
            
            Guidelines:
            1. Use the documentation to answer platform-related questions.
            2. If asked about a recent trade, use the User Context provided.
            3. Be professional, concise, and helpful.
            4. If you don't know the answer, tell them to contact 'support@growthquantix.com'.
            """
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
        finally:
            db.close()

# Example usage singleton
ai_support = AISupportService(os.getenv("GEMINI_API_KEY", ""))
