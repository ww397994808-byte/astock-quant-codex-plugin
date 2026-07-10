from __future__ import annotations

import csv
from pathlib import Path

from backtest_feedback_loop.regime_analyzer import RegimeAnalyzer
from core.data_loader import load_csv_data
from experiment_scheduler.batch_result_aggregator import BatchResultAggregator
from experiment_scheduler.batch_scheduler import BatchScheduler
from experiment_scheduler.experiment_job import ExperimentJob


class RegimeSliceRunner:
    def run(self, parent_iteration: int, symbol: str, timeframe: str, adjust: str, dsl: dict, data_path: str, output_dir: str | Path) -> list[ExperimentJob]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = load_csv_data(data_path, symbol=symbol)
        slices = RegimeAnalyzer().generate_slices(rows, output_dir)
        jobs: list[ExperimentJob] = []
        for idx, item in enumerate(slices, start=1):
            slice_rows = self._slice_rows(rows, item["start_datetime"], item["end_datetime"])
            if len(slice_rows) < 3:
                continue
            slice_path = self._write_slice_data(output_dir / "slice_data" / f"{idx}_{item['regime']}.csv", slice_rows)
            job = ExperimentJob(
                job_id=f"regime_slice_{parent_iteration}_{idx}_{item['regime']}",
                parent_iteration=parent_iteration,
                experiment_type="regime_slice",
                symbol=symbol,
                timeframe=timeframe,
                adjust=adjust,
                strategy_dsl=dsl,
                data_path=str(slice_path),
                regime=item["regime"],
                parameters=item,
            )
            BatchScheduler()._run_job(job, output_dir)
            jobs.append(job)
        BatchResultAggregator().write(output_dir, jobs)
        self._write_slice_results(output_dir / "regime_slice_results.csv", jobs)
        self._write_best(output_dir / "best_by_regime_slice.csv", jobs)
        self._write_weak_report(output_dir / "weak_regime_report.md", jobs)
        return jobs

    def _slice_rows(self, rows: list[dict], start: str, end: str) -> list[dict]:
        return [row for row in rows if start <= row["datetime"].strftime("%Y-%m-%d %H:%M:%S") <= end]

    def _write_slice_data(self, path: Path, rows: list[dict]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0])
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                item = dict(row)
                item["datetime"] = item["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                item["date"] = item["date"].strftime("%Y-%m-%d")
                writer.writerow(item)
        return path

    def _write_slice_results(self, path: Path, jobs: list[ExperimentJob]) -> None:
        headers = ["job_id", "regime", "status", "audit_status", "readiness", "score", "result_path", "failure_reason"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for job in jobs:
                writer.writerow({key: getattr(job, key, "") for key in headers})

    def _write_best(self, path: Path, jobs: list[ExperimentJob]) -> None:
        best = {}
        for job in jobs:
            if job.regime not in best or job.score > best[job.regime].score:
                best[job.regime] = job
        self._write_slice_results(path, list(best.values()))

    def _write_weak_report(self, path: Path, jobs: list[ExperimentJob]) -> None:
        weak = [job for job in jobs if job.score < 0.5 or job.audit_status == "INVALID"]
        lines = ["# Weak Regime Report", ""]
        if not weak:
            lines.append("未发现明显弱势 regime。")
        for job in weak:
            lines.append(f"- {job.regime}: score={job.score}, audit={job.audit_status}, readiness={job.readiness}")
        if any(job.regime == "bear" for job in weak):
            lines.append("\n策略在 bear 区间表现较弱，需要在最终候选中降权。")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
