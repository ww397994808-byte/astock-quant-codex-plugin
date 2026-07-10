from __future__ import annotations

from core.result import TaskResult
from services.explain_report_service import ExplainReportService
from tasks.base_task import BaseTask


class ExplainReportTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return ExplainReportService().run(kwargs["run_id"])

