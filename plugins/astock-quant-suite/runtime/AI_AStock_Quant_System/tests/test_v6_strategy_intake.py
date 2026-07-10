import json
import subprocess
import sys
from pathlib import Path

import yaml

from intake.completeness_checker import CompletenessChecker
from intake.dsl_builder import DSLBuilder
from intake.intent_parser import IntentParser
from intake.prompt_builder import PromptBuilder
from intake.strategy_intake_agent import StrategyIntakeAgent


ROOT = Path(__file__).resolve().parents[1]


def checked(idea: str):
    return CompletenessChecker().score(IntentParser().parse(idea))


def test_china_shenhua_buy_drop_sell_rebound_is_swing():
    assert checked("中国神华跌多了买涨回去卖").strategy_pattern == "swing"


def test_dividend_etf_grid_is_grid():
    req = checked("红利ETF网格")
    assert req.strategy_pattern == "grid"


def test_sector_rotation_is_rotation():
    assert checked("煤炭银行电力轮动").strategy_pattern == "rotation"


def test_high_dividend_low_vol_selection_is_stock_selection():
    assert checked("高股息低波动选股").strategy_pattern == "stock_selection"


def test_one_hour_detected_as_1h():
    assert checked("中国神华1小时布林低吸").timeframe == "1h"


def test_ten_minutes_detected_as_10m():
    assert checked("中国神华10分钟波段").timeframe == "10m"


def test_qfq_phrase_defaults_to_point_in_time_qfq():
    assert checked("中国神华前复权布林低吸").data_adjustment == "point_in_time_qfq"


def test_vague_idea_score_below_70():
    req = checked("我想赚钱")
    assert req.completeness_score < 70


def test_complete_idea_score_at_least_70():
    req = checked("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    assert req.completeness_score >= 70


def test_unanswered_questions_generated():
    req = checked("中国神华跌多了买")
    assert req.unanswered_questions


def test_strategy_requirement_json_generated():
    result = StrategyIntakeAgent().run("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    path = Path(result.report_path) / "strategy_requirement.json"
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["symbols"] == ["601088.SH"]


def test_strategy_dsl_yaml_generated():
    result = StrategyIntakeAgent().run("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    path = Path(result.report_path) / "strategy_dsl.yaml"
    assert path.exists()
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["pattern"] == "swing"


def test_codex_research_prompt_generated():
    result = StrategyIntakeAgent().run("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    path = Path(result.report_path) / "codex_research_prompt.md"
    assert path.exists()


def test_prompt_contains_symbol_timeframe_entry_exit_risk():
    req = checked("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    prompt = PromptBuilder().build(req)
    assert "601088.SH" in prompt
    assert "1h" in prompt
    assert "入场" in prompt
    assert "出场" in prompt
    assert "风险" in prompt


def test_dsl_can_feed_research_agent_shape():
    req = checked("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    dsl = DSLBuilder().build(req)
    assert dsl["symbols"] == ["601088.SH"]
    assert dsl["timeframe"] == "1h"
    assert dsl["adjust"] == "point_in_time_qfq"


def test_intraday_ma5_grid_dsl_uses_small_grid_steps():
    req = checked("中国神华10分钟MA5网格，分批买卖")
    dsl = DSLBuilder().build(req)
    assert dsl["entry"]["params"]["grid_step"] == [0.001, 0.002, 0.003, 0.004, 0.005]


def test_incomplete_strategy_cannot_enter_research():
    result = StrategyIntakeAgent().run("我想赚钱")
    assert result.status == "INVALID"
    assert result.artifacts["readiness_for_research"] is False


def test_conservative_preference_sets_max_drawdown_constraint():
    req = checked("中国神华1小时布林低吸，涨回中轨卖，固定比例仓位，稳健控制回撤")
    assert req.risk_control["max_drawdown"] == 0.15


def test_user_return_and_drawdown_gate_extracted():
    req = checked("只有年化大于20%，回撤小于10%的策略才有模拟盘价值")
    assert req.objective["min_annual_return"] == 0.2
    assert req.risk_control["max_drawdown"] == 0.1


def test_low_frequency_preference_sets_trade_count_penalty():
    req = checked("中国神华跌多了买涨回去卖，不要太频繁交易")
    assert req.constraints["trade_count_penalty"] is True
    assert req.constraints["min_holding_period"]


def test_live_intent_triggers_qmt_safety_note():
    req = checked("中国神华1小时布林低吸，最终想接QMT实盘")
    assert "QMT" in req.qmt_safety_note


def test_cli_intake_can_run():
    result = subprocess.run([sys.executable, "cli.py", "intake", "--idea", "我想做中国神华，跌多了买，涨回去卖，控制回撤，不要太频繁交易"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "report_path" in result.stdout


def test_cli_intake_interactive_lists_questions():
    result = subprocess.run([sys.executable, "cli.py", "intake", "--interactive"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "交互式澄清模式" in result.stdout


def test_intake_report_outputs_unanswered_questions_file():
    result = StrategyIntakeAgent().run("中国神华跌多了买")
    assert (Path(result.report_path) / "unanswered_questions.md").exists()
