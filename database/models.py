from datetime import datetime
from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Date,
    Text,
    UniqueConstraint,
    Numeric,
    BigInteger,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =======================
# User & Authentication
# =======================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(String, default="trader")  # Options: Admin, Trader, Analyst
    isVerified = Column(Boolean, default=False)
    country_code = Column(String, nullable=True)
    phone_number = Column(String, nullable=True, index=True, unique=True)
    phone_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    google_id = Column(String, nullable=True, unique=True)
    avatar_url = Column(String, nullable=True)
    auth_provider = Column(String, default="email")  # email, google
    email_verified = Column(Boolean, default=False)
    profile_picture = Column(String, nullable=True)

    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete")
    broker_configs = relationship(
        "BrokerConfig", back_populates="user", cascade="all, delete"
    )
    trading_sessions = relationship(
        "TradingSession", back_populates="user", cascade="all, delete"
    )
    trades = relationship("Trade", back_populates="user", cascade="all, delete")
    orders = relationship("Order", back_populates="user", cascade="all, delete")
    ai_models = relationship("AIModel", back_populates="user", cascade="all, delete")
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete")
    trading_performance = relationship(
        "TradingPerformance", back_populates="user", cascade="all, delete"
    )
    trade_performance = relationship(
        "TradePerformance", back_populates="user", cascade="all, delete"
    )
    trading_config = relationship(
        "UserTradingConfig", back_populates="user", cascade="all, delete", uselist=False
    )
    trading_reports = relationship(
        "TradingReport", back_populates="user", cascade="all, delete"
    )
    historical_data = relationship(
        "HistoricalData", back_populates="user", cascade="all, delete"
    )
    user_capital = relationship(
        "UserCapital", back_populates="user", cascade="all, delete"
    )
    paper_account = relationship(
        "PaperTradingAccount",
        back_populates="user",
        uselist=False,
        cascade="all, delete",
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete"
    )
    social_auths = relationship(
        "SocialAuth", back_populates="user", cascade="all, delete"
    )

    auto_trading_sessions = relationship(
        "AutoTradingSession", back_populates="user", cascade="all, delete"
    )
    daily_trading_reports = relationship(
        "DailyTradingReport", back_populates="user", cascade="all, delete"
    )
    notification_preferences = relationship(
        "UserNotificationPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete",
    )

    # New Auto-Trading System Relationships
    auto_trade_executions = relationship(
        "AutoTradeExecution", back_populates="user", cascade="all, delete"
    )
    active_positions = relationship(
        "ActivePosition", back_populates="user", cascade="all, delete"
    )
    daily_performances = relationship(
        "DailyTradingPerformance", back_populates="user", cascade="all, delete"
    )
    emergency_controls = relationship(
        "EmergencyControl", back_populates="user", cascade="all, delete"
    )
    trading_logs = relationship(
        "TradingSystemLog", back_populates="user", cascade="all, delete"
    )
    audit_trails = relationship(
        "TradingAuditTrail", back_populates="user", cascade="all, delete"
    )
    fno_selection_history = relationship(
        "FNOSelectionHistory", back_populates="user", cascade="all, delete"
    )

    # Password Management
    def set_password(self, password):
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)


# =======================
# Broker & Configuration
# =======================
class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    broker_name = Column(String, nullable=False)
    account_number = Column(String, unique=True, nullable=False)
    balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="accounts")
    trades = relationship("Trade", back_populates="account", cascade="all, delete")
    orders = relationship("Order", back_populates="account", cascade="all, delete")


class BrokerConfig(Base):
    __tablename__ = "broker_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    client_id = Column(String, nullable=True)
    broker_name = Column(String, index=True)
    api_key = Column(String, nullable=True)
    api_secret = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    feed_token = Column(String, nullable=True)
    additional_params = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=False)
    access_token_expiry = Column(DateTime, nullable=True)
    last_error_message = Column(String, nullable=True)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Funds and Margin Fields (Equity)
    available_margin = Column(
        Float, nullable=True, comment="Available margin for trading"
    )
    used_margin = Column(Float, nullable=True, comment="Currently used margin")
    payin_amount = Column(Float, nullable=True, comment="Instant payin amount")
    span_margin = Column(Float, nullable=True, comment="SPAN margin for F&O")
    adhoc_margin = Column(Float, nullable=True, comment="Adhoc margin")
    notional_cash = Column(Float, nullable=True, comment="Notional cash")
    exposure_margin = Column(Float, nullable=True, comment="Exposure margin for F&O")

    # Commodity Funds (if applicable)
    commodity_available_margin = Column(
        Float, nullable=True, comment="Commodity available margin"
    )
    commodity_used_margin = Column(
        Float, nullable=True, comment="Commodity used margin"
    )

    # Calculated Fields
    total_portfolio_value = Column(
        Float, nullable=True, comment="Total portfolio value"
    )
    margin_utilization_percent = Column(
        Float, nullable=True, comment="Margin utilization percentage"
    )
    funds_last_updated = Column(
        DateTime, nullable=True, comment="Last funds data update"
    )

    # User Profile Fields (cached from broker API)
    user_name = Column(String, nullable=True, comment="Broker account user name")
    email = Column(String, nullable=True, comment="Broker account email")
    user_type = Column(String, nullable=True, comment="User type (individual, etc.)")
    exchanges = Column(JSON, nullable=True, comment="Enabled exchanges")
    products = Column(JSON, nullable=True, comment="Enabled products")
    order_types = Column(JSON, nullable=True, comment="Enabled order types")
    poa_enabled = Column(Boolean, nullable=True, comment="Power of Attorney enabled")
    ddpi_enabled = Column(Boolean, nullable=True, comment="DDPI enabled")
    account_status = Column(String, nullable=True, comment="Account status")
    profile_last_updated = Column(
        DateTime, nullable=True, comment="Last profile data update"
    )

    # Relationships
    user = relationship("User", back_populates="broker_configs")

    def get_margin_utilization(self):
        """Calculate margin utilization percentage"""
        if self.available_margin and self.available_margin > 0:
            return (self.used_margin or 0) / self.available_margin * 100
        return 0.0

    def get_free_margin(self):
        """Get available free margin"""
        available = self.available_margin or 0
        used = self.used_margin or 0
        return max(0, available - used)

    def can_place_order(self, required_margin):
        """Check if broker has enough margin for order"""
        return self.get_free_margin() >= required_margin

    def update_funds_data(self, funds_data):
        """Update funds data from API response"""
        if not funds_data or "data" not in funds_data:
            return

        data = funds_data["data"]

        # Update equity funds
        if "equity" in data:
            equity = data["equity"]
            self.available_margin = equity.get("available_margin", 0)
            self.used_margin = equity.get("used_margin", 0)
            self.payin_amount = equity.get("payin_amount", 0)
            self.span_margin = equity.get("span_margin", 0)
            self.adhoc_margin = equity.get("adhoc_margin", 0)
            self.notional_cash = equity.get("notional_cash", 0)
            self.exposure_margin = equity.get("exposure_margin", 0)

        # Update commodity funds
        if "commodity" in data:
            commodity = data["commodity"]
            self.commodity_available_margin = commodity.get("available_margin", 0)
            self.commodity_used_margin = commodity.get("used_margin", 0)

        # Update calculated fields
        self.margin_utilization_percent = self.get_margin_utilization()
        self.funds_last_updated = datetime.now()

    def update_profile_data(self, profile_data):
        """Update profile data from API response"""
        if not profile_data or "data" not in profile_data:
            return

        data = profile_data["data"]

        self.user_name = data.get("user_name")
        self.email = data.get("email")
        self.user_type = data.get("user_type", "individual")
        self.exchanges = data.get("exchanges", [])
        self.products = data.get("products", [])
        self.order_types = data.get("order_types", [])
        self.poa_enabled = data.get("poa", False)
        self.ddpi_enabled = data.get("ddpi", False)
        self.account_status = "active" if data.get("is_active", False) else "inactive"
        self.profile_last_updated = datetime.now()


