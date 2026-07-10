from __future__ import annotations

from experiment_scheduler.experiment_job import ExperimentJob


class ExperimentQueue:
    def __init__(self) -> None:
        self.jobs: list[ExperimentJob] = []

    def add(self, job: ExperimentJob) -> None:
        self.jobs.append(job)

    def extend(self, jobs: list[ExperimentJob]) -> None:
        self.jobs.extend(jobs)

    def pop_all(self) -> list[ExperimentJob]:
        jobs = self.jobs
        self.jobs = []
        return jobs
