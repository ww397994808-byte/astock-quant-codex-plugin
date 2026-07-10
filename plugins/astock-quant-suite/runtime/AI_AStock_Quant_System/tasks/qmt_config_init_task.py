from __future__ import annotations

from core.result import TaskResult
from services.qmt_config_init_service import QMTConfigInitService
from tasks.base_task import BaseTask


class QMTConfigInitTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return QMTConfigInitService().run(
            config=kwargs.get("config", "config/qmt_config.yaml"),
            account_id=kwargs.get("account_id"),
            mini_qmt_path=kwargs.get("mini_qmt_path"),
            session_id=kwargs.get("session_id"),
            force=kwargs.get("force", False),
        )
