from __future__ import annotations

from core.result import TaskResult
from services.pretrade_runbook_refresh_service import PretradeRunbookRefreshService
from tasks.base_task import BaseTask


class PretradeRunbookRefreshTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return PretradeRunbookRefreshService().run(
            package=kwargs["package"],
            qmt_run_id=kwargs.get("qmt_run_id"),
            confirmation=kwargs.get("confirmation", ""),
            strategy=kwargs.get("strategy"),
            symbol=kwargs.get("symbol"),
        )
