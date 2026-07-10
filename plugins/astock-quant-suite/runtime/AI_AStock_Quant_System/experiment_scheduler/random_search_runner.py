from __future__ import annotations

import random
from copy import deepcopy

from experiment_scheduler.experiment_job import ExperimentJob
from strategy_compiler.component_registry import ComponentRegistry


class RandomSearchRunner:
    def __init__(self, random_seed: int = 42) -> None:
        self.random = random.Random(random_seed)
        self.registry = ComponentRegistry()

    def sample(self, dsl: dict, max_samples: int = 5) -> list[dict]:
        ranges = self._ranges_for_dsl(dsl)
        samples = []
        for _ in range(max_samples):
            params = {}
            for key, values in ranges.items():
                if not values:
                    continue
                value = self.random.choice(values)
                if self._legal(key, value):
                    params[key] = value
            if params:
                samples.append(params)
        return samples

    def create_jobs(self, parent_iteration: int, symbol: str, timeframe: str, adjust: str, dsl: dict, max_samples: int = 3) -> list[ExperimentJob]:
        jobs = []
        for idx, params in enumerate(self.sample(dsl, max_samples=max_samples), start=1):
            job_dsl = deepcopy(dsl)
            entry = job_dsl.setdefault("entry", {})
            entry.setdefault("params", {}).update({k: v for k, v in params.items() if k in {"window", "num_std", "drawdown_threshold", "deviation", "atr_multiple"}})
            jobs.append(ExperimentJob(f"random_{parent_iteration}_{idx}", parent_iteration, "random_search", symbol, timeframe, adjust, job_dsl, parameters=params))
        return jobs

    def _ranges_for_dsl(self, dsl: dict) -> dict:
        names = [(dsl.get("entry") or {}).get("type"), (dsl.get("sizing") or {}).get("type")]
        ranges = {}
        for name in names:
            if not name:
                continue
            spec = self.registry.get(name)
            if spec:
                ranges.update(spec.parameter_ranges)
        return ranges or {"window": [10, 20, 30], "num_std": [1.6, 2.0, 2.4]}

    def _legal(self, key: str, value) -> bool:
        if isinstance(value, (int, float)):
            return value > 0
        return True