# =======================
# AI Model & Prediction Logs
# =======================
class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    model_type = Column(String, nullable=True)
    parameters = Column(JSON)
    accuracy = Column(Float, nullable=True)
    training_data_size = Column(Integer, nullable=True)
    last_trained_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="ai_models")
    predictions = relationship(
        "AIPredictionLog", back_populates="ai_model", cascade="all, delete"
    )
    strategies = relationship("Strategy", back_populates="ai_model")


class AIPredictionLog(Base):
    __tablename__ = "ai_prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(
        Integer, ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    symbol = Column(String, nullable=False)
    predicted_price = Column(Float, nullable=False)
    actual_price = Column(Float, nullable=True)
    prediction_time = Column(DateTime, default=func.now())
    accuracy = Column(Float, nullable=True)

    # Relationships
    ai_model = relationship("AIModel", back_populates="predictions")


# =======================
# Strategies
# =======================
class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    ai_model_id = Column(
        Integer, ForeignKey("ai_models.id", ondelete="SET NULL"), index=True
    )
    parameters = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="strategies")
    ai_model = relationship("AIModel", back_populates="strategies")
    trades = relationship("Trade", back_populates="strategy", cascade="all, delete")
    backtests = relationship(
        "Backtest", back_populates="strategy", cascade="all, delete"
    )
    paper_trades = relationship(
        "PaperTrade", back_populates="strategy", cascade="all, delete"
    )


# =======================
# Trading Sessions
# =======================
class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ai_model_id = Column(
        Integer, ForeignKey("ai_models.id", ondelete="SET NULL"), index=True
    )
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime, nullable=True)
    total_pnl = Column(Float, default=0.0)

    # Relationships
    user = relationship("User", back_populates="trading_sessions")
    ai_model = relationship("AIModel")
    trades = relationship("Trade", back_populates="session", cascade="all, delete")
    trading_performance = relationship(
        "TradingPerformance", back_populates="session", cascade="all, delete"
    )
    trading_reports = relationship(
        "TradingReport", back_populates="session", cascade="all, delete"
    )


# =======================
# Trades
# =======================
class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id = Column(
        Integer, ForeignKey("trading_sessions.id", ondelete="CASCADE"), index=True
    )
    strategy_id = Column(
        Integer, ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)  # BUY/SELL
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    status = Column(String, default="OPEN", nullable=False)  # OPEN, FILLED, CANCELED
    profit_loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="trades")
    session = relationship("TradingSession", back_populates="trades")
    account = relationship("Account", back_populates="trades")
    strategy = relationship("Strategy", back_populates="trades")


# =======================
# Orders
# =======================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    symbol = Column(String, nullable=False)
    order_type = Column(String, nullable=False)  # LIMIT, MARKET, STOP-LOSS
    price = Column(Float)
    quantity = Column(Integer)
    status = Column(String, default="PENDING")  # PENDING, FILLED, CANCELED
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="orders")
    account = relationship("Account", back_populates="orders")


# =======================
# Backtesting
# =======================
class Backtest(Base):
    __tablename__ = "backtests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    strategy_id = Column(
        Integer, ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_pnl = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User")
    strategy = relationship("Strategy", back_populates="backtests")


# =======================
# Paper Trading
# =======================
class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    strategy_id = Column(
        Integer, ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)  # BUY/SELL
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    status = Column(String, default="OPEN", nullable=False)
    profit_loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User")
    strategy = relationship("Strategy", back_populates="paper_trades")


# =======================
# Trading Performance
# =======================
class TradingPerformance(Base):
    __tablename__ = "trading_performance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id = Column(
        Integer, ForeignKey("trading_sessions.id", ondelete="CASCADE"), index=True
    )
    total_trades = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=False)
    total_profit_loss = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    performance_type = Column(String, nullable=False)  # LIVE, PAPER, BACKTEST
    generated_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="trading_performance")
    session = relationship("TradingSession")


# =======================
# Trading Reports
# =======================
class TradingReport(Base):
    __tablename__ = "trading_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id = Column(
        Integer, ForeignKey("trading_sessions.id", ondelete="CASCADE"), index=True
    )
    total_trades = Column(Integer, nullable=False)
    total_profit = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    report_type = Column(String, nullable=False)  # LIVE, PAPER, BACKTEST
    generated_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="trading_reports")
    session = relationship("TradingSession")


# =======================
# Stocks
# =======================
class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    exchange = Column(String(10), nullable=False, default="NSE")

    # Relationships
    stock_trades = relationship("StockTrade", back_populates="stock")


# =======================
# Stock Trading History
# =======================
class StockTrade(Base):
    __tablename__ = "stock_trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    trade_id = Column(
        Integer, ForeignKey("trades.id", ondelete="CASCADE"), index=True, nullable=True
    )
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    trade_date = Column(DateTime, default=func.now())
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    profit_loss = Column(Float, nullable=True)
    status = Column(String, default="OPEN")

    # Relationships
    user = relationship("User")
    stock = relationship("Stock", back_populates="stock_trades")


class OTP(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    otp_code = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    verification_method = Column(String, default="sms")
    is_verified = Column(Boolean, default=False)
    otp_type = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())

    __table_args__ = (CheckConstraint("phone_number IS NOT NULL OR email IS NOT NULL"),)


class HistoricalData(Base):
    __tablename__ = "historical_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False, default="NSE")
    date = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    user = relationship("User", back_populates="historical_data")


class UserCapital(Base):
    __tablename__ = "user_capital"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_capital = Column(Float, nullable=False)
    risk_percentage = Column(Float, nullable=False, default=1)

    user = relationship("User", back_populates="user_capital")


