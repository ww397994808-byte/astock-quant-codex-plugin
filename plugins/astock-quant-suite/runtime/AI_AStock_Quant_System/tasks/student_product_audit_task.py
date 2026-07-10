from __future__ import annotations

from core.result import TaskResult
from services.student_product_audit_service import StudentProductAuditService
from tasks.base_task import BaseTask


class StudentProductAuditTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentProductAuditService().run(
            workflow=kwargs.get("workflow"),
            limit=int(kwargs.get("limit") or 5),
        )
