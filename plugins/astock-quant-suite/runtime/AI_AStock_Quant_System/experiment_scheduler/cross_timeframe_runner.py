from __future__ import annotations

from copy import deepcopy

from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest
from experiment_scheduler.experiment_job import ExperimentJob


class CrossTimeframeRunner:
    TIMEFRAMES = ["10m", "30m", "1h", "1d", "1w"]

    def create_jobs(self, parent_iteration: int, symbol: str, adjust: str, dsl: dict) -> list[ExperimentJob]:
        jobs = []
        for timeframe in self.TIMEFRAMES:
            job_dsl = deepcopy(dsl)
            job_dsl["timeframe"] = timeframe
            record = DataAcquisitionAgent().fetch(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))
            jobs.append(ExperimentJob(f"timeframe_{parent_iteration}_{timeframe}", parent_iteration, "cross_timeframe", symbol, timeframe, adjust, job_dsl, data_path=record["path"]))
        return jobs