class PaperTradingAccount(Base):
    """Paper trading virtual account"""

    __tablename__ = "paper_trading_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    initial_capital = Column(
        Float, nullable=False, default=500000.0
    )  # ₹5 lakhs default
    current_balance = Column(Float, nullable=False, default=500000.0)
    used_margin = Column(Float, nullable=False, default=0.0)
    available_margin = Column(Float, nullable=False, default=500000.0)
    total_pnl = Column(Float, nullable=False, default=0.0)
    daily_pnl = Column(Float, nullable=False, default=0.0)
    positions_count = Column(Integer, nullable=False, default=0)
    max_positions = Column(Integer, nullable=False, default=10)
    max_risk_per_trade = Column(Float, nullable=False, default=0.02)  # 2%
    max_daily_loss = Column(Float, nullable=False, default=0.05)  # 5%
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="paper_account")


class PaperTradingPosition(Base):
    """Paper trading position tracking"""

    __tablename__ = "paper_trading_positions"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(
        Integer, ForeignKey("paper_trading_accounts.id"), nullable=False
    )
    symbol = Column(String, nullable=False)
    instrument_key = Column(String, nullable=False)
    option_type = Column(String, nullable=False)  # CE/PE
    strike_price = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    lot_size = Column(Integer, nullable=False)
    invested_amount = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False, default=0.0)
    pnl_percentage = Column(Float, nullable=False, default=0.0)
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")  # ACTIVE, CLOSED, PARTIAL
    entry_time = Column(DateTime(timezone=True), default=func.now())
    exit_time = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    account = relationship("PaperTradingAccount")


class PaperTradingHistory(Base):
    """Paper trading transaction history"""

    __tablename__ = "paper_trading_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(
        Integer, ForeignKey("paper_trading_accounts.id"), nullable=False
    )
    position_id = Column(
        String, ForeignKey("paper_trading_positions.position_id"), nullable=False
    )
    action = Column(String, nullable=False)  # BUY, SELL
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    pnl = Column(Float, nullable=True)  # Only for SELL actions
    pnl_percentage = Column(Float, nullable=True)  # Only for SELL actions
    timestamp = Column(DateTime(timezone=True), default=func.now())

    user = relationship("User")
    account = relationship("PaperTradingAccount")


class UserTradingConfig(Base):
    """User-specific trading configuration and preferences"""

    __tablename__ = "user_trading_config"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Trading Mode and Basic Settings
    trade_mode = Column(String(20), default="PAPER")  # LIVE, PAPER, SIMULATION
    default_qty = Column(Integer, default=1)  # Default quantity for trades

    # Risk Management Settings
    stop_loss_percent = Column(Float, default=2.0)  # Default stop loss percentage
    target_percent = Column(Float, default=4.0)  # Default target percentage
    max_positions = Column(Integer, default=3)  # Maximum concurrent positions
    risk_per_trade_percent = Column(Float, default=1.0)  # Risk per trade percentage

    # Trading Strategy Settings
    default_strategy = Column(
        String(50), default="MOMENTUM"
    )  # Default trading strategy
    default_timeframe = Column(String(10), default="5M")  # Default chart timeframe

    # Option Trading Settings
    option_strategy = Column(String(20), default="BUY")  # BUY, SELL, STRADDLE, STRANGLE
    option_expiry_preference = Column(
        String(20), default="NEAREST"
    )  # NEAREST, WEEKLY, MONTHLY
    enable_option_trading = Column(
        Boolean, default=True
    )  # Enable/disable option trading

    # Advanced Settings
    enable_auto_square_off = Column(
        Boolean, default=True
    )  # Auto square off at market close
    enable_bracket_orders = Column(Boolean, default=False)  # Enable bracket orders
    enable_trailing_stop = Column(Boolean, default=False)  # Enable trailing stop loss

    # Notification Settings
    enable_trade_notifications = Column(
        Boolean, default=True
    )  # Enable trade notifications
    enable_profit_loss_alerts = Column(Boolean, default=True)  # Enable P&L alerts

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="trading_config")

    # Indexes
    __table_args__ = (Index("idx_user_trading_config_user_id", "user_id"),)


class TradeSignal(Base):
    __tablename__ = "trade_signals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    execution_status = Column(String, nullable=False, default="PENDING")
    signal_time = Column(DateTime(timezone=True), nullable=False, default=func.now())


class BreakoutSignal(Base):
    """Database model for storing breakout/breakdown signals for historical analysis"""
    __tablename__ = "breakout_signals"

    id = Column(Integer, primary_key=True, index=True)
    instrument_key = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    breakout_type = Column(String, nullable=False, index=True)  # volume_breakout, momentum_breakout, resistance_breakout, etc.
    
    # Price data
    current_price = Column(Numeric(precision=10, scale=2), nullable=False)
    breakout_price = Column(Numeric(precision=10, scale=2), nullable=False)
    trigger_price = Column(Numeric(precision=10, scale=2), nullable=False)
    
    # Signal strength and confidence
    percentage_move = Column(Float, nullable=False)
    strength = Column(Float, nullable=False)  # 1-10 scale
    confidence = Column(Float, nullable=False)  # 0-100% confidence score
    
    # Volume data
    volume = Column(BigInteger, nullable=False)
    volume_ratio = Column(Float, nullable=True)
    
    # Technical indicators
    volatility_score = Column(Float, nullable=True)
    market_cap_category = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    
    # Metadata
    confirmation_signals = Column(JSON, nullable=True)  # Array of confirmation signals
    detected_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    trading_date = Column(Date, nullable=False, index=True)  # For daily cleanup and analysis
    
    # Market context
    market_hours = Column(Boolean, default=True)
    market_status = Column(String, nullable=True)
    
    # Performance tracking (to be updated later)
    follow_through = Column(Boolean, nullable=True)  # Did breakout continue?
    max_move_after = Column(Float, nullable=True)  # Maximum % move after breakout
    duration_held = Column(Integer, nullable=True)  # Minutes the breakout was sustained
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_breakout_symbol_date', 'symbol', 'trading_date'),
        Index('idx_breakout_type_date', 'breakout_type', 'trading_date'),
        Index('idx_breakout_detected_at', 'detected_at'),
        Index('idx_breakout_strength', 'strength'),
    )


class AITradeJournal(Base):
    __tablename__ = "ai_trade_journal"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)
    ai_confidence = Column(Float, nullable=False)
    execution_status = Column(String, nullable=False)
    profit_loss = Column(Float, nullable=True)
    trade_time = Column(DateTime(timezone=True), nullable=False, default=func.now())


