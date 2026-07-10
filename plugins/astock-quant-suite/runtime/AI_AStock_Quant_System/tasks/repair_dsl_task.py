from __future__ import annotations

from core.result import TaskResult
from services.repair_dsl_service import RepairDSLService
from tasks.base_task import BaseTask


class RepairDSLTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return RepairDSLService().run(
            dsl_path=kwargs["dsl"],
            symbol=kwargs.get("symbol"),
            data=kwargs.get("data", "__auto_fetch__"),
            timeframe=kwargs.get("timeframe"),
            adjust=kwargs.get("adjust"),
            paper_observation=bool(kwargs.get("paper_observation")),
            stage_check=bool(kwargs.get("stage_check")),
            qmt_run_id=kwargs.get("qmt_run_id"),
            auto_repair=bool(kwargs.get("auto_repair")),
        )
