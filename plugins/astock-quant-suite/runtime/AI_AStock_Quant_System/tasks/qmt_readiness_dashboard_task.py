from __future__ import annotations

from core.result import TaskResult
from services.qmt_readiness_dashboard_service import QMTReadinessDashboardService
from tasks.base_task import BaseTask


class QMTReadinessDashboardTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTReadinessDashboardService().run(
            pretrade_package=kwargs.get("pretrade_package"),
            runbook_refresh=kwargs.get("runbook_refresh"),
            handoff_wizard=kwargs.get("handoff_wizard"),
            batch_handoff_wizard=kwargs.get("batch_handoff_wizard"),
            daily_review=kwargs.get("daily_review"),
            batch_daily_review=kwargs.get("batch_daily_review"),
        )
