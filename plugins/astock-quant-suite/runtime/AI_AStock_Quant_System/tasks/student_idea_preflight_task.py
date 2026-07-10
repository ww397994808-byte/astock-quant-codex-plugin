from __future__ import annotations

from core.result import TaskResult
from services.student_idea_preflight_service import StudentIdeaPreflightService
from tasks.base_task import BaseTask


class StudentIdeaPreflightTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentIdeaPreflightService().run(
            idea=kwargs.get("idea"),
            timeframe=kwargs.get("timeframe"),
            adjust=kwargs.get("adjust", "point_in_time_qfq"),
            session_id=kwargs.get("session_id"),
            case_id=kwargs.get("case_id"),
            auto_refine=not kwargs.get("no_auto_refine", False),
        )
