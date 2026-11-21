# Import necessary modules
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import ssl
import websockets.connection
import logging
import websockets
import requests
from google.protobuf.json_format import MessageToDict
import services.upstox.MarketDataFeed_pb2 as pb
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import math

logger = logging.getLogger("ws_relay")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TradingStrategy:
    def __init__(self):
        self.positions = {}
        self.order_history = []
        self.pnl_history = []
        self.spot_data = {}
        self.option_data = {}
        self.ema_period = 20
        self.supertrend_period = 10
        self.supertrend_multiplier = 3
        self.trailing_sl_percent = 0.02  # 2% trailing SL
        self.quantity = 1  # Number of lots
        self.min_data_points = 30  # Minimum data points before trading

        # Store historical data for each instrument
        self.historical_data = {}

    def initialize_instrument_data(self, instrument_key: str):
        """Initialize data structure for a new instrument"""
        if instrument_key not in self.historical_data:
            self.historical_data[instrument_key] = {
                "timestamp": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
                "ema": [],
                "supertrend": [],
                "direction": [],
            }

    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return [None] * len(prices)

        ema_values = []
        multiplier = 2 / (period + 1)

        # SMA for first value
        sma = sum(prices[:period]) / period
        ema_values.extend([None] * (period - 1))
        ema_values.append(sma)

        for price in prices[period:]:
            ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)

        return ema_values

    def calculate_supertrend(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int,
        multiplier: float,
    ) -> Dict:
        """Calculate SuperTrend indicator"""
        if len(close) < period:
            return {"supertrend": [None] * len(close), "direction": [None] * len(close)}

        # Calculate ATR
        tr = []
        for i in range(1, len(close)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i - 1])
            tr3 = abs(low[i] - close[i - 1])
            tr.append(max(tr1, tr2, tr3))

        atr = [sum(tr[:period]) / period]
        for i in range(period, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)

        # Calculate SuperTrend
        supertrend = []
        direction = []

        # First value
        hl2 = (high[period] + low[period]) / 2
        upper_band = hl2 + multiplier * atr[0]
        lower_band = hl2 - multiplier * atr[0]

        if close[period] <= upper_band:
            supertrend.append(upper_band)
            direction.append("DOWN")
        else:
            supertrend.append(lower_band)
            direction.append("UP")

        # Subsequent values
        for i in range(period + 1, len(close)):
            hl2 = (high[i] + low[i]) / 2
            upper_band = hl2 + multiplier * atr[i - period]
            lower_band = hl2 - multiplier * atr[i - period]

            prev_supertrend = supertrend[-1]
            prev_direction = direction[-1]

            if prev_direction == "UP":
                if lower_band > prev_supertrend:
                    current_supertrend = lower_band
                    current_direction = "UP"
                else:
                    current_supertrend = upper_band
                    current_direction = "DOWN"
            else:  # DOWN
                if upper_band < prev_supertrend:
                    current_supertrend = upper_band
                    current_direction = "DOWN"
                else:
                    current_supertrend = lower_band
                    current_direction = "UP"

            supertrend.append(current_supertrend)
            direction.append(current_direction)

        return {
            "supertrend": [None] * period + supertrend,
            "direction": [None] * period + direction,
        }

    def check_entry_conditions(self, instrument_key: str) -> Optional[str]:
        """Check for entry conditions (BUY/SELL)"""
        if instrument_key not in self.historical_data:
            return None

        data = self.historical_data[instrument_key]

        if len(data["close"]) < max(self.ema_period, self.supertrend_period) + 1:
            return None

        current_close = data["close"][-1]
        prev_close = data["close"][-2] if len(data["close"]) > 1 else current_close
        current_ema = data["ema"][-1]
        current_supertrend = data["supertrend"][-1]
        current_direction = data["direction"][-1]
        prev_direction = data["direction"][-2] if len(data["direction"]) > 1 else None

        if current_ema is None or current_supertrend is None or prev_direction is None:
            return None

        # BUY Condition: Price above EMA and SuperTrend turning UP
        if (
            current_close > current_ema
            and current_direction == "UP"
            and prev_direction == "DOWN"
        ):
            return "BUY"

        # SELL Condition: Price below EMA and SuperTrend turning DOWN
        elif (
            current_close < current_ema
            and current_direction == "DOWN"
            and prev_direction == "UP"
        ):
            return "SELL"

        return None

    def check_exit_conditions(self, instrument_key: str) -> Optional[str]:
        """Check for exit conditions"""
        if instrument_key not in self.positions:
            return None

        position = self.positions[instrument_key]

        if instrument_key not in self.historical_data:
            return None

        data = self.historical_data[instrument_key]
        current_price = data["close"][-1] if data["close"] else position["entry_price"]

        # Trailing Stop Loss
        if position["type"] == "BUY":
            # Update trailing SL
            new_sl = current_price * (1 - self.trailing_sl_percent)
            if new_sl > position["trailing_sl"]:
                position["trailing_sl"] = new_sl

            # Check if hit SL
            if current_price <= position["trailing_sl"]:
                return "EXIT_BUY"

        elif position["type"] == "SELL":
            # Update trailing SL
            new_sl = current_price * (1 + self.trailing_sl_percent)
            if new_sl < position["trailing_sl"]:
                position["trailing_sl"] = new_sl

            # Check if hit SL
            if current_price >= position["trailing_sl"]:
                return "EXIT_SELL"

        return None

    def execute_trade(
        self, instrument_key: str, action: str, price: float, timestamp: datetime
    ):
        """Execute a trade"""
        if action.startswith("EXIT"):
            if instrument_key not in self.positions:
                return

            position = self.positions[instrument_key]
            exit_price = price
            pnl = 0

            if position["type"] == "BUY":
                pnl = (exit_price - position["entry_price"]) * position["quantity"]
            else:  # SELL
                pnl = (position["entry_price"] - exit_price) * position["quantity"]

            # Record exit
            order = {
                "symbol": instrument_key,
                "action": "EXIT",
                "type": position["type"],
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "quantity": position["quantity"],
                "pnl": pnl,
                "timestamp": timestamp,
                "position_type": "EQUITY" if "EQ" in instrument_key else "OPTION",
            }

            self.order_history.append(order)
            self.pnl_history.append(
                {
                    "timestamp": timestamp,
                    "pnl": pnl,
                    "cumulative_pnl": sum([p["pnl"] for p in self.pnl_history]) + pnl,
                }
            )

            # Remove position
            del self.positions[instrument_key]

            logger.info(
                f"🚪 EXIT {position['type']} | Symbol: {instrument_key} | "
                f"Entry: {position['entry_price']:.2f} | Exit: {exit_price:.2f} | "
                f"P&L: {pnl:.2f}"
            )

        else:  # ENTRY
            if instrument_key in self.positions:
                return  # Already in position

            # Create new position
            self.positions[instrument_key] = {
                "type": action,
                "entry_price": price,
                "quantity": self.quantity,
                "entry_time": timestamp,
                "trailing_sl": (
                    price * (1 - self.trailing_sl_percent)
                    if action == "BUY"
                    else price * (1 + self.trailing_sl_percent)
                ),
            }

            order = {
                "symbol": instrument_key,
                "action": "ENTRY",
                "type": action,
                "price": price,
                "quantity": self.quantity,
                "timestamp": timestamp,
                "position_type": "EQUITY" if "EQ" in instrument_key else "OPTION",
            }

            self.order_history.append(order)
            logger.info(
                f"🎯 ENTRY {action} | Symbol: {instrument_key} | "
                f"Price: {price:.2f} | Qty: {self.quantity}"
            )

    def update_live_pnl(self, current_prices: Dict) -> float:
        """Calculate live P&L for open positions"""
        total_pnl = 0
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                if position["type"] == "BUY":
                    pnl = (current_price - position["entry_price"]) * position[
                        "quantity"
                    ]
                else:  # SELL
                    pnl = (position["entry_price"] - current_price) * position[
                        "quantity"
                    ]
                total_pnl += pnl

        return total_pnl

    def print_status(self, timestamp: datetime):
        """Print current status"""
        current_prices = {}
        for instrument_key, data in self.historical_data.items():
            if data["close"]:
                current_prices[instrument_key] = data["close"][-1]

        live_pnl = self.update_live_pnl(current_prices)
        cumulative_pnl = sum([p["pnl"] for p in self.pnl_history]) + live_pnl

        logger.info(f"\n" + "=" * 80)
        logger.info(f"📊 STRATEGY STATUS - {timestamp}")
        logger.info(
            f"💰 Live P&L: {live_pnl:.2f} | Cumulative P&L: {cumulative_pnl:.2f}"
        )
        logger.info(f"📈 Open Positions: {len(self.positions)}")

        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, position["entry_price"])
            pnl = (
                (current_price - position["entry_price"]) * position["quantity"]
                if position["type"] == "BUY"
                else (position["entry_price"] - current_price) * position["quantity"]
            )
            logger.info(
                f"   {symbol} | {position['type']} | Entry: {position['entry_price']:.2f} | "
                f"Current: {current_price:.2f} | P&L: {pnl:.2f}"
            )
        logger.info("=" * 80)


