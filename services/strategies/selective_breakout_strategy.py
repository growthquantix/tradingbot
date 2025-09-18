"""
Selective Breakout Strategy with Real-time PnL
Only processes specific stocks based on instrument_key filtering
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Real-time position tracking"""

    instrument_key: str
    symbol: str
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    entry_time: datetime
    pnl: Decimal = Decimal("0")
    pnl_percentage: Decimal = Decimal("0")


@dataclass
class BreakoutSignal:
    """Breakout signal with risk/reward calculation"""

    instrument_key: str
    signal_type: str  # 'BUY' or 'SELL'
    entry_price: Decimal
    target_price: Decimal
    stop_loss: Decimal
    risk_reward_ratio: Decimal
    confidence: Decimal
    timestamp: datetime


class SelectiveBreakoutStrategy:
    """
    Breakout strategy that only processes selected stocks
    with real-time PnL calculation and risk management
    """

    def __init__(self, selected_stocks: List[str]):
        """
        Initialize strategy for specific stocks

        Args:
            selected_stocks: List of instrument_keys to monitor
            Example: ['NSE_EQ|INE002A01018', 'NSE_EQ|INE467B01029']  # RELIANCE, ASIANPAINT
        """
        self.selected_stocks: Set[str] = set(selected_stocks)
        self.positions: Dict[str, Position] = {}
        self.active_signals: Dict[str, BreakoutSignal] = {}
        self.price_history: Dict[str, List[Dict]] = {}
        self.kafka_system = None
        self.running = False

        # Strategy Parameters
        self.breakout_threshold = Decimal("0.02")  # 2% breakout threshold
        self.risk_reward_ratio = Decimal("2.0")  # 1:2 risk reward
        self.stop_loss_pct = Decimal("0.015")  # 1.5% stop loss

        logger.info(
            f"Selective Breakout Strategy initialized for {len(selected_stocks)} stocks"
        )

    async def start_strategy(self):
        """Start the selective breakout strategy"""
        try:
            from services.hft.producer import get_hft_kafka_config

            self.kafka_system = get_hft_kafka_config()

            if not await self.kafka_system.initialize():
                logger.error("Failed to initialize Kafka system")
                return

            logger.info("Starting selective breakout strategy consumers...")

            # Start market data consumer (filtered)
            market_data_task = asyncio.create_task(
                self.kafka_system.start_consumer(
                    consumer_name="selective_breakout_market",
                    topics=["trading.market_data.raw"],
                    message_handler=self.handle_market_data,
                )
            )

            # Start PnL calculator task
            pnl_task = asyncio.create_task(self.calculate_realtime_pnl())

            # Start UI updater task
            ui_task = asyncio.create_task(self.update_ui_data())

            self.running = True
            logger.info(
                f"Selective breakout strategy started for stocks: {list(self.selected_stocks)}"
            )

            # Keep running
            await asyncio.gather(market_data_task, pnl_task, ui_task)

        except Exception as e:
            logger.error(f"Error starting selective breakout strategy: {e}")

    async def handle_market_data(self, message: Dict):
        """
        Handle market data - ONLY for selected stocks
        Filter by instrument_key before processing
        """
        try:
            feeds = message.get("feeds", {})

            for instrument_key, feed_data in feeds.items():
                # ⭐ KEY FILTERING: Only process selected stocks
                if instrument_key not in self.selected_stocks:
                    continue  # Skip unwanted stocks

                # Extract price data for our selected stock
                if "fullFeed" not in feed_data:
                    continue

                market_data = feed_data["fullFeed"].get("marketFF", {})
                ltpc = market_data.get("ltpc", {})

                current_price = ltpc.get("ltp")
                if not current_price:
                    continue

                current_price = Decimal(str(current_price))

                # Update price history for this stock
                await self.update_price_history(
                    instrument_key,
                    {
                        "price": current_price,
                        "timestamp": datetime.now(),
                        "volume": ltpc.get("ltq", 0),
                    },
                )

                # Check for breakout signal
                signal = await self.detect_breakout(instrument_key, current_price)
                if signal:
                    await self.publish_breakout_signal(signal)

                # Update existing positions PnL
                await self.update_position_pnl(instrument_key, current_price)

                logger.debug(f"Processed {instrument_key}: {current_price}")

        except Exception as e:
            logger.error(f"Error handling market data: {e}")

    async def detect_breakout(
        self, instrument_key: str, current_price: Decimal
    ) -> Optional[BreakoutSignal]:
        """
        Detect breakout patterns for specific stock
        Calculate risk/reward before generating signal
        """
        try:
            # Get price history for this stock
            history = self.price_history.get(instrument_key, [])
            if len(history) < 20:  # Need minimum history
                return None

            # Calculate recent high/low (last 20 periods)
            recent_prices = [p["price"] for p in history[-20:]]
            recent_high = max(recent_prices)
            recent_low = min(recent_prices)

            # Check for breakout above recent high
            if current_price > recent_high * (1 + self.breakout_threshold):
                # Calculate targets
                target_price = current_price * (
                    1 + self.stop_loss_pct * self.risk_reward_ratio
                )
                stop_loss = current_price * (1 - self.stop_loss_pct)

                risk = current_price - stop_loss
                reward = target_price - current_price
                risk_reward = reward / risk if risk > 0 else Decimal("0")

                # Only signal if risk/reward is favorable
                if risk_reward >= self.risk_reward_ratio:
                    return BreakoutSignal(
                        instrument_key=instrument_key,
                        signal_type="BUY",
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        risk_reward_ratio=risk_reward,
                        confidence=Decimal("0.85"),
                        timestamp=datetime.now(),
                    )

            # Check for breakdown below recent low
            elif current_price < recent_low * (1 - self.breakout_threshold):
                # Calculate targets for short
                target_price = current_price * (
                    1 - self.stop_loss_pct * self.risk_reward_ratio
                )
                stop_loss = current_price * (1 + self.stop_loss_pct)

                risk = stop_loss - current_price
                reward = current_price - target_price
                risk_reward = reward / risk if risk > 0 else Decimal("0")

                if risk_reward >= self.risk_reward_ratio:
                    return BreakoutSignal(
                        instrument_key=instrument_key,
                        signal_type="SELL",
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        risk_reward_ratio=risk_reward,
                        confidence=Decimal("0.80"),
                        timestamp=datetime.now(),
                    )

            return None

        except Exception as e:
            logger.error(f"Error detecting breakout for {instrument_key}: {e}")
            return None

    async def publish_breakout_signal(self, signal: BreakoutSignal):
        """Publish breakout signal to Kafka"""
        try:
            signal_message = {
                "instrument_key": signal.instrument_key,
                "signal_type": signal.signal_type,
                "entry_price": float(signal.entry_price),
                "target_price": float(signal.target_price),
                "stop_loss": float(signal.stop_loss),
                "risk_reward_ratio": float(signal.risk_reward_ratio),
                "confidence": float(signal.confidence),
                "timestamp": signal.timestamp.isoformat(),
                "strategy": "selective_breakout",
            }

            await self.kafka_system.publish_message(
                topic="trading.signals.breakout",
                message=signal_message,
                key=signal.instrument_key,
            )

            # Store active signal
            self.active_signals[signal.instrument_key] = signal

            logger.info(
                f"BREAKOUT SIGNAL: {signal.signal_type} {signal.instrument_key} @ {signal.entry_price} (R:R {signal.risk_reward_ratio})"
            )

        except Exception as e:
            logger.error(f"Error publishing breakout signal: {e}")

    async def update_position_pnl(self, instrument_key: str, current_price: Decimal):
        """Update real-time PnL for existing positions"""
        try:
            if instrument_key in self.positions:
                position = self.positions[instrument_key]
                position.current_price = current_price

                # Calculate PnL
                if position.quantity > 0:  # Long position
                    position.pnl = (
                        current_price - position.entry_price
                    ) * position.quantity
                else:  # Short position
                    position.pnl = (position.entry_price - current_price) * abs(
                        position.quantity
                    )

                # Calculate percentage
                position.pnl_percentage = (
                    position.pnl / (position.entry_price * abs(position.quantity))
                ) * 100

                logger.debug(
                    f"Updated PnL {instrument_key}: {position.pnl} ({position.pnl_percentage:.2f}%)"
                )

        except Exception as e:
            logger.error(f"Error updating PnL for {instrument_key}: {e}")

    async def calculate_realtime_pnl(self):
        """Calculate and publish real-time PnL data"""
        while self.running:
            try:
                if self.positions:
                    total_pnl = sum(pos.pnl for pos in self.positions.values())
                    total_positions = len(self.positions)

                    pnl_data = {
                        "strategy": "selective_breakout",
                        "total_pnl": float(total_pnl),
                        "positions_count": total_positions,
                        "positions": [
                            {
                                "instrument_key": pos.instrument_key,
                                "symbol": pos.symbol,
                                "quantity": pos.quantity,
                                "entry_price": float(pos.entry_price),
                                "current_price": float(pos.current_price),
                                "pnl": float(pos.pnl),
                                "pnl_percentage": float(pos.pnl_percentage),
                            }
                            for pos in self.positions.values()
                        ],
                        "timestamp": datetime.now().isoformat(),
                    }

                    # Publish to UI updates topic
                    await self.kafka_system.publish_message(
                        topic="trading.ui.pnl_updates",
                        message=pnl_data,
                        key="selective_breakout_pnl",
                    )

                await asyncio.sleep(1)  # Update every second

            except Exception as e:
                logger.error(f"Error calculating real-time PnL: {e}")
                await asyncio.sleep(5)

    async def update_ui_data(self):
        """Send real-time strategy data to UI"""
        while self.running:
            try:
                ui_data = {
                    "strategy_name": "Selective Breakout",
                    "selected_stocks": list(self.selected_stocks),
                    "active_signals": len(self.active_signals),
                    "total_positions": len(self.positions),
                    "strategy_status": "ACTIVE" if self.running else "STOPPED",
                    "timestamp": datetime.now().isoformat(),
                }

                await self.kafka_system.publish_message(
                    topic="trading.ui.strategy_updates",
                    message=ui_data,
                    key="selective_breakout_status",
                )

                await asyncio.sleep(5)  # Update every 5 seconds

            except Exception as e:
                logger.error(f"Error updating UI data: {e}")
                await asyncio.sleep(10)

    async def update_price_history(self, instrument_key: str, price_data: Dict):
        """Update price history for technical analysis"""
        if instrument_key not in self.price_history:
            self.price_history[instrument_key] = []

        self.price_history[instrument_key].append(price_data)

        # Keep only last 100 data points
        if len(self.price_history[instrument_key]) > 100:
            self.price_history[instrument_key] = self.price_history[instrument_key][
                -100:
            ]

    def add_position(
        self, instrument_key: str, symbol: str, quantity: int, entry_price: Decimal
    ):
        """Add a new position to track"""
        self.positions[instrument_key] = Position(
            instrument_key=instrument_key,
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            entry_time=datetime.now(),
        )
        logger.info(f"Added position: {symbol} {quantity} @ {entry_price}")


# Example usage
async def start_selective_breakout_for_stocks():
    """Start selective breakout strategy for specific stocks"""

    # Define which stocks to monitor
    selected_stocks = [
        "NSE_EQ|INE002A01018",  # RELIANCE
        "NSE_EQ|INE467B01029",  # ASIANPAINT
        "NSE_EQ|INE848E01016",  # NESTLEIND
        "NSE_EQ|INE040A01034",  # HDFCBANK
        "NSE_EQ|INE009A01021",  # INFOSYS
    ]

    strategy = SelectiveBreakoutStrategy(selected_stocks)

    # Add some test positions
    strategy.add_position("NSE_EQ|INE002A01018", "RELIANCE", 10, Decimal("2500.00"))
    strategy.add_position("NSE_EQ|INE467B01029", "ASIANPAINT", 5, Decimal("3200.00"))

    # Start the strategy
    await strategy.start_strategy()


if __name__ == "__main__":
    asyncio.run(start_selective_breakout_for_stocks())
