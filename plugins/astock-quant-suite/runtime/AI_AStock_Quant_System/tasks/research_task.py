from __future__ import annotations

from core.result import TaskResult
from services.research_service import ResearchService
from tasks.base_task import BaseTask


class ResearchTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return ResearchService().run(kwargs["direction"], kwargs["symbol"], kwargs["data"], timeframe=kwargs.get("timeframe", "1d"), adjust=kwargs.get("adjust", "raw"))