def get_market_data_feed_authorize_v3():
    """Get authorization for market data feed."""
    access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is not set; export a current Upstox access token")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
    api_response = requests.get(url=url, headers=headers)
    print("Response:", api_response.status_code, api_response.text)
    if api_response.status_code != 200:
        print("Failed to authorize market data feed")
    return api_response.json()


def decode_protobuf(buffer):
    """Decode protobuf message."""
    feed_response = pb.FeedResponse()
    feed_response.ParseFromString(buffer)
    return feed_response


def parse_market_data(feed_data: Dict) -> Dict:
    """Parse market data from WebSocket feed"""
    try:
        instrument_key = list(feed_data["feeds"].keys())[0]
        feed = feed_data["feeds"][instrument_key]["fullFeed"]["marketFF"]

        # Extract LTP data
        ltp_data = feed.get("ltpc", {})
        ltp = float(ltp_data.get("ltp", 0))
        ltt = ltp_data.get("ltt", "")
        ltq = ltp_data.get("ltq", "")

        # Extract OHLC data
        ohlc_data = feed.get("marketOHLC", {}).get("ohlc", [])
        daily_ohlc = next(
            (item for item in ohlc_data if item.get("interval") == "1d"), {}
        )
        intraday_ohlc = next(
            (item for item in ohlc_data if item.get("interval") == "I1"), {}
        )

        # Extract bid-ask data
        bid_ask = feed.get("marketLevel", {}).get("bidAskQuote", [])
        best_bid = bid_ask[0]["bidP"] if bid_ask else ltp
        best_ask = bid_ask[0]["askP"] if bid_ask else ltp

        return {
            "instrument_key": instrument_key,
            "timestamp": datetime.now(),
            "ltp": ltp,
            "ltq": ltq,
            "ltt": ltt,
            "open": float(daily_ohlc.get("open", ltp)),
            "high": float(daily_ohlc.get("high", ltp)),
            "low": float(daily_ohlc.get("low", ltp)),
            "close": float(daily_ohlc.get("close", ltp)),
            "volume": int(daily_ohlc.get("vol", 0)),
            "best_bid": float(best_bid),
            "best_ask": float(best_ask),
            "atp": float(feed.get("atp", ltp)),  # Average Trade Price
            "total_buy_qty": float(feed.get("tbq", 0)),
            "total_sell_qty": float(feed.get("tsq", 0)),
        }
    except Exception as e:
        logger.error(f"Error parsing market data: {e}")
        return None


