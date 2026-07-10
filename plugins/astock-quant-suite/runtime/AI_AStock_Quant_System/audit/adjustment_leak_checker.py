from __future__ import annotations

from pathlib import Path


class AdjustmentLeakChecker:
    def check(self, rows: list[dict] | None = None, source_paths: list[Path] | None = None) -> dict:
        findings = []
        for row in rows or []:
            adjust_type = row.get("adjust_type", "raw")
            if adjust_type in {"qfq", "hfq"}:
                findings.append({"severity": "HIGH", "message": f"普通 {adjust_type} 可能使用未来 corporate action，FUTURE_LEAK_RISK"})
            if row.get("FUTURE_LEAK_RISK"):
                findings.append({"severity": "HIGH", "message": "检测到 FUTURE_LEAK_RISK 标记"})
        for path in source_paths or []:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                for pattern in ["qfq", "hfq", "all_history_qfq", "future_adjust_factor"]:
                    if pattern in text:
                        findings.append({"severity": "HIGH", "message": f"源码中疑似一次性加载未来复权：{pattern}", "path": str(path)})
        return {"status": "INVALID" if any(f["severity"] == "HIGH" for f in findings) else "VALID", "findings": findings}

