from __future__ import annotations

from core.result import TaskResult
from services.audit_service import AuditService
from tasks.base_task import BaseTask


class AuditTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return AuditService().run(kwargs["run_id"])

