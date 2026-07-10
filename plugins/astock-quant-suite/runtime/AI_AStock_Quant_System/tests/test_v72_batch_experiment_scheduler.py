from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from backtest_feedback_loop.candidate_selector import CandidateSelector
from experiment_scheduler.batch_budget_manager import BatchBudgetManager
from experiment_scheduler.batch_result_aggregator import BatchResultAggregator
from experiment_scheduler.batch_scheduler import BatchScheduler
from experiment_scheduler.cross_symbol_runner import CrossSymbolRunner
from experiment_scheduler.cross_timeframe_runner import CrossTimeframeRunner
from experiment_scheduler.experiment_job import ExperimentJob
from experiment_scheduler.random_search_runner import RandomSearchRunner
from experiment_scheduler.regime_split_runner import RegimeSplitRunner


ROOT = Path(__file__).resolve().parents[1]


def base_dsl() -> dict:
    return {
        "pattern": "swing",
        "symbols": ["601088.SH"],
        "entry": {"type": "BollLowerEntry", "params": {"window": 20, "num_std": 2.0}},
        "exit": [{"type": "BollMiddleExit", "params": {"window": 20}}],
        "filters": [],
        "sizing": {"type": "FixedPercentSizing", "params": {"percent": 0.5}},
    }


def test_experiment_job_can_be_created():
    job = ExperimentJob("j1", 1, "random_search", "601088.SH", "1h", "raw", base_dsl())
    assert job.job_id == "j1"


def test_batch_scheduler_splits_jobs(monkeypatch):
    monkeypatch_fetch(monkeypatch)
    jobs = BatchScheduler().build_jobs(1, ["random_search", "cross_symbol_validate"], "601088.SH", "1h", "raw", base_dsl())
    assert len(jobs) >= 2


def test_random_search_runner_samples():
    assert RandomSearchRunner().sample(base_dsl(), max_samples=3)


def test_random_seed_reproducible():
    a = RandomSearchRunner(random_seed=7).sample(base_dsl(), 3)
    b = RandomSearchRunner(random_seed=7).sample(base_dsl(), 3)
    assert a == b


def test_random_search_does_not_generate_illegal_params():
    samples = RandomSearchRunner().sample(base_dsl(), 10)
    assert all(value > 0 for sample in samples for value in sample.values() if isinstance(value, (int, float)))


def test_cross_timeframe_runner_generates_jobs(monkeypatch):
    monkeypatch_fetch(monkeypatch)
    jobs = CrossTimeframeRunner().create_jobs(1, "601088.SH", "raw", base_dsl())
    assert {"10m", "30m", "1h", "1d"}.issubset({job.timeframe for job in jobs})


def test_cross_symbol_runner_generates_multi_symbol_jobs(monkeypatch):
    monkeypatch_fetch(monkeypatch)
    jobs = CrossSymbolRunner().create_jobs(1, "601088.SH", "1h", "raw", base_dsl())
    assert {"601088.SH", "601398.SH", "601939.SH", "510880.SH"}.issubset({job.symbol for job in jobs})


def test_regime_split_runner_generates_regime_jobs():
    jobs = RegimeSplitRunner().create_jobs(1, "601088.SH", "1h", "raw", base_dsl())
    assert {"bull", "bear", "sideways", "high_volatility", "low_volatility"}.issubset({job.regime for job in jobs})


def test_missing_data_calls_data_acquisition(monkeypatch):
    calls = []

    def fake_fetch(self, request):
        calls.append(request.symbol)
        return {"path": "data/sample/601088.csv", "source": "fake", "data_quality_score": 100}

    monkeypatch.setattr("data_acquisition.acquisition_agent.DataAcquisitionAgent.fetch", fake_fetch)
    CrossSymbolRunner().create_jobs(1, "601088.SH", "1h", "raw", base_dsl(), symbols=["601088.SH"])
    assert calls == ["601088.SH"]


