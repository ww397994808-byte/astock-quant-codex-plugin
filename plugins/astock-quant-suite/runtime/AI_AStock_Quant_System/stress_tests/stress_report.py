from __future__ import annotations

from pathlib import Path


def write_stress_report(path: str | Path, results: list[dict]) -> None:
    lines = ["# Stress Report", ""]
    for row in results:
        lines.append(f"- {row['scenario']}: status={row['status']}, notes={row.get('notes', '')}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

