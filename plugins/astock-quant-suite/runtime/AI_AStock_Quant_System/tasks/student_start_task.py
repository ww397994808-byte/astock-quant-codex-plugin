from __future__ import annotations

from core.result import TaskResult
from services.student_start_service import StudentStartService
from tasks.base_task import BaseTask


class StudentStartTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentStartService().run(
            workflow=kwargs.get("workflow"),
            promotion=kwargs.get("promotion"),
            qmt_dashboard=kwargs.get("qmt_dashboard"),
            session_id=kwargs.get("session_id"),
            include_session_index=not kwargs.get("no_session_index", False),
            preview_next=not kwargs.get("no_preview", False),
        )
