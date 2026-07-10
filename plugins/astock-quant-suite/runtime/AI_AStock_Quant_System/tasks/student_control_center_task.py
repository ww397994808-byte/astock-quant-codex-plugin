from __future__ import annotations

from core.result import TaskResult
from services.student_control_center_service import StudentControlCenterService
from tasks.base_task import BaseTask


class StudentControlCenterTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentControlCenterService().run(
            workflow=kwargs.get("workflow"),
            promotion=kwargs.get("promotion"),
            qmt_dashboard=kwargs.get("qmt_dashboard"),
            session_id=kwargs.get("session_id"),
        )
