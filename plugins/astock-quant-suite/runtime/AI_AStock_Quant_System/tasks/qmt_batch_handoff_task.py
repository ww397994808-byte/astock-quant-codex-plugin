from __future__ import annotations

from core.result import TaskResult
from services.qmt_batch_handoff_service import QMTBatchHandoffService
from tasks.base_task import BaseTask


class QMTBatchHandoffTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTBatchHandoffService().run(
            package=kwargs["package"],
            orders=kwargs["orders"],
            default_timeframe=kwargs.get("default_timeframe", "1d"),
        )
