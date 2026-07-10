from __future__ import annotations

from core.result import TaskResult
from services.pretrade_service import PreTradeService
from tasks.base_task import BaseTask


class PretradeTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return PreTradeService().run(
            kwargs["strategy"],
            kwargs["symbol"],
            kwargs.get("confirmation", ""),
            run_id=kwargs.get("run_id", "latest"),
            plan_run_id=kwargs.get("plan_run_id"),
            qmt_run_id=kwargs.get("qmt_run_id"),
        )
