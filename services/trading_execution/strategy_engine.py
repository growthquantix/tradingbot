"""
Strategy Engine - SuperTrend + EMA
Generates entry/exit signals based on technical indicators with live market data
"""

import logging
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from utils.logging_utils import log_signal_generation, log_trailing_update, generate_trace_id

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


class TrailingStopType(Enum):
    """Trailing stop loss types"""
    SUPERTREND_1X = "supertrend_1x"  # 1x multiplier SuperTrend
    SUPERTREND_2X = "supertrend_2x"  # 2x multiplier SuperTrend
    PERCENTAGE = "percentage"         # Fixed percentage


@dataclass
class TradingSignal:
    """
    Trading signal with entry/exit details

    Attributes:
        signal_type: Type of signal (BUY/SELL/HOLD/EXIT)
        price: Price at which signal generated
        confidence: Signal confidence (0-1)
        reason: Reason for signal generation
        indicators: Indicator values at signal time
        entry_price: Recommended entry price
        stop_loss: Stop loss price
        target_price: Target price
        trailing_stop_config: Trailing stop loss configuration
        timestamp: Signal generation timestamp
    """
    signal_type: SignalType
    price: Decimal
    confidence: Decimal
    reason: str
    indicators: Dict[str, Any]
    entry_price: Decimal
    stop_loss: Decimal
    target_price: Decimal
    trailing_stop_config: Dict[str, Any]
    timestamp: str