class TradePerformance(Base):
    __tablename__ = "trade_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    trailing_stop_loss = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    profit_loss = Column(Float, nullable=True)
    trade_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    status = Column(String, nullable=False, default="OPEN")

    user = relationship("User", back_populates="trade_performance")


class BrokerInstrument(Base):
    __tablename__ = "broker_instruments"

    id = Column(Integer, primary_key=True)
    broker_name = Column(String, nullable=False, default="Upstox")
    symbol = Column(String, nullable=False)
    name = Column(String, nullable=False)
    exchange = Column(String, nullable=False, index=True)
    segment = Column(String, nullable=False)
    instrument_type = Column(String, nullable=False)
    isin = Column(String, nullable=True)
    lot_size = Column(Float, nullable=True)
    tick_size = Column(Float, nullable=True)
    instrument_key = Column(String, nullable=False, unique=True)
    security_type = Column(String, nullable=True)


class SocialAuth(Base):
    __tablename__ = "social_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider = Column(String, nullable=False)
    provider_id = Column(String, nullable=False)
    provider_email = Column(String, nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="social_auths")

    __table_args__ = (
        Index("ix_social_auth_provider_id", "provider", "provider_id", unique=True),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(
        String(50), nullable=False
    )  # trade_executed, price_alert, stop_loss, etc.
    priority = Column(String(20), default="normal")  # low, normal, high
    category = Column(String(50), nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User")


class UserNotificationPreferences(Base):
    __tablename__ = "user_notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Channel preferences
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)
    push_enabled = Column(Boolean, default=True)

    # Notification type preferences (JSON)
    email_types = Column(
        JSON,
        default=lambda: {
            "trading": True,
            "token_expiry": True,
            "system": True,
            "portfolio": True,
            "alerts": True,
            "risk_management": True,
        },
    )

    sms_types = Column(
        JSON,
        default=lambda: {
            "token_expiry": True,
            "critical_trades": True,
            "system_critical": True,
            "margin_call": True,
            "stop_loss_hit": True,
        },
    )

    push_types = Column(JSON, default=lambda: {"all": True})

    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=True)
    quiet_start_time = Column(String, default="22:00")  # 10 PM
    quiet_end_time = Column(String, default="07:00")  # 7 AM

    # Frequency limits
    max_emails_per_hour = Column(Integer, default=10)
    max_sms_per_day = Column(Integer, default=5)
    max_push_per_hour = Column(Integer, default=50)

    # Priority overrides (critical notifications ignore quiet hours and limits)
    critical_override_quiet_hours = Column(Boolean, default=True)
    critical_override_limits = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    user = relationship("User")


class AutoTradingSession(Base):
    __tablename__ = "auto_trading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_date = Column(Date, nullable=False)
    selected_stocks = Column(JSON, nullable=False)  # List of selected stocks
    screening_config = Column(JSON, nullable=True)  # Screening parameters used
    stocks_screened = Column(Integer, nullable=True)  # Total stocks screened
    session_type = Column(String, nullable=False)  # AUTO_PAPER_TRADING, MANUAL, etc.
    status = Column(String, default="ACTIVE")  # ACTIVE, COMPLETED, FAILED
    total_trades = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)
    session_pnl = Column(Float, default=0.0)
    start_capital = Column(Float, nullable=True)
    end_capital = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="auto_trading_sessions")
    trading_reports = relationship("DailyTradingReport", back_populates="session")
    trade_executions = relationship(
        "AutoTradeExecution", back_populates="session", cascade="all, delete"
    )


class DailyTradingReport(Base):
    __tablename__ = "daily_trading_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id = Column(
        Integer,
        ForeignKey("auto_trading_sessions.id", ondelete="CASCADE"),
        nullable=True,
    )
    report_date = Column(Date, nullable=False)
    stocks_selected = Column(JSON, nullable=False)
    trades_executed = Column(Integer, default=0)
    daily_pnl = Column(Float, default=0.0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    portfolio_value = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    best_trade_pnl = Column(Float, nullable=True)
    worst_trade_pnl = Column(Float, nullable=True)
    avg_trade_duration = Column(Float, nullable=True)  # in minutes
    total_commissions = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)
    auto_generated = Column(Boolean, default=True)
    report_data = Column(JSON, nullable=True)  # Additional metrics
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="daily_trading_reports")
    session = relationship("AutoTradingSession", back_populates="trading_reports")


class TradeExecution(Base):
    __tablename__ = "trade_executions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id = Column(
        Integer,
        ForeignKey("auto_trading_sessions.id", ondelete="CASCADE"),
        nullable=True,
    )
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)  # BUY, SELL
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    entry_time = Column(DateTime, default=func.now())
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_percentage = Column(Float, nullable=True)
    commission = Column(Float, default=0.0)
    status = Column(String, default="OPEN")  # OPEN, CLOSED, CANCELLED
    exit_reason = Column(String, nullable=True)  # STOP_LOSS, TARGET, MANUAL, TIME_BASED
    confidence_score = Column(Float, nullable=True)  # AI confidence
    technical_indicators = Column(JSON, nullable=True)
    execution_notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    session = relationship("AutoTradingSession")


class SelectedStock(Base):
    """Daily selected stocks for trading - Optimized"""

    __tablename__ = "selected_stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    instrument_key = Column(String(100), nullable=False)
    selection_date = Column(Date, nullable=False, index=True)

    # Selection Criteria
    selection_score = Column(Float, nullable=False)
    selection_reason = Column(String(100), nullable=False)

    # Price Data at Selection
    price_at_selection = Column(Float, nullable=False)
    volume_at_selection = Column(Integer, default=0)
    change_percent_at_selection = Column(Float, default=0.0)

    # Classification
    sector = Column(String(50), default="OTHER")
    score_breakdown = Column(Text)  # JSON string with detailed scoring

    # Status
    is_active = Column(Boolean, default=True)

    option_type = Column(String)  # CE / PE / NEUTRAL
    option_contract = Column(Text)  # JSON string - Single ATM contract
    option_contracts_available = Column(
        Integer, default=0
    )  # Count of available contracts
    option_chain_data = Column(Text)  # JSON string - Complete option chain
    option_expiry_date = Column(String)  # Selected expiry date (YYYY-MM-DD)
    option_expiry_dates = Column(Text)  # JSON array - All available expiry dates

    # Performance Tracking (optional)
    max_price_achieved = Column(Float)
    min_price_achieved = Column(Float)
    exit_price = Column(Float)
    exit_reason = Column(String(100))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_symbol_selection_date", "symbol", "selection_date"),
        Index("idx_selection_date_active", "selection_date", "is_active"),
        Index("idx_selection_score", "selection_score"),
    )


