from __future__ import annotations

from core.result import TaskResult
from services.adaptive_intake_service import AdaptiveIntakeService
from tasks.base_task import BaseTask


class AdaptiveIntakeTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return AdaptiveIntakeService().run(idea=kwargs.get("idea"), confirm=kwargs.get("confirm", False))
