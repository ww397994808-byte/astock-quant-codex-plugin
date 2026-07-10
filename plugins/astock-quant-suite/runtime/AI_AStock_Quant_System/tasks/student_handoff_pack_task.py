from __future__ import annotations

from core.result import TaskResult
from services.student_handoff_pack_service import StudentHandoffPackService
from tasks.base_task import BaseTask


class StudentHandoffPackTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentHandoffPackService().run(
            workflow=kwargs.get("workflow"),
            session_id=kwargs.get("session_id"),
            include_product_audit=not kwargs.get("no_product_audit", False),
            include_session_report=not kwargs.get("no_session_report", False),
        )
