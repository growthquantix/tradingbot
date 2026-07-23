"""
Shared Instrument Registry
Central registry for monitoring instruments across all users without duplication
"""

import logging
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class InstrumentState(Enum):
    """Instrument monitoring state"""
    MONITORING = "monitoring"
    SIGNAL_DETECTED = "signal_detected"
    ACTIVE = "active"


@dataclass
class SharedInstrument:
    """
    Shared instrument data structure (common across all users)

    This represents the MARKET DATA for an instrument, not user positions.
    Multiple users can monitor the same instrument without duplication.

    Attributes:
        stock_symbol: Stock symbol (e.g., RELIANCE)
        spot_instrument_key: Spot instrument key for price feed
        option_instrument_key: Option instrument key for premium feed
        option_type: Option type (CE/PE)
        strike_price: Strike price
        expiry_date: Expiry date
        lot_size: Lot size for this option
        state: Current monitoring state
        live_spot_price: Current spot price
        live_option_premium: Current option premium
        historical_spot_data: Historical OHLC data
        option_greeks: Option Greeks (delta, theta, gamma, vega, rho)
        implied_volatility: Implied volatility
        open_interest: Open interest
        volume: Trading volume
        bid_price: Bid price
        ask_price: Ask price
        last_signal: Last generated trading signal
        last_update_time: Last data update timestamp
    """
    stock_symbol: str
    spot_instrument_key: str
    option_instrument_key: str
    option_type: str
    strike_price: Decimal
    expiry_date: str
    lot_size: int
    target_lots: int = 1

    state: InstrumentState = InstrumentState.MONITORING

    # Live market data
    live_spot_price: Decimal = Decimal("0")
    live_option_premium: Decimal = Decimal("0")

    # Historical data for strategy
    historical_spot_data: Dict[str, List[float]] = field(
        default_factory=lambda: {
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }
    )

    # Option market data
    option_greeks: Optional[Dict[str, float]] = None
    implied_volatility: Optional[float] = None
    open_interest: Optional[float] = None
    volume: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None

    # Signal tracking
    last_signal: Optional[Any] = None
    last_update_time: datetime = field(default_factory=datetime.now)
    last_processed_candle_count: int = 0
    # BUG-05 FIX: Track the last candle timestamp to avoid appending duplicate candles.
    # Upstox full-feed sends the current open candle on EVERY tick — without this guard,
    # the same 1-minute candle gets appended 30-50 times per minute, corrupting EMA/SuperTrend.
    last_candle_timestamp: Optional[str] = None


