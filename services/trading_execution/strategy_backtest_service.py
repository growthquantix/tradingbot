"""
Backtesting helpers for the trading execution SuperTrend + EMA strategy.

This service evaluates the same strategy engine used in live auto-trading on a
single OHLC candle stream and returns trade-level metrics plus a small parameter
comparison table that can guide tuning decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from itertools import product
from typing import Any, Dict, List, Optional

from services.trading_execution.strategy_engine import SignalType, StrategyEngine, TrailingStopType


@dataclass
class BacktestTradeRecord:
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float
    bars_held: int
    reason: str


class StrategyBacktestService:
    """Evaluate and compare SuperTrend + EMA parameter sets."""

    def _make_engine(self, overrides: Optional[Dict[str, Any]] = None) -> StrategyEngine:
        engine = StrategyEngine()
        for key, value in (overrides or {}).items():
            if hasattr(engine, key):
                setattr(engine, key, value)
        return engine

    def _calc_trade_pnl(self, option_type: str, entry_price: Decimal, exit_price: Decimal) -> Decimal:
        if option_type == "PE":
            return entry_price - exit_price
        return exit_price - entry_price

    def run_backtest(
        self,
        candles: List[Dict[str, Any]],
        option_type: str = "CE",
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        option_type = (option_type or "CE").upper()
        if option_type not in {"CE", "PE"}:
            raise ValueError("option_type must be CE or PE")

        normalized = sorted(
            [
                {
                    "timestamp": candle.get("timestamp") or candle.get("ts") or candle.get("time"),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": float(candle.get("volume", candle.get("vol", 0)) or 0),
                }
                for candle in candles
                if all(key in candle for key in ("open", "high", "low", "close"))
            ],
            key=lambda x: x["timestamp"] or "",
        )

        engine = self._make_engine(config_overrides)
        min_bars = max(engine.ema_period, engine.supertrend_period) + 10
        if len(normalized) < min_bars + 2:
            raise ValueError(f"Need at least {min_bars + 2} candles for backtest")

        trades: List[BacktestTradeRecord] = []
        equity_curve: List[float] = [0.0]
        running_pnl = Decimal("0")
        position: Optional[Dict[str, Any]] = None

        for idx in range(min_bars, len(normalized) - 1):
            current = normalized[idx]
            next_bar = normalized[idx + 1]

            history = {
                "open": [bar["open"] for bar in normalized[: idx + 1]],
                "high": [bar["high"] for bar in normalized[: idx + 1]],
                "low": [bar["low"] for bar in normalized[: idx + 1]],
                "close": [bar["close"] for bar in normalized[: idx + 1]],
                "volume": [bar["volume"] for bar in normalized[: idx + 1]],
            }

            signal = engine.generate_signal(
                current_price=Decimal(str(current["close"])),
                historical_data=history,
                option_type=option_type,
            )

            if position is None:
                if signal.signal_type == SignalType.BUY and signal.confidence >= engine.min_confidence_threshold:
                    position = {
                        "entry_time": next_bar["timestamp"],
                        "entry_price": Decimal(str(next_bar["open"])),
                        "entry_index": idx + 1,
                        "stop_loss": signal.stop_loss,
                        "target_price": signal.target_price,
                    }
                continue

            current_close = Decimal(str(current["close"]))
            current_low = Decimal(str(current["low"]))
            current_high = Decimal(str(current["high"]))
            entry_price = position["entry_price"]

            updated_sl = engine.update_trailing_stop(
                current_price=current_close,
                entry_price=entry_price,
                current_stop_loss=position["stop_loss"],
                trailing_type=TrailingStopType.SUPERTREND_1X,
                supertrend_value=Decimal(str(signal.indicators.get("supertrend_1x", float(position["stop_loss"])))),
                target_price=position["target_price"],
            )
            if isinstance(updated_sl, Decimal):
                position["stop_loss"] = updated_sl

            exit_price: Optional[Decimal] = None
            exit_reason: Optional[str] = None

            if option_type == "CE":
                if current_low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "stop_loss"
                elif current_high >= position["target_price"]:
                    exit_price = position["target_price"]
                    exit_reason = "target"
            else:
                if current_high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "stop_loss"
                elif current_low <= position["target_price"]:
                    exit_price = position["target_price"]
                    exit_reason = "target"

            if exit_price is None and signal.signal_type in {SignalType.EXIT_LONG, SignalType.EXIT_SHORT}:
                exit_price = Decimal(str(next_bar["open"]))
                exit_reason = "signal_exit"

            if exit_price is None and idx == len(normalized) - 2:
                exit_price = Decimal(str(next_bar["close"]))
                exit_reason = "end_of_data"

            if exit_price is None:
                continue

            pnl = self._calc_trade_pnl(option_type, entry_price, exit_price)
            pnl_percent = (pnl / entry_price * Decimal("100")) if entry_price > 0 else Decimal("0")
            running_pnl += pnl
            equity_curve.append(float(running_pnl))

            trades.append(
                BacktestTradeRecord(
                    entry_time=str(position["entry_time"]),
                    exit_time=str(next_bar["timestamp"]),
                    side=option_type,
                    entry_price=float(entry_price),
                    exit_price=float(exit_price),
                    pnl=float(pnl),
                    pnl_percent=float(pnl_percent),
                    bars_held=max(1, (idx + 1) - position["entry_index"]),
                    reason=exit_reason,
                )
            )
            position = None

        return self._build_report(trades, equity_curve, option_type, config_overrides or {})

    def compare_parameter_sets(
        self,
        candles: List[Dict[str, Any]],
        option_type: str = "CE",
    ) -> List[Dict[str, Any]]:
        """Run a compact parameter sweep and rank configurations by expectancy then drawdown."""
        candidates = []
        for ema_period, st_period, st_mult, confidence in product(
            [13, 20, 34],
            [7, 10],
            [2.5, 3.0, 3.5],
            [Decimal("0.55"), Decimal("0.60"), Decimal("0.65")],
        ):
            candidates.append(
                {
                    "ema_period": ema_period,
                    "supertrend_period": st_period,
                    "supertrend_multiplier_1x": st_mult,
                    "min_confidence_threshold": confidence,
                }
            )

        results: List[Dict[str, Any]] = []
        for overrides in candidates:
            try:
                report = self.run_backtest(candles, option_type=option_type, config_overrides=overrides)
                summary = report["summary"]
                results.append(
                    {
                        "params": {
                            **overrides,
                            "min_confidence_threshold": float(overrides["min_confidence_threshold"]),
                        },
                        "total_trades": summary["total_trades"],
                        "win_rate": summary["win_rate"],
                        "profit_factor": summary["profit_factor"],
                        "expectancy": summary["expectancy"],
                        "max_drawdown": summary["max_drawdown"],
                        "net_pnl": summary["net_pnl"],
                    }
                )
            except Exception:
                continue

        ranked = sorted(
            [row for row in results if row["total_trades"] > 0],
            key=lambda row: (row["expectancy"], row["profit_factor"], -row["max_drawdown"]),
            reverse=True,
        )
        return ranked[:10]

    def _build_report(
        self,
        trades: List[BacktestTradeRecord],
        equity_curve: List[float],
        option_type: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        total_trades = len(trades)
        winning = [trade for trade in trades if trade.pnl > 0]
        losing = [trade for trade in trades if trade.pnl < 0]
        gross_profit = sum(trade.pnl for trade in winning)
        gross_loss = abs(sum(trade.pnl for trade in losing))
        net_pnl = sum(trade.pnl for trade in trades)
        avg_win = gross_profit / len(winning) if winning else 0.0
        avg_loss = gross_loss / len(losing) if losing else 0.0
        win_rate = (len(winning) / total_trades * 100) if total_trades else 0.0
        expectancy = ((win_rate / 100.0) * avg_win) - (((100.0 - win_rate) / 100.0) * avg_loss)

        peak = 0.0
        max_drawdown = 0.0
        for equity in equity_curve:
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)

        summary = {
            "option_type": option_type,
            "total_trades": total_trades,
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_pnl": round(net_pnl, 2),
            "profit_factor": round((gross_profit / gross_loss), 4) if gross_loss > 0 else 0.0,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round(expectancy, 4),
            "max_drawdown": round(max_drawdown, 2),
            "avg_bars_held": round(sum(t.bars_held for t in trades) / total_trades, 2) if total_trades else 0.0,
            "config": {
                key: float(value) if isinstance(value, Decimal) else value
                for key, value in config.items()
            },
        }

        return {
            "summary": summary,
            "trades": [asdict(trade) for trade in trades],
            "equity_curve": equity_curve,
        }


strategy_backtest_service = StrategyBacktestService()
