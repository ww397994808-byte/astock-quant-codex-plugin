from __future__ import annotations

from core.result import TaskResult
from services.data_acquisition_service import DataAcquisitionService
from tasks.base_task import BaseTask


class FetchDataTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return DataAcquisitionService().fetch(kwargs["symbol"], kwargs.get("timeframe", "1d"), kwargs.get("adjust", "raw"))


class UpdateDataTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return DataAcquisitionService().fetch(kwargs["symbol"], kwargs.get("timeframe", "1d"), kwargs.get("adjust", "raw"))


class DataStatusTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        return DataAcquisitionService().status(kwargs["symbol"], kwargs.get("timeframe", "1d"), kwargs.get("adjust", "raw"))

