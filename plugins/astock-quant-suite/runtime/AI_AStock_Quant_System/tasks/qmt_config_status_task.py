from __future__ import annotations

from core.result import TaskResult
from services.qmt_config_status_service import QMTConfigStatusService
from tasks.base_task import BaseTask


class QMTConfigStatusTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTConfigStatusService().run(config=kwargs.get("config", "config/qmt_config.yaml"))
