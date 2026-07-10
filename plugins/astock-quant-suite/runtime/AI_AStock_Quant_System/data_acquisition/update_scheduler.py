from __future__ import annotations

from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest


class UpdateScheduler:
    def update(self, request: DataRequest) -> dict:
        return DataAcquisitionAgent().fetch(request)

