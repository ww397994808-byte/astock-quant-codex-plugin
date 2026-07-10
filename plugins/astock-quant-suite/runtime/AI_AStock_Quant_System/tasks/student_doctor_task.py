from __future__ import annotations

from core.result import TaskResult
from services.student_doctor_service import StudentDoctorService
from tasks.base_task import BaseTask


class StudentDoctorTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return StudentDoctorService().run()
