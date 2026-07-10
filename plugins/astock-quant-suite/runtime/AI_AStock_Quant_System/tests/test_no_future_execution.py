import csv
from pathlib import Path

from backtest.engine import BacktestEngine
from core.run_manager import RunManager
from examples.sample_data_generator import generate_sample_data


def test_backtest_order_execute_time_after_signal_time(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    data = generate_sample_data(tmp_path / "601088.csv")
    ctx = RunManager(base_dir=tmp_path / "reports").create_run("test")
    BacktestEngine().run(ctx, "boll_mean_reversion", "601088.SH", data)
    with (ctx.output_dir / "orders.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert row["execute_time"] > row["signal_time"]

