import csv
import json
from pathlib import Path

from paper_live.observation import PaperObservationChecker
from services.paper_service import PaperService
from examples.sample_data_generator import generate_sample_data


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_paper_observation_blocks_short_observation(tmp_path: Path):
    write_csv(tmp_path / "equity_curve.csv", [{"date": "2024-01-01", "equity": 100}], ["date", "equity"])
    write_csv(tmp_path / "trades.csv", [], ["date"])
    write_csv(tmp_path / "orders.csv", [], ["status"])
    (tmp_path / "performance.json").write_text(json.dumps({"max_drawdown": 0}), encoding="utf-8")

    result = PaperObservationChecker().check(tmp_path, min_observed_days=20, min_trades=1)
    assert result.status == "INVALID"
    assert any("观察期不足" in item for item in result.failures)
    assert any("成交次数不足" in item for item in result.failures)


def test_paper_observation_passes_when_thresholds_met(tmp_path: Path):
    equity = [{"date": f"2024-01-{day:02d}", "equity": 100000 + day} for day in range(1, 22)]
    trades = [
        {"date": "2024-01-05", "action": "BUY"},
        {"date": "2024-01-10", "action": "SELL"},
        {"date": "2024-01-18", "action": "BUY"},
    ]
    write_csv(tmp_path / "equity_curve.csv", equity, ["date", "equity"])
    write_csv(tmp_path / "trades.csv", trades, ["date", "action"])
    write_csv(tmp_path / "orders.csv", [{"status": "FILLED"}], ["status"])
    (tmp_path / "performance.json").write_text(json.dumps({"max_drawdown": -0.01}), encoding="utf-8")

    result = PaperObservationChecker().check(tmp_path, min_observed_days=20, min_trades=1)
    assert result.status == "VALID"
    assert result.completed_rounds == 1
    PaperObservationChecker().write_report(tmp_path, result)
    assert (tmp_path / "paper_observation_report.md").exists()
    assert (tmp_path / "paper_observation_policy_card.json").exists()
    observation = json.loads((tmp_path / "paper_observation.json").read_text(encoding="utf-8"))
    assert "policy" in observation
    assert observation["policy_card"]["can_continue_qmt_readonly"] is True


def test_paper_observation_uses_archetype_policy(tmp_path: Path):
    equity = [{"date": f"2024-01-{day:02d}", "equity": 100000 + day} for day in range(1, 31)]
    trades = [
        {"date": "2024-01-01", "action": "BUY"},
        {"date": "2024-01-02", "action": "SELL"},
        {"date": "2024-01-03", "action": "BUY"},
        {"date": "2024-01-04", "action": "SELL"},
        {"date": "2024-01-05", "action": "BUY"},
        {"date": "2024-01-06", "action": "SELL"},
    ]
    write_csv(tmp_path / "equity_curve.csv", equity, ["date", "equity"])
    write_csv(tmp_path / "trades.csv", trades, ["date", "action"])
    write_csv(tmp_path / "orders.csv", [{"status": "FILLED"}], ["status"])
    (tmp_path / "performance.json").write_text(json.dumps({"max_drawdown": -0.01}), encoding="utf-8")

    grid_result = PaperObservationChecker().check(tmp_path, strategy_pattern="grid", timeframe="1h")
    intraday_result = PaperObservationChecker().check(tmp_path, strategy_pattern="swing", timeframe="1h")

    assert grid_result.status == "INVALID"
    assert grid_result.policy["min_trades"] == 8
    assert grid_result.policy["min_completed_rounds"] == 3
    assert intraday_result.status == "VALID"
    assert intraday_result.policy["min_trades"] == 6
    assert intraday_result.policy["min_completed_rounds"] == 3


def test_paper_observation_blocks_without_completed_round(tmp_path: Path):
    equity = [{"date": f"2024-01-{day:02d}", "equity": 100000 + day} for day in range(1, 22)]
    trades = [
        {"date": "2024-01-05", "action": "BUY"},
        {"date": "2024-01-10", "action": "BUY"},
        {"date": "2024-01-18", "action": "BUY"},
    ]
    write_csv(tmp_path / "equity_curve.csv", equity, ["date", "equity"])
    write_csv(tmp_path / "trades.csv", trades, ["date", "action"])
    write_csv(tmp_path / "orders.csv", [{"status": "FILLED"}], ["status"])
    (tmp_path / "performance.json").write_text(json.dumps({"max_drawdown": -0.01}), encoding="utf-8")

    result = PaperObservationChecker().check(tmp_path, min_observed_days=20, min_trades=3)

    assert result.status == "INVALID"
    assert result.completed_rounds == 0
    assert any("完整买卖回合不足" in item for item in result.failures)


def test_paper_observation_blocks_high_rejected_order_rate(tmp_path: Path):
    equity = [{"date": f"2024-01-{day:02d}", "equity": 100000 + day} for day in range(1, 22)]
    trades = [
        {"date": "2024-01-05", "action": "BUY"},
        {"date": "2024-01-10", "action": "SELL"},
        {"date": "2024-01-18", "action": "BUY"},
    ]
    orders = [{"status": "FILLED"}, {"status": "REJECTED"}, {"status": "REJECTED"}]
    write_csv(tmp_path / "equity_curve.csv", equity, ["date", "equity"])
    write_csv(tmp_path / "trades.csv", trades, ["date", "action"])
    write_csv(tmp_path / "orders.csv", orders, ["status"])
    (tmp_path / "performance.json").write_text(json.dumps({"max_drawdown": -0.01}), encoding="utf-8")

    result = PaperObservationChecker().check(tmp_path, min_observed_days=20, min_trades=1)
    PaperObservationChecker().write_report(tmp_path, result)
    card = json.loads((tmp_path / "paper_observation_policy_card.json").read_text(encoding="utf-8"))

    assert result.status == "INVALID"
    assert result.rejected_order_rate == 0.666667
    assert any("拒单率过高" in item for item in result.failures)
    assert any(item["metric"] == "rejected_order_rate" and item["status"] == "FAIL" for item in card["requirements"])


def test_paper_service_writes_observation_report(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    data = generate_sample_data(tmp_path / "601088.csv")
    result = PaperService().run("boll_mean_reversion", "601088.SH", str(data))
    assert result.report_path
    assert (Path(result.report_path) / "paper_observation_report.md").exists()
    assert "paper_observation" in result.artifacts


def test_paper_service_loads_policy_from_plan(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    data = generate_sample_data(tmp_path / "601088.csv")
    plan_dir = root / "reports" / "test_plan_for_paper_policy"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "backtest_plan.yaml").write_text(
        "strategy_pattern: grid\ntimeframe: 1h\nstatus: VALID\nblockers: []\n",
        encoding="utf-8",
    )

    result = PaperService().run("boll_mean_reversion", "601088.SH", str(data), plan_run_id="test_plan_for_paper_policy")

    assert result.report_path
    assert result.artifacts["paper_policy"]["strategy_pattern"] == "grid"
    assert result.artifacts["paper_policy"]["timeframe"] == "1h"
