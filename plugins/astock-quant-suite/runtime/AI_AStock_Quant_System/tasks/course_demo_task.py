from __future__ import annotations

from core.result import TaskResult
from services.course_demo_service import CourseDemoService
from tasks.base_task import BaseTask


class CourseDemoTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return CourseDemoService().run()
