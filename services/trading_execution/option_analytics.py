"""
Option Analytics Service
Handles Greeks-based risk management, IV analysis, liquidity validation, and advanced option calculations
"""

import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OptionGreeks:
    """
    Option Greeks data

    Attributes:
        delta: Rate of change of option price with respect to underlying price
        theta: Rate of change of option price with respect to time (time decay)
        gamma: Rate of change of delta with respect to underlying price
        vega: Rate of change of option price with respect to volatility
        rho: Rate of change of option price with respect to interest rate
    """
    delta: Decimal
    theta: Decimal
    gamma: Decimal
    vega: Decimal
    rho: Decimal


@dataclass
class PositionGreeks:
    """
    Position-level Greeks (Greeks × Position Size)

    Attributes:
        position_delta: Total delta exposure
        position_theta: Total daily time decay
        position_gamma: Total gamma exposure
        position_vega: Total volatility sensitivity
        expected_daily_pnl_range: Expected PnL range based on delta and spot ATR
        daily_holding_cost: Cost to hold position for one day (theta)
    """
    position_delta: Decimal
    position_theta: Decimal
    position_gamma: Decimal
    position_vega: Decimal
    expected_daily_pnl_range: Decimal
    daily_holding_cost: Decimal


@dataclass
class LiquidityMetrics:
    """
    Option liquidity metrics

    Attributes:
        open_interest: Current open interest
        volume: Current trading volume
        volume_oi_ratio: Volume to OI ratio
        bid_price: Best bid price
        ask_price: Best ask price
        bid_ask_spread: Spread between bid and ask
        spread_percent: Spread as percentage of mid price
        is_liquid: Whether option meets liquidity criteria
        liquidity_score: Liquidity score (0-100)
    """
    open_interest: float
    volume: float
    volume_oi_ratio: float
    bid_price: Decimal
    ask_price: Decimal
    bid_ask_spread: Decimal
    spread_percent: Decimal
    is_liquid: bool
    liquidity_score: int


@dataclass
class OptionValidationResult:
    """
    Option validation result

    Attributes:
        valid: Whether option is valid for trading
        reason: Reason for validation result
        warnings: List of warning messages
        metrics: Dictionary of calculated metrics
    """
    valid: bool
    reason: str
    warnings: List[str]
    metrics: Dict[str, Any]