def test_each_job_calls_action_compiler_and_dsl_to_strategy(tmp_path):
    summary = BatchScheduler().run(1, ["component_combination_experiments"], "601088.SH", "1d", "raw", base_dsl(), tmp_path, data_path="data/sample/601088.csv")
    assert summary["total_jobs"] >= 1
    assert (tmp_path / "batch_results.csv").exists()


def test_each_job_has_audit_and_readiness(tmp_path):
    summary = BatchScheduler().run(1, ["random_search"], "601088.SH", "1d", "raw", base_dsl(), tmp_path, data_path="data/sample/601088.csv")
    job = summary["jobs"][0]
    assert job["audit_status"] in {"VALID", "INVALID"}
    assert job["readiness"]


def test_failed_jobs_csv_generated(tmp_path):
    jobs = [ExperimentJob("bad", 1, "x", "601088.SH", "1h", "raw", {"entry": {"type": "NoSuchEntry"}})]
    jobs[0].status = "FAILED"
    jobs[0].audit_status = "INVALID"
    BatchResultAggregator().write(tmp_path, jobs)
    assert (tmp_path / "failed_jobs.csv").exists()


def test_batch_results_csv_generated(tmp_path):
    BatchResultAggregator().write(tmp_path, [ExperimentJob("j", 1, "x", "601088.SH", "1h", "raw", base_dsl())])
    assert (tmp_path / "batch_results.csv").exists()


def test_best_by_timeframe_generated(tmp_path):
    BatchResultAggregator().write(tmp_path, [ExperimentJob("j", 1, "x", "601088.SH", "1h", "raw", base_dsl())])
    assert (tmp_path / "best_by_timeframe.csv").exists()


def test_best_by_symbol_generated(tmp_path):
    BatchResultAggregator().write(tmp_path, [ExperimentJob("j", 1, "x", "601088.SH", "1h", "raw", base_dsl())])
    assert (tmp_path / "best_by_symbol.csv").exists()


def test_best_by_regime_generated(tmp_path):
    job = ExperimentJob("j", 1, "x", "601088.SH", "1h", "raw", base_dsl(), regime="bull")
    BatchResultAggregator().write(tmp_path, [job])
    assert (tmp_path / "best_by_regime.csv").exists()


