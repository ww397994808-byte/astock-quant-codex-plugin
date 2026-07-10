from __future__ import annotations

from core.result import TaskResult
from services.qmt_order_lifecycle_service import QMTOrderLifecycleService
from tasks.base_task import BaseTask


class QMTOrderLifecycleTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTOrderLifecycleService().run(
            sandbox=kwargs["sandbox"],
            qmt_run_id=kwargs.get("qmt_run_id"),
        )
