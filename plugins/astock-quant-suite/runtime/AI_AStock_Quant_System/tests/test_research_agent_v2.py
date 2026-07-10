import csv
import json
import subprocess
import sys
from pathlib import Path

from research.overfit_detector import OverfitDetector
from research.pattern_classifier import PatternClassifier
from research.research_loop import ResearchLoop
from research.research_plan import ResearchPlan
from research.result_ranker import ResultRanker
from research.search_space_builder import SearchSpaceBuilder
from research.strategy_variant_generator import StrategyVariantGenerator


ROOT = Path(__file__).resolve().parents[1]


def test_boll_low_buy_classified_as_swing():
    assert PatternClassifier().classify("布林低吸波段策略").pattern == "swing"


def test_ma_trend_classified_as_timing():
    assert PatternClassifier().classify("均线趋势择时").pattern == "timing"


def test_grid_direction_classified_as_grid():
    assert PatternClassifier().classify("区间震荡网格分层买卖").pattern == "grid"


def test_intraday_ma_grid_classified_as_grid():
    assert PatternClassifier().classify("中国神华10分钟MA5网格策略").pattern == "grid"


def test_high_dividend_stock_selection_classified_as_stock_selection():
    assert PatternClassifier().classify("高股息选股 TopN").pattern == "stock_selection"


def test_etf_rotation_classified_as_rotation():
    assert PatternClassifier().classify("ETF轮动强弱切换").pattern == "rotation"


def test_equal_weight_portfolio_classified_as_portfolio():
    assert PatternClassifier().classify("等权组合再平衡").pattern == "portfolio"


def test_pair_trading_returns_blocker():
    result = PatternClassifier().classify("A/H价差配对套利")
    assert result.pattern == "pair_trading"
    assert result.blocker


def test_event_driven_returns_blocker():
    result = PatternClassifier().classify("财报公告事件驱动")
    assert result.pattern == "event_driven"
    assert result.blocker


def test_research_plan_fields_complete():
    plan = ResearchPlan(
        original_direction="x",
        selected_pattern="swing",
        hypothesis="h",
        variables_to_test=["window"],
        entry_logic_candidates=["entry"],
        exit_logic_candidates=["exit"],
        sizing_candidates=["size"],
        filter_candidates=["filter"],
        risk_candidates=["risk"],
        search_space={"window": [20]},
        constraints=["T+1"],
        evaluation_metrics=["calmar"],
    )
    data = plan.to_dict()
    for key in [
        "original_direction",
        "selected_pattern",
        "hypothesis",
        "variables_to_test",
        "entry_logic_candidates",
        "exit_logic_candidates",
        "sizing_candidates",
        "filter_candidates",
        "risk_candidates",
        "search_space",
        "constraints",
        "evaluation_metrics",
        "blocker_notes",
    ]:
        assert key in data


def test_strategy_variant_fields_complete():
    search_space = SearchSpaceBuilder().build("swing", "稳健控制回撤")
    variant = StrategyVariantGenerator().generate("swing", search_space, max_variants=1)[0]
    data = variant.to_dict()
    for key in ["variant_id", "pattern", "template_name", "components", "params", "description", "expected_behavior"]:
        assert key in data


def test_swing_variant_uses_swing_template():
    variant = StrategyVariantGenerator().generate("swing", {"window": [20], "num_std": [2.0], "stop_loss": [0.08]}, max_variants=1)[0]
    assert variant.template_name == "swing_template"


def test_timing_variant_uses_timing_template():
    variant = StrategyVariantGenerator().generate("timing", {"short_window": [5], "long_window": [20]}, max_variants=1)[0]
    assert variant.template_name == "timing_template"


def test_grid_variant_uses_grid_template():
    variant = StrategyVariantGenerator().generate("grid", {"grid_step": [0.03], "levels": [2], "layer_percent": [0.1]}, max_variants=1)[0]
    assert variant.template_name == "grid_template"


def test_ma5_grid_search_space_contains_dynamic_grid_parameters():
    search_space = SearchSpaceBuilder().build("grid", "中国神华 日线 MA5 网格，最多5层，最大仓位100%，参数寻优")
    assert search_space["grid_base"] == ["ma"]
    assert search_space["ma_window"] == [5]
    assert 0.005 in search_space["grid_step"]
    assert 5 in search_space["levels"]
    assert 1.0 in search_space["max_position_percent"]


