from __future__ import annotations

from core.result import TaskResult
from services.pretrade_package_service import PretradePackageService
from tasks.base_task import BaseTask


class PretradePackageTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return PretradePackageService().run(
            promotion=kwargs["promotion"],
            symbol=kwargs.get("symbol"),
            strategy=kwargs.get("strategy", "compiled_repair_dsl"),
            qmt_run_id=kwargs.get("qmt_run_id"),
            confirmation=kwargs.get("confirmation", ""),
        )
