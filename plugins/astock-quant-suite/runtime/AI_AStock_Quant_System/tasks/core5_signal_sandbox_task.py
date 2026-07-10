from __future__ import annotations

from core.result import TaskResult
from services.core5_signal_sandbox_service import Core5SignalSandboxService
from tasks.base_task import BaseTask


class Core5SignalSandboxTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        try:
            return Core5SignalSandboxService().run(
                signal=kwargs.get("signal") or "",
                config=kwargs.get("config") or "config/qmt_config.yaml",
                confirmation=kwargs.get("confirmation") or "",
            )
        except Exception as exc:
            return TaskResult(
                status="INVALID",
                message=f"Core5 模拟盘订单演练失败：{exc}",
                audit_status="CORE5_SIGNAL_SANDBOX_INVALID",
                warnings=[str(exc)],
            )
