from __future__ import annotations

from pathlib import Path


class RunHistory:
    def __init__(self, reports_dir: str | Path = "reports") -> None:
        self.reports_dir = Path(reports_dir)

    def list_runs(self) -> list[str]:
        return sorted([p.name for p in self.reports_dir.glob("*") if p.is_dir()])

