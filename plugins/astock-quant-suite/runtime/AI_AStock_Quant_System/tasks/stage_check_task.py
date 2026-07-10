from __future__ import annotations

from core.result import TaskResult
from services.stage_check_service import StageCheckService
from tasks.base_task import BaseTask


class StageCheckTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StageCheckService().run(
            run_id=kwargs.get("run_id") or "latest",
            plan_run_id=kwargs.get("plan_run_id"),
            qmt_run_id=kwargs.get("qmt_run_id"),
        )
