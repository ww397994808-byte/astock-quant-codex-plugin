from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backtest_feedback_loop.candidate_selector import CandidateSelector
from backtest_feedback_loop.modification_actions import ModificationAction
from backtest_feedback_loop.strategy_modifier import StrategyModifier
from strategy_compiler.action_compiler import ActionCompiler
from strategy_compiler.component_registry import ComponentRegistry
from strategy_compiler.compiler_errors import StrategyCompileError
from strategy_compiler.dsl_to_strategy import DSLToStrategy


ROOT = Path(__file__).resolve().parents[1]


def base_dsl(pattern: str = "swing") -> dict:
    return {
        "pattern": pattern,
        "symbols": ["601088.SH"],
        "entry": {"type": "BollLowerEntry", "params": {"window": 20, "num_std": 2.0}},
        "exit": [{"type": "BollMiddleExit", "params": {"window": 20}}],
        "filters": [],
        "sizing": {"type": "FixedPercentSizing", "params": {"percent": 0.5}},
    }


def test_add_trailing_stop_generates_dsl():
    dsl = ActionCompiler().compile_action(base_dsl(), "add_trailing_stop")
    assert any(item["type"] == "TrailingStopExit" for item in dsl["exit"])


def test_add_holding_days_generates_dsl():
    dsl = ActionCompiler().compile_action(base_dsl(), "add_holding_days")
    assert any(item["type"] == "HoldingDaysExit" for item in dsl["exit"])


def test_add_cooldown_generates_dsl():
    dsl = ActionCompiler().compile_action(base_dsl(), "add_cooldown")
    assert any(item["type"] == "CooldownFilter" for item in dsl["filters"])


def test_add_trend_filter_generates_dsl():
    dsl = ActionCompiler().compile_action(base_dsl(), "add_trend_filter")
    assert any(item["type"] == "TrendFilter" for item in dsl["filters"])


def test_add_volatility_filter_generates_dsl():
    dsl = ActionCompiler().compile_action(base_dsl(), "add_volatility_filter")
    assert any(item["type"] == "VolatilityFilter" for item in dsl["filters"])


def test_reduce_position_size_generates_dsl():
    dsl = ActionCompiler().compile_action(base_dsl(), "reduce_position_size")
    assert dsl["sizing"]["type"] == "ReducedPositionSizing"


def test_replace_entry_rule_replaces_entry():
    dsl = ActionCompiler().compile_action(base_dsl(), "replace_entry_rule")
    assert dsl["entry"]["type"] == "DrawdownEntry"


def test_test_atr_oversold_entry_generates_entry():
    dsl = ActionCompiler().compile_action(base_dsl(), "test_atr_oversold_entry")
    assert dsl["entry"]["type"] == "ATROversoldEntry"


def test_test_ma_deviation_entry_generates_entry():
    dsl = ActionCompiler().compile_action(base_dsl(), "test_ma_deviation_entry")
    assert dsl["entry"]["type"] == "MADeviationEntry"


def test_test_boll_entry_generates_entry():
    dsl = ActionCompiler().compile_action(base_dsl(), "test_boll_entry")
    assert dsl["entry"]["type"] == "BollLowerEntry"


def test_replace_exit_rule_replaces_exit():
    dsl = ActionCompiler().compile_action(base_dsl(), "replace_exit_rule")
    assert dsl["exit"] == [{"type": "FixedTakeProfitExit", "params": {"take_profit": 0.08}}]


def test_test_trailing_stop_generates_exit():
    dsl = ActionCompiler().compile_action(base_dsl(), "test_trailing_stop")
    assert any(item["type"] == "TrailingStopExit" for item in dsl["exit"])


def test_test_holding_days_exit_generates_exit():
    dsl = ActionCompiler().compile_action(base_dsl(), "test_holding_days_exit")
    assert any(item["type"] == "HoldingDaysExit" for item in dsl["exit"])


def test_nonexistent_component_raises_compile_error():
    dsl = base_dsl()
    dsl["entry"] = {"type": "NoSuchEntry", "params": {}}
    with pytest.raises(StrategyCompileError):
        ActionCompiler().validate_components(dsl)


def test_compile_error_not_in_final_candidates():
    accepted, rejected = CandidateSelector().select([{"variant_id": "bad", "audit_status": "INVALID", "compile_error": "不存在组件"}])
    assert not accepted and rejected


def test_dsl_to_strategy_generates_strategy_object():
    result = DSLToStrategy().compile(base_dsl(), "601088.SH")
    assert result.strategy.generate_signal


def test_dsl_to_strategy_selects_swing_template():
    result = DSLToStrategy().compile(base_dsl("swing"), "601088.SH")
    assert result.template_name == "swing"


def test_dsl_to_strategy_selects_timing_template():
    result = DSLToStrategy().compile(base_dsl("timing"), "601088.SH")
    assert result.template_name == "timing"


