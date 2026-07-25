"""
Multi-Factor XGBoost / Quant Ranking Engine for 180+ F&O Stocks & Indices
Ranks all F&O stock candidates based on 4 quantitative factors.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class MultiFactorQuantRanker:
    """
    Multi-Factor Quantitative Ranking Engine for F&O Stocks & Indices.
    Ranks candidates across Momentum, Volume Surge, OI Accumulation, and IV Skew.
    """

    def __init__(self):
        # Default factor weights: Momentum (30%), Volume (25%), OI (25%), IV Skew (20%)
        self.factor_weights = np.array([0.30, 0.25, 0.25, 0.20], dtype=np.float64)

    def rank_fno_candidates(self, market_snapshot: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank all F&O stocks in market_snapshot using multi-factor quantitative scores.

        Args:
            market_snapshot: List of stock dicts containing 'symbol', 'momentum', 'volume_ratio', 'oi_change', 'iv_skew'

        Returns:
            Ranked list of stock dicts sorted by 'composite_quant_score' descending.
        """
        try:
            if not market_snapshot:
                return []

            ranked_results = []
            for stock in market_snapshot:
                # Factor 1: Normalized Momentum (-1.0 to +1.0)
                f_momentum = np.clip(float(stock.get("momentum", 0.0)), -1.0, 1.0)

                # Factor 2: Volume Surge Ratio (0.0 to +2.0)
                vol_ratio = float(stock.get("volume_ratio", 1.0))
                f_volume = np.clip((vol_ratio - 1.0), -1.0, 1.0)

                # Factor 3: Open Interest Change % (-1.0 to +1.0)
                oi_change = float(stock.get("oi_change", 0.0))
                f_oi = np.clip(oi_change / 10.0, -1.0, 1.0)

                # Factor 4: IV Skew (-1.0 to +1.0)
                iv_skew = float(stock.get("iv_skew", 0.0))
                f_iv = np.clip(iv_skew / 20.0, -1.0, 1.0)

                # Vectorized factor inner product
                factors = np.array([f_momentum, f_volume, f_oi, f_iv], dtype=np.float64)
                raw_score = float(np.dot(factors, self.factor_weights))

                # Normalize composite quant score to 0 - 100%
                composite_score = round(float(np.clip((raw_score + 1.0) / 2.0 * 100.0, 0.0, 100.0)), 2)

                # Determine recommended Option Direction
                option_type = "CE" if f_momentum >= 0 else "PE"
                conviction = "HIGH" if composite_score >= 75.0 else ("MEDIUM" if composite_score >= 60.0 else "LOW")

                ranked_results.append({
                    "symbol": stock.get("symbol", "N/A"),
                    "composite_quant_score": composite_score,
                    "option_type": option_type,
                    "conviction": conviction,
                    "factors": {
                        "momentum": round(f_momentum, 3),
                        "volume_surge": round(f_volume, 3),
                        "oi_buildup": round(f_oi, 3),
                        "iv_skew": round(f_iv, 3)
                    },
                    "original_data": stock
                })

            # Sort descending by composite quant score
            ranked_results.sort(key=lambda x: x["composite_quant_score"], reverse=True)
            logger.info(f"📊 Quant Ranker evaluated {len(ranked_results)} F&O stocks. Top candidate: {ranked_results[0]['symbol']} ({ranked_results[0]['composite_quant_score']}%)")

            return ranked_results

        except Exception as e:
            logger.error(f"Quant ranking failed: {e}")
            return market_snapshot
