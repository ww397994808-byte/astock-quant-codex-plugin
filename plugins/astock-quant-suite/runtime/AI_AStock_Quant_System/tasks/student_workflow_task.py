from __future__ import annotations

import json

from core.result import TaskResult
from services.student_workflow_service import StudentWorkflowService
from tasks.base_task import BaseTask


class StudentWorkflowTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        strategy_params = json.loads(kwargs.get("strategy_params") or "{}")
        return StudentWorkflowService().run(
            idea=kwargs["idea"],
            symbol=kwargs.get("symbol"),
            strategy=kwargs.get("strategy"),
            strategy_params=strategy_params,
            data=kwargs.get("data", "__auto_fetch__"),
            timeframe=kwargs.get("timeframe", "1d"),
            adjust=kwargs.get("adjust", "point_in_time_qfq"),
            include_qmt=kwargs.get("include_qmt", False),
            auto_refine=kwargs.get("auto_refine", False),
            max_refinements=kwargs.get("max_refinements", 1),
            session_id=kwargs.get("session_id"),
            case_id=kwargs.get("case_id"),
        )