class StrategyEngine:
    """
    SuperTrend + EMA Strategy Engine

    Strategy Rules:
    - Entry: Price crosses above SuperTrend AND price > EMA (for longs)
    - Entry: Price crosses below SuperTrend AND price < EMA (for shorts)
    - Exit: SuperTrend reversal OR price crosses EMA (opposite direction)
    - Trailing Stop: Uses SuperTrend levels with 1x or 2x multiplier options
    """

    def __init__(self):
        """Initialize strategy engine with default parameters"""
        # EMA Configuration
        self.ema_period = 20  # 20-period EMA

        # SuperTrend Configuration
        self.supertrend_period = 10  # ATR period
        self.supertrend_multiplier_1x = 3.0  # Standard multiplier
        self.supertrend_multiplier_2x = 6.0  # Conservative multiplier

        # Risk Management
        self.default_risk_reward_ratio = Decimal('2.0')  # 1:2 risk-reward
        self.min_confidence_threshold = Decimal('0.60')  # Minimum 60% confidence

        # Exit Protection - Prevent premature exits
        self.min_profit_before_exit_percent = Decimal('0.05')  # 5% minimum profit before allowing exit (was 10%)
        self.min_hold_time_minutes = 3  # Minimum 3 minutes hold time (was 5)

        # Lock Profit Configuration - Make position risk-free
        self.breakeven_profit_threshold = Decimal('0.35')  # Start trailing to breakeven at 35% of target (was 75%)
        self.min_roi_for_breakeven = Decimal('0.05')       # Minimum 5% ROI required to move to breakeven (was 2%)
        self.lock_profit_threshold = Decimal('1.00')  # Lock profit when target hit
        self.lock_profit_percent = Decimal('0.80')  # Lock 80% of profit

        # Stop Loss Buffer - Prevent tight stops
        # BUG-01 FIX: Increased from 3% to 8% — FNO option premiums move 5-10% on normal ticks.
        # A 3% minimum SL was getting hit by market noise before the strategy had a chance to work.
        self.sl_buffer_percent = Decimal('0.08')  # 8% minimum SL buffer for option premiums

        logger.info("Strategy Engine initialized with SuperTrend + EMA")
        logger.info(f"  EMA Period: {self.ema_period}")
        logger.info(f"  SuperTrend Period: {self.supertrend_period}")
        logger.info(f"  SuperTrend Multipliers: 1x={self.supertrend_multiplier_1x}, 2x={self.supertrend_multiplier_2x}")
        logger.info(f"  Exit Protection: Min profit {self.min_profit_before_exit_percent:.0%}, Min hold {self.min_hold_time_minutes}min")
        logger.info(f"  Lock Profit: Breakeven at {self.breakeven_profit_threshold:.0%} target (min {self.min_roi_for_breakeven:.0%} ROI), Lock {self.lock_profit_percent:.0%} at target")

    def calculate_ema(self, prices: List[float], period: int) -> np.ndarray:
        """
        Calculate Exponential Moving Average

        Args:
            prices: List of price values
            period: EMA period

        Returns:
            NumPy array of EMA values

        Raises:
            ValueError: If prices list is too short
        """
        if len(prices) < period:
            raise ValueError(f"Insufficient data: need at least {period} prices")

        try:
            prices_series = pd.Series(prices)
            ema = prices_series.ewm(span=period, adjust=False).mean()
            return ema.values

        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            raise

    def calculate_atr(
        self,
        high_prices: List[float],
        low_prices: List[float],
        close_prices: List[float],
        period: int
    ) -> np.ndarray:
        """
        Calculate Average True Range (ATR)

        Args:
            high_prices: List of high prices
            low_prices: List of low prices
            close_prices: List of close prices
            period: ATR period

        Returns:
            NumPy array of ATR values

        Raises:
            ValueError: If price lists have different lengths
        """
        if not (len(high_prices) == len(low_prices) == len(close_prices)):
            raise ValueError("Price lists must have same length")

        try:
            df = pd.DataFrame({
                'high': high_prices,
                'low': low_prices,
                'close': close_prices
            })

            # True Range calculation
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift())
            df['tr3'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

            # ATR = Moving average of TR
            atr = df['tr'].rolling(window=period).mean()

            return atr.values

        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            raise

    def calculate_supertrend(
        self,
        high_prices: List[float],
        low_prices: List[float],
        close_prices: List[float],
        period: int = 10,
        multiplier: float = 3.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate SuperTrend indicator

        Args:
            high_prices: List of high prices
            low_prices: List of low prices
            close_prices: List of close prices
            period: ATR period
            multiplier: ATR multiplier

        Returns:
            Tuple of (supertrend_values, trend_direction)
            trend_direction: 1 = uptrend, -1 = downtrend

        Raises:
            ValueError: If parameters are invalid
        """
        if period <= 0 or multiplier <= 0:
            raise ValueError("Period and multiplier must be positive")

        try:
            df = pd.DataFrame({
                'high': high_prices,
                'low': low_prices,
                'close': close_prices
            })

            # Calculate ATR
            atr = self.calculate_atr(high_prices, low_prices, close_prices, period)
            df['atr'] = atr

            # Basic Bands
            df['hl_avg'] = (df['high'] + df['low']) / 2
            df['basic_ub'] = df['hl_avg'] + (multiplier * df['atr'])
            df['basic_lb'] = df['hl_avg'] - (multiplier * df['atr'])

            # Final Bands
            df['final_ub'] = 0.0
            df['final_lb'] = 0.0
            df['supertrend'] = 0.0
            df['trend'] = 1

            for i in range(period, len(df)):
                # Upper Band
                if df['basic_ub'].iloc[i] < df['final_ub'].iloc[i-1] or df['close'].iloc[i-1] > df['final_ub'].iloc[i-1]:
                    df.loc[df.index[i], 'final_ub'] = df['basic_ub'].iloc[i]
                else:
                    df.loc[df.index[i], 'final_ub'] = df['final_ub'].iloc[i-1]

                # Lower Band
                if df['basic_lb'].iloc[i] > df['final_lb'].iloc[i-1] or df['close'].iloc[i-1] < df['final_lb'].iloc[i-1]:
                    df.loc[df.index[i], 'final_lb'] = df['basic_lb'].iloc[i]
                else:
                    df.loc[df.index[i], 'final_lb'] = df['final_lb'].iloc[i-1]

                # SuperTrend
                if df['close'].iloc[i] <= df['final_ub'].iloc[i]:
                    df.loc[df.index[i], 'supertrend'] = df['final_ub'].iloc[i]
                    df.loc[df.index[i], 'trend'] = -1
                else:
                    df.loc[df.index[i], 'supertrend'] = df['final_lb'].iloc[i]
                    df.loc[df.index[i], 'trend'] = 1

            return df['supertrend'].values, df['trend'].values

        except Exception as e:
            logger.error(f"Error calculating SuperTrend: {e}")
            raise

    def should_allow_exit_signal(
        self,
        current_price: Decimal,
        entry_price: Decimal,
        entry_time: Optional[datetime] = None,
        current_pnl_percent: Optional[Decimal] = None
    ) -> Tuple[bool, str]:
        """
        Check if exit signal should be allowed - NEUTRALIZED
        Authority moved to pnl_tracker.py
        """
        # Always allow exit signals. Control/blocking logic is managed by pnl_tracker.py.
        return True, "Exit allowed: Control managed by pnl_tracker"

    def generate_signal(
        self,
        current_price: Decimal,
        historical_data: Dict[str, List[float]],
        option_type: str = "CE"
    ) -> TradingSignal:
        """
        Generate trading signal based on SuperTrend + EMA strategy

        Args:
            current_price: Current market price
            historical_data: Dict with 'open', 'high', 'low', 'close', 'volume' lists
            option_type: "CE" for calls, "PE" for puts

        Returns:
            TradingSignal with entry/exit details

        Raises:
            ValueError: If historical_data is insufficient
        """
        if not historical_data or 'close' not in historical_data:
            raise ValueError("Historical data must contain 'close' prices")

        try:
            close_prices = historical_data['close']
            high_prices = historical_data.get('high', close_prices)
            low_prices = historical_data.get('low', close_prices)

            if len(close_prices) < max(self.ema_period, self.supertrend_period) + 10:
                raise ValueError(f"Need at least {max(self.ema_period, self.supertrend_period) + 10} candles")

            # Calculate indicators
            ema = self.calculate_ema(close_prices, self.ema_period)
            supertrend_1x, trend_1x = self.calculate_supertrend(
                high_prices, low_prices, close_prices,
                self.supertrend_period, self.supertrend_multiplier_1x
            )
            supertrend_2x, trend_2x = self.calculate_supertrend(
                high_prices, low_prices, close_prices,
                self.supertrend_period, self.supertrend_multiplier_2x
            )

            # Current values (latest)
            current_ema = Decimal(str(ema[-1]))
            current_supertrend_1x = Decimal(str(supertrend_1x[-1]))
            current_supertrend_2x = Decimal(str(supertrend_2x[-1]))
            current_trend_1x = int(trend_1x[-1])
            current_trend_2x = int(trend_2x[-1])

            # Previous values (for 2-candle confirmation)
            prev_trend_1x = int(trend_1x[-2]) if len(trend_1x) > 1 else current_trend_1x
            prev_prev_trend_1x = int(trend_1x[-3]) if len(trend_1x) > 2 else prev_trend_1x

            # Determine signal type
            signal_type = SignalType.HOLD
            confidence = Decimal('0.5')
            reason = "No clear signal"

            # DIAGNOSTIC LOGGING FOR CORRECTNESS
            logger.info(
                f"DEBUG [{option_type}]: Price: {current_price:.2f} | EMA: {current_ema:.2f} | "
                f"ST_1x: {current_supertrend_1x:.2f} ({'UP' if current_trend_1x == 1 else 'DOWN'}) | "
                f"Prev_ST: {'UP' if prev_trend_1x == 1 else 'DOWN'} | "
                f"PPrev_ST: {'UP' if prev_prev_trend_1x == 1 else 'DOWN'}"
            )

            # LONG ENTRY LOGIC (for CE options)
            if option_type == "CE":
                # Uptrend conditions
                price_above_ema = current_price > current_ema
                price_above_supertrend = current_price > current_supertrend_1x
                trend_bullish = current_trend_1x == 1
                
                # REQUIRMENT: 2 consecutive candles confirming trend
                # We want the NEW trend to be established for 2 candles (current and previous)
                # This prevents entering on the very first candle which might be a fakeout
                new_trend_established = current_trend_1x == 1 and prev_trend_1x == 1 and prev_prev_trend_1x == -1
                existing_strong_trend = current_trend_1x == 1 and prev_trend_1x == 1 and price_above_ema and price_above_supertrend

                # ENTRY CONDITIONS (open new position)
                if new_trend_established and price_above_ema:
                    signal_type = SignalType.BUY
                    confidence = Decimal('0.85')
                    reason = "SuperTrend reversal to uptrend (2-candle confirmation) + Price above EMA"
                elif existing_strong_trend:
                    signal_type = SignalType.BUY
                    confidence = Decimal('0.75')
                    reason = "Strong confirmed uptrend: Price above SuperTrend and EMA (2-candle confirmation)"
                
                # EXIT CONDITIONS - ENHANCED: Require STRONG confirmation before exit
                # This prevents premature exits on minor pullbacks
                elif not trend_bullish and not price_above_supertrend and not price_above_ema:
                    # ALL THREE must be bearish: Trend reversed, price below SuperTrend AND EMA
                    signal_type = SignalType.EXIT_LONG
                    confidence = Decimal('0.80')
                    reason = "Exit: Strong bearish reversal - trend, price below SuperTrend & EMA"
                elif current_trend_1x == -1 and prev_trend_1x == -1:
                    # Explicit trend reversal from bullish to bearish (2 candles)
                    if not price_above_supertrend and not price_above_ema:
                        signal_type = SignalType.EXIT_LONG
                        confidence = Decimal('0.85')
                        reason = "Exit: Confirmed trend reversal (2 candles) with price breakdown"
                    else:
                        signal_type = SignalType.HOLD
                        confidence = Decimal('0.50')
                        reason = "Trend reversal but price holding - trailing SL active"
                else:
                    signal_type = SignalType.HOLD
                    confidence = Decimal('0.50')
                    reason = "Waiting for clear signal - no strong reversal"

            # PE OPTIONS LOGIC (Buying Put Options)
            else:
                # Downtrend conditions
                price_below_ema = current_price < current_ema
                price_below_supertrend = current_price < current_supertrend_1x
                trend_bearish = current_trend_1x == -1
                
                # REQUIRMENT: 2 consecutive candles confirming trend
                new_trend_established = current_trend_1x == -1 and prev_trend_1x == -1 and prev_prev_trend_1x == 1
                existing_strong_trend = current_trend_1x == -1 and prev_trend_1x == -1 and price_below_ema and price_below_supertrend

                # ENTRY CONDITIONS (BUY put option when bearish)
                if new_trend_established and price_below_ema:
                    signal_type = SignalType.BUY
                    confidence = Decimal('0.85')
                    reason = "SuperTrend reversal to downtrend (2-candle confirmation) + Price below EMA (Buy Put)"
                elif existing_strong_trend:
                    signal_type = SignalType.BUY
                    confidence = Decimal('0.75')
                    reason = "Strong confirmed downtrend: Price below SuperTrend and EMA (2-candle confirmation)"
                
                # EXIT CONDITIONS - ENHANCED: Require STRONG confirmation before exit
                elif not trend_bearish and not price_below_supertrend and not price_below_ema:
                    # ALL THREE must be bullish: Trend reversed, price above SuperTrend AND EMA
                    signal_type = SignalType.EXIT_LONG
                    confidence = Decimal('0.80')
                    reason = "Exit: Strong bullish reversal - trend, price above SuperTrend & EMA (Exit Put)"
                elif current_trend_1x == 1 and prev_trend_1x == 1:
                    # Explicit trend reversal from bearish to bullish (2 candles)
                    if not price_below_supertrend and not price_below_ema:
                        signal_type = SignalType.EXIT_LONG
                        confidence = Decimal('0.85')
                        reason = "Exit: Confirmed trend reversal (2 candles) with price breakout (Exit Put)"
                    else:
                        signal_type = SignalType.HOLD
                        confidence = Decimal('0.50')
                        reason = "Trend reversal but price holding - trailing SL active (Put)"
                else:
                    signal_type = SignalType.HOLD
                    confidence = Decimal('0.50')
                    reason = "Waiting for clear signal - no strong reversal"

            # Calculate entry, stop loss, and target IN SPOT TERMS
            # These will be converted to premium terms later
            entry_price = current_price
            sl_buffer = entry_price * self.sl_buffer_percent

            if option_type == "CE":
                # For CE: SL below SuperTrend with buffer
                stop_loss = current_supertrend_1x - sl_buffer
                risk = abs(entry_price - stop_loss)
                target_price = entry_price + (risk * self.default_risk_reward_ratio)
            else:
                # For PE: SL above SuperTrend with buffer
                # Note: For buying PE, price drop is target, price rise is SL
                stop_loss = current_supertrend_1x + sl_buffer
                risk = abs(entry_price - stop_loss)
                # PE target is BELOW spot entry price
                target_price = entry_price - (risk * self.default_risk_reward_ratio)

            logger.debug(
                f"{option_type} Signal (SPOT-BASED): Entry={entry_price:.2f}, "
                f"SL={stop_loss:.2f}, Target={target_price:.2f}, Risk={risk:.2f}"
            )

            # Trailing stop configuration
            trailing_stop_config = {
                "type": TrailingStopType.SUPERTREND_1X.value,
                "supertrend_1x_value": float(current_supertrend_1x),
                "supertrend_2x_value": float(current_supertrend_2x),
                "multiplier_1x": self.supertrend_multiplier_1x,
                "multiplier_2x": self.supertrend_multiplier_2x,
                "trailing_distance_percent": 2.0  # 2% trailing for percentage-based
            }

            # Indicator values
            indicators = {
                "ema": float(current_ema),
                "supertrend_1x": float(current_supertrend_1x),
                "supertrend_2x": float(current_supertrend_2x),
                "trend_1x": current_trend_1x,
                "trend_2x": current_trend_2x,
                "atr": float(supertrend_1x[-1] - supertrend_1x[-2]) if len(supertrend_1x) > 1 else 0.0
            }

            signal = TradingSignal(
                signal_type=signal_type,
                price=current_price,
                confidence=confidence,
                reason=reason,
                indicators=indicators,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                trailing_stop_config=trailing_stop_config,
                timestamp=datetime.now().isoformat()
            )

            logger.info(f"Signal generated: {signal_type.value} at {current_price}")
            logger.info(f"  Confidence: {confidence:.2f}")
            logger.info(f"  Entry: {entry_price}, SL: {stop_loss}, Target: {target_price}")
            
            # Structured logging
            log_signal_generation(
                symbol="Unknown",  # Strategy engine doesn't know symbol, passed in auto_trade
                signal_type=signal_type.value,
                confidence=float(confidence),
                strategy="SuperTrend+EMA",
                price=float(current_price),
                trace_id=generate_trace_id()
            )

            return signal

        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            raise

    def convert_spot_signal_to_premium(
        self,
        signal: TradingSignal,
        spot_price: Decimal,
        option_premium: Decimal,
        option_delta: Optional[float] = None
    ) -> TradingSignal:
        """
        Convert spot-based trading signal to premium-based values

        This is CRITICAL: Strategy generates signals on SPOT prices (trend detection),
        but we execute trades on OPTION PREMIUMS. This method converts spot-based
        SL/Target to equivalent premium values.

        Args:
            signal: Original signal with spot-based SL/Target
            spot_price: Current spot price
            option_premium: Current option premium
            option_delta: Option delta (if available), defaults to 0.5

        Returns:
            New TradingSignal with premium-based SL/Target

        Example:
            Spot Signal: BUY at 3100, SL=3090 (10 points risk)
            Delta: 0.4
            Premium: 45

            Spot risk = 10 points = 0.32% of spot
            Premium risk = 45 * 0.32% * 0.4 (delta adjustment) = 0.58
            Premium SL = 45 - 0.58 = 44.42
        """
        try:
            # Use provided delta or estimate based on option type and moneyness
            if option_delta is None:
                # Rough estimation: ATM options have ~0.5 delta
                option_delta = 0.5

            # Calculate spot-based risk percentage
            spot_risk_points = abs(signal.entry_price - signal.stop_loss)
            spot_risk_percent = spot_risk_points / signal.entry_price if signal.entry_price > 0 else Decimal('0.05')

            # Convert to premium terms using delta
            # Delta represents how much option price moves per 1 point spot move
            # So premium_risk = spot_risk * delta
            premium_risk_percent = spot_risk_percent * Decimal(str(abs(option_delta)))

            # Apply min/max bounds (3% to 40% risk)
            # REQUIREMENT: SL distance = max(3% of premium, calculated risk)
            # CRITICAL: Prevent 100% risk which leads to 0 lots. Cap at 40%.
            premium_risk_percent = max(self.sl_buffer_percent, min(premium_risk_percent, Decimal('0.40')))

            # Calculate premium-based SL and Target
            premium_sl = option_premium * (Decimal('1') - premium_risk_percent)
            premium_risk_amount = option_premium - premium_sl
            risk_reward_ratio = Decimal(str(signal.trailing_stop_config.get('risk_reward_ratio', 2.0)))
            # Target is ALWAYS above entry for LONG premium trades
            premium_target = option_premium + (premium_risk_amount * risk_reward_ratio)

            logger.info(
                f"Converted spot signal to premium: "
                f"Spot Risk={spot_risk_percent:.2%}, Delta={option_delta:.2f}, "
                f"Premium Risk={premium_risk_percent:.2%}, "
                f"Premium SL={premium_sl:.2f}, Target={premium_target:.2f}"
            )

            # Create new signal with premium-based values
            return TradingSignal(
                signal_type=signal.signal_type,
                price=option_premium,  # Use premium as current price
                confidence=signal.confidence,
                reason=signal.reason + " (converted to premium)",
                indicators=signal.indicators,  # Keep spot indicators for reference
                entry_price=option_premium,
                stop_loss=premium_sl,
                target_price=premium_target,
                trailing_stop_config=signal.trailing_stop_config,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Error converting spot signal to premium: {e}")
            # Fallback: use percentage-based approach
            return self._fallback_premium_signal(signal, option_premium)

    def _fallback_premium_signal(
        self,
        signal: TradingSignal,
        option_premium: Decimal
    ) -> TradingSignal:
        """
        Fallback method for premium signal conversion when delta not available
        Uses fixed 10% risk (as 5% is now the minimum buffer)
        """
        premium_risk = option_premium * Decimal('0.10')  # 10% risk
        premium_sl = option_premium - premium_risk
        premium_target = option_premium + (premium_risk * Decimal('2.0'))  # 1:2 R:R

        return TradingSignal(
            signal_type=signal.signal_type,
            price=option_premium,
            confidence=signal.confidence,
            reason=signal.reason + " (fallback premium conversion)",
            indicators=signal.indicators,
            entry_price=option_premium,
            stop_loss=premium_sl,
            target_price=premium_target,
            trailing_stop_config=signal.trailing_stop_config,
            timestamp=datetime.now().isoformat()
        )

    def update_trailing_stop(
        self,
        current_price: Decimal,
        entry_price: Decimal,
        current_stop_loss: Decimal,
        trailing_type: TrailingStopType,
        supertrend_value: Optional[Decimal] = None,
        position_type: str = "LONG",
        target_price: Optional[Decimal] = None,
        symbol: str = "Unknown"
    ) -> Decimal:
        """
        Update trailing stop loss with LOCK PROFIT mechanism

        ENHANCED LOGIC:
        1. If profit >= 50% of target: Trail to BREAKEVEN (make position risk-free)
        2. If profit >= 100% of target: Lock 80% of profit
        3. Otherwise: Use standard SuperTrend/percentage trailing

        This implements the user's requirement to trail stop loss to target,
        making position risk-free and locking in profits.

        Args:
            current_price: Current market price
            entry_price: Entry price of position
            current_stop_loss: Current stop loss level
            trailing_type: Type of trailing stop
            supertrend_value: Current SuperTrend value (for SuperTrend-based trailing)
            position_type: "LONG" or "SHORT"
            target_price: Target price (for lock profit calculation)
            symbol: Stock symbol for logging

        Returns:
            Updated stop loss price

        Raises:
            ValueError: If parameters are invalid
        """
        # CRITICAL: Both CE and PE are LONG premium positions for option buying
        # We always want the trailing SL to move UP as premium increases
        position_type = "LONG"
        
        if current_price <= 0 or entry_price <= 0:
            raise ValueError("Prices must be positive")

        try:
            new_stop_loss = current_stop_loss

            # Calculate current profit
            if position_type == "LONG":
                current_profit = current_price - entry_price
            else:
                current_profit = entry_price - current_price

            # Calculate target profit (if target provided)
            if target_price:
                if position_type == "LONG":
                    target_profit = target_price - entry_price
                else:
                    target_profit = entry_price - target_price

                # Calculate profit percentage of target
                profit_percent_of_target = (current_profit / target_profit) if target_profit > 0 else Decimal('0')
                
                # Calculate ROI percentage (Return on Investment)
                roi_percent = (current_profit / entry_price) if entry_price > 0 else Decimal('0')

                # LOCK PROFIT MECHANISM
                # Level 1: >= 75% of target AND Min 5% ROI -> Trail to BREAKEVEN (risk-free)
                # Added ROI check to prevent moving to breakeven too early on small targets
                if profit_percent_of_target >= self.breakeven_profit_threshold and roi_percent >= self.min_roi_for_breakeven:
                    breakeven_sl = entry_price
                    new_stop_loss = max(current_stop_loss, breakeven_sl)

                    if new_stop_loss > current_stop_loss:
                        logger.info(
                            f"LOCK PROFIT (Breakeven): Profit {profit_percent_of_target:.1%} of target (ROI {roi_percent:.1%}), "
                            f"trailing SL to breakeven {breakeven_sl:.2f}"
                        )

                # Level 2: >= 100% of target -> Lock 80% of profit
                if profit_percent_of_target >= self.lock_profit_threshold:
                    locked_profit = current_profit * self.lock_profit_percent
                    locked_sl = entry_price + locked_profit if position_type == "LONG" else entry_price - locked_profit
                    new_stop_loss = max(current_stop_loss, locked_sl)

                    if new_stop_loss > current_stop_loss:
                        logger.info(
                            f"LOCK PROFIT (80%): Target hit, locking {self.lock_profit_percent:.0%} profit, "
                            f"trailing SL to {locked_sl:.2f}"
                        )

            # Standard trailing mechanisms (when lock profit not applicable)
            if new_stop_loss == current_stop_loss:
                if trailing_type == TrailingStopType.SUPERTREND_1X or trailing_type == TrailingStopType.SUPERTREND_2X:
                    # Use SuperTrend as trailing stop
                    if supertrend_value:
                        if position_type == "LONG":
                            # Move SL up only (never down)
                            new_stop_loss = max(current_stop_loss, supertrend_value)
                        else:
                            # Move SL down only (never up)
                            new_stop_loss = min(current_stop_loss, supertrend_value)

                elif trailing_type == TrailingStopType.PERCENTAGE:
                    # Percentage-based trailing
                    # BUG-11 FIX: Increased from 2% to 5% — options move 3-5% in a single tick during
                    # high volatility. A 2% trailing stop was exiting on pure noise, not real reversals.
                    trailing_percent = Decimal('0.05')  # 5% trailing

                    if position_type == "LONG":
                        # Trail below current price by 2%
                        potential_stop = current_price * (Decimal('1') - trailing_percent)
                        new_stop_loss = max(current_stop_loss, potential_stop)
                    else:
                        # Trail above current price by 2%
                        potential_stop = current_price * (Decimal('1') + trailing_percent)
                        new_stop_loss = min(current_stop_loss, potential_stop)

            if new_stop_loss != current_stop_loss:
                logger.debug(f"Trailing SL updated: {current_stop_loss:.2f} -> {new_stop_loss:.2f}")
                
                log_trailing_update(
                    symbol=symbol,
                    old_sl=float(current_stop_loss),
                    new_sl=float(new_stop_loss),
                    reason="SuperTrend/Profit Lock",
                    current_price=float(current_price)
                )

            return new_stop_loss

        except Exception as e:
            logger.error(f"Error updating trailing stop: {e}")
            return current_stop_loss


# Create singleton instance
strategy_engine = StrategyEngine()