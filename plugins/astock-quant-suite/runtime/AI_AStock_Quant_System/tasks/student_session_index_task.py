from __future__ import annotations

from core.result import TaskResult
from services.student_session_index_service import StudentSessionIndexService
from tasks.base_task import BaseTask


class StudentSessionIndexTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentSessionIndexService().run(limit=kwargs.get("limit", 50))
