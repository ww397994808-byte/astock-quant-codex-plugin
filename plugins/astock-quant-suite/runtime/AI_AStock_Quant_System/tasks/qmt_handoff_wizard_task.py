from __future__ import annotations

from core.result import TaskResult
from services.qmt_handoff_wizard_service import QMTHandoffWizardService
from tasks.base_task import BaseTask


class QMTHandoffWizardTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTHandoffWizardService().run(
            package=kwargs["package"],
            action=kwargs["action"],
            quantity=kwargs["quantity"],
            price=kwargs.get("price"),
            symbol=kwargs.get("symbol"),
            signal_time=kwargs.get("signal_time"),
            execute_time=kwargs.get("execute_time"),
            reason=kwargs.get("reason", ""),
            timeframe=kwargs.get("timeframe", "1d"),
            qmt_run_id=kwargs.get("qmt_run_id"),
            trade_date=kwargs.get("trade_date"),
            config=kwargs.get("config", "config/qmt_config.yaml"),
            notes=kwargs.get("notes", ""),
        )
