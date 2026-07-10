from __future__ import annotations

from core.result import TaskResult
from services.student_contract_check_service import StudentContractCheckService
from tasks.base_task import BaseTask


class StudentContractCheckTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentContractCheckService().run(
            contract=kwargs.get("contract"),
            workflow=kwargs.get("workflow"),
            session_id=kwargs.get("session_id"),
        )
