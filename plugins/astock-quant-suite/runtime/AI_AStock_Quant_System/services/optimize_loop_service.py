from __future__ import annotations

from backtest_feedback_loop.feedback_loop_controller import FeedbackLoopController
from core.result import TaskResult


class OptimizeLoopService:
    def run(
        self,
        idea: str,
        symbol: str,
        timeframe: str = "1d",
        adjust: str = "raw",
        max_iterations: int | None = None,
    ) -> TaskResult:
        return FeedbackLoopController().run(
            idea=idea,
            symbol=symbol,
            timeframe=timeframe,
            adjust=adjust,
            max_iterations=max_iterations,
        )
