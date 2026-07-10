from __future__ import annotations

from core.result import TaskResult
from services.qmt_check_service import QMTCheckService
from tasks.base_task import BaseTask


class QMTCheckTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTCheckService().run()

