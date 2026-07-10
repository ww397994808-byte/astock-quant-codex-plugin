import ast
import csv
from datetime import datetime
from pathlib import Path

from backtest.engine import BacktestEngine
from backtest_templates.base_template import RebalancePlan
from backtest_templates.event_driven_template import EventDrivenTemplate
from backtest_templates.grid_template import GridTemplate
from backtest_templates.pair_trading_template import PairTradingTemplate
from backtest_templates.portfolio_rebalance_template import PortfolioRebalanceTemplate
from backtest_templates.rotation_template import RotationTemplate
from backtest_templates.stock_selection_template import StockSelectionTemplate
from backtest_templates.timing_template import TimingTemplate
from core.data_loader import load_csv_data
from core.run_manager import RunManager
from examples.sample_data_generator import generate_sample_data
from strategies.strategy_registry import create_strategy


ROOT = Path(__file__).resolve().parents[1]


def run_strategy(tmp_path: Path, strategy_name: str):
    data = generate_sample_data(tmp_path / f"{strategy_name}.csv")
    ctx = RunManager(base_dir=tmp_path / "reports").create_run(strategy_name)
    result = BacktestEngine().run(ctx, strategy_name, "601088.SH", data)
    return result


def test_timing_template_can_run_ma_strategy(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = run_strategy(tmp_path, "ma_cross")
    assert result.status == "VALID"
    assert (result.output_dir / "audit_report.md").exists()


def test_swing_template_can_run_boll_strategy(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = run_strategy(tmp_path, "boll_mean_reversion")
    assert result.status == "VALID"
    assert (result.output_dir / "audit_report.md").exists()


def test_swing_template_can_run_dividend_drawdown_strategy(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = run_strategy(tmp_path, "dividend_drawdown")
    assert result.status == "VALID"
    assert (result.output_dir / "audit_report.md").exists()


def test_grid_template_can_run_simple_grid(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    data = generate_sample_data(tmp_path / "grid.csv")
    rows = []
    with data.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    for i, row in enumerate(rows):
        if i > 5:
            price = 30 - (i % 10) * 0.2
            row["open"] = row["close"] = f"{price:.2f}"
            row["high"] = f"{price * 1.01:.2f}"
            row["low"] = f"{price * 0.99:.2f}"
    with data.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    from core.data_loader import load_csv_data

    strategy = create_strategy("ma_cross")
    template = GridTemplate(strategy, "601088.SH", grid_step=0.01)
    ctx = RunManager(base_dir=tmp_path / "reports").create_run("grid")
    result = template.run(ctx, load_csv_data(data, "601088.SH"), source_paths=[])
    assert result.status == "VALID"
    assert (result.output_dir / "audit_report.md").exists()


def test_registered_grid_strategy_can_run_with_grid_template(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    data = generate_sample_data(tmp_path / "registered_grid.csv")
    ctx = RunManager(base_dir=tmp_path / "reports").create_run("grid_registered")
    result = BacktestEngine().run(ctx, "grid", "601088.SH", data)
    assert result.status == "VALID"
    assert (result.output_dir / "audit_report.md").exists()


def test_stock_selection_template_generates_rebalance_plan():
    template = StockSelectionTemplate(create_strategy("ma_cross"), "601088.SH")
    plan = template.build_rebalance_plan(datetime(2024, 1, 2), {"A": 1.0, "B": 2.0, "C": 0.5}, top_n=2)
    assert plan.target_weights == {"B": 0.5, "A": 0.5}


def test_rotation_template_generates_rebalance_plan():
    template = RotationTemplate(create_strategy("ma_cross"), "601088.SH")
    plan = template.build_rebalance_plan(datetime(2024, 1, 2), {"煤炭ETF": 0.8, "银行ETF": 1.2}, top_k=1)
    assert plan.target_weights == {"银行ETF": 1.0}


def test_portfolio_rebalance_template_generates_rebalance_plan():
    template = PortfolioRebalanceTemplate(create_strategy("ma_cross"), "601088.SH")
    plan = template.build_rebalance_plan(datetime(2024, 1, 2), {"601088.SH": 0.4, "601398.SH": 0.6})
    assert plan.target_weights["601398.SH"] == 0.588


def test_templates_keep_signal_and_execute_time(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = run_strategy(tmp_path, "boll_mean_reversion")
    with (result.output_dir / "orders.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert row["signal_time"]
            assert row["execute_time"]
            assert row["execute_time"] > row["signal_time"]


def test_templates_do_not_directly_modify_portfolio_or_place_order():
    template_dir = ROOT / "backtest_templates"
    forbidden_attrs = {"cash"}
    forbidden_calls = {"buy", "sell", "place_order"}
    for path in template_dir.glob("*_template.py"):
        if path.name == "base_template.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Attribute) and node.attr in forbidden_attrs), f"{path} directly touches portfolio cash"
            assert not (isinstance(node, ast.Attribute) and node.attr in forbidden_calls), f"{path} directly calls {node.attr}"


def test_grid_template_initializes_grid_levels():
    template = GridTemplate(create_strategy("ma_cross"), "601088.SH", grid_step=0.02, levels=3, layer_percent=0.1)
    template.initialize_grid(100.0)
    assert len(template.grid_levels) == 3
    assert template.grid_levels[0].buy_price == 98.0
    assert template.grid_levels[0].sell_price == 102.0


def test_grid_template_buy_on_cross_down(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    data = generate_sample_data(tmp_path / "grid_down.csv")
    rows = load_csv_data(data, "601088.SH")[:3]
    rows[0]["close"] = 100.0
    rows[1]["close"] = 99.0
    rows[2]["close"] = 97.0
    template = GridTemplate(create_strategy("ma_cross"), "601088.SH", grid_step=0.02, levels=2)
    assert template.create_intents(0, rows[:1], portfolio=__import__("core.portfolio", fromlist=["Portfolio"]).Portfolio(1000000)) == []
    intents = template.create_intents(1, rows[:2], portfolio=__import__("core.portfolio", fromlist=["Portfolio"]).Portfolio(1000000))
    assert intents == []
    intents = template.create_intents(2, rows[:3], portfolio=__import__("core.portfolio", fromlist=["Portfolio"]).Portfolio(1000000))
    assert intents[0].action == "BUY"
    assert template.grid_levels[0].filled
    assert template.grid_trades[-1]["grid_level"] == 1


def test_grid_template_sell_on_cross_up_after_fill(tmp_path):
    data = generate_sample_data(tmp_path / "grid_up.csv")
    rows = load_csv_data(data, "601088.SH")[:3]
    rows[0]["close"] = 100.0
    rows[1]["close"] = 97.0
    rows[2]["close"] = 103.0
    from core.portfolio import Portfolio

    template = GridTemplate(create_strategy("ma_cross"), "601088.SH", grid_step=0.02, levels=1)
    portfolio = Portfolio(1000000)
    template.create_intents(0, rows[:1], portfolio)
    template.create_intents(1, rows[:2], portfolio)
    intents = template.create_intents(2, rows[:3], portfolio)
    assert intents[0].action == "SELL"
    assert not template.grid_levels[0].filled
    assert template.grid_trades[-1]["action"] == "SELL"


def test_grid_template_records_multiple_layers(tmp_path):
    data = generate_sample_data(tmp_path / "grid_layers.csv")
    rows = load_csv_data(data, "601088.SH")[:3]
    rows[0]["close"] = 100.0
    rows[1]["close"] = 95.0
    rows[2]["close"] = 90.0
    from core.portfolio import Portfolio

    template = GridTemplate(create_strategy("ma_cross"), "601088.SH", grid_step=0.02, levels=3)
    portfolio = Portfolio(1000000)
    template.create_intents(0, rows[:1], portfolio)
    intents = template.create_intents(1, rows[:2], portfolio)
    assert len(intents) >= 2
    assert len(template.grid_trades) >= 2


def test_grid_template_can_use_ma_base_for_dynamic_grid(tmp_path):
    data = generate_sample_data(tmp_path / "ma_grid.csv")
    rows = load_csv_data(data, "601088.SH")[:12]
    closes = [100, 100, 100, 100, 100, 99.4, 100.7, 99.3, 100.8, 99.2, 100.9, 99.1]
    for row, close in zip(rows, closes):
        row["open"] = row["high"] = row["low"] = row["close"] = float(close)
    from core.portfolio import Portfolio

    template = GridTemplate(create_strategy("ma_cross"), "601088.SH", grid_step=0.005, levels=1, layer_percent=0.2, grid_base="ma", ma_window=5)
    portfolio = Portfolio(1000000)
    actions = []
    for i in range(len(rows)):
        actions.extend(intent.action for intent in template.create_intents(i, rows[: i + 1], portfolio))
    assert actions.count("BUY") >= 2
    assert actions.count("SELL") >= 1


def test_stock_selection_template_universe_factor_ranking_top_n():
    template = StockSelectionTemplate(create_strategy("ma_cross"), "601088.SH", universe=["A", "B", "C"], factor_table={"A": 0.1, "B": 0.9, "C": 0.4}, top_n=2)
    plan = template.build_rebalance_plan(datetime(2024, 1, 2))
    assert list(plan.target_weights) == ["B", "C"]
    assert template.ranking_history[-1]["ranking"][0] == ("B", 0.9)


def test_stock_selection_rebalance_frequency():
    template = StockSelectionTemplate(create_strategy("ma_cross"), "601088.SH", rebalance_frequency=5)
    assert template.should_rebalance(10)
    assert not template.should_rebalance(11)


def test_stock_selection_plan_metadata_contains_top_n_and_frequency():
    template = StockSelectionTemplate(create_strategy("ma_cross"), "601088.SH", universe=["A"], factor_table={"A": 1.0}, top_n=1, rebalance_frequency=7)
    plan = template.build_rebalance_plan(datetime(2024, 1, 2))
    assert plan.metadata["top_n"] == 1
    assert plan.metadata["rebalance_frequency"] == 7


def test_rotation_template_asset_pool_score_rules_top_k():
    template = RotationTemplate(create_strategy("ma_cross"), "601088.SH", asset_pool=["煤炭", "银行", "红利"], score_rules={"煤炭": 0.3, "银行": 0.8, "红利": 0.7}, top_k=2)
    plan = template.build_rebalance_plan(datetime(2024, 1, 2))
    assert plan.target_weights == {"银行": 0.5, "红利": 0.5}


def test_rotation_switch_threshold_blocks_small_improvement():
    template = RotationTemplate(create_strategy("ma_cross"), "601088.SH", asset_pool=["A", "B"], score_rules={"A": 1.0, "B": 0.9}, top_k=1, switch_threshold=0.5)
    first = template.build_rebalance_plan(datetime(2024, 1, 2))
    assert first.target_weights == {"A": 1.0}
    second = template.build_rebalance_plan(datetime(2024, 1, 3), {"A": 1.0, "B": 1.2}, top_k=1)
    assert second.target_weights == {"A": 1.0}


def test_rotation_rebalance_frequency():
    template = RotationTemplate(create_strategy("ma_cross"), "601088.SH", rebalance_frequency=10)
    assert template.should_rebalance(20)
    assert not template.should_rebalance(21)


def test_portfolio_rebalance_adjusts_for_cash_buffer():
    template = PortfolioRebalanceTemplate(create_strategy("ma_cross"), "601088.SH", target_weights={"A": 0.5, "B": 0.5}, cash_buffer=0.1)
    assert template.adjusted_target_weights() == {"A": 0.45, "B": 0.45}


def test_portfolio_rebalance_drift_triggers():
    template = PortfolioRebalanceTemplate(create_strategy("ma_cross"), "601088.SH", target_weights={"601088.SH": 0.5}, drift_threshold=0.05, rebalance_frequency=1, cash_buffer=0.0)
    assert template.should_rebalance(1, {"601088.SH": 0.2})
    assert not template.should_rebalance(1, {"601088.SH": 0.98})


def test_portfolio_rebalance_frequency_blocks():
    template = PortfolioRebalanceTemplate(create_strategy("ma_cross"), "601088.SH", target_weights={"601088.SH": 0.5}, rebalance_frequency=5)
    assert not template.should_rebalance(6, {"601088.SH": 0.0})


def test_rebalance_plan_to_order_intents_buy_and_sell():
    plan = RebalancePlan(datetime(2024, 1, 2), {"A": 0.6, "B": 0.0}, "test")
    intents = plan.to_order_intents(current_weights={"A": 0.2, "B": 0.4})
    actions = {intent.symbol: intent.action for intent in intents}
    assert actions == {"A": "BUY", "B": "SELL"}


def test_rebalance_plan_skips_unchanged_weight():
    plan = RebalancePlan(datetime(2024, 1, 2), {"A": 0.2}, "test")
    assert plan.to_order_intents(current_weights={"A": 0.2}) == []


def test_timing_template_uses_execution_engine_instance():
    template = TimingTemplate(create_strategy("ma_cross"), "601088.SH")
    assert template.execution.__class__.__name__ == "ExecutionEngine"


def test_grid_template_uses_execution_engine_instance():
    template = GridTemplate(create_strategy("ma_cross"), "601088.SH")
    assert template.execution.__class__.__name__ == "ExecutionEngine"


def test_selection_rotation_rebalance_templates_use_execution_engine_instance():
    templates = [
        StockSelectionTemplate(create_strategy("ma_cross"), "601088.SH"),
        RotationTemplate(create_strategy("ma_cross"), "601088.SH"),
        PortfolioRebalanceTemplate(create_strategy("ma_cross"), "601088.SH"),
    ]
    assert all(template.execution.__class__.__name__ == "ExecutionEngine" for template in templates)


def test_pair_trading_template_declares_astock_short_blocker():
    assert "不支持裸卖空" in PairTradingTemplate.BLOCKER
    assert "市场中性" in PairTradingTemplate.BLOCKER


def test_event_driven_template_declares_event_data_source_blocker():
    assert "事件数据源" in EventDrivenTemplate.BLOCKER


def test_all_template_runs_generate_audit_report(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = run_strategy(tmp_path, "ma_cross")
    assert (result.output_dir / "audit_report.md").exists()
    assert (result.output_dir / "future_leak_report.md").exists()
    assert (result.output_dir / "trade_rule_report.md").exists()


def test_template_blockers_doc_exists():
    text = (ROOT / "docs/architecture/template_blockers.md").read_text(encoding="utf-8")
    assert "pair_trading_template" in text
    assert "event_driven_template" in text
