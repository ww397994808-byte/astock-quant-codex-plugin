from __future__ import annotations

from core.result import TaskResult
from services.student_backtest_plan_precheck_service import StudentBacktestPlanPrecheckService
from tasks.base_task import BaseTask


class StudentBacktestPlanPrecheckTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentBacktestPlanPrecheckService().run(
            idea=kwargs.get("idea"),
            timeframe=kwargs.get("timeframe"),
            adjust=kwargs.get("adjust", "point_in_time_qfq"),
            strategy_pattern=kwargs.get("strategy_pattern"),
            session_id=kwargs.get("session_id"),
            case_id=kwargs.get("case_id"),
        )
