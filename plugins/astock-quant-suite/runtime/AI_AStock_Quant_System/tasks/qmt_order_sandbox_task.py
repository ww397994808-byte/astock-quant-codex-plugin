from __future__ import annotations

from core.result import TaskResult
from services.qmt_order_sandbox_service import QMTOrderSandboxService
from tasks.base_task import BaseTask


class QMTOrderSandboxTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTOrderSandboxService().run(
            handoff=kwargs["handoff"],
            config=kwargs.get("config", "config/qmt_config.yaml"),
            confirmation=kwargs.get("confirmation", ""),
        )