class DailyStockSummary(Base):
    """Daily aggregated stock data - MUCH more efficient than individual ticks"""

    __tablename__ = "daily_stock_summaries"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    instrument_key = Column(String(100), nullable=False)
    trading_date = Column(Date, nullable=False, index=True)

    # OHLC Data
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)

    # Volume and Trading Data
    volume = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    avg_price = Column(Float, nullable=False)

    # Performance Metrics
    change_percent = Column(Float, default=0.0)

    # Classification
    sector = Column(String(50), default="OTHER")
    exchange = Column(String(10), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for performance
    __table_args__ = (
        Index("idx_symbol_date", "symbol", "trading_date"),
        Index("idx_date_sector", "trading_date", "sector"),
        Index("idx_change_percent", "change_percent"),
    )


class MarketSnapshot(Base):
    """Market snapshots at key times (open, close, significant events)"""

    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    snapshot_time = Column(DateTime, nullable=False)

    # Summary Statistics
    total_instruments = Column(Integer, default=0)
    processed_ticks = Column(Integer, default=0)

    # Market Data (JSON)
    market_summary = Column(Text)  # JSON with market breadth, sentiment, etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)


class HourlyMarketStats(Base):
    """Hourly aggregated market statistics"""

    __tablename__ = "hourly_market_stats"

    id = Column(Integer, primary_key=True, index=True)
    stats_date = Column(Date, nullable=False, index=True)
    stats_hour = Column(Integer, nullable=False)  # 0-23

    # Market Breadth
    total_stocks = Column(Integer, default=0)
    advancing_stocks = Column(Integer, default=0)
    declining_stocks = Column(Integer, default=0)
    unchanged_stocks = Column(Integer, default=0)

    # Volume Data
    total_volume = Column(Integer, default=0)
    avg_volume = Column(Float, default=0.0)

    # Price Movement
    avg_change_percent = Column(Float, default=0.0)
    volatility_index = Column(Float, default=0.0)

    # Sector Performance (JSON)
    sector_performance = Column(Text)  # JSON with sector-wise data

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("stats_date", "stats_hour", name="unique_date_hour"),
    )


# =======================
# AUTO-TRADING SYSTEM MODELS - HFT Grade Performance & Monitoring
# =======================


class AutoTradeExecution(Base):
    """Enhanced trade execution tracking for Fibonacci + EMA auto-trading system"""

    __tablename__ = "auto_trade_executions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id = Column(
        Integer, ForeignKey("auto_trading_sessions.id", ondelete="CASCADE")
    )

    # Trade Identification
    trade_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    instrument_key = Column(String(100), nullable=False)

    # Strategy Details
    strategy_name = Column(String(50), default="fibonacci_ema")
    signal_type = Column(String(10), nullable=False)  # BUY_CE, BUY_PE
    signal_strength = Column(Numeric(5, 2))  # 0-100 score

    # Fibonacci Strategy Specific (JSON fields for complex data)
    fibonacci_levels = Column(JSON)  # All fib levels at entry {fib_23_6: 2450.50, ...}
    ema_values = Column(JSON)  # EMA 9,21,50 values at entry {ema_9: 2455, ...}
    swing_high = Column(Numeric(10, 2))  # Swing high used for Fibonacci
    swing_low = Column(Numeric(10, 2))  # Swing low used for Fibonacci

    # Trade Execution Details
    entry_time = Column(DateTime, nullable=False, index=True)
    entry_price = Column(Numeric(10, 2), nullable=False)
    entry_order_id = Column(String(50))
    quantity = Column(Integer, nullable=False)
    lot_size = Column(Integer, nullable=False)

    # Exit Details
    exit_time = Column(DateTime)
    exit_price = Column(Numeric(10, 2))
    exit_order_id = Column(String(50))
    exit_reason = Column(
        String(50)
    )  # stop_loss, target_1, target_2, trailing_stop, time_based, manual

    # P&L Tracking with Precision
    gross_pnl = Column(Numeric(15, 2))
    net_pnl = Column(Numeric(15, 2))  # After brokerage and taxes
    pnl_percentage = Column(Numeric(10, 4))
    risk_reward_actual = Column(Numeric(10, 2))  # Actual R:R achieved

    # Risk Management Data
    initial_stop_loss = Column(Numeric(10, 2))
    target_1 = Column(Numeric(10, 2))
    target_2 = Column(Numeric(10, 2))
    max_profit_reached = Column(Numeric(10, 2))
    max_drawdown_in_trade = Column(Numeric(10, 2))

    # HFT Performance Metrics (milliseconds)
    signal_generation_latency_ms = Column(Integer)
    order_execution_latency_ms = Column(Integer)
    total_execution_latency_ms = Column(Integer)
    time_in_trade_minutes = Column(Integer)

    # Status & Metadata
    status = Column(
        String(20), default="ACTIVE", index=True
    )  # ACTIVE, CLOSED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="auto_trade_executions")
    session = relationship("AutoTradingSession", back_populates="trade_executions")
    active_position = relationship(
        "ActivePosition", back_populates="trade_execution", uselist=False
    )

    # Indexes for HFT performance
    __table_args__ = (
        Index("idx_auto_trade_user_time", "user_id", "entry_time"),
        Index("idx_auto_trade_symbol_status", "symbol", "status"),
        Index("idx_auto_trade_strategy", "strategy_name", "signal_type"),
    )


