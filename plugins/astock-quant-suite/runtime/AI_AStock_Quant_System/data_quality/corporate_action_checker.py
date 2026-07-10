from __future__ import annotations

from pathlib import Path


class CorporateActionChecker:
    def check(self, rows: list[dict]) -> dict:
        findings = []
        for prev, curr in zip(rows, rows[1:]):
            prev_close = float(prev["close"])
            if prev_close <= 0:
                continue
            gap = float(curr["open"]) / prev_close - 1
            close_jump = float(curr["close"]) / prev_close - 1
            if abs(gap) > 0.18 and abs(close_jump) > 0.18:
                findings.append({
                    "severity": "MEDIUM",
                    "message": f"{curr['date'].strftime('%Y-%m-%d')} 出现大幅除权/复权式跳空，可能未复权或复权方式变化",
                })
        status = "WARNING" if findings else "VALID"
        return {"status": status, "findings": findings, "inference": "仅基于价格跳空推断，需要结合分红送转数据确认。"}

    def write_report(self, path: str | Path, report: dict) -> None:
        lines = ["# Corporate Action Report", "", f"status: {report['status']}", f"inference: {report['inference']}", ""]
        lines.extend([f"- [{f['severity']}] {f['message']}" for f in report["findings"]] or ["- 未发现明显除权/复权异常。"])
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

