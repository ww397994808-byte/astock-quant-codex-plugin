from __future__ import annotations

from core.result import TaskResult
from intake.adaptive.adaptive_interview_agent import AdaptiveInterviewAgent


class AdaptiveIntakeService:
    def run(self, idea: str | None = None, confirm: bool = False) -> TaskResult:
        return AdaptiveInterviewAgent().run(idea=idea, confirm=confirm)