class ActivePosition(Base):
    """Real-time position tracking for active trades"""

    __tablename__ = "active_positions"

    id = Column(Integer, primary_key=True, index=True)
    trade_execution_id = Column(
        Integer, ForeignKey("auto_trade_executions.id", ondelete="CASCADE"), unique=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Current Position Data
    symbol = Column(String(20), nullable=False, index=True)
    instrument_key = Column(String(100), nullable=False)
    current_price = Column(Numeric(10, 2))
    current_pnl = Column(Numeric(15, 2))
    current_pnl_percentage = Column(Numeric(10, 4))

    # Dynamic Stop Loss Management (Trailing)
    current_stop_loss = Column(Numeric(10, 2))
    trailing_stop_triggered = Column(Boolean, default=False)
    highest_price_reached = Column(Numeric(10, 2))

    # Risk Monitoring
    unrealized_risk = Column(Numeric(15, 2))
    mark_to_market_time = Column(DateTime, index=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trade_execution = relationship(
        "AutoTradeExecution", back_populates="active_position"
    )
    user = relationship("User", back_populates="active_positions")

    # Index for fast queries
    __table_args__ = (Index("idx_active_position_user_active", "user_id", "is_active"),)


class DailyTradingPerformance(Base):
    """Comprehensive daily performance analytics"""

    __tablename__ = "daily_trading_performance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    trading_date = Column(Date, nullable=False, index=True)

    # Basic Trade Counts
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    breakeven_trades = Column(Integer, default=0)

    # P&L Analysis
    gross_pnl = Column(Numeric(15, 2), default=0)
    net_pnl = Column(Numeric(15, 2), default=0)
    largest_win = Column(Numeric(15, 2), default=0)
    largest_loss = Column(Numeric(15, 2), default=0)

    # Performance Ratios
    win_rate = Column(Numeric(5, 2))  # Percentage
    avg_win = Column(Numeric(15, 2))
    avg_loss = Column(Numeric(15, 2))
    profit_factor = Column(Numeric(10, 4))  # Total wins / Total losses
    expectancy = Column(Numeric(15, 2))  # Average per trade

    # Risk Metrics
    max_drawdown = Column(Numeric(15, 2))
    max_consecutive_losses = Column(Integer, default=0)
    max_consecutive_wins = Column(Integer, default=0)
    sharpe_ratio = Column(Numeric(10, 4))

    # Strategy-Specific Metrics
    fibonacci_signals_generated = Column(Integer, default=0)
    fibonacci_signals_executed = Column(Integer, default=0)
    signal_to_execution_ratio = Column(Numeric(5, 2))

    # Account Impact
    account_balance_start = Column(Numeric(15, 2))
    account_balance_end = Column(Numeric(15, 2))
    daily_return_percentage = Column(Numeric(10, 4))

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="daily_performances")

    # Unique constraint per user per day
    __table_args__ = (
        UniqueConstraint("user_id", "trading_date", name="uq_daily_perf_user_date"),
        Index("idx_daily_perf_date", "trading_date"),
    )


class TradingSystemLog(Base):
    """Structured logging for the auto-trading system"""

    __tablename__ = "trading_system_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_level = Column(
        String(20), nullable=False, index=True
    )  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    component = Column(
        String(50), nullable=False, index=True
    )  # fibonacci_strategy, order_manager, risk_manager
    message = Column(Text, nullable=False)

    # Context Data
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    trade_id = Column(String(50), index=True)
    symbol = Column(String(20))
    latency_ms = Column(Integer)

    # Technical Details
    function_name = Column(String(100))
    line_number = Column(Integer)
    stack_trace = Column(Text)

    # Metadata (JSON for flexible data)
    additional_data = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="trading_logs")

    # Indexes for efficient log searching
    __table_args__ = (
        Index("idx_trading_log_timestamp", "timestamp"),
        Index("idx_trading_log_level_component", "log_level", "component"),
    )


class EmergencyControl(Base):
    """Kill switch and emergency trading controls"""

    __tablename__ = "emergency_controls"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Control Configuration
    control_type = Column(
        String(50), nullable=False
    )  # KILL_SWITCH, DAILY_LIMIT, POSITION_LIMIT
    is_active = Column(Boolean, default=True, index=True)

    # Kill Switch Triggers
    max_daily_loss = Column(Numeric(15, 2))  # Maximum daily loss in currency
    max_consecutive_losses = Column(Integer)
    max_drawdown_percentage = Column(Numeric(5, 2))
    max_position_count = Column(Integer, default=3)

    # Current Status (Real-time tracking)
    current_daily_loss = Column(Numeric(15, 2), default=0)
    current_consecutive_losses = Column(Integer, default=0)
    current_drawdown = Column(Numeric(15, 2), default=0)
    current_position_count = Column(Integer, default=0)

    # Emergency State
    emergency_triggered = Column(Boolean, default=False, index=True)
    trigger_reason = Column(Text)
    triggered_at = Column(DateTime)

    # Reset Controls
    auto_reset_daily = Column(Boolean, default=True)
    manual_reset_required = Column(Boolean, default=False)
    last_reset = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="emergency_controls")


