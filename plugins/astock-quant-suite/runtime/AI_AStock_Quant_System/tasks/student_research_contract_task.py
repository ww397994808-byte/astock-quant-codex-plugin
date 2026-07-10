from __future__ import annotations

from core.result import TaskResult
from services.student_research_contract_service import StudentResearchContractService
from tasks.base_task import BaseTask


class StudentResearchContractTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentResearchContractService().run(
            idea=kwargs.get("idea"),
            timeframe=kwargs.get("timeframe"),
            adjust=kwargs.get("adjust", "point_in_time_qfq"),
            strategy_pattern=kwargs.get("strategy_pattern"),
            code=kwargs.get("code"),
            file=kwargs.get("file"),
            session_id=kwargs.get("session_id"),
            case_id=kwargs.get("case_id"),
        )