class SharedInstrumentRegistry:
    """
    Central registry for shared instruments

    Features:
    - Single source of truth for instrument market data
    - No duplication across users
    - Efficient memory usage
    - Centralized signal generation
    - User subscription management
    """

    def __init__(self):
        """Initialize shared instrument registry"""
        # Shared instruments (option_key -> SharedInstrument)
        self.instruments: Dict[str, SharedInstrument] = {}

        # User subscriptions (user_id -> Set[option_keys])
        self.user_subscriptions: Dict[int, Set[str]] = {}

        # User metadata (user_id -> broker info)
        self.user_metadata: Dict[int, Dict[str, Any]] = {}

        # Instrument to users mapping (option_key -> Set[user_ids])
        self.instrument_subscribers: Dict[str, Set[int]] = {}

        # Global Kill-Switch State
        self.is_risk_halted: bool = False
        self.halt_reason: Optional[str] = None

        logger.info("Shared Instrument Registry initialized")

    def register_instrument(
        self,
        stock_symbol: str,
        spot_key: str,
        option_key: str,
        option_type: str,
        strike_price: Decimal,
        expiry_date: str,
        lot_size: int,
        target_lots: int = 1
    ) -> SharedInstrument:
        """
        Register an instrument in shared registry (idempotent)

        Args:
            stock_symbol: Stock symbol
            spot_key: Spot instrument key
            option_key: Option instrument key
            option_type: Option type (CE/PE)
            strike_price: Strike price
            expiry_date: Expiry date
            lot_size: Lot size
            target_lots: Recommended number of lots

        Returns:
            SharedInstrument instance
        """
        if option_key in self.instruments:
            # Already registered - update target_lots if provided
            if target_lots > 1:
                self.instruments[option_key].target_lots = target_lots
            return self.instruments[option_key]

        instrument = SharedInstrument(
            stock_symbol=stock_symbol,
            spot_instrument_key=spot_key,
            option_instrument_key=option_key,
            option_type=option_type,
            strike_price=strike_price,
            expiry_date=expiry_date,
            lot_size=lot_size,
            target_lots=target_lots
        )

        self.instruments[option_key] = instrument
        self.instrument_subscribers[option_key] = set()

        logger.info(f"Registered instrument: {stock_symbol} {option_type} {strike_price} (Key: {option_key})")

        return instrument

    def subscribe_user(
        self,
        user_id: int,
        option_key: str,
        broker_name: str,
        broker_config_id: int
    ):
        """
        Subscribe a user to an instrument

        Args:
            user_id: User identifier
            option_key: Option instrument key
            broker_name: Broker name
            broker_config_id: Broker config ID
        """
        if option_key not in self.instruments:
            logger.warning(f"Cannot subscribe user {user_id} to unregistered instrument {option_key}")
            return

        # Add to user subscriptions
        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = set()
        self.user_subscriptions[user_id].add(option_key)

        # Add to instrument subscribers
        self.instrument_subscribers[option_key].add(user_id)

        # Store user metadata
        if user_id not in self.user_metadata:
            self.user_metadata[user_id] = {}
        self.user_metadata[user_id].update({
            "broker_name": broker_name,
            "broker_config_id": broker_config_id
        })

        logger.debug(f"User {user_id} subscribed to {option_key} ({broker_name})")

    def unsubscribe_user(self, user_id: int, option_key: Optional[str] = None):
        """
        Unsubscribe a user from instrument(s)

        Args:
            user_id: User identifier
            option_key: Specific option key (if None, unsubscribe from all)
        """
        if option_key:
            # Unsubscribe from specific instrument
            if user_id in self.user_subscriptions:
                self.user_subscriptions[user_id].discard(option_key)
            if option_key in self.instrument_subscribers:
                self.instrument_subscribers[option_key].discard(user_id)
        else:
            # Unsubscribe from all instruments
            if user_id in self.user_subscriptions:
                for key in self.user_subscriptions[user_id]:
                    if key in self.instrument_subscribers:
                        self.instrument_subscribers[key].discard(user_id)
                del self.user_subscriptions[user_id]
            if user_id in self.user_metadata:
                del self.user_metadata[user_id]

    def get_instrument(self, option_key: str) -> Optional[SharedInstrument]:
        """
        Get instrument by option key

        Args:
            option_key: Option instrument key

        Returns:
            SharedInstrument or None
        """
        return self.instruments.get(option_key)

    def get_user_instruments(self, user_id: int) -> List[SharedInstrument]:
        """
        Get all instruments a user is subscribed to

        Args:
            user_id: User identifier

        Returns:
            List of SharedInstrument
        """
        if user_id not in self.user_subscriptions:
            return []

        return [
            self.instruments[key]
            for key in self.user_subscriptions[user_id]
            if key in self.instruments
        ]

    def get_instrument_subscribers(self, option_key: str) -> Set[int]:
        """
        Get all user IDs subscribed to an instrument

        Args:
            option_key: Option instrument key

        Returns:
            Set of user IDs
        """
        return self.instrument_subscribers.get(option_key, set())

    def get_user_metadata(self, user_id: int) -> Dict[str, Any]:
        """
        Get user metadata (broker info, etc.)

        Args:
            user_id: User identifier

        Returns:
            User metadata dict
        """
        return self.user_metadata.get(user_id, {})

    def update_spot_price(
        self,
        spot_key: str,
        price: Decimal,
        ohlc_data: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Update spot price for all instruments with this spot key

        Args:
            spot_key: Spot instrument key
            price: Current spot price
            ohlc_data: OHLC candle data
        """
        for instrument in self.instruments.values():
            if instrument.spot_instrument_key == spot_key:
                instrument.live_spot_price = price
                instrument.last_update_time = datetime.now()

                # Update historical data if OHLC provided
                if ohlc_data:
                    for candle in ohlc_data:
                        if candle.get("interval") == "I1":
                            # BUG-05 FIX: Only append a candle when its timestamp changes (new minute).
                            # The Upstox live feed sends the same open candle on every tick with
                            # updated values — without this guard we get 30-50 duplicate candles
                            # per minute, which completely corrupts EMA and SuperTrend calculations.
                            candle_ts = str(
                                candle.get("ts", candle.get("timestamp", ""))
                            )
                            if candle_ts and candle_ts == instrument.last_candle_timestamp:
                                break  # Same candle — skip duplicate
                            instrument.last_candle_timestamp = candle_ts

                            instrument.historical_spot_data["open"].append(
                                float(candle.get("open", price))
                            )
                            instrument.historical_spot_data["high"].append(
                                float(candle.get("high", price))
                            )
                            instrument.historical_spot_data["low"].append(
                                float(candle.get("low", price))
                            )
                            instrument.historical_spot_data["close"].append(
                                float(candle.get("close", price))
                            )
                            instrument.historical_spot_data["volume"].append(
                                int(candle.get("vol", 0))
                            )
                            # Keep only last 50 candles
                            for k in instrument.historical_spot_data:
                                if len(instrument.historical_spot_data[k]) > 50:
                                    instrument.historical_spot_data[k] = (
                                        instrument.historical_spot_data[k][-50:]
                                    )
                            break

    def update_option_data(
        self,
        option_key: str,
        premium: Decimal,
        greeks: Optional[Dict[str, float]] = None,
        implied_vol: Optional[float] = None,
        open_interest: Optional[float] = None,
        volume: Optional[float] = None,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None
    ):
        """
        Update option data for an instrument

        Args:
            option_key: Option instrument key
            premium: Current option premium
            greeks: Option Greeks
            implied_vol: Implied volatility
            open_interest: Open interest
            volume: Trading volume
            bid_price: Bid price
            ask_price: Ask price
        """
        instrument = self.instruments.get(option_key)
        if not instrument:
            return

        instrument.live_option_premium = premium
        instrument.last_update_time = datetime.now()

        if greeks and any(greeks.values()):
            instrument.option_greeks = greeks

        if implied_vol is not None:
            instrument.implied_volatility = implied_vol

        if open_interest is not None:
            instrument.open_interest = open_interest

        if volume is not None:
            instrument.volume = volume

        if bid_price is not None:
            instrument.bid_price = bid_price

        if ask_price is not None:
            instrument.ask_price = ask_price

    def get_all_instrument_keys(self) -> List[str]:
        """
        Get all unique instrument keys for subscription

        Returns:
            List of unique instrument keys (spot + option)
        """
        keys = set()
        for instrument in self.instruments.values():
            keys.add(instrument.spot_instrument_key)
            keys.add(instrument.option_instrument_key)
        return list(keys)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics

        Returns:
            Statistics dict
        """
        return {
            "total_instruments": len(self.instruments),
            "total_users": len(self.user_subscriptions),
            "total_subscriptions": sum(len(subs) for subs in self.user_subscriptions.values()),
            "instruments_with_data": sum(
                1 for inst in self.instruments.values()
                if inst.live_option_premium > 0
            ),
            "instruments_with_signals": sum(
                1 for inst in self.instruments.values()
                if inst.last_signal is not None
            )
        }

    def clear(self):
        """Clear all data from registry"""
        self.instruments.clear()
        self.user_subscriptions.clear()
        self.user_metadata.clear()
        self.instrument_subscribers.clear()
        logger.info("Shared Instrument Registry cleared")


# Singleton instance
shared_registry = SharedInstrumentRegistry()