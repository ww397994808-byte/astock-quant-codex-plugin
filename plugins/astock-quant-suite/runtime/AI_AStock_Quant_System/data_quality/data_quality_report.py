from __future__ import annotations

import csv
from pathlib import Path


def write_jump_csv(path: str | Path, jumps: list[dict]) -> None:
    fieldnames = ["date", "symbol", "prev_close", "close", "pct_change", "consecutive_jump_count"]
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jumps)


def write_data_quality_report(path: str | Path, profile: dict, findings: list[dict], status: str) -> None:
    lines = ["# Data Quality Report", "", f"status: {status}", "", "## Profile"]
    lines.extend([f"- {k}: {v}" for k, v in profile.items()])
    lines.extend(["", "## Findings"])
    lines.extend([f"- [{f['severity']}] {f['message']}" for f in findings] or ["- 未发现严重数据质量问题。"])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