class OptionAnalyticsService:
    """
    Option Analytics Service for advanced option calculations

    Features:
    - IV validation (volatility crush risk)
    - Liquidity checks (OI, volume, bid-ask spread)
    - Greeks-based position risk
    - Time decay analysis
    - Entry quality scoring
    """

    def __init__(self):
        """Initialize option analytics with default thresholds"""
        # IV thresholds
        self.max_iv = Decimal('0.70')  # 70% max IV (adjusted for volatile stock options)
        self.high_iv_percentile = 85  # Warn if IV in top 15%

        # Liquidity thresholds
        self.min_open_interest = 5000  # Minimum OI for safe trading (was 25000, too strict for mid-caps)
        self.min_volume_oi_ratio = Decimal('0.10')  # Volume should be 10%+ of OI
        self.max_spread_percent = Decimal('5.0')  # 5% max bid-ask spread (adjusted for stock options)

        # Greeks thresholds
        self.high_theta_threshold = Decimal('0.10')  # 10% daily decay is high
        self.high_gamma_threshold = Decimal('0.01')  # High gamma near ATM

        # Risk thresholds
        self.max_vega_risk_percent = Decimal('0.15')  # 15% max vega risk

        logger.info("Option Analytics Service initialized")
        logger.info(f"  Max IV: {self.max_iv}")
        logger.info(f"  Min OI: {self.min_open_interest:,}")
        logger.info(f"  Max Spread: {self.max_spread_percent}%")

    def validate_option_for_entry(
        self,
        greeks: Dict[str, float],
        iv: float,
        oi: float,
        volume: float,
        bid_price: float,
        ask_price: float,
        premium: float,
        quantity: int,
        spot_atr: Optional[float] = None
    ) -> OptionValidationResult:
        """
        Comprehensive option validation before trade entry

        Args:
            greeks: Dictionary with delta, theta, gamma, vega, rho
            iv: Implied volatility (as decimal, e.g., 0.2258 for 22.58%)
            oi: Open interest
            volume: Trading volume
            bid_price: Best bid price
            ask_price: Best ask price
            premium: Current option premium
            quantity: Position size (number of shares)
            spot_atr: Average True Range of underlying (optional)

        Returns:
            OptionValidationResult with validation status and metrics
        """
        warnings = []
        metrics = {}

        try:
            # Validate IV
            iv_check = self._validate_iv(iv, premium)
            if not iv_check["valid"]:
                return OptionValidationResult(
                    valid=False,
                    reason=iv_check["reason"],
                    warnings=warnings,
                    metrics=metrics
                )
            warnings.extend(iv_check.get("warnings", []))
            metrics["iv_metrics"] = iv_check["metrics"]

            # Validate liquidity
            liquidity_check = self._validate_liquidity(
                oi, volume, bid_price, ask_price
            )
            if not liquidity_check["valid"]:
                return OptionValidationResult(
                    valid=False,
                    reason=liquidity_check["reason"],
                    warnings=warnings,
                    metrics=metrics
                )
            warnings.extend(liquidity_check.get("warnings", []))
            metrics["liquidity_metrics"] = liquidity_check["metrics"]

            # Calculate Greeks-based risk
            greeks_analysis = self._analyze_greeks(
                greeks, premium, quantity, spot_atr
            )
            warnings.extend(greeks_analysis.get("warnings", []))
            metrics["greeks_analysis"] = greeks_analysis["metrics"]

            # Overall quality score (0-100)
            quality_score = self._calculate_quality_score(
                iv_check, liquidity_check, greeks_analysis
            )
            metrics["quality_score"] = quality_score

            logger.info(f"Option validation passed - Quality Score: {quality_score}/100")

            return OptionValidationResult(
                valid=True,
                reason="Option validated successfully",
                warnings=warnings,
                metrics=metrics
            )

        except Exception as e:
            logger.error(f"Error in option validation: {e}")
            return OptionValidationResult(
                valid=False,
                reason=f"Validation error: {str(e)}",
                warnings=warnings,
                metrics=metrics
            )

    def _validate_iv(
        self,
        iv: float,
        premium: float
    ) -> Dict[str, Any]:
        """
        Validate implied volatility levels

        Args:
            iv: Implied volatility (decimal)
            premium: Current premium

        Returns:
            Dict with validation result
        """
        iv_decimal = Decimal(str(iv))
        warnings = []
        metrics = {}

        # Check if IV is too high (volatility crush risk)
        if iv_decimal > self.max_iv:
            return {
                "valid": False,
                "reason": f"IV too high ({iv*100:.2f}%) - Volatility crush risk after events",
                "metrics": {"iv": float(iv), "iv_percent": float(iv*100)}
            }

        # Warn if IV is elevated (above 35%)
        if iv_decimal > Decimal('0.35'):
            warnings.append(
                f"Elevated IV ({iv*100:.2f}%) - Monitor for volatility changes"
            )

        # Warn if IV is very low (less than 15%)
        if iv_decimal < Decimal('0.15'):
            warnings.append(
                f"Low IV ({iv*100:.2f}%) - May indicate low profit potential"
            )

        metrics = {
            "iv": float(iv),
            "iv_percent": float(iv * 100),
            "iv_status": "high" if iv_decimal > Decimal('0.35') else ("low" if iv_decimal < Decimal('0.15') else "normal")
        }

        logger.info(f"IV validation passed: {iv*100:.2f}%")

        return {
            "valid": True,
            "reason": "IV within acceptable range",
            "warnings": warnings,
            "metrics": metrics
        }

    def _validate_liquidity(
        self,
        oi: float,
        volume: float,
        bid_price: float,
        ask_price: float
    ) -> Dict[str, Any]:
        """
        Validate option liquidity

        Args:
            oi: Open interest
            volume: Trading volume
            bid_price: Best bid
            ask_price: Best ask

        Returns:
            Dict with validation result
        """
        warnings = []
        bid_decimal = Decimal(str(bid_price))
        ask_decimal = Decimal(str(ask_price))

        # Check minimum OI (only reject if explicit low non-zero OI; warn if OI omitted in feed tick)
        if 0 < oi < self.min_open_interest:
            return {
                "valid": False,
                "reason": f"Low open interest ({oi:,.0f}) - Illiquid option, may face high slippage",
                "metrics": {"oi": oi, "min_required": self.min_open_interest}
            }
        elif oi == 0:
            warnings.append("Open interest not present in current feed tick - proceeding with spread check")

        # Check volume/OI ratio
        volume_oi_ratio = Decimal(str(volume / oi)) if oi > 0 else Decimal('0')
        if volume_oi_ratio < self.min_volume_oi_ratio:
            warnings.append(
                f"Low volume ({volume:,.0f}) relative to OI - Volume/OI ratio: {float(volume_oi_ratio)*100:.1f}%"
            )

        # Check bid-ask spread
        spread = ask_decimal - bid_decimal
        mid_price = (bid_decimal + ask_decimal) / Decimal('2')
        spread_percent = (spread / mid_price) * Decimal('100') if mid_price > 0 else Decimal('0')

        # DYNAMIC SPREAD LIMITS (More flexible for low-priced options)
        # For a 1.0 premium, 0.05 tick is 5%. Standard 5% limit is too tight for low premiums.
        max_spread_allowed = self.max_spread_percent
        if mid_price < Decimal('2.0'):
            max_spread_allowed = Decimal('25.0')  # 25% for very low premiums
        elif mid_price < Decimal('5.0'):
            max_spread_allowed = Decimal('15.0')  # 15% for mid-low premiums
            
        # REJECT if bid is 0 (indicates no buyers, 100% loss upon exit)
        if bid_decimal <= 0:
            return {
                "valid": False,
                "reason": f"No buyers (Bid=0) - Option is extremely illiquid (Ask={float(ask_decimal):.2f})",
                "metrics": {
                    "bid": float(bid_decimal),
                    "ask": float(ask_decimal),
                    "spread_percent": 100.0
                }
            }

        if spread_percent > max_spread_allowed:
            return {
                "valid": False,
                "reason": f"Wide bid-ask spread ({float(spread_percent):.2f}%) - High slippage risk. Bid: {float(bid_decimal):.2f}, Ask: {float(ask_decimal):.2f}",
                "metrics": {
                    "bid": float(bid_decimal),
                    "ask": float(ask_decimal),
                    "spread": float(spread),
                    "spread_percent": float(spread_percent),
                    "max_allowed": float(max_spread_allowed)
                }
            }

        if spread_percent > Decimal('5.0'):
            warnings.append(
                f"Significant bid-ask spread ({float(spread_percent):.2f}%) - Expect slippage upon entry/exit"
            )
        elif spread_percent > Decimal('1.5'):
            warnings.append(
                f"Moderate bid-ask spread ({float(spread_percent):.2f}%) - Slippage risk detected"
            )

        # Calculate liquidity score (0-100)
        oi_score = min(100, int((oi / self.min_open_interest) * 50))
        volume_score = min(50, int(float(volume_oi_ratio) * 250))
        spread_score = max(0, int((max_spread_allowed - spread_percent) * 25))

        liquidity_score = oi_score + volume_score + spread_score
        liquidity_score = min(100, max(0, liquidity_score))

        is_liquid = (
            oi >= self.min_open_interest and
            volume_oi_ratio >= self.min_volume_oi_ratio and
            spread_percent <= max_spread_allowed
        )

        metrics = LiquidityMetrics(
            open_interest=float(oi),
            volume=float(volume),
            volume_oi_ratio=float(volume_oi_ratio),
            bid_price=bid_decimal,
            ask_price=ask_decimal,
            bid_ask_spread=spread,
            spread_percent=spread_percent,
            is_liquid=is_liquid,
            liquidity_score=liquidity_score
        )

        logger.info(f"Liquidity validated: OI={oi:,.0f}, Spread={float(spread_percent):.2f}%, Score={liquidity_score}")

        return {
            "valid": True,
            "reason": "Liquidity acceptable",
            "warnings": warnings,
            "metrics": metrics.__dict__
        }

    def _analyze_greeks(
        self,
        greeks: Dict[str, float],
        premium: float,
        quantity: int,
        spot_atr: Optional[float]
    ) -> Dict[str, Any]:
        """
        Analyze option Greeks for position risk

        Args:
            greeks: Dict with delta, theta, gamma, vega
            premium: Current premium
            quantity: Position size
            spot_atr: Spot ATR (optional)

        Returns:
            Dict with Greeks analysis
        """
        warnings = []

        delta = Decimal(str(greeks.get("delta", 0)))
        theta = Decimal(str(greeks.get("theta", 0)))
        gamma = Decimal(str(greeks.get("gamma", 0)))
        vega = Decimal(str(greeks.get("vega", 0)))

        premium_decimal = Decimal(str(premium))
        qty_decimal = Decimal(str(quantity))

        # Position Greeks (scaled by position size)
        # For options, Greeks are typically per contract (100 shares)
        # So we need to scale by (quantity / 100)
        contracts = qty_decimal / Decimal('100')

        position_delta = delta * qty_decimal
        position_theta = theta * contracts
        position_gamma = gamma * qty_decimal
        position_vega = vega * contracts

        # Expected daily PnL range (if spot ATR available)
        if spot_atr:
            spot_atr_decimal = Decimal(str(spot_atr))
            expected_premium_move = delta * spot_atr_decimal
            expected_daily_pnl = expected_premium_move * qty_decimal
        else:
            expected_daily_pnl = Decimal('0')

        # Daily holding cost (theta decay)
        daily_holding_cost = abs(position_theta)

        # Theta risk check
        theta_percent_of_premium = abs(theta) / premium_decimal if premium_decimal > 0 else Decimal('0')
        if theta_percent_of_premium > self.high_theta_threshold:
            warnings.append(
                f"High time decay: {float(abs(theta)):.2f}/day ({float(theta_percent_of_premium)*100:.1f}% of premium)"
            )

        # Gamma check (near ATM options have high gamma)
        if gamma > self.high_gamma_threshold:
            warnings.append(
                f"High gamma ({float(gamma):.4f}) - Delta changes rapidly, consider tighter trailing SL"
            )

        # Vega risk check
        vega_percent_of_premium = vega / premium_decimal if premium_decimal > 0 else Decimal('0')
        if vega_percent_of_premium > self.max_vega_risk_percent:
            warnings.append(
                f"High vega risk: {float(vega):.2f} per 1% IV change ({float(vega_percent_of_premium)*100:.1f}% of premium)"
            )

        position_greeks = PositionGreeks(
            position_delta=position_delta,
            position_theta=position_theta,
            position_gamma=position_gamma,
            position_vega=position_vega,
            expected_daily_pnl_range=expected_daily_pnl if spot_atr else Decimal('0'),
            daily_holding_cost=daily_holding_cost
        )

        metrics = {
            "greeks": {
                "delta": float(delta),
                "theta": float(theta),
                "gamma": float(gamma),
                "vega": float(vega)
            },
            "position_greeks": {
                "position_delta": float(position_delta),
                "position_theta": float(position_theta),
                "position_gamma": float(position_gamma),
                "position_vega": float(position_vega),
                "expected_daily_pnl_range": float(expected_daily_pnl) if spot_atr else None,
                "daily_holding_cost": float(daily_holding_cost)
            },
            "risk_indicators": {
                "theta_percent_of_premium": float(theta_percent_of_premium * Decimal('100')),
                "vega_percent_of_premium": float(vega_percent_of_premium * Decimal('100')),
                "is_high_gamma": gamma > self.high_gamma_threshold
            }
        }

        logger.info(f"Greeks analyzed: Delta={float(delta):.4f}, Theta={float(theta):.2f}, Position Delta={float(position_delta):.2f}")

        return {
            "warnings": warnings,
            "metrics": metrics
        }

    def _calculate_quality_score(
        self,
        iv_check: Dict,
        liquidity_check: Dict,
        greeks_analysis: Dict
    ) -> int:
        """
        Calculate overall option quality score (0-100)

        Args:
            iv_check: IV validation result
            liquidity_check: Liquidity validation result
            greeks_analysis: Greeks analysis result

        Returns:
            Quality score (0-100)
        """
        score = 0

        # IV score (30 points)
        iv_metrics = iv_check.get("metrics", {})
        iv_status = iv_metrics.get("iv_status", "normal")
        if iv_status == "normal":
            score += 30
        elif iv_status == "low":
            score += 20  # Low IV is okay but not ideal
        else:
            score += 10  # High IV is risky

        # Liquidity score (40 points)
        liquidity_metrics = liquidity_check.get("metrics", {})
        liquidity_score = liquidity_metrics.get("liquidity_score", 0)
        score += int(liquidity_score * 0.4)

        # Greeks risk score (30 points)
        greeks_warnings = len(greeks_analysis.get("warnings", []))
        if greeks_warnings == 0:
            score += 30
        elif greeks_warnings == 1:
            score += 20
        elif greeks_warnings == 2:
            score += 10
        else:
            score += 0

        return min(100, max(0, score))

    def calculate_optimal_entry_price(
        self,
        bid: float,
        ask: float
    ) -> Tuple[Decimal, str]:
        """
        Calculate optimal entry price using mid-price strategy

        Args:
            bid: Best bid price
            ask: Best ask price

        Returns:
            Tuple of (optimal_price, strategy)
        """
        bid_decimal = Decimal(str(bid))
        ask_decimal = Decimal(str(ask))

        # Calculate mid price
        mid_price = (bid_decimal + ask_decimal) / Decimal('2')

        # Calculate spread
        spread = ask_decimal - bid_decimal
        spread_percent = (spread / mid_price) * Decimal('100')

        if spread_percent > self.max_spread_percent:
            strategy = f"Wide spread ({float(spread_percent):.2f}%) - Consider avoiding"
        elif spread_percent > Decimal('1.0'):
            strategy = f"Use limit order at mid price Rs.{float(mid_price):.2f} (spread {float(spread_percent):.2f}%)"
        else:
            strategy = f"Good liquidity - Can use market order or limit at Rs.{float(mid_price):.2f}"

        return mid_price, strategy


# Create singleton instance
option_analytics = OptionAnalyticsService()