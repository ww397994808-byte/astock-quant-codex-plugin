from __future__ import annotations

from pathlib import Path

from audit.future_leak_checker import FutureLeakChecker
from core.result import TaskResult
from core.run_manager import RunManager


class AuditService:
    def run(self, run_id: str) -> TaskResult:
        output_dir = RunManager().resolve_run_dir(run_id)
        report = FutureLeakChecker().check(output_dir=output_dir)
        audit_path = output_dir / "audit_report.md"
        status = "INVALID" if report["status"] == "INVALID" or "INVALID" in audit_path.read_text(encoding="utf-8")[:200] else "VALID"
        return TaskResult(status=status, message=f"审计完成：{status}", run_id=output_dir.name, report_path=str(output_dir), audit_status=status)