# Global strategy instance
strategy = TradingStrategy()


async def fetch_market_data():
    """Fetch market data using WebSocket and run trading strategy"""

    # Create default SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Get market data feed authorization
    authorize_response = get_market_data_feed_authorize_v3()

    if authorize_response.get("status") != "success":
        logger.error("Failed to authorize market data feed")
        return

    async with websockets.connect(
        authorize_response["data"]["authorized_redirect_uri"], ssl=ssl_context
    ) as websocket:
        logger.info("✅ WebSocket connection established")
        await asyncio.sleep(1)

        # Subscribe to instruments (modify as needed)
        instruments = ["NSE_EQ|INE127D01025"]  # Example instrument
        data = {
            "guid": "strategy_guid",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": instruments,
            },
        }

        binary_data = json.dumps(data).encode("utf-8")
        await websocket.send(binary_data)
        logger.info(f"✅ Subscribed to instruments: {instruments}")

        last_status_print = datetime.now()
        message_count = 0

        while True:
            try:
                message = await websocket.recv()
                decoded_data = decode_protobuf(message)
                data_dict = MessageToDict(decoded_data)

                # Process live feed data
                if data_dict.get("type") == "live_feed" and "feeds" in data_dict:
                    market_data = parse_market_data(data_dict)

                    if market_data and market_data["ltp"] > 0:
                        instrument_key = market_data["instrument_key"]
                        strategy.initialize_instrument_data(instrument_key)

                        # Add new data point
                        data = strategy.historical_data[instrument_key]
                        data["timestamp"].append(market_data["timestamp"])
                        data["open"].append(market_data["open"])
                        data["high"].append(market_data["high"])
                        data["low"].append(market_data["low"])
                        data["close"].append(market_data["ltp"])  # Use LTP as close
                        data["volume"].append(market_data["volume"])

                        # Keep only last 100 data points
                        max_points = 100
                        for key in [
                            "timestamp",
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                        ]:
                            if len(data[key]) > max_points:
                                data[key] = data[key][-max_points:]

                        # Calculate indicators if we have enough data
                        if len(data["close"]) >= strategy.min_data_points:
                            # Calculate EMA
                            ema_values = strategy.calculate_ema(
                                data["close"], strategy.ema_period
                            )
                            data["ema"] = ema_values

                            # Calculate SuperTrend
                            supertrend_data = strategy.calculate_supertrend(
                                data["high"],
                                data["low"],
                                data["close"],
                                strategy.supertrend_period,
                                strategy.supertrend_multiplier,
                            )
                            data["supertrend"] = supertrend_data["supertrend"]
                            data["direction"] = supertrend_data["direction"]

                            # Check trading conditions
                            if (
                                len(data["close"])
                                >= max(strategy.ema_period, strategy.supertrend_period)
                                + 1
                            ):
                                # Check entry conditions
                                action = strategy.check_entry_conditions(instrument_key)
                                if action:
                                    strategy.execute_trade(
                                        instrument_key,
                                        action,
                                        market_data["ltp"],
                                        market_data["timestamp"],
                                    )
                                    logger.info(
                                        f"📊 Indicators - EMA: {data['ema'][-1]:.2f}, "
                                        f"SuperTrend: {data['supertrend'][-1]:.2f}, "
                                        f"Direction: {data['direction'][-1]}"
                                    )

                                # Check exit conditions for all positions
                                for symbol in list(strategy.positions.keys()):
                                    if symbol in strategy.historical_data:
                                        exit_action = strategy.check_exit_conditions(
                                            symbol
                                        )
                                        if exit_action:
                                            current_price = strategy.historical_data[
                                                symbol
                                            ]["close"][-1]
                                            strategy.execute_trade(
                                                symbol,
                                                exit_action,
                                                current_price,
                                                market_data["timestamp"],
                                            )

                        message_count += 1

                        # Print status every 50 messages or 30 seconds
                        current_time = datetime.now()
                        if (
                            current_time - last_status_print
                        ).seconds >= 30 or message_count % 50 == 0:
                            strategy.print_status(current_time)
                            last_status_print = current_time

                            # Print latest market data
                            logger.info(
                                f"📈 Market Data - {instrument_key}: "
                                f"LTP: {market_data['ltp']:.2f}, "
                                f"Volume: {market_data['volume']}, "
                                f"Bid: {market_data['best_bid']:.2f}, "
                                f"Ask: {market_data['best_ask']:.2f}"
                            )

                # Print raw data occasionally for monitoring
                if message_count % 100 == 0:
                    logger.debug(f"Raw data: {json.dumps(data_dict, indent=2)}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                continue


# Run the strategy
if __name__ == "__main__":
    try:
        asyncio.run(fetch_market_data())
    except KeyboardInterrupt:
        logger.info("Strategy stopped by user")
    except Exception as e:
        logger.error(f"Strategy error: {e}")
