from __future__ import annotations

from datetime import timedelta
from pathlib import Path


class TradingCalendarChecker:
    def check(self, rows: list[dict]) -> dict:
        findings = []
        seen = set()
        prev = None
        for row in rows:
            dt = row["date"]
            if dt in seen:
                findings.append({"severity": "HIGH", "message": f"重复交易日：{dt.strftime('%Y-%m-%d')}"})
            seen.add(dt)
            if dt.weekday() >= 5:
                findings.append({"severity": "MEDIUM", "message": f"周末出现数据：{dt.strftime('%Y-%m-%d')}"})
            if prev and dt <= prev:
                findings.append({"severity": "HIGH", "message": f"日期逆序或重复：{dt.strftime('%Y-%m-%d')}"})
            if prev:
                day = prev + timedelta(days=1)
                missing_weekdays = 0
                while day < dt:
                    if day.weekday() < 5:
                        missing_weekdays += 1
                    day += timedelta(days=1)
                if missing_weekdays >= 5:
                    findings.append({"severity": "MEDIUM", "message": f"疑似缺交易日：{prev.strftime('%Y-%m-%d')} 到 {dt.strftime('%Y-%m-%d')} 间隔过长"})
            prev = dt
        return {"status": "INVALID" if any(f["severity"] == "HIGH" for f in findings) else "VALID", "findings": findings}

    def write_report(self, path: str | Path, report: dict) -> None:
        lines = ["# Calendar Quality Report", "", f"status: {report['status']}", ""]
        lines.extend([f"- [{f['severity']}] {f['message']}" for f in report["findings"]] or ["- 未发现严重交易日历问题。"])
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

