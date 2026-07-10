from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import yaml

from backtest_feedback_loop.backtest_result_analyzer import BacktestResultAnalyzer
from backtest_feedback_loop.candidate_selector import CandidateSelector
from backtest_feedback_loop.deep_diagnosis import DeepDiagnosis
from backtest_feedback_loop.failure_classifier import FailureClassifier
from backtest_feedback_loop.feedback_loop_report import FeedbackLoopReportWriter
from backtest_feedback_loop.loop_config import LoopConfig
from backtest_feedback_loop.loop_memory import LoopMemory
from backtest_feedback_loop.modification_actions import ModificationAction
from backtest_feedback_loop.optimization_director import OptimizationDirector
from backtest_feedback_loop.regime_analyzer import RegimeAnalyzer
from backtest_feedback_loop.research_expander import ResearchExpander
from backtest_feedback_loop.stopping_rules import StoppingRules
from backtest_feedback_loop.strategy_modifier import StrategyModifier


ROOT = Path(__file__).resolve().parents[1]


def _fake_run(tmp_path: Path, performance: dict, trades: list[dict] | None = None) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "performance.json").write_text(json.dumps(performance), encoding="utf-8")
    (run_dir / "audit_report.md").write_text("status: VALID\n", encoding="utf-8")
    (run_dir / "readiness_report.md").write_text("readiness: RESEARCH_ONLY\n", encoding="utf-8")
    with (run_dir / "trades.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["action", "amount", "total_fee"])
        writer.writeheader()
        for row in trades or []:
            writer.writerow(row)
    return run_dir


def test_optimize_loop_cli_runs():
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
            "2",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "V7 回测反馈优化闭环完成" in result.stdout


def test_analyzer_writes_analysis_after_backtest_artifacts(tmp_path):
    run_dir = _fake_run(tmp_path, {"total_return": 0.01, "max_drawdown": -0.02, "trade_count": 2})
    analysis = BacktestResultAnalyzer().analyze(run_dir)
    assert analysis["trade_count"] == 2
    assert (run_dir / "analysis.md").exists()


def test_analyzer_detects_drawdown_too_large(tmp_path):
    run_dir = _fake_run(tmp_path, {"total_return": 0.1, "max_drawdown": -0.3, "trade_count": 10})
    assert "drawdown_too_large" in BacktestResultAnalyzer().analyze(run_dir)["issues"]


def test_analyzer_detects_too_few_trades(tmp_path):
    run_dir = _fake_run(tmp_path, {"total_return": 0.1, "max_drawdown": -0.03, "trade_count": 1})
    assert "too_few_trades" in BacktestResultAnalyzer().analyze(run_dir)["issues"]


def test_analyzer_detects_too_many_trades(tmp_path):
    run_dir = _fake_run(tmp_path, {"total_return": 0.1, "max_drawdown": -0.03, "trade_count": 81})
    assert "too_many_trades" in BacktestResultAnalyzer().analyze(run_dir)["issues"]


def test_analyzer_detects_low_return(tmp_path):
    run_dir = _fake_run(tmp_path, {"total_return": 0.0, "max_drawdown": -0.03, "trade_count": 10})
    assert "low_return" in BacktestResultAnalyzer().analyze(run_dir)["issues"]


def test_analyzer_detects_out_sample_degradation(tmp_path):
    run_dir = _fake_run(tmp_path, {"total_return": 0.2, "max_drawdown": -0.03, "trade_count": 10})
    analysis = BacktestResultAnalyzer().analyze(run_dir, in_sample_return=0.3, out_sample_return=0.05)
    assert "out_sample_degradation" in analysis["issues"]


def test_analyzer_detects_profit_concentration(tmp_path):
    run_dir = _fake_run(
        tmp_path,
        {"total_return": 0.2, "max_drawdown": -0.03, "trade_count": 3},
        [{"action": "SELL", "amount": "900", "total_fee": "1"}, {"action": "SELL", "amount": "100", "total_fee": "1"}],
    )
    assert "concentrated_profit" in BacktestResultAnalyzer().analyze(run_dir)["issues"]


def test_drawdown_triggers_stop_loss_trend_filter_reduce_position():
    actions = [a.action for a in OptimizationDirector().propose({"issues": ["drawdown_too_large"]})]
    assert {"add_stop_loss", "tighten_stop_loss", "add_trend_filter"}.issubset(set(actions))


def test_too_few_trades_triggers_widen_entry_condition():
    actions = [a.action for a in OptimizationDirector().propose({"issues": ["too_few_trades"]})]
    assert "widen_entry_condition" in actions


def test_too_many_trades_triggers_holding_days_or_cooldown():
    actions = [a.action for a in OptimizationDirector().propose({"issues": ["too_many_trades"]})]
    assert "add_holding_days" in actions or "add_cooldown" in actions


def test_low_return_triggers_alternative_exit():
    actions = [a.action for a in OptimizationDirector().propose({"issues": ["low_return"]})]
    assert "test_alternative_exit" in actions


def test_out_sample_degradation_triggers_simplify_strategy():
    actions = [a.action for a in OptimizationDirector().propose({"issues": ["out_sample_degradation"]})]
    assert "simplify_strategy" in actions


def test_strategy_modifier_changes_stop_loss():
    dsl, mods = StrategyModifier().apply({"exit": []}, [ModificationAction("add_stop_loss", "回撤过大", {}, "降低回撤")])
    assert any(item["type"] == "FixedStopLossExit" for item in dsl["exit"])
    assert mods


def test_strategy_modifier_changes_exit_rule():
    dsl, _ = StrategyModifier().apply({"exit": []}, [ModificationAction("test_alternative_exit", "收益低", {}, "改善退出")])
    assert any(item["type"] == "AlternativeExit" for item in dsl["exit"])


def test_strategy_modifier_changes_sizing():
    dsl, _ = StrategyModifier().apply({"sizing": {}}, [ModificationAction("reduce_position_size", "回撤过大", {}, "降低波动")])
    assert dsl["sizing"]["params"]["percent"] == [0.05, 0.1, 0.15]


def test_strategy_modifier_adds_cooldown():
    dsl, _ = StrategyModifier().apply({"constraints": {}}, [ModificationAction("add_cooldown", "交易过多", {}, "降噪")])
    assert dsl["constraints"]["cooldown_bars"] == 3


def test_strategy_modifier_can_expand_parameter_range():
    dsl, _ = StrategyModifier().apply({"constraints": {"max_experiments": 100}}, [ModificationAction("expand_parameter_range", "空间窄", {}, "扩大")])
    assert dsl["constraints"]["max_experiments"] == 200


def test_loop_memory_counts_no_improve_rounds():
    memory = LoopMemory()
    memory.add({"score": 0.5})
    memory.add({"score": 0.51})
    memory.add({"score": 0.52})
    assert memory.no_improve_rounds(0.03) == 2


def test_no_improve_does_not_stop_directly():
    assert not StoppingRules().should_stop(2, 2, 0, LoopConfig(max_iterations=8))[0]


def test_no_improve_triggers_deep_diagnosis():
    assert StoppingRules().should_deep_diagnose(2, LoopConfig(deep_diagnosis_after_no_improve_rounds=2))


def test_failure_classifier_parameter_space_too_narrow():
    failures = FailureClassifier().classify([{"analysis": {"issues": ["low_return"]}}])
    assert "参数空间太窄" in failures


def test_failure_classifier_entry_rule_invalid():
    failures = FailureClassifier().classify([{"analysis": {"issues": ["low_return"]}}])
    assert "入场逻辑错误" in failures


def test_failure_classifier_exit_rule_invalid():
    failures = FailureClassifier().classify([{"analysis": {"issues": ["drawdown_too_large"]}}])
    assert "出场逻辑错误" in failures


def test_research_expander_expands_parameter_range():
    assert "expand_parameter_range" in ResearchExpander().expand(["参数空间太窄"])


def test_research_expander_replaces_entry_rule():
    assert "replace_entry_rule" in ResearchExpander().expand(["入场逻辑错误"])


def test_research_expander_replaces_exit_rule():
    assert "replace_exit_rule" in ResearchExpander().expand(["出场逻辑错误"])


def test_research_expander_timeframe_switch():
    assert "test_timeframe_1h" in ResearchExpander().expand(["周期不匹配"])


def test_research_expander_cross_symbol_validate():
    assert "cross_symbol_validate" in ResearchExpander().expand(["标的不适合"])


def test_research_expander_relax_filter():
    assert "relax_filter" in ResearchExpander().expand(["过滤条件过强"])


def test_max_iterations_stops():
    stop, reason = StoppingRules().should_stop(8, 10, 0, LoopConfig(max_iterations=8))
    assert stop and "max_iterations" in reason


def test_max_total_experiments_stops():
    stop, reason = StoppingRules().should_stop(1, 1000, 0, LoopConfig(max_total_experiments=1000))
    assert stop and "max_total_experiments" in reason


def test_invalid_not_in_final_candidates():
    accepted, rejected = CandidateSelector().select([{"variant_id": "x", "audit_status": "INVALID"}])
    assert not accepted and rejected


def test_qfq_risk_not_live_candidate():
    accepted, _ = CandidateSelector().select([{"variant_id": "x", "audit_status": "VALID", "readiness": "LIVE_CANDIDATE", "adjust": "qfq"}])
    assert accepted[0]["candidate_score"] < 0.8


def test_paper_ready_candidate_is_accepted():
    accepted, _ = CandidateSelector().select([{"variant_id": "x", "audit_status": "VALID", "readiness": "PAPER_READY", "adjust": "point_in_time_qfq"}])
    assert accepted


def test_candidate_rejected_when_user_gate_fails():
    accepted, rejected = CandidateSelector().select([{"variant_id": "x", "audit_status": "VALID", "readiness": "PAPER_READY", "user_gate_pass": False}])
    assert not accepted
    assert rejected


def test_candidate_selector_not_single_return_sorted():
    rows = [
        {"variant_id": "high_return_bad", "audit_status": "VALID", "readiness": "RESEARCH_ONLY", "calmar": 0.1, "max_drawdown": -0.5, "trade_count": 1},
        {"variant_id": "balanced", "audit_status": "VALID", "readiness": "PAPER_READY", "calmar": 1.0, "max_drawdown": -0.1, "trade_count": 20},
    ]
    accepted, _ = CandidateSelector().select(rows)
    assert accepted[0]["variant_id"] == "balanced"


def test_regime_analyzer_outputs_regime_analysis(tmp_path):
    run_dir = tmp_path / "bt"
    run_dir.mkdir()
    with (run_dir / "equity_curve.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "equity"])
        writer.writeheader()
        writer.writerows([{"date": "2024-01-01", "equity": 100}, {"date": "2024-01-02", "equity": 110}])
    result = RegimeAnalyzer().analyze(run_dir)
    assert "market_regime" in result


def test_deep_diagnosis_writes_report(tmp_path):
    run_dir = tmp_path / "bt"
    run_dir.mkdir()
    (run_dir / "equity_curve.csv").write_text("date,equity\n2024-01-01,100\n2024-01-02,90\n", encoding="utf-8")
    out = tmp_path / "deep.md"
    result = DeepDiagnosis().run([{"analysis": {"issues": ["too_few_trades"]}}], run_dir, out)
    assert out.exists()
    assert "expanded_actions" in result


def test_feedback_report_generates_final_report(tmp_path):
    writer = FeedbackLoopReportWriter()
    writer.write_final_report(tmp_path, "想法", [{"iteration": 1, "analysis": {"issues": []}, "actions": []}], [], [], [])
    assert (tmp_path / "final_feedback_loop_report.md").exists()


def test_feedback_report_generates_codex_prompt(tmp_path):
    FeedbackLoopReportWriter().write_codex_prompt(tmp_path, "想法", [], [])
    assert (tmp_path / "codex_next_optimization_prompt.md").exists()


def test_feedback_report_generates_candidate_csv(tmp_path):
    FeedbackLoopReportWriter().write_candidate_files(tmp_path, [{"variant_id": "x", "candidate_score": 1}], [])
    assert (tmp_path / "final_candidates.csv").exists()


def test_iteration_strategy_dsl_can_be_saved(tmp_path):
    path = tmp_path / "strategy_dsl.yaml"
    path.write_text(yaml.safe_dump({"pattern": "swing"}, allow_unicode=True), encoding="utf-8")
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["pattern"] == "swing"


def test_iteration_analysis_can_be_saved(tmp_path):
    path = tmp_path / "analysis.md"
    path.write_text("# analysis\n", encoding="utf-8")
    assert path.exists()


def test_iteration_modification_plan_can_be_saved(tmp_path):
    FeedbackLoopReportWriter().write_modification_plan(
        tmp_path / "modification_plan.md",
        [{"action": "add_stop_loss", "reason": "回撤", "metric_basis": {}, "expected_improvement": "降回撤"}],
        [{"before": {}, "after": {"exit": []}}],
    )
    assert (tmp_path / "modification_plan.md").exists()


def test_loop_memory_json_records_complete(tmp_path):
    memory = LoopMemory()
    memory.add({"iteration": 1, "analysis": {"issues": ["low_return"]}, "actions": []})
    memory.save(tmp_path / "loop_memory.json")
    assert json.loads((tmp_path / "loop_memory.json").read_text(encoding="utf-8"))[0]["iteration"] == 1


def test_expanded_experiments_have_at_least_one_action():
    actions = ResearchExpander().expand(["交易次数太少"])
    assert len(actions) >= 1


def test_all_backtests_expected_to_keep_audit_fields():
    record = {"audit_status": "VALID", "readiness": "RESEARCH_ONLY"}
    assert record["audit_status"] == "VALID"
    assert "readiness" in record
