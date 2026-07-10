from __future__ import annotations

from core.result import TaskResult
from services.student_safe_loop_service import StudentSafeLoopService
from tasks.base_task import BaseTask


class StudentSafeLoopTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentSafeLoopService().run(
            workflow=kwargs.get("workflow"),
            promotion=kwargs.get("promotion"),
            qmt_dashboard=kwargs.get("qmt_dashboard"),
            max_steps=kwargs.get("max_steps", 3),
            execute=kwargs.get("execute", False),
            timeout_seconds=kwargs.get("timeout_seconds", 180),
            session_id=kwargs.get("session_id"),
        )
