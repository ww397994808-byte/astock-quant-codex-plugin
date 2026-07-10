from __future__ import annotations

from pathlib import Path


def write_acquisition_report(path: str | Path, record: dict) -> None:
    lines = ["# Data Acquisition Report", ""]
    lines.extend([f"- {k}: {v}" for k, v in record.items()])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

