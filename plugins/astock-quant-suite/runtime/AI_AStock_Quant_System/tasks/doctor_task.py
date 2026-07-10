from __future__ import annotations

from core.result import TaskResult
from services.doctor_service import DoctorService
from tasks.base_task import BaseTask


class DoctorTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return DoctorService().run()