def test_candidate_selector_uses_batch_results():
    weak = {"variant_id": "weak", "audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 0, "cross_symbol_stability": 0, "regime_stability": 0}}
    strong = {"variant_id": "strong", "audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 1, "cross_symbol_stability": 1, "regime_stability": 1}}
    accepted, _ = CandidateSelector().select([weak, strong])
    assert accepted[0]["variant_id"] == "strong"


def test_cross_timeframe_instability_downweights():
    score = CandidateSelector().score({"audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 0, "cross_symbol_stability": 1, "regime_stability": 1}})
    better = CandidateSelector().score({"audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 1, "cross_symbol_stability": 1, "regime_stability": 1}})
    assert better > score


def test_cross_symbol_instability_downweights():
    score = CandidateSelector().score({"audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 1, "cross_symbol_stability": 0, "regime_stability": 1}})
    better = CandidateSelector().score({"audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 1, "cross_symbol_stability": 1, "regime_stability": 1}})
    assert better > score


def test_regime_instability_downweights():
    score = CandidateSelector().score({"audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 1, "cross_symbol_stability": 1, "regime_stability": 0}})
    better = CandidateSelector().score({"audit_status": "VALID", "batch_summary": {"cross_timeframe_stability": 1, "cross_symbol_stability": 1, "regime_stability": 1}})
    assert better > score


def test_max_jobs_per_round_effective(tmp_path, monkeypatch):
    config = tmp_path / "scheduler.yaml"
    config.write_text("max_jobs_per_round: 2\nmax_total_jobs: 100\nmax_runtime_seconds: 1800\n", encoding="utf-8")
    budget = BatchBudgetManager(config)
    assert len(budget.trim_round([1, 2, 3])) == 2


def test_max_total_jobs_effective(tmp_path):
    config = tmp_path / "scheduler.yaml"
    config.write_text("max_jobs_per_round: 100\nmax_total_jobs: 1\nmax_runtime_seconds: 1800\n", encoding="utf-8")
    budget = BatchBudgetManager(config)
    assert len(budget.trim_round([1, 2, 3])) == 1


def test_max_runtime_seconds_effective(tmp_path):
    config = tmp_path / "scheduler.yaml"
    config.write_text("max_jobs_per_round: 100\nmax_total_jobs: 100\nmax_runtime_seconds: -1\n", encoding="utf-8")
    assert not BatchBudgetManager(config).allow()


def test_optimize_loop_calls_batch_scheduler():
    run = run_loop(3)
    report_path = report_path_from_stdout(run.stdout)
    assert list(report_path.glob("iteration_*/batch_results.csv"))


def test_loop_memory_records_batch_jobs():
    run = run_loop(3)
    report_path = report_path_from_stdout(run.stdout)
    assert "batch_jobs" in (report_path / "loop_memory.json").read_text(encoding="utf-8")


def test_loop_memory_records_batch_results():
    run = run_loop(3)
    report_path = report_path_from_stdout(run.stdout)
    assert "batch_results_path" in (report_path / "loop_memory.json").read_text(encoding="utf-8")


def test_final_report_mentions_batch_conclusion():
    run = run_loop(3)
    report_path = report_path_from_stdout(run.stdout)
    assert "批量实验结论" in (report_path / "final_feedback_loop_report.md").read_text(encoding="utf-8")


def test_qfq_risk_not_live_candidate():
    accepted, _ = CandidateSelector().select([{"variant_id": "x", "audit_status": "VALID", "readiness": "LIVE_CANDIDATE", "adjust": "qfq"}])
    assert accepted[0]["candidate_score"] < 0.8


def test_invalid_not_candidate():
    accepted, rejected = CandidateSelector().select([{"variant_id": "x", "audit_status": "INVALID"}])
    assert not accepted and rejected


def test_point_in_time_qfq_preserved():
    run = run_loop(2)
    report_path = report_path_from_stdout(run.stdout)
    assert "point_in_time_qfq" in (report_path / "initial_strategy_dsl.yaml").read_text(encoding="utf-8")


def test_t_plus_1_still_reported():
    run = run_loop(2)
    report_path = report_path_from_stdout(run.stdout)
    assert list(report_path.glob("iteration_*/trade_rule_report.md"))


def test_signal_datetime_execute_datetime_still_recorded():
    run = run_loop(2)
    report_path = report_path_from_stdout(run.stdout)
    orders = next(report_path.glob("iteration_*/orders.csv"))
    text = orders.read_text(encoding="utf-8")
    assert "signal_datetime" in text and "execute_datetime" in text


def test_batch_summary_contains_stability_fields(tmp_path):
    jobs = [ExperimentJob("j", 1, "cross_timeframe", "601088.SH", "1h", "raw", base_dsl())]
    jobs[0].audit_status = "VALID"
    jobs[0].score = 0.3
    summary = BatchResultAggregator().write(tmp_path, jobs)
    assert "cross_timeframe_stability" in summary


def test_parameter_sweep_alias_creates_component_jobs():
    jobs = BatchScheduler().build_jobs(1, ["component_combination_experiments"], "601088.SH", "1h", "raw", base_dsl())
    assert jobs


def test_pytest_cli_path_runs():
    run = run_loop(2)
    assert run.returncode == 0


def monkeypatch_fetch(monkeypatch):
    def fake_fetch(self, request):
        return {"path": "data/sample/601088.csv", "source": "fake", "data_quality_score": 100}

    monkeypatch.setattr("data_acquisition.acquisition_agent.DataAcquisitionAgent.fetch", fake_fetch)


def run_loop(max_iterations: int):
    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "optimize-loop",
            "--idea",
            "中国神华1小时布林低吸波段，控制回撤，不要太频繁交易",
            "--symbol",
            "601088.SH",
            "--timeframe",
            "1h",
            "--adjust",
            "point_in_time_qfq",
            "--max-iterations",
            str(max_iterations),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return result


def report_path_from_stdout(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("report_path:"):
            return ROOT / line.split(":", 1)[1].strip()
    raise AssertionError(stdout)
