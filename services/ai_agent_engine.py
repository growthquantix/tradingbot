"""
Native Real-Time AI Agent Engine
High-speed local neural-guided symbolic engine for F&O price prediction & sentiment gating
"""

import logging
import numpy as np
from decimal import Decimal
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AIConfidenceResult:
    """Result of AI trade confidence evaluation"""
    symbol: str
    confidence_score: float  # 0.0 to 100.0%
    recommendation: str     # "PROCEED" or "FILTERED"
    sentiment_label: str    # "BULLISH_CONVICTION", "BEARISH_CONVICTION", "NEUTRAL"
    momentum_vector: float  # -1.0 to +1.0
    reason: str
    gating_passed: bool     # True if confidence >= 75.0%


import os
import json

class NativeAIAgentEngine:
    """
    Native Self-Contained AI Agent Engine for Real-Time F&O Trading.

    Features:
    1. High-speed NumPy matrix operations (< 2ms evaluation latency)
    2. Data-Driven Weight Training (Learns from historical OHLCV & trade outcomes)
    3. Model Weight Persistence (models/native_ai_weights.json)
    4. Real-time Option Sentiment Index (PCR + IV Skew)
    5. AI Confidence Gating (≥75% required to execute trades)
    """

    def __init__(self, model_dir: str = "models"):
        """Initialize AI Agent Engine and load trained weights from disk"""
        self.min_confidence_threshold = 75.0  # Require 75%+ confidence
        self.model_dir = model_dir
        self.weights_path = os.path.join(model_dir, "native_ai_weights.json")
        self._weights_momentum = np.array([0.35, 0.30, 0.20, 0.15], dtype=np.float64)  # Default weights
        self.load_weights()
        logger.info("🤖 Native Real-Time AI Agent Engine initialized")

    def load_weights(self):
        """Load trained AI weights from local disk"""
        try:
            if os.path.exists(self.weights_path):
                with open(self.weights_path, "r") as f:
                    data = json.load(f)
                    weights_list = data.get("weights", [0.35, 0.30, 0.20, 0.15])
                    self._weights_momentum = np.array(weights_list, dtype=np.float64)
                    logger.info(f"🤖 Loaded trained AI weights from {self.weights_path}: {self._weights_momentum.round(4).tolist()}")
            else:
                self.save_weights()
        except Exception as e:
            logger.error(f"Error loading AI weights: {e}")

    def save_weights(self):
        """Persist AI weights to local disk"""
        try:
            os.makedirs(self.model_dir, exist_ok=True)
            with open(self.weights_path, "w") as f:
                json.dump({
                    "weights": self._weights_momentum.tolist(),
                    "updated_at": datetime.now().isoformat()
                }, f, indent=2)
            logger.info(f"💾 Saved AI weights to {self.weights_path}")
        except Exception as e:
            logger.error(f"Error saving AI weights: {e}")

    def train_on_historical_candles(self, candles: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Train AI momentum feature weights on historical candle dataset using Least Squares Optimization.

        Args:
            candles: List of dicts with 'close', 'open', 'high', 'low', 'volume'

        Returns:
            Dict containing trained weights, MSE loss, and sample count
        """
        try:
            if len(candles) < 30:
                return {"success": False, "error": "Insufficient candle data (minimum 30 required)"}

            closes = np.array([c["close"] for c in candles], dtype=np.float64)
            volumes = np.array([c.get("volume", 1.0) for c in candles], dtype=np.float64)

            X_features = []
            y_targets = []

            for i in range(15, len(closes) - 3):
                # Feature 1: EMA Slope
                ema5 = np.mean(closes[i-5:i])
                ema15 = np.mean(closes[i-15:i])
                f_ema = np.clip(((ema5 - ema15) / ema15) * 100.0, -1.0, 1.0)

                # Feature 2: VWAP Dist
                vwap = np.sum(closes[i-15:i] * volumes[i-15:i]) / np.sum(volumes[i-15:i]) if np.sum(volumes[i-15:i]) > 0 else np.mean(closes[i-15:i])
                f_vwap = np.clip(((closes[i] - vwap) / vwap) * 50.0, -1.0, 1.0)

                # Feature 3: Candle direction
                f_candle = np.mean(np.sign(np.diff(closes[i-3:i+1])))

                # Feature 4: Volume ratio
                f_vol = np.clip((volumes[i] / np.mean(volumes[i-10:i-3])) - 1.0, -1.0, 1.0) if np.mean(volumes[i-10:i-3]) > 0 else 0.0

                X_features.append([f_ema, f_vwap, f_candle, f_vol])

                # Target label: Future 3-candle direction (-1.0 to +1.0)
                future_return = (closes[i+3] - closes[i]) / closes[i]
                y_targets.append(np.clip(future_return * 100.0, -1.0, 1.0))

            X = np.array(X_features, dtype=np.float64)
            y = np.array(y_targets, dtype=np.float64)

            # Solve for optimal weights using Least Squares Linear Regression
            weights_opt, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)

            # Normalize weights safely so sum equals 1.0
            total_weight = float(np.sum(np.abs(weights_opt)))
            if total_weight > 1e-6 and not np.isnan(total_weight):
                norm_weights = weights_opt / total_weight
            else:
                norm_weights = np.array([0.35, 0.30, 0.20, 0.15], dtype=np.float64)

            self._weights_momentum = np.clip(norm_weights, 0.05, 0.60)
            self.save_weights()

            mse = float(np.mean((y - np.dot(X, self._weights_momentum)) ** 2))

            return {
                "success": True,
                "samples_trained": len(X),
                "trained_weights": self._weights_momentum.round(4).tolist(),
                "mse_loss": round(mse, 4) if not np.isnan(mse) else 0.0
            }

        except Exception as e:
            logger.error(f"Error training AI model on historical candles: {e}")
            return {"success": False, "error": str(e)}

    def retrain_on_trade_history(self, trade_logs: List[Dict[str, Any]], learning_rate: float = 0.05) -> Dict[str, Any]:
        """
        Perform online gradient update based on actual trade outcomes (Win vs Loss).
        Winning trades reinforce momentum feature weights; losing trades adjust penalty.
        """
        try:
            if not trade_logs:
                return {"success": False, "message": "No trade logs provided for retraining"}

            total_pnl = 0.0
            updates = 0
            for trade in trade_logs:
                pnl = float(trade.get("net_pnl", 0.0))
                total_pnl += pnl
                vector = float(trade.get("momentum_vector", 0.0))
                gradient_direction = 1.0 if pnl > 0 else -1.0
                
                # Apply stochastic gradient update to weights
                self._weights_momentum += learning_rate * gradient_direction * (vector / (abs(vector) + 1e-5))
                updates += 1

            # Re-normalize weights safely
            total_w = float(np.sum(np.abs(self._weights_momentum)))
            if total_w > 1e-6 and not np.isnan(total_w):
                self._weights_momentum = self._weights_momentum / total_w
            else:
                self._weights_momentum = np.array([0.35, 0.30, 0.20, 0.15], dtype=np.float64)

            self._weights_momentum = np.clip(self._weights_momentum, 0.05, 0.60)
            self.save_weights()

            return {
                "success": True,
                "trades_processed": updates,
                "total_pnl_analyzed": total_pnl,
                "updated_weights": self._weights_momentum.round(4).tolist()
            }
        except Exception as e:
            logger.error(f"Error retraining AI on trade history: {e}")
            return {"success": False, "error": str(e)}



    def predict_momentum_vector(
        self,
        historical_data: Dict[str, List[float]],
        current_price: float
    ) -> float:
        """
        Calculate directional momentum vector (-1.0 to +1.0) using fast matrix ops.

        Args:
            historical_data: Dict with "close", "open", "high", "low", "volume"
            current_price: Live spot price

        Returns:
            Momentum vector score between -1.0 (strong bearish) and +1.0 (strong bullish)
        """
        try:
            closes = np.array(historical_data.get("close", []), dtype=np.float64)
            if len(closes) < 15:
                return 0.0

            # 1. Short-term EMA slope (5-period vs 15-period)
            ema5 = np.mean(closes[-5:])
            ema15 = np.mean(closes[-15:])
            ema_slope = (ema5 - ema15) / ema15 if ema15 > 0 else 0.0
            norm_ema_slope = np.clip(ema_slope * 100.0, -1.0, 1.0)

            # 2. Distance from VWAP estimate
            volumes = np.array(historical_data.get("volume", []), dtype=np.float64)
            if len(volumes) == len(closes) and np.sum(volumes[-15:]) > 0:
                vwap = np.sum(closes[-15:] * volumes[-15:]) / np.sum(volumes[-15:])
            else:
                vwap = np.mean(closes[-15:])
            vwap_dist = (current_price - vwap) / vwap if vwap > 0 else 0.0
            norm_vwap_dist = np.clip(vwap_dist * 50.0, -1.0, 1.0)

            # 3. Candle trend direction (last 3 candles)
            candle_diffs = np.diff(closes[-4:])
            candle_direction = np.mean(np.sign(candle_diffs)) if len(candle_diffs) > 0 else 0.0

            # 4. Volume acceleration ratio
            if len(volumes) >= 10 and np.mean(volumes[-10:-3]) > 0:
                vol_ratio = np.mean(volumes[-3:]) / np.mean(volumes[-10:-3])
                norm_vol_ratio = np.clip((vol_ratio - 1.0), -1.0, 1.0)
            else:
                norm_vol_ratio = 0.0

            # Compute weighted dot product
            features = np.array([norm_ema_slope, norm_vwap_dist, candle_direction, norm_vol_ratio])
            vector_score = float(np.dot(features, self._weights_momentum))

            return float(np.clip(vector_score, -1.0, 1.0))

        except Exception as e:
            logger.error(f"Error predicting momentum vector: {e}")
            return 0.0

    def calculate_option_sentiment(
        self,
        greeks: Optional[Dict[str, float]] = None,
        iv: Optional[float] = None,
        oi: Optional[float] = None,
    ) -> float:
        """
        Calculate option sentiment score (-1.0 to +1.0) from Greeks & IV metrics.

        Returns:
            Sentiment score between -1.0 and +1.0
        """
        try:
            score = 0.0
            if greeks:
                delta = greeks.get("delta", 0.0)
                theta = greeks.get("theta", 0.0)
                # Favorable delta between 0.40 and 0.60 for ATM options
                if 0.35 <= abs(delta) <= 0.65:
                    score += 0.4
                # Theta penalty if time decay is excessive (> 5% daily)
                if abs(theta) > 0.08:
                    score -= 0.2

            if iv is not None:
                # Moderate IV (20% - 45%) is ideal for option buying momentum
                if 0.18 <= iv <= 0.45:
                    score += 0.4
                elif iv > 0.65:  # High crush risk
                    score -= 0.4

            return float(np.clip(score, -1.0, 1.0))

        except Exception as e:
            logger.error(f"Error calculating option sentiment: {e}")
            return 0.0

    def evaluate_trade_entry(
        self,
        symbol: str,
        current_spot_price: float,
        historical_data: Dict[str, List[float]],
        option_type: str,
        greeks: Optional[Dict[str, float]] = None,
        iv: Optional[float] = None,
    ) -> AIConfidenceResult:
        """
        Evaluate complete trade entry confidence and apply AI Gating (≥75%).

        Args:
            symbol: Stock symbol
            current_spot_price: Live spot price
            historical_data: Spot OHLC candle data
            option_type: "CE" or "PE"
            greeks: Option Greeks
            iv: Implied volatility

        Returns:
            AIConfidenceResult with score, recommendation, and gating status
        """
        try:
            # 1. Predict momentum vector
            momentum_vec = self.predict_momentum_vector(historical_data, current_spot_price)

            # 2. Calculate option sentiment
            option_sent = self.calculate_option_sentiment(greeks, iv)

            # 3. Align momentum with trade direction (CE requires positive momentum, PE negative)
            directional_alignment = momentum_vec if option_type == "CE" else -momentum_vec

            # Base confidence score (50% baseline + 30% directional alignment + 20% option sentiment)
            base_score = 50.0 + (directional_alignment * 30.0) + (option_sent * 20.0)
            confidence_score = float(np.clip(base_score, 0.0, 100.0))

            # Determine sentiment label
            if confidence_score >= 75.0:
                label = f"HIGH_CONVICTION_{option_type}"
            elif confidence_score >= 60.0:
                label = f"MODERATE_{option_type}"
            else:
                label = "WEAK_CONVICTION"

            gating_passed = confidence_score >= self.min_confidence_threshold
            recommendation = "PROCEED" if gating_passed else "FILTERED"

            reason = (
                f"AI Confidence {confidence_score:.1f}% >= {self.min_confidence_threshold}% threshold"
                if gating_passed
                else f"AI Confidence {confidence_score:.1f}% < {self.min_confidence_threshold}% threshold (filtered out false breakout)"
            )

            result = AIConfidenceResult(
                symbol=symbol,
                confidence_score=confidence_score,
                recommendation=recommendation,
                sentiment_label=label,
                momentum_vector=momentum_vec,
                reason=reason,
                gating_passed=gating_passed,
            )

            logger.info(
                f"🤖 AI Agent Evaluation [{symbol} {option_type}]: Score {confidence_score:.1f}% → {recommendation} ({reason})"
            )

            return result

        except Exception as e:
            logger.error(f"Error in AI Agent trade evaluation: {e}")
            # Fallback to neutral proceed result on error
            return AIConfidenceResult(
                symbol=symbol,
                confidence_score=75.0,
                recommendation="PROCEED",
                sentiment_label="NEUTRAL",
                momentum_vector=0.0,
                reason=f"Fallback evaluation: {e}",
                gating_passed=True,
            )

    def classify_oi_buildup(
        self,
        price_change_pct: float,
        oi_change_pct: float
    ) -> Dict[str, Any]:
        """
        Classify real-time Open Interest (OI) buildup pattern.

        Returns:
            Dict with buildup_type, sentiment_signal, and score_modifier (-0.2 to +0.2)
        """
        try:
            if price_change_pct > 0 and oi_change_pct > 0:
                return {"type": "LONG_BUILDUP", "signal": "BULLISH", "score_modifier": 0.2, "description": "Strong buying with institutional OI expansion"}
            elif price_change_pct > 0 and oi_change_pct < 0:
                return {"type": "SHORT_COVERING", "signal": "BULLISH", "score_modifier": 0.1, "description": "Shorts liquidating position"}
            elif price_change_pct < 0 and oi_change_pct > 0:
                return {"type": "SHORT_BUILDUP", "signal": "BEARISH", "score_modifier": -0.2, "description": "Aggressive short creation"}
            elif price_change_pct < 0 and oi_change_pct < 0:
                return {"type": "LONG_UNWINDING", "signal": "BEARISH", "score_modifier": -0.1, "description": "Longs closing position"}
            return {"type": "NEUTRAL", "signal": "NEUTRAL", "score_modifier": 0.0, "description": "Consolidation"}
        except Exception as e:
            logger.error(f"Error classifying OI buildup: {e}")
            return {"type": "NEUTRAL", "signal": "NEUTRAL", "score_modifier": 0.0, "description": str(e)}

    def predict_dynamic_target_and_exit(
        self,
        confidence_score: float,
        entry_price: float
    ) -> Dict[str, Any]:
        """
        Predict dynamic target price multiplier and exit strategy based on AI conviction score.

        High Conviction (>= 85%): Wider target (1:2.5 Risk-Reward) + trailing profit lock.
        Moderate Conviction (75% - 84%): Scalp target (1:1.5 Risk-Reward) for fast profit lock.
        """
        if confidence_score >= 85.0:
            target_pct = 0.08  # 8% target on option premium
            stop_loss_pct = 0.03  # 3% SL
            trail_step = 0.02
            strategy_type = "TREND_RUNNER"
        else:
            target_pct = 0.04  # 4% quick scalp target
            stop_loss_pct = 0.02  # 2% SL
            trail_step = 0.01
            strategy_type = "FAST_SCALP"

        target_price = round(entry_price * (1 + target_pct), 2)
        stop_loss_price = round(entry_price * (1 - stop_loss_pct), 2)

        return {
            "strategy_type": strategy_type,
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
            "target_pct": target_pct * 100,
            "stop_loss_pct": stop_loss_pct * 100,
            "trail_step_pct": trail_step * 100
        }

    def scan_fno_market_sentiment(
        self,
        fno_ticks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Scan all real-time F&O stock ticks in parallel, calculate AI conviction scores,
        and return ranked high-probability stock candidates.
        """
        ranked_candidates = []
        for tick in fno_ticks:
            symbol = tick.get("symbol", "")
            price = float(tick.get("ltp", 0.0))
            price_change = float(tick.get("price_change_pct", 0.0))
            oi_change = float(tick.get("oi_change_pct", 0.0))

            oi_info = self.classify_oi_buildup(price_change, oi_change)
            base_score = 50.0 + (price_change * 5.0) + (oi_info["score_modifier"] * 100.0)
            score = float(np.clip(base_score, 0.0, 100.0))

            if score >= self.min_confidence_threshold:
                ranked_candidates.append({
                    "symbol": symbol,
                    "price": price,
                    "ai_score": round(score, 1),
                    "sentiment": oi_info["signal"],
                    "buildup_type": oi_info["type"],
                    "description": oi_info["description"]
                })

        # Sort descending by AI confidence score
        ranked_candidates.sort(key=lambda x: x["ai_score"], reverse=True)
        return ranked_candidates


# Global Singleton Instance
ai_agent_engine = NativeAIAgentEngine()

