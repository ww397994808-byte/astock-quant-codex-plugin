from __future__ import annotations

import csv
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from backtest_feedback_loop.candidate_selector import CandidateSelector
from backtest_feedback_loop.regime_analyzer import RegimeAnalyzer
from experiment_scheduler.batch_scheduler import BatchScheduler
from experiment_scheduler.cross_timeframe_runner import CrossTimeframeRunner
from experiment_scheduler.regime_slice_runner import RegimeSliceRunner
from intake.intent_parser import IntentParser
from market_data.resampler import Resampler
from research.pattern_classifier import PatternClassifier


ROOT = Path(__file__).resolve().parents[1]


def daily_rows() -> list[dict]:
    rows = []
    start = datetime(2024, 1, 1)
    prices = [10, 11, 12, 11, 13, 14, 13, 12, 13, 15]
    for i, price in enumerate(prices):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        rows.append(
            {
                "datetime": day,
                "date": day,
                "time": "00:00:00",
                "timeframe": "1d",
                "open": price - 0.5,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 100 + i,
                "amount": (100 + i) * price,
                "symbol": "601088.SH",
                "name": "中国神华",
                "is_st": False,
                "board": "main",
                "paused": False,
                "source": "test",
                "adjust_type": "raw",
                "adjust_factor": 1,
                "corporate_action_flag": False,
            }
        )
    return rows


def base_dsl() -> dict:
    return {
        "pattern": "swing",
        "symbols": ["601088.SH"],
        "entry": {"type": "BollLowerEntry", "params": {"window": 3, "num_std": 1.0}},
        "exit": [{"type": "BollMiddleExit", "params": {"window": 3}}],
        "sizing": {"type": "FixedPercentSizing", "params": {"percent": 0.2}},
    }


def test_daily_to_weekly_aggregation_correct():
    weekly = Resampler().resample(daily_rows(), "1w")
    assert weekly
    assert weekly[0]["timeframe"] == "1w"


def test_weekly_ohlc_correct():
    weekly = Resampler().resample(daily_rows(), "1w")
    first = weekly[0]
    source = daily_rows()[:5]
    assert first["open"] == source[0]["open"]
    assert first["high"] == max(row["high"] for row in source)
    assert first["low"] == min(row["low"] for row in source)
    assert first["close"] == source[-1]["close"]


def test_weekly_volume_amount_correct():
    weekly = Resampler().resample(daily_rows(), "1w")
    source = daily_rows()[:5]
    assert weekly[0]["volume"] == sum(row["volume"] for row in source)
    assert weekly[0]["amount"] == sum(row["amount"] for row in source)


def test_weekly_does_not_cross_natural_week():
    weekly = Resampler().resample(daily_rows(), "1w")
    assert len({row["datetime"].isocalendar()[1] for row in weekly}) == len(weekly)


def test_weekly_signal_datetime_correct():
    weekly = Resampler().resample(daily_rows(), "1w")
    assert weekly[0]["datetime"].weekday() <= 4
    assert weekly[0]["datetime"] == daily_rows()[4]["datetime"]


