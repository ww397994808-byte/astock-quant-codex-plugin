from __future__ import annotations

from pathlib import Path


class ReportService:
    def latest_report_dir(self) -> Path:
        from core.run_manager import RunManager

        return RunManager().resolve_run_dir("latest")

