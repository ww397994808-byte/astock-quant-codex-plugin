from __future__ import annotations

from copy import deepcopy

from experiment_scheduler.experiment_job import ExperimentJob


class RegimeSplitRunner:
    REGIMES = ["bull", "bear", "sideways", "high_volatility", "low_volatility"]

    def create_jobs(self, parent_iteration: int, symbol: str, timeframe: str, adjust: str, dsl: dict, data_path: str = "") -> list[ExperimentJob]:
        jobs = []
        for regime in self.REGIMES:
            job_dsl = deepcopy(dsl)
            job_dsl.setdefault("metadata", {})["regime"] = regime
            jobs.append(ExperimentJob(f"regime_{parent_iteration}_{regime}", parent_iteration, "regime_split", symbol, timeframe, adjust, job_dsl, data_path=data_path, regime=regime))
        return jobs