def test_weekly_execute_datetime_correct():
    run = subprocess.run(
        [sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--timeframe", "1w", "--adjust", "point_in_time_qfq"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    report = report_path(run.stdout)
    orders = (report / "orders.csv").read_text(encoding="utf-8")
    assert "signal_datetime" in orders and "execute_datetime" in orders


def test_cli_backtest_weekly_runs():
    run = subprocess.run(
        [sys.executable, "cli.py", "backtest", "--strategy", "boll_mean_reversion", "--symbol", "601088.SH", "--timeframe", "1w", "--adjust", "point_in_time_qfq"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    assert "status: VALID" in run.stdout


def test_cross_timeframe_contains_weekly_and_runs(monkeypatch):
    jobs = CrossTimeframeRunner().create_jobs(1, "601088.SH", "point_in_time_qfq", base_dsl())
    assert "1w" in {job.timeframe for job in jobs}
    assert next(job for job in jobs if job.timeframe == "1w").data_path


def test_research_agent_recognizes_weekly():
    assert PatternClassifier().classify("中国神华周线布林低吸").pattern == "swing"
    assert IntentParser().parse("中国神华 weekly 布林低吸").timeframe == "1w"


def test_generate_bull_slice(tmp_path):
    slices = RegimeAnalyzer().generate_slices(slice_rows("bull"), tmp_path, window=5)
    assert any(item["regime"] == "bull" for item in slices)


def test_generate_bear_slice(tmp_path):
    slices = RegimeAnalyzer().generate_slices(slice_rows("bear"), tmp_path, window=5)
    assert any(item["regime"] == "bear" for item in slices)


def test_generate_sideways_slice(tmp_path):
    slices = RegimeAnalyzer().generate_slices(slice_rows("sideways"), tmp_path, window=5)
    assert any(item["regime"] == "sideways" for item in slices)


def test_generate_high_volatility_slice(tmp_path):
    slices = RegimeAnalyzer().generate_slices(slice_rows("volatile"), tmp_path, window=5)
    assert any(item["regime"] == "high_volatility" for item in slices)


def test_generate_low_volatility_slice(tmp_path):
    slices = RegimeAnalyzer().generate_slices(slice_rows("sideways"), tmp_path, window=5)
    assert any(item["regime"] == "low_volatility" for item in slices)


def test_regime_slices_csv_fields_complete(tmp_path):
    RegimeAnalyzer().generate_slices(slice_rows("bull"), tmp_path, window=5)
    with (tmp_path / "regime_slices.csv").open("r", encoding="utf-8") as f:
        assert {"regime", "start_datetime", "end_datetime", "reason", "volatility", "trend_return", "bar_count"}.issubset(set(csv.DictReader(f).fieldnames or []))


def test_regime_slice_runner_slices_data(tmp_path):
    path = write_rows(tmp_path / "rows.csv", slice_rows("bull") + slice_rows("bear", offset=20))
    jobs = RegimeSliceRunner().run(1, "601088.SH", "1d", "raw", base_dsl(), str(path), tmp_path / "out")
    assert jobs
    assert list((tmp_path / "out" / "slice_data").glob("*.csv"))


def test_each_slice_independent_backtest(tmp_path):
    path = write_rows(tmp_path / "rows.csv", slice_rows("bull") + slice_rows("bear", offset=20))
    jobs = RegimeSliceRunner().run(1, "601088.SH", "1d", "raw", base_dsl(), str(path), tmp_path / "out")
    assert all(job.result_path for job in jobs)


def test_bear_weak_report_mentions_bear(tmp_path):
    path = write_rows(tmp_path / "rows.csv", slice_rows("bear"))
    RegimeSliceRunner().run(1, "601088.SH", "1d", "raw", base_dsl(), str(path), tmp_path / "out")
    text = (tmp_path / "out" / "weak_regime_report.md").read_text(encoding="utf-8")
    assert "bear" in text


def test_candidate_selector_uses_regime_slice_results():
    weak = {"audit_status": "VALID", "batch_summary": {"regime_slice_stability": 0, "cross_timeframe_stability": 1, "cross_symbol_stability": 1}}
    strong = {"audit_status": "VALID", "batch_summary": {"regime_slice_stability": 1, "cross_timeframe_stability": 1, "cross_symbol_stability": 1}}
    assert CandidateSelector().score(strong) > CandidateSelector().score(weak)


def test_optimize_loop_weekly_runs():
    run = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "optimize-loop",
            "--idea",
            "中国神华周线布林低吸波段，控制回撤，不要太频繁交易",
            "--symbol",
            "601088.SH",
            "--timeframe",
            "1w",
            "--adjust",
            "point_in_time_qfq",
            "--max-iterations",
            "3",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    assert "status: VALID" in run.stdout


def slice_rows(kind: str, offset: int = 0) -> list[dict]:
    rows = []
    start = datetime(2024, 1, 1) + timedelta(days=offset)
    price = 10.0
    for i in range(12):
        day = start + timedelta(days=i)
        if kind == "bull":
            price += 0.2
        elif kind == "bear":
            price -= 0.2
        elif kind == "volatile":
            price += 0.8 if i % 2 == 0 else -0.7
        else:
            price += 0.01 if i % 2 == 0 else -0.01
        rows.append(
            {
                "datetime": day,
                "date": day,
                "time": "00:00:00",
                "timeframe": "1d",
                "open": price,
                "high": price + 0.3,
                "low": price - 0.3,
                "close": price,
                "volume": 1000 + i,
                "amount": (1000 + i) * price,
                "symbol": "601088.SH",
                "name": "中国神华",
                "is_st": False,
                "board": "main",
                "paused": False,
                "source": "test",
                "adjust_type": "raw",
                "adjust_factor": 1,
                "corporate_action_flag": False,
            }
        )
    return rows


def write_rows(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            item = dict(row)
            item["datetime"] = item["datetime"].strftime("%Y-%m-%d %H:%M:%S")
            item["date"] = item["date"].strftime("%Y-%m-%d")
            writer.writerow(item)
    return path


def report_path(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("report_path:"):
            return ROOT / line.split(":", 1)[1].strip()
    raise AssertionError(stdout)
