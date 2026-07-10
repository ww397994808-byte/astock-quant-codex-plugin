from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from experiment_scheduler.experiment_job import ExperimentJob


class BatchResultAggregator:
    HEADERS = ["job_id", "parent_iteration", "experiment_type", "symbol", "timeframe", "adjust", "regime", "status", "result_path", "audit_status", "readiness", "score", "failure_reason"]

    def write(self, output_dir: str | Path, jobs: list[ExperimentJob]) -> dict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_csv(output_dir / "batch_results.csv", jobs)
        self._write_csv(output_dir / "batch_jobs.csv", jobs)
        failed = [job for job in jobs if job.status == "FAILED" or job.audit_status == "INVALID"]
        self._write_csv(output_dir / "failed_jobs.csv", failed)
        self._write_best(output_dir / "best_by_timeframe.csv", jobs, "timeframe")
        self._write_best(output_dir / "best_by_symbol.csv", jobs, "symbol")
        self._write_best(output_dir / "best_by_regime.csv", jobs, "regime")
        summary = self.summary(jobs)
        self._write_summary(output_dir / "batch_summary.md", summary)
        return summary

    def summary(self, jobs: list[ExperimentJob]) -> dict:
        valid = [job for job in jobs if job.audit_status == "VALID"]
        scores = [job.score for job in valid]
        by_type = defaultdict(list)
        for job in valid:
            by_type[job.experiment_type].append(job.score)
        return {
            "total_jobs": len(jobs),
            "valid_jobs": len(valid),
            "failed_jobs": len(jobs) - len(valid),
            "avg_score": sum(scores) / len(scores) if scores else 0.0,
            "cross_timeframe_stability": self._stability(by_type.get("cross_timeframe", [])),
            "cross_symbol_stability": self._stability(by_type.get("cross_symbol", [])),
            "regime_stability": self._stability(by_type.get("regime_split", [])),
        }

    def _stability(self, scores: list[float]) -> float:
        if not scores:
            return 0.5
        return max(0.0, min(1.0, sum(1 for score in scores if score >= 0.2) / len(scores)))

    def _write_csv(self, path: Path, jobs: list[ExperimentJob]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            writer.writeheader()
            for job in jobs:
                data = job.to_dict()
                writer.writerow({key: data.get(key, "") for key in self.HEADERS})

    def _write_best(self, path: Path, jobs: list[ExperimentJob], key: str) -> None:
        best = {}
        for job in jobs:
            group = getattr(job, key) or "unknown"
            if group not in best or job.score > best[group].score:
                best[group] = job
        self._write_csv(path, list(best.values()))

    def _write_summary(self, path: Path, summary: dict) -> None:
        lines = ["# Batch Summary", ""]
        lines.extend(f"- {key}: {value}" for key, value in summary.items())
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
