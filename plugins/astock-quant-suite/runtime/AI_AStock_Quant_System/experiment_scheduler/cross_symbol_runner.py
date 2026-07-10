from __future__ import annotations

from copy import deepcopy

from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest
from experiment_scheduler.experiment_job import ExperimentJob


class CrossSymbolRunner:
    DEFAULT_SIMILAR = {
        "601088.SH": ["601088.SH", "601398.SH", "601939.SH", "510880.SH"],
    }

    def create_jobs(self, parent_iteration: int, symbol: str, timeframe: str, adjust: str, dsl: dict, symbols: list[str] | None = None) -> list[ExperimentJob]:
        jobs = []
        for target in symbols or self.DEFAULT_SIMILAR.get(symbol, [symbol]):
            job_dsl = deepcopy(dsl)
            job_dsl["symbols"] = [target]
            record = DataAcquisitionAgent().fetch(DataRequest(symbol=target, timeframe=timeframe, adjust=adjust))
            jobs.append(ExperimentJob(f"symbol_{parent_iteration}_{target}", parent_iteration, "cross_symbol", target, timeframe, adjust, job_dsl, data_path=record["path"]))
        return jobs