def test_intraday_ma5_grid_search_space_uses_smaller_steps():
    search_space = SearchSpaceBuilder().build("grid", "中国神华 10分钟 MA5 网格")
    assert search_space["grid_step"] == [0.001, 0.002, 0.003, 0.004, 0.005]


def test_audit_invalid_not_in_ranked_results():
    ranked = ResultRanker().rank([
        {"variant_id": "bad", "audit_status": "INVALID", "total_return": 10, "max_drawdown": 0.01, "out_sample_return": 10, "trade_count": 20},
        {"variant_id": "good", "audit_status": "VALID", "total_return": 0.01, "max_drawdown": 0.01, "out_sample_return": 0.01, "trade_count": 5},
    ])
    assert [row["variant_id"] for row in ranked] == ["good"]


def test_low_trade_count_gets_lower_score():
    ranker = ResultRanker()
    low = {"audit_status": "VALID", "total_return": 0.05, "max_drawdown": -0.05, "out_sample_return": 0.04, "trade_count": 1}
    high = dict(low)
    high["trade_count"] = 10
    assert ranker.score(high) > ranker.score(low)


def test_out_sample_degradation_is_flagged():
    flags = OverfitDetector().detect({"variant_id": "x", "params": "{}", "audit_status": "VALID", "in_sample_return": 0.2, "out_sample_return": 0.01, "trade_count": 10}, {})
    assert any("样本外" in flag for flag in flags)


def test_parameter_boundary_is_flagged():
    flags = OverfitDetector().detect({"variant_id": "x", "params": "{'window': 20}", "audit_status": "VALID", "in_sample_return": 0.1, "out_sample_return": 0.1, "trade_count": 10}, {"window": [20, 30]})
    assert any("搜索边界" in flag for flag in flags)


def test_research_cli_can_run():
    cmd = [
        sys.executable,
        "cli.py",
        "research",
        "--direction",
        "中国神华周线布林低吸波段策略，偏稳健，控制回撤",
        "--symbol",
        "601088.SH",
        "--data",
        "data/sample/601088.csv",
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "Research Agent V2 完成" in result.stdout


def test_final_research_report_generated(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = ResearchLoop().run("中国神华周线布林低吸波段策略，偏稳健，控制回撤", "601088.SH", "data/sample/601088.csv")
    path = Path(result.report_path) / "final_research_report.md"
    assert path.exists()
    assert "Final Research Report" in path.read_text(encoding="utf-8")


def test_next_round_suggestions_generated(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    result = ResearchLoop().run("中国神华周线布林低吸波段策略，偏稳健，控制回撤", "601088.SH", "data/sample/601088.csv")
    path = Path(result.report_path) / "next_round_suggestions.md"
    assert path.exists()
    assert "Next Round Suggestions" in path.read_text(encoding="utf-8")


def test_research_output_contains_required_files(monkeypatch):
    monkeypatch.chdir(ROOT)
    result = ResearchLoop().run("中国神华周线布林低吸波段策略，偏稳健，控制回撤", "601088.SH", "data/sample/601088.csv")
    files = {p.name for p in Path(result.report_path).iterdir() if p.is_file()}
    assert {
        "research_plan.md",
        "hypothesis.md",
        "strategy_variants.csv",
        "search_space.json",
        "experiment_results.csv",
        "ranked_results.csv",
        "overfit_report.md",
        "stability_report.md",
        "next_round_suggestions.md",
        "final_research_report.md",
    }.issubset(files)


def test_research_search_space_json_is_valid(monkeypatch):
    monkeypatch.chdir(ROOT)
    result = ResearchLoop().run("中国神华周线布林低吸波段策略，偏稳健，控制回撤", "601088.SH", "data/sample/601088.csv")
    data = json.loads((Path(result.report_path) / "search_space.json").read_text(encoding="utf-8"))
    assert "window" in data


def test_research_ranked_results_only_valid(monkeypatch):
    monkeypatch.chdir(ROOT)
    result = ResearchLoop().run("中国神华周线布林低吸波段策略，偏稳健，控制回撤", "601088.SH", "data/sample/601088.csv")
    with (Path(result.report_path) / "ranked_results.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            assert row["audit_status"] == "VALID"
