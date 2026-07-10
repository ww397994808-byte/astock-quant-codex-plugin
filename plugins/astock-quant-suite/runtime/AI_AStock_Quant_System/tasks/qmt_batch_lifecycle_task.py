from __future__ import annotations

from core.result import TaskResult
from services.qmt_batch_lifecycle_service import QMTBatchLifecycleService
from tasks.base_task import BaseTask


class QMTBatchLifecycleTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTBatchLifecycleService().run(
            batch_sandbox=kwargs["batch_sandbox"],
            qmt_run_id=kwargs.get("qmt_run_id"),
        )
