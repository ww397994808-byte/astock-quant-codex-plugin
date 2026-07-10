from __future__ import annotations

from core.result import TaskResult
from services.qmt_daily_review_service import QMTDailyReviewService
from tasks.base_task import BaseTask


class QMTDailyReviewTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTDailyReviewService().run(
            lifecycle=kwargs["lifecycle"],
            trade_date=kwargs.get("trade_date"),
            notes=kwargs.get("notes", ""),
        )
