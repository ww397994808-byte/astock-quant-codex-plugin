from __future__ import annotations

from core.result import TaskResult
from services.intake_service import IntakeService
from tasks.base_task import BaseTask


class IntakeTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return IntakeService().run(kwargs.get("idea"), kwargs.get("interactive", False))

