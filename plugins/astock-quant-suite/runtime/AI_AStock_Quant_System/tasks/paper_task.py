from __future__ import annotations

import json

from core.result import TaskResult
from services.paper_service import PaperService
from tasks.base_task import BaseTask


class PaperTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        params = json.loads(kwargs.get("strategy_params") or "{}")
        return PaperService().run(
            kwargs["strategy"],
            kwargs["symbol"],
            kwargs["data"],
            params=params,
            timeframe=kwargs.get("timeframe", "1d"),
            adjust=kwargs.get("adjust", "raw"),
            plan_run_id=kwargs.get("plan_run_id"),
        )
