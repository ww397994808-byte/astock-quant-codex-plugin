from __future__ import annotations

from core.result import TaskResult
from services.student_next_step_runner_service import StudentNextStepRunnerService
from tasks.base_task import BaseTask


class StudentNextStepRunnerTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentNextStepRunnerService().run(
            workflow=kwargs.get("workflow"),
            promotion=kwargs.get("promotion"),
            qmt_dashboard=kwargs.get("qmt_dashboard"),
            dry_run=kwargs.get("dry_run", False),
            timeout_seconds=kwargs.get("timeout_seconds", 180),
            session_id=kwargs.get("session_id"),
        )
