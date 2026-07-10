from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from intake.adaptive.answer_parser import AnswerParser
from intake.adaptive.adaptive_interview_agent import AdaptiveInterviewAgent
from intake.adaptive.question_tree import QuestionTree
from intake.adaptive.research_readiness_checker import ResearchReadinessChecker


ROOT = Path(__file__).resolve().parents[1]


def test_intake_chat_cli_starts():
    result = subprocess.run([sys.executable, "cli.py", "intake-chat"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "Adaptive Intake" in result.stdout


def test_china_shenhua_resolves_symbol():
    assert AnswerParser().parse("我想做中国神华")["symbols"] == ["601088.SH"]


def test_drawdown_buy_triggers_entry_clarification():
    fields = AnswerParser().parse("中国神华跌多了买")
    questions = QuestionTree().next_questions(fields)
    assert any(qid == "entry_swing" for qid, _ in questions)


def test_grid_uses_grid_question_tree():
    questions = QuestionTree().next_questions(AnswerParser().parse("红利ETF网格"))
    assert any(qid == "grid_step" for qid, _ in questions)
    assert not any("布林" in question for _, question in questions)


def test_rotation_uses_rotation_question_tree():
    questions = QuestionTree().next_questions(AnswerParser().parse("煤炭银行电力轮动"))
    assert any(qid == "rotation_pool" for qid, _ in questions)
    assert not any(qid == "exit" for qid, _ in questions)


def test_stock_selection_uses_selection_tree():
    questions = QuestionTree().next_questions(AnswerParser().parse("高股息低波动选股"))
    assert any(qid == "selection_factor" for qid, _ in questions)


def test_weekly_and_hour_parse():
    fields = AnswerParser().parse("周线和1小时都研究")
    assert {"1w", "1h"}.issubset(set(fields["timeframes"]))


def test_10min_parse():
    assert AnswerParser().parse("10分钟布林低吸")["timeframes"] == ["10m"]


def test_conservative_parse():
    fields = AnswerParser().parse("偏稳健，控制回撤")
    assert fields["risk_preference"] == "conservative"
    assert fields["risk_control"]["max_drawdown"] == 0.15


def test_low_frequency_parse():
    fields = AnswerParser().parse("不要太频繁交易")
    assert fields["constraints"]["trade_count_penalty"] is True


def test_max_drawdown_parse():
    fields = AnswerParser().parse("最大回撤别超过15%")
    assert fields["risk_control"]["max_drawdown"] == 0.15


def test_buy_20_percent_parse():
    fields = AnswerParser().parse("每次买20%")
    assert fields["sizing_logic"] == "固定比例仓位"
    assert fields["sizing_percent"] == 0.2


def test_future_qmt_triggers_risk_note():
    fields = AnswerParser().parse("以后想接QMT")
    assert fields["live_intent"] == "future_qmt"
    assert "QMT" in fields["qmt_safety_note"]


def test_incomplete_idea_below_70():
    result = AdaptiveInterviewAgent().run("我想做神华")
    assert result.artifacts["completeness_score"] < 70


def test_complete_idea_above_70():
    result = AdaptiveInterviewAgent().run("中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究")
    assert result.artifacts["completeness_score"] >= 70


def test_unconfirmed_research_ready_false():
    result = AdaptiveInterviewAgent().run("中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究")
    assert result.artifacts["research_ready"] is False


def test_confirmed_research_ready_true():
    result = AdaptiveInterviewAgent().run("中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究", confirm=True)
    assert result.artifacts["research_ready"] is True


def test_conversation_log_generated():
    result = AdaptiveInterviewAgent().run("中国神华跌多了买")
    assert (Path(result.report_path) / "conversation_log.md").exists()


def test_interview_state_generated():
    result = AdaptiveInterviewAgent().run("中国神华跌多了买")
    assert (Path(result.report_path) / "interview_state.json").exists()


def test_strategy_requirement_generated():
    result = AdaptiveInterviewAgent().run("中国神华跌多了买")
    assert (Path(result.report_path) / "strategy_requirement.json").exists()


def test_strategy_dsl_generated():
    result = AdaptiveInterviewAgent().run("中国神华跌多了买")
    assert (Path(result.report_path) / "strategy_dsl.yaml").exists()


def test_confirmation_summary_generated():
    result = AdaptiveInterviewAgent().run("中国神华跌多了买")
    assert (Path(result.report_path) / "confirmation_summary.md").exists()


def test_confirmation_summary_uses_student_friendly_language():
    result = AdaptiveInterviewAgent().run("我想做中国神华，跌多了买，涨回去卖，控制回撤")
    text = (Path(result.report_path) / "confirmation_summary.md").read_text(encoding="utf-8")
    assert "买入条件：还需要你补充" in text
    assert "卖出条件：涨回布林中轨附近时考虑卖出" in text
    assert "最大可接受回撤：15%" in text


def test_confirmation_summary_hides_internal_component_names():
    result = AdaptiveInterviewAgent().run("我想做中国神华，跌多了买，涨回去卖，控制回撤")
    text = (Path(result.report_path) / "confirmation_summary.md").read_text(encoding="utf-8")
    assert "NEEDS_ENTRY_CLARIFICATION" not in text
    assert "BollMiddleExit" not in text
    assert "{'max_drawdown': 0.15}" not in text


def test_fuzzy_idea_not_research_ready():
    result = AdaptiveInterviewAgent().run("我想赚钱")
    state = json.loads((Path(result.report_path) / "interview_state.json").read_text(encoding="utf-8"))
    assert state["research_ready"] is False


def test_old_intake_still_available():
    result = subprocess.run([sys.executable, "cli.py", "intake", "--idea", "中国神华跌多了买，涨回去卖"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert "report_path:" in result.stdout


def test_readme_mentions_intake_chat():
    assert "intake-chat" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_quick_start_mentions_intake_chat():
    assert "intake-chat" in (ROOT / "QUICK_START_FOR_STUDENTS.md").read_text(encoding="utf-8")


def test_course_plan_mentions_adaptive_intake():
    assert "Adaptive Intake" in (ROOT / "COURSE_DELIVERY_PLAN.md").read_text(encoding="utf-8")


def test_grid_tree_does_not_ask_boll_question():
    questions = QuestionTree().next_questions(AnswerParser().parse("网格策略，跌5%加仓，涨5%减仓"))
    assert not any("布林" in question for _, question in questions)


def test_rotation_tree_does_not_ask_single_symbol_exit():
    questions = QuestionTree().next_questions(AnswerParser().parse("行业轮动"))
    assert not any(qid == "exit" for qid, _ in questions)


def test_readiness_checker_requires_confirmation():
    score, ready, missing = ResearchReadinessChecker().score(
        {
            "symbols": ["601088.SH"],
            "strategy_pattern": "swing",
            "timeframes": ["1w"],
            "entry_logic": "BollLowerEntry",
            "exit_logic": "BollMiddleExit",
            "sizing_logic": "固定比例仓位",
            "risk_control": {"max_drawdown": 0.15},
            "objective": {"primary": "calmar"},
        },
        user_confirmed=False,
    )
    assert score == 100
    assert ready is False
    assert missing == []


def test_intake_chat_confirm_cli_sets_ready():
    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "intake-chat",
            "--idea",
            "中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
            "--confirm",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "可进入 Research Agent" in result.stdout


def test_grid_step_parse():
    fields = AnswerParser().parse("红利ETF网格，跌5%加仓，涨5%减仓")
    assert fields["grid"] == {"buy_step": 0.05, "sell_step": 0.05}
