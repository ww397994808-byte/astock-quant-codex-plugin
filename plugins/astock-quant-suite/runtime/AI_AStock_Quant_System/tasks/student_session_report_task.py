from __future__ import annotations

from core.result import TaskResult
from services.student_session_report_service import StudentSessionReportService
from tasks.base_task import BaseTask


class StudentSessionReportTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentSessionReportService().run(
            ledger=kwargs.get("ledger", "reports/student_session_ledger.jsonl"),
            limit=kwargs.get("limit", 20),
            session_id=kwargs.get("session_id"),
        )