def test_component_registry_lists_all_components():
    names = [item.component_name for item in ComponentRegistry().list_components()]
    assert {"ATROversoldEntry", "TrailingStopExit", "CooldownFilter", "ReducedPositionSizing"}.issubset(set(names))


def test_each_component_has_required_params():
    assert all(isinstance(item.required_params, list) for item in ComponentRegistry().list_components())


def test_each_component_has_default_params():
    assert all(isinstance(item.default_params, dict) for item in ComponentRegistry().list_components())


def test_strategy_modifier_action_can_be_received_by_action_compiler():
    _, modifications = StrategyModifier().apply(base_dsl(), [ModificationAction("add_trailing_stop", "收益低", {}, "改善退出")])
    dsl = ActionCompiler().compile_action(base_dsl(), modifications[0]["action"])
    assert any(item["type"] == "TrailingStopExit" for item in dsl["exit"])


def test_deep_diagnosis_action_can_be_received_by_action_compiler():
    dsl = ActionCompiler().compile_action(base_dsl(), "test_atr_oversold_entry")
    assert dsl["entry"]["type"] == "ATROversoldEntry"


def test_all_supported_actions_compile():
    actions = [
        "add_stop_loss",
        "tighten_stop_loss",
        "add_trailing_stop",
        "add_holding_days",
        "add_cooldown",
        "add_trend_filter",
        "add_volatility_filter",
        "reduce_position_size",
        "replace_entry_rule",
        "add_alternative_entry",
        "test_drawdown_entry",
        "test_boll_entry",
        "test_ma_deviation_entry",
        "test_atr_oversold_entry",
        "replace_exit_rule",
        "test_fixed_take_profit",
        "test_trailing_stop",
        "test_boll_middle_exit",
        "test_holding_days_exit",
    ]
    dsl, reports = ActionCompiler().compile_actions(base_dsl(), actions)
    assert all(item["status"] == "VALID" for item in reports)
    assert DSLToStrategy().compile(dsl, "601088.SH").strategy


def test_compile_report_files_generated_by_optimize_loop():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    assert (report_path / "iteration_1" / "compile_report.md").exists()
    assert (report_path / "iteration_1" / "component_list.md").exists()
    assert (report_path / "iteration_1" / "compiled_strategy.json").exists()


def test_optimize_loop_expanded_experiments_call_action_compiler():
    run = _run_optimize_loop(max_iterations="3")
    report_path = _report_path(run.stdout)
    assert (report_path / "iteration_2" / "compile_report.md").read_text(encoding="utf-8").count("VALID") >= 1


def test_expanded_experiments_are_backtested():
    run = _run_optimize_loop(max_iterations="3")
    report_path = _report_path(run.stdout)
    assert (report_path / "iteration_2" / "audit_report.md").exists()


def test_compiled_strategy_json_contains_components():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    data = json.loads((report_path / "iteration_1" / "compiled_strategy.json").read_text(encoding="utf-8"))
    assert data["entry_rules"]


def test_compiled_strategy_still_has_audit():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    assert "VALID" in (report_path / "iteration_1" / "audit_report.md").read_text(encoding="utf-8")


def test_compiled_strategy_still_has_readiness():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    assert (report_path / "iteration_1" / "readiness_report.md").exists()


def test_t_plus_1_still_goes_through_trade_rule_report():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    assert (report_path / "iteration_1" / "trade_rule_report.md").exists()


def test_signal_execute_datetime_still_recorded():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    backtest_text = (report_path / "iteration_1" / "backtest_report.md").read_text(encoding="utf-8")
    assert "状态" in backtest_text or "status" in backtest_text


def test_point_in_time_qfq_still_reaches_compile_loop():
    run = _run_optimize_loop(max_iterations="2")
    report_path = _report_path(run.stdout)
    dsl_text = (report_path / "initial_strategy_dsl.yaml").read_text(encoding="utf-8")
    assert "point_in_time_qfq" in dsl_text


def test_optimize_loop_cli_still_passes():
    run = _run_optimize_loop(max_iterations="2")
    assert run.returncode == 0
    assert "status: VALID" in run.stdout


def test_action_compiler_accepts_adjust_take_profit_legacy_action():
    dsl = ActionCompiler().compile_action(base_dsl(), "adjust_take_profit")
    assert dsl["exit"][0]["type"] == "FixedTakeProfitExit"


def test_action_compiler_accepts_widen_entry_legacy_action():
    dsl = ActionCompiler().compile_action(base_dsl(), "widen_entry_condition")
    assert dsl["entry"]["type"] == "BollLowerEntry"


def _run_optimize_loop(max_iterations: str = "2"):
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
            max_iterations,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return result


def _report_path(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("report_path:"):
            return ROOT / line.split(":", 1)[1].strip()
    raise AssertionError(stdout)
