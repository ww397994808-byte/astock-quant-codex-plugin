from __future__ import annotations

from core.result import TaskResult
from services.optimize_service import OptimizeService
from tasks.base_task import BaseTask


class OptimizeTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return OptimizeService().run(kwargs["strategy"], kwargs["symbol"], kwargs["data"])

