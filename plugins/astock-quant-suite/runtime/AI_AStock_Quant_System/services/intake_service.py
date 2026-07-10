from __future__ import annotations

from core.result import TaskResult
from intake.question_bank import QUESTION_BANK
from intake.strategy_intake_agent import StrategyIntakeAgent


class IntakeService:
    def run(self, idea: str | None = None, interactive: bool = False) -> TaskResult:
        if interactive:
            questions = list(QUESTION_BANK.values())[:5]
            return TaskResult(
                status="INVALID",
                message="进入交互式澄清模式：请先回答以下问题",
                warnings=questions,
                artifacts={"interactive": True},
            )
        if not idea:
            return TaskResult("INVALID", "请提供 --idea，或使用 --interactive", warnings=[QUESTION_BANK["symbols"], QUESTION_BANK["strategy_pattern"]])
        return StrategyIntakeAgent().run(idea)

