from __future__ import annotations

from core.result import TaskResult
from services.qmt_handoff_service import QMTHandoffService
from tasks.base_task import BaseTask


class QMTHandoffTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTHandoffService().run(
            package=kwargs["package"],
            action=kwargs["action"],
            quantity=kwargs["quantity"],
            price=kwargs.get("price"),
            symbol=kwargs.get("symbol"),
            signal_time=kwargs.get("signal_time"),
            execute_time=kwargs.get("execute_time"),
            reason=kwargs.get("reason", ""),
            timeframe=kwargs.get("timeframe", "1d"),
        )
