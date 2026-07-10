from __future__ import annotations

from core.result import TaskResult
from services.student_future_leak_precheck_service import StudentFutureLeakPrecheckService
from tasks.base_task import BaseTask


class StudentFutureLeakPrecheckTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentFutureLeakPrecheckService().run(
            code=kwargs.get("code"),
            file=kwargs.get("file"),
            strategy_name=kwargs.get("strategy_name"),
            session_id=kwargs.get("session_id"),
        )
