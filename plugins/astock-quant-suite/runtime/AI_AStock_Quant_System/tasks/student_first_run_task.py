from __future__ import annotations

from core.result import TaskResult
from services.student_first_run_service import StudentFirstRunService
from tasks.base_task import BaseTask


class StudentFirstRunTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentFirstRunService().run(
            idea=kwargs.get("idea"),
            timeframe=kwargs.get("timeframe"),
            adjust=kwargs.get("adjust", "point_in_time_qfq"),
            session_id=kwargs.get("session_id"),
            case_id=kwargs.get("case_id"),
            execute=bool(kwargs.get("execute", False)),
            timeout_seconds=int(kwargs.get("timeout_seconds") or 300),
        )
