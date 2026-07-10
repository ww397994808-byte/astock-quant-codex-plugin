from pathlib import Path

import yaml

from backtest_plans.plan_builder import BacktestPlanBuilder
from intake.intent_parser import IntentParser
from intake.strategy_intake_agent import StrategyIntakeAgent
from strategy_patterns.classifier import StrategyArchetypeClassifier


def req(idea: str):
    return IntentParser().parse(idea)


def test_archetype_classifier_detects_grid():
    spec = StrategyArchetypeClassifier().classify_requirement(req("红利ETF网格，分层买卖"))
    assert spec.archetype.value == "grid"
    assert spec.template_name == "grid"
    assert spec.qmt_allowed is True


def test_archetype_classifier_blocks_event_driven_without_point_in_time_events():
    spec = StrategyArchetypeClassifier().classify(None, "业绩预告事件驱动策略")
    assert spec.archetype.value == "event_driven"
    assert spec.qmt_allowed is False
    assert spec.template_name is None


def test_backtest_plan_for_weekly_swing_is_qmt_candidate_after_later_gates():
    plan = BacktestPlanBuilder().build(req("中国神华周线布林低吸，涨回中轨卖，固定比例仓位，控制回撤"))
    assert plan.status == "VALID"
    assert plan.template_name == "swing"
    assert plan.timeframe == "1w"
    assert plan.qmt_allowed is True
    assert "signal_causality" in plan.audit_required
    assert plan.execution_model["fill_bar"] == "next_bar_open"


def test_backtest_plan_rejects_intraday_rotation_timeframe():
    plan = BacktestPlanBuilder().build(req("煤炭银行电力1小时轮动"))
    assert plan.status == "INVALID"
    assert any("不支持 1h 周期" in item for item in plan.blockers)


def test_intake_writes_backtest_plan_yaml():
    result = StrategyIntakeAgent().run("中国神华周线布林低吸，涨回中轨卖，固定比例仓位，控制回撤")
    plan_path = Path(result.report_path) / "backtest_plan.yaml"
    assert plan_path.exists()
    data = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert data["strategy_pattern"] == "swing"
    assert data["execution_model"]["t_plus_1"] is True
