from __future__ import annotations

import time
from pathlib import Path

import yaml


class BatchBudgetManager:
    def __init__(self, config_path: str | Path = "config/experiment_scheduler.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}
        self.start_time = time.time()
        self.total_jobs = 0

    @property
    def max_jobs_per_round(self) -> int:
        return int(self.config.get("max_jobs_per_round", 100))

    @property
    def max_total_jobs(self) -> int:
        return int(self.config.get("max_total_jobs", 1000))

    @property
    def max_runtime_seconds(self) -> int:
        return int(self.config.get("max_runtime_seconds", 1800))

    def allow(self, count: int = 1) -> bool:
        if self.total_jobs + count > self.max_total_jobs:
            return False
        if time.time() - self.start_time > self.max_runtime_seconds:
            return False
        return True

    def trim_round(self, jobs: list) -> list:
        allowed = min(len(jobs), self.max_jobs_per_round, max(0, self.max_total_jobs - self.total_jobs))
        trimmed = jobs[:allowed]
        self.total_jobs += len(trimmed)
        return trimmed
