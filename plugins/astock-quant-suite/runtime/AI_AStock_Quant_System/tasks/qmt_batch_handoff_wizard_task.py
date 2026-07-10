from __future__ import annotations

from core.result import TaskResult
from services.qmt_batch_handoff_wizard_service import QMTBatchHandoffWizardService
from tasks.base_task import BaseTask


class QMTBatchHandoffWizardTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTBatchHandoffWizardService().run(
            package=kwargs["package"],
            orders=kwargs["orders"],
            default_timeframe=kwargs.get("default_timeframe", "1d"),
            qmt_run_id=kwargs.get("qmt_run_id"),
            trade_date=kwargs.get("trade_date"),
            config=kwargs.get("config", "config/qmt_config.yaml"),
            notes=kwargs.get("notes", ""),
        )
