from __future__ import annotations

from core.result import TaskResult
from services.qmt_batch_sandbox_service import QMTBatchSandboxService
from tasks.base_task import BaseTask


class QMTBatchSandboxTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTBatchSandboxService().run(
            batch_handoff=kwargs["batch_handoff"],
            config=kwargs.get("config", "config/qmt_config.yaml"),
            confirmation=kwargs.get("confirmation", ""),
        )