class TradingAuditTrail(Base):
    """Complete audit trail for compliance and monitoring"""

    __tablename__ = "trading_audit_trail"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Action Details
    action_type = Column(
        String(50), nullable=False, index=True
    )  # SIGNAL_GENERATED, ORDER_PLACED, POSITION_CLOSED
    entity_type = Column(String(50), index=True)  # TRADE, ORDER, POSITION, SYSTEM
    entity_id = Column(String(50), index=True)

    # State Tracking (Before/After snapshots)
    state_before = Column(JSON)
    state_after = Column(JSON)

    # Context Information
    triggered_by = Column(String(50))  # SYSTEM, USER, EMERGENCY
    ip_address = Column(String(45))  # Support IPv6
    user_agent = Column(Text)

    # Additional Metadata
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User")

    # Indexes for fast audit queries
    __table_args__ = (
        Index("idx_audit_user_time", "user_id", "timestamp"),
        Index("idx_audit_action_type", "action_type"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )


# =======================
# PREMARKET CANDLE & GAP DETECTION SYSTEM
# =======================


class PremarketCandle(Base):
    """
    Premarket candle data for gap detection (9:00 AM to 9:08 AM IST)
    Stores OHLC data built from tick-by-tick WebSocket feeds
    """

    __tablename__ = "premarket_candles"

    id = Column(Integer, primary_key=True, index=True)
    
    # Instrument Identification
    symbol = Column(String(50), nullable=False, index=True)
    instrument_key = Column(String(100), nullable=False, index=True)
    exchange = Column(String(10), default="NSE")
    
    # Candle Time Information
    candle_date = Column(Date, nullable=False, index=True)
    candle_start_time = Column(DateTime, nullable=False)  # 9:00 AM IST
    candle_end_time = Column(DateTime, nullable=False)    # 9:08 AM IST
    
    # OHLC Data (Decimal for precision)
    open_price = Column(Numeric(12, 2), nullable=False)
    high_price = Column(Numeric(12, 2), nullable=False) 
    low_price = Column(Numeric(12, 2), nullable=False)
    close_price = Column(Numeric(12, 2), nullable=False)
    
    # Volume and Trade Data
    total_volume = Column(BigInteger, default=0)
    total_trades = Column(Integer, default=0)
    avg_price = Column(Numeric(12, 2), nullable=False)
    
    # Previous Session Data (for gap calculation)
    previous_close = Column(Numeric(12, 2), nullable=False)
    
    # Gap Analysis
    gap_percentage = Column(Numeric(10, 4))  # (open - prev_close) / prev_close * 100
    gap_type = Column(String(10))  # "GAP_UP", "GAP_DOWN", "NO_GAP"
    gap_strength = Column(String(15))  # "WEAK", "MODERATE", "STRONG", "VERY_STRONG"
    
    # Volume Analysis  
    volume_ratio = Column(Numeric(8, 2))  # Current volume / 20-day avg volume
    volume_confirmation = Column(Boolean, default=False)  # Volume supports gap
    
    # Market Data Quality
    ticks_received = Column(Integer, default=0)
    data_quality_score = Column(Numeric(4, 3))  # 0-1 based on data completeness
    
    # Sector and Classification
    sector = Column(String(50))
    market_cap_category = Column(String(15))  # "LARGE_CAP", "MID_CAP", "SMALL_CAP"
    
    # Status and Metadata
    is_significant_gap = Column(Boolean, default=False, index=True)  # Gap > 1%
    processed_by_strategy = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Optimized indexes for gap detection queries
    __table_args__ = (
        # Primary index for daily gap screening
        Index("idx_premarket_date_gap", "candle_date", "is_significant_gap", "gap_type"),
        # Index for symbol-based queries
        Index("idx_premarket_symbol_date", "symbol", "candle_date"),
        # Index for gap strength analysis  
        Index("idx_premarket_gap_analysis", "gap_strength", "volume_confirmation", "sector"),
        # Index for instrument key lookup
        Index("idx_premarket_instrument_date", "instrument_key", "candle_date"),
        # Index for data quality monitoring
        Index("idx_premarket_quality", "data_quality_score", "ticks_received"),
        # Unique constraint per instrument per day
        UniqueConstraint("instrument_key", "candle_date", name="uq_premarket_instrument_date"),
        # Check constraints for data integrity
        CheckConstraint("gap_percentage >= -50 AND gap_percentage <= 50", name="ck_gap_percentage_range"),
        CheckConstraint("gap_type IN ('GAP_UP', 'GAP_DOWN', 'NO_GAP')", name="ck_valid_gap_type"),
        CheckConstraint("gap_strength IN ('WEAK', 'MODERATE', 'STRONG', 'VERY_STRONG')", name="ck_valid_gap_strength"),
        CheckConstraint("data_quality_score >= 0 AND data_quality_score <= 1", name="ck_quality_score_range"),
        CheckConstraint("volume_ratio >= 0", name="ck_positive_volume_ratio"),
        CheckConstraint("high_price >= low_price", name="ck_high_low_price"),
        CheckConstraint("high_price >= open_price AND high_price >= close_price", name="ck_high_price_validity"),
        CheckConstraint("low_price <= open_price AND low_price <= close_price", name="ck_low_price_validity"),
    )


class GapDetectionAlert(Base):
    """
    Real-time gap detection alerts generated during premarket hours
    """
    
    __tablename__ = "gap_detection_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Reference to premarket candle
    premarket_candle_id = Column(Integer, ForeignKey("premarket_candles.id", ondelete="CASCADE"), index=True)
    
    # Alert Details
    alert_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    
    # Gap Information
    gap_percentage = Column(Numeric(10, 4), nullable=False)
    gap_type = Column(String(10), nullable=False)  # "GAP_UP", "GAP_DOWN"
    gap_strength = Column(String(15), nullable=False)
    
    # Price Data
    trigger_price = Column(Numeric(12, 2), nullable=False)
    previous_close = Column(Numeric(12, 2), nullable=False)
    
    # Alert Priority and Status
    alert_priority = Column(String(10), default="MEDIUM")  # "LOW", "MEDIUM", "HIGH", "CRITICAL" 
    alert_status = Column(String(15), default="ACTIVE")  # "ACTIVE", "ACKNOWLEDGED", "EXPIRED"
    
    # Confidence Scoring
    confidence_score = Column(Numeric(4, 3))  # 0-1 based on volume, gap size, etc.
    
    # Volume Confirmation
    volume_at_alert = Column(BigInteger, default=0)
    volume_ratio = Column(Numeric(8, 2))
    
    # Expiry and Processing
    expires_at = Column(DateTime, nullable=False)  # Alert expiry time (market open)
    acknowledged_at = Column(DateTime)
    processed_by_trading_system = Column(Boolean, default=False)
    
    # Relationships
    premarket_candle = relationship("PremarketCandle")
    
    # Optimized indexes
    __table_args__ = (
        Index("idx_gap_alert_active", "alert_status", "alert_time"),
        Index("idx_gap_alert_symbol", "symbol", "gap_type", "alert_time"),
        Index("idx_gap_alert_priority", "alert_priority", "confidence_score"),
        Index("idx_gap_alert_processing", "processed_by_trading_system", "alert_status"),
        CheckConstraint("gap_type IN ('GAP_UP', 'GAP_DOWN')", name="ck_alert_gap_type"),
        CheckConstraint("alert_priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_alert_priority"),
        CheckConstraint("alert_status IN ('ACTIVE', 'ACKNOWLEDGED', 'EXPIRED')", name="ck_alert_status"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_alert_confidence_range"),
    )


# =======================
# F&O STOCK SELECTION METADATA - Phase 2 Implementation
# =======================


class FNOStockMetadata(Base):
    """
    F&O Stock Metadata for Fibonacci Strategy Selection

    Stores detailed metadata about F&O stocks including:
    - Index membership and sector classification
    - Option liquidity metrics and lot sizes
    - Historical Fibonacci respect scores
    - Technical analysis scores for strategy selection
    """

    __tablename__ = "fno_stock_metadata"

    id = Column(Integer, primary_key=True, index=True)

    # Stock Identification
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    company_name = Column(String(100))
    sector = Column(String(50), index=True)
    industry = Column(String(100))

    # Index Membership (JSON array for multiple index membership)
    index_membership = Column(
        JSON, nullable=False
    )  # ['NIFTY', 'BANKNIFTY'] if in multiple
    primary_index = Column(String(20), index=True)  # Primary index for classification

    # F&O Contract Details
    lot_size = Column(Integer, nullable=False)
    tick_size = Column(Numeric(6, 4), default=0.05)  # Minimum price movement
    instrument_type = Column(String(20), default="EQ")  # EQ, FUTIDX, FUTSTK, etc.

    # Market Data Metrics (Updated daily)
    avg_daily_volume = Column(BigInteger, index=True)  # 30-day average volume
    market_cap = Column(BigInteger)  # Market capitalization in lakhs
    current_price = Column(Numeric(10, 2))
    price_change_percent = Column(Numeric(8, 4))  # Daily % change

    # Option Liquidity Scores (0.0 to 1.0)
    option_liquidity_score = Column(
        Numeric(4, 3), index=True
    )  # Overall option liquidity
    ce_liquidity_score = Column(Numeric(4, 3))  # Call option liquidity
    pe_liquidity_score = Column(Numeric(4, 3))  # Put option liquidity
    liquid_strikes_count = Column(Integer)  # Number of liquid strikes
    total_option_oi = Column(BigInteger)  # Total open interest across all strikes

    # Fibonacci Strategy Specific Metrics (Updated weekly)
    fibonacci_respect_score = Column(
        Numeric(4, 3), index=True
    )  # Historical Fibonacci level respect (0-1)
    swing_clarity_score = Column(
        Numeric(4, 3), index=True
    )  # Clear swing highs/lows score (0-1)
    ema_alignment_score = Column(
        Numeric(4, 3), index=True
    )  # EMA trend alignment score (0-1)
    overall_fibonacci_score = Column(
        Numeric(4, 3), index=True
    )  # Combined Fibonacci suitability score

    # Technical Analysis Metrics
    volatility_30d = Column(Numeric(6, 4))  # 30-day historical volatility
    avg_true_range = Column(Numeric(10, 2))  # ATR for volatility measurement
    beta_vs_nifty = Column(Numeric(6, 4))  # Beta coefficient vs Nifty
    correlation_nifty = Column(Numeric(6, 4))  # Correlation with Nifty (-1 to 1)

    # Selection History Tracking
    times_selected = Column(
        Integer, default=0
    )  # How many times selected for auto-trading
    last_selected_date = Column(Date)
    selection_success_rate = Column(Numeric(5, 2))  # % of profitable selections
    avg_holding_period_hours = Column(Numeric(8, 2))  # Average position holding time

    # Status and Quality Flags
    is_active_fno = Column(
        Boolean, default=True, index=True
    )  # Currently has F&O availability
    quality_grade = Column(
        String(2), index=True
    )  # A+, A, B+, B, C based on overall suitability
    is_fibonacci_friendly = Column(
        Boolean, default=False, index=True
    )  # Passes Fibonacci criteria
    last_liquidity_check = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_analysis_date = Column(Date)  # Last technical analysis update

    # Enhanced indexing for fast queries
    __table_args__ = (
        # Index for Fibonacci strategy selection
        Index(
            "idx_fno_fibonacci_selection",
            "is_fibonacci_friendly",
            "overall_fibonacci_score",
            "option_liquidity_score",
        ),
        # Index for active F&O stocks by quality
        Index(
            "idx_fno_active_quality", "is_active_fno", "quality_grade", "primary_index"
        ),
        # Index for option liquidity filtering
        Index(
            "idx_fno_liquidity",
            "option_liquidity_score",
            "liquid_strikes_count",
            "total_option_oi",
        ),
        # Index for sector and index analysis
        Index("idx_fno_sector_index", "sector", "primary_index", "market_cap"),
        # Index for performance tracking
        Index(
            "idx_fno_performance",
            "times_selected",
            "selection_success_rate",
            "last_selected_date",
        ),
        # Index for volatility-based selection
        Index(
            "idx_fno_volatility", "volatility_30d", "avg_true_range", "beta_vs_nifty"
        ),
        # Check constraints for data quality
        CheckConstraint(
            "fibonacci_respect_score >= 0 AND fibonacci_respect_score <= 1",
            name="ck_fib_respect_range",
        ),
        CheckConstraint(
            "swing_clarity_score >= 0 AND swing_clarity_score <= 1",
            name="ck_swing_clarity_range",
        ),
        CheckConstraint(
            "option_liquidity_score >= 0 AND option_liquidity_score <= 1",
            name="ck_option_liquidity_range",
        ),
        CheckConstraint("lot_size > 0", name="ck_positive_lot_size"),
        CheckConstraint(
            "quality_grade IN ('A+', 'A', 'B+', 'B', 'C')",
            name="ck_valid_quality_grade",
        ),
        CheckConstraint(
            "selection_success_rate >= 0 AND selection_success_rate <= 100",
            name="ck_success_rate_range",
        ),
    )


class FNOSelectionHistory(Base):
    """
    Historical record of F&O stock selections for performance tracking and analysis
    """

    __tablename__ = "fno_selection_history"

    id = Column(Integer, primary_key=True, index=True)

    # Selection Session Details
    selection_date = Column(Date, nullable=False, index=True)
    selection_time = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_type = Column(
        String(20), default="PREMARKET"
    )  # PREMARKET, INTRADAY, CUSTOM

    # Selected Stock Information
    symbol = Column(String(20), nullable=False, index=True)
    selection_score = Column(
        Numeric(6, 3), nullable=False
    )  # Score at time of selection
    selection_rank = Column(Integer)  # Rank among all candidates (1st, 2nd, etc.)

    # Market Context at Selection
    market_sentiment = Column(String(20))  # BULLISH, BEARISH, NEUTRAL
    nifty_change_percent = Column(Numeric(8, 4))
    sector_momentum = Column(Numeric(8, 4))  # Sector performance %

    # Fibonacci Strategy Metrics at Selection
    fibonacci_levels_at_selection = Column(JSON)  # Fib levels when selected
    ema_values_at_selection = Column(JSON)  # EMA values when selected
    price_at_selection = Column(Numeric(10, 2))

    # Selection Criteria Met
    technical_score = Column(Numeric(4, 3))  # Technical analysis score (0-1)
    liquidity_score = Column(Numeric(4, 3))  # Liquidity score (0-1)
    market_score = Column(Numeric(4, 3))  # Market conditions score (0-1)

    # Option Details Selected
    option_type_selected = Column(String(5))  # CE or PE
    atm_strike = Column(Numeric(10, 2))
    option_premium = Column(Numeric(8, 2))
    option_liquidity = Column(JSON)  # Liquidity metrics for selected option

    # Performance Tracking
    was_traded = Column(Boolean, default=False)  # Was actually traded
    trade_outcome = Column(String(20))  # PROFIT, LOSS, BREAKEVEN, NOT_TRADED
    profit_loss_points = Column(Numeric(10, 2))  # P&L in points
    profit_loss_percent = Column(Numeric(8, 4))  # P&L percentage
    holding_period_minutes = Column(Integer)  # How long position was held

    # Analysis Results
    max_favorable_move = Column(Numeric(8, 4))  # Max % move in predicted direction
    max_adverse_move = Column(Numeric(8, 4))  # Max % move against prediction
    fibonacci_level_accuracy = Column(Boolean)  # Did price respect predicted Fib level?

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    trade_closed_at = Column(DateTime)  # When trade was closed (if traded)

    # Relationships
    user = relationship("User")

    # Optimized indexes for analysis queries
    __table_args__ = (
        # Index for performance analysis by date
        Index("idx_selection_history_date", "selection_date", "symbol"),
        # Index for user performance tracking
        Index(
            "idx_selection_history_user", "user_id", "selection_date", "trade_outcome"
        ),
        # Index for symbol performance analysis
        Index("idx_selection_history_symbol", "symbol", "was_traded", "trade_outcome"),
        # Index for strategy performance analysis
        Index(
            "idx_selection_history_strategy",
            "fibonacci_level_accuracy",
            "profit_loss_percent",
            "holding_period_minutes",
        ),
        # Index for market condition analysis
        Index(
            "idx_selection_history_market",
            "market_sentiment",
            "session_type",
            "selection_date",
        ),
        # Unique constraint to prevent duplicate selections on same date
        UniqueConstraint(
            "selection_date", "symbol", "user_id", name="uq_daily_stock_selection"
        ),
    )


# =======================
# Model Aliases for Backward Compatibility
# =======================

# Position alias for auto-trading system compatibility
Position = ActivePosition
