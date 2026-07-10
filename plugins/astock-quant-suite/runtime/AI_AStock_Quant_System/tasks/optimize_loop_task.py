from __future__ import annotations

from core.result import TaskResult
from services.optimize_loop_service import OptimizeLoopService
from tasks.base_task import BaseTask


class OptimizeLoopTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return OptimizeLoopService().run(
            idea=kwargs["idea"],
            symbol=kwargs["symbol"],
            timeframe=kwargs.get("timeframe", "1d"),
            adjust=kwargs.get("adjust", "raw"),
            max_iterations=kwargs.get("max_iterations"),
        )
