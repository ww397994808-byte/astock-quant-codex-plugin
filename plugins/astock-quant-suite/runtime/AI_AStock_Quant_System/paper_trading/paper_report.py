from __future__ import annotations

from pathlib import Path


def write_paper_report(path: str | Path, message: str) -> None:
    Path(path).write_text(f"# Paper Trading Report\n\n{message}\n", encoding="utf-8")
