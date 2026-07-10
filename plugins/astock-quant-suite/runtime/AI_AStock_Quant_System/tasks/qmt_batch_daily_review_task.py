from __future__ import annotations

from core.result import TaskResult
from services.qmt_batch_daily_review_service import QMTBatchDailyReviewService
from tasks.base_task import BaseTask


class QMTBatchDailyReviewTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTBatchDailyReviewService().run(
            batch_lifecycle=kwargs["batch_lifecycle"],
            trade_date=kwargs.get("trade_date"),
            notes=kwargs.get("notes", ""),
        )
