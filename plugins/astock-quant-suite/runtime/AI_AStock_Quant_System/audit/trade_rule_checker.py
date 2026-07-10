from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from core.market_rules import MarketRules


class TradeRuleChecker:
    def __init__(self, market_rules: MarketRules | None = None) -> None:
        self.market_rules = market_rules or MarketRules()

    def check(self, output_dir: str | Path, market_rows: list[dict] | None = None) -> dict:
        output_dir = Path(output_dir)
        findings: list[dict] = []
        rows_by_date = {r["date"].strftime("%Y-%m-%d"): r for r in (market_rows or [])}
        prev_close_by_date = {}
        for i, row in enumerate(market_rows or []):
            if i > 0:
                prev_close_by_date[row["date"].strftime("%Y-%m-%d")] = float((market_rows or [])[i - 1]["close"])
        trades = self._read_csv(output_dir / "trades.csv")
        orders = self._read_csv(output_dir / "orders.csv")
        positions = self._read_csv(output_dir / "positions.csv")

        for order in orders:
            signal_time = order.get("signal_datetime") or order.get("signal_time")
            execute_time = order.get("execute_datetime") or order.get("execute_time")
            if signal_time >= execute_time:
                findings.append({"severity": "HIGH", "message": "成交时间早于或等于信号时间"})
            if self._same_bar(signal_time, execute_time, order.get("timeframe", "1d")):
                findings.append({"severity": "HIGH", "message": f"信号与成交发生在同一根 {order.get('timeframe', '1d')} K 线，疑似同 K 线成交"})
            if order.get("action") == "BUY" and int(float(order.get("quantity") or 0)) % self.market_rules.lot_size != 0:
                findings.append({"severity": "HIGH", "message": "买入数量不是 100 股整数倍"})

        buy_dates: dict[str, int] = {}
        for trade in trades:
            date = trade.get("execute_time")
            action = trade.get("action")
            qty = int(float(trade.get("quantity") or 0))
            if action == "BUY":
                buy_dates[date] = buy_dates.get(date, 0) + qty
            if action == "SELL" and buy_dates.get(date, 0) > 0:
                findings.append({"severity": "HIGH", "message": "发现当日买入当日卖出，违反 T+1"})
            if float(trade.get("total_fee") or 0) <= 0:
                findings.append({"severity": "HIGH", "message": "手续费为 0"})
            market_row = rows_by_date.get(date)
            if market_row:
                if market_row.get("paused") or int(market_row.get("volume", 0)) <= 0:
                    findings.append({"severity": "HIGH", "message": "停牌或无量日期发生成交"})
                prev_close = prev_close_by_date.get(date)
                if prev_close:
                    price = float(trade["price"])
                    if action == "BUY" and self.market_rules.is_limit_up(prev_close, market_row, price):
                        findings.append({"severity": "HIGH", "message": "涨停价买入"})
                    if action == "SELL" and self.market_rules.is_limit_down(prev_close, market_row, price):
                        findings.append({"severity": "HIGH", "message": "跌停价卖出"})

        for pos in positions:
            if float(pos.get("cash") or 0) < -1e-6:
                findings.append({"severity": "HIGH", "message": "现金为负"})
            if int(float(pos.get("total_position") or 0)) < 0 or int(float(pos.get("available_position") or 0)) < 0:
                findings.append({"severity": "HIGH", "message": "持仓为负"})

        status = "INVALID" if any(f["severity"] == "HIGH" for f in findings) else "VALID"
        report = {"status": status, "findings": findings}
        self._write_report(output_dir / "trade_rule_report.md", report)
        return report

    def _read_csv(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _same_bar(self, signal_time: str, execute_time: str, timeframe: str) -> bool:
        signal_dt = self._parse_dt(signal_time)
        execute_dt = self._parse_dt(execute_time)
        if signal_dt is None or execute_dt is None:
            return False
        tf = str(timeframe or "1d").lower()
        if tf.endswith("w"):
            return signal_dt.isocalendar()[:2] == execute_dt.isocalendar()[:2]
        if tf.endswith("d"):
            return signal_dt.date() == execute_dt.date()
        if tf.endswith("h"):
            hours = self._timeframe_number(tf, "h")
            return signal_dt.date() == execute_dt.date() and signal_dt.hour // hours == execute_dt.hour // hours
        if tf.endswith("m"):
            minutes = self._timeframe_number(tf, "m")
            signal_bucket = signal_dt.hour * 60 + signal_dt.minute
            execute_bucket = execute_dt.hour * 60 + execute_dt.minute
            return signal_dt.date() == execute_dt.date() and signal_bucket // minutes == execute_bucket // minutes
        return signal_dt == execute_dt

    def _parse_dt(self, value: str) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _timeframe_number(self, timeframe: str, suffix: str) -> int:
        raw = timeframe.removesuffix(suffix)
        try:
            return max(1, int(raw or 1))
        except ValueError:
            return 1

    def _write_report(self, path: Path, report: dict) -> None:
        lines = ["# Trade Rule Report", "", f"status: {report['status']}", ""]
        for item in report["findings"]:
            lines.append(f"- [{item['severity']}] {item['message']}")
        if not report["findings"]:
            lines.append("- 未发现严重 A股交易规则违规。")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
