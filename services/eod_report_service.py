"""
Automated EOD Performance Reporting Service
Generates end-of-day summary reports for F&O trading sessions and dispatches via Telegram.
"""

import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import AutoTradeExecution
from services.notifications.telegram_service import TelegramNotificationService
from utils.timezone_utils import get_ist_now_naive

logger = logging.getLogger("eod_report_service")


class EODReportService:
    """
    Generates and dispatches daily End-Of-Day performance reports.
    """

    def __init__(self):
        self.telegram = TelegramNotificationService()

    def generate_eod_report(
        self,
        db: Session,
        user_id: int,
        target_date: Optional[date] = None,
        trading_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate EOD Performance summary for a given user and date.
        """
        report_date = target_date or get_ist_now_naive().date()

        query = db.query(AutoTradeExecution).filter(
            AutoTradeExecution.user_id == user_id,
            func.date(AutoTradeExecution.entry_time) == report_date
        )

        if trading_mode:
            query = query.filter(AutoTradeExecution.trading_mode == trading_mode)

        trades = query.all()

        total_trades = len(trades)
        closed_trades = [t for t in trades if t.status == "CLOSED"]
        failed_trades = [t for t in trades if t.status == "FAILED"]
        winning_trades = [t for t in closed_trades if (t.net_pnl or 0) > 0]
        losing_trades = [t for t in closed_trades if (t.net_pnl or 0) <= 0]

        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / len(closed_trades) * 100) if closed_trades else 0.0

        total_gross_pnl = sum((t.gross_pnl or 0) for t in closed_trades)
        total_net_pnl = sum((t.net_pnl or 0) for t in closed_trades)
        total_charges = total_gross_pnl - total_net_pnl

        # Symbol level breakdown
        symbol_summary: Dict[str, Dict[str, Any]] = {}
        for t in closed_trades:
            sym = t.symbol
            if sym not in symbol_summary:
                symbol_summary[sym] = {"trades": 0, "pnl": Decimal("0.0"), "wins": 0}
            symbol_summary[sym]["trades"] += 1
            symbol_summary[sym]["pnl"] += Decimal(str(t.net_pnl or 0))
            if (t.net_pnl or 0) > 0:
                symbol_summary[sym]["wins"] += 1

        best_symbol = max(symbol_summary.items(), key=lambda x: x[1]["pnl"])[0] if symbol_summary else "N/A"
        worst_symbol = min(symbol_summary.items(), key=lambda x: x[1]["pnl"])[0] if symbol_summary else "N/A"

        report_data = {
            "date": report_date.strftime("%Y-%m-%d"),
            "trading_mode": trading_mode or "ALL",
            "total_trades": total_trades,
            "closed_trades": len(closed_trades),
            "failed_trades": len(failed_trades),
            "wins": win_count,
            "losses": loss_count,
            "win_rate_percent": round(win_rate, 2),
            "gross_pnl": float(total_gross_pnl),
            "net_pnl": float(total_net_pnl),
            "total_charges": float(total_charges),
            "best_symbol": best_symbol,
            "worst_symbol": worst_symbol,
            "symbol_summary": {
                k: {"trades": v["trades"], "pnl": float(v["pnl"]), "wins": v["wins"]}
                for k, v in symbol_summary.items()
            }
        }

        return report_data

    def format_telegram_message(self, report: Dict[str, Any]) -> str:
        """
        Format EOD report data into HTML mode string for Telegram dispatch.
        """
        net_pnl = report["net_pnl"]
        pnl_emoji = "🟩" if net_pnl >= 0 else "🟥"
        mode_label = report["trading_mode"].upper()

        msg = (
            f"<b>📊 END OF DAY PERFORMANCE REPORT</b>\n"
            f"<b>📅 Date:</b> {report['date']} | <b>Mode:</b> {mode_label}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{pnl_emoji} Net Realized PnL:</b> ₹{net_pnl:,.2f}\n"
            f"<b>📈 Gross PnL:</b> ₹{report['gross_pnl']:,.2f}\n"
            f"<b>💸 Est. Charges & Tax:</b> ₹{report['total_charges']:,.2f}\n\n"
            f"<b>🎯 Execution Stats:</b>\n"
            f" • Total Trades: <b>{report['total_trades']}</b>\n"
            f" • Win / Loss: <b>{report['wins']} W / {report['losses']} L</b>\n"
            f" • Win Rate: <b>{report['win_rate_percent']}%</b>\n"
            f" • Best Symbol: <b>{report['best_symbol']}</b>\n"
            f" • Worst Symbol: <b>{report['worst_symbol']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>🤖 Automated HFT Execution Engine</i>"
        )
        return msg

    async def send_eod_telegram_report(
        self,
        db: Session,
        user_id: int,
        target_date: Optional[date] = None,
        trading_mode: Optional[str] = None
    ) -> bool:
        """
        Generate and send the EOD report to Telegram.
        """
        try:
            report = self.generate_eod_report(db, user_id, target_date, trading_mode)
            msg = self.format_telegram_message(report)
            sent = await self.telegram.send_message(msg)
            if sent:
                logger.info(f"✅ EOD Telegram report dispatched for user {user_id}")
            else:
                logger.warning(f"⚠️ Telegram bot token missing or failed to send EOD report")
            return sent
        except Exception as e:
            logger.error(f"❌ Error sending EOD Telegram report: {e}")
            return False


eod_report_service = EODReportService()
