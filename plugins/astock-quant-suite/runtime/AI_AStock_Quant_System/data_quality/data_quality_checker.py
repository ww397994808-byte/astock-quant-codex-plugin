from __future__ import annotations

from pathlib import Path

from data_quality.anomaly_detector import AnomalyDetector
from data_quality.corporate_action_checker import CorporateActionChecker
from data_quality.data_profile import profile_data
from data_quality.data_quality_report import write_data_quality_report, write_jump_csv
from data_quality.trading_calendar_checker import TradingCalendarChecker
from market_data.intraday_calendar import IntradayCalendar
from market_data.trading_session import TradingSession


class DataQualityChecker:
    def check(self, rows: list[dict], output_dir: str | Path | None = None) -> dict:
        findings = []
        for prev, curr in zip(rows, rows[1:]):
            if curr["date"] <= prev["date"]:
                findings.append({"severity": "HIGH", "message": "日期逆序或重复"})
        seen = set()
        for row in rows:
            dt = row["date"]
            if dt in seen:
                findings.append({"severity": "HIGH", "message": f"日期重复：{dt.strftime('%Y-%m-%d')}"})
            seen.add(dt)
            for col in ["open", "high", "low", "close"]:
                if float(row[col]) <= 0:
                    findings.append({"severity": "HIGH", "message": f"{dt.strftime('%Y-%m-%d')} {col} <= 0"})
            if float(row["high"]) < float(row["low"]):
                findings.append({"severity": "HIGH", "message": f"{dt.strftime('%Y-%m-%d')} high < low"})
            if float(row["open"]) > float(row["high"]) or float(row["open"]) < float(row["low"]):
                findings.append({"severity": "HIGH", "message": f"{dt.strftime('%Y-%m-%d')} open 不在 high/low 区间"})
            if float(row["close"]) > float(row["high"]) or float(row["close"]) < float(row["low"]):
                findings.append({"severity": "HIGH", "message": f"{dt.strftime('%Y-%m-%d')} close 不在 high/low 区间"})
            if int(row["volume"]) < 0:
                findings.append({"severity": "HIGH", "message": f"{dt.strftime('%Y-%m-%d')} volume < 0"})
            if float(row["amount"]) < 0:
                findings.append({"severity": "HIGH", "message": f"{dt.strftime('%Y-%m-%d')} amount < 0"})
        for prev, curr in zip(rows, rows[1:]):
            if int(curr["volume"]) == 0 and any(float(curr[c]) != float(prev[c]) for c in ["open", "high", "low", "close"]):
                findings.append({"severity": "MEDIUM", "message": f"{curr['date'].strftime('%Y-%m-%d')} volume=0 但价格变化"})

        jumps = AnomalyDetector().suspicious_price_jumps(rows)
        findings.extend([{"severity": "MEDIUM", "message": f"单日涨跌幅超过30%：{j['date']} {j['pct_change']}"} for j in jumps])
        findings.extend(self._check_intraday(rows))
        calendar = TradingCalendarChecker().check(rows)
        findings.extend(calendar["findings"])
        status = "INVALID" if any(f["severity"] == "HIGH" for f in findings) else "VALID"
        report = {"status": status, "profile": profile_data(rows), "findings": findings, "jumps": jumps, "calendar": calendar}
        if output_dir:
            output_dir = Path(output_dir)
            write_jump_csv(output_dir / "suspicious_price_jumps.csv", jumps)
            write_data_quality_report(output_dir / "data_quality_report.md", report["profile"], findings, status)
            TradingCalendarChecker().write_report(output_dir / "calendar_quality_report.md", calendar)
            CorporateActionChecker().write_report(output_dir / "corporate_action_report.md", CorporateActionChecker().check(rows))
        return report

    def _check_intraday(self, rows: list[dict]) -> list[dict]:
        findings = []
        intraday = [r for r in rows if r.get("timeframe", "1d") not in {"1d", "1w"}]
        if not intraday:
            return findings
        session = TradingSession()
        seen = set()
        by_day: dict[tuple, list[dict]] = {}
        for row in intraday:
            dt = row["datetime"]
            key = (row["symbol"], dt)
            if key in seen:
                findings.append({"severity": "HIGH", "message": f"重复 datetime：{dt}"})
            seen.add(key)
            ok, reason = session.validate_bar(row)
            if not ok:
                findings.append({"severity": "HIGH", "message": f"非交易时间或午休 bar：{dt} {reason}"})
            by_day.setdefault((row["symbol"], dt.date(), row.get("timeframe", "1d")), []).append(row)
        for (symbol, day, timeframe), items in by_day.items():
            expected = IntradayCalendar().expected_bar_count(timeframe)
            if len(items) != expected:
                findings.append({"severity": "MEDIUM", "message": f"{symbol} {day} {timeframe} 一天 bar 数量异常：{len(items)} != {expected}"})
            morning = [r for r in items if r["datetime"].hour < 12]
            afternoon = [r for r in items if r["datetime"].hour >= 13]
            if not morning:
                findings.append({"severity": "MEDIUM", "message": f"{symbol} {day} 上午缺失"})
            if not afternoon:
                findings.append({"severity": "MEDIUM", "message": f"{symbol} {day} 下午缺失"})
        return findings
