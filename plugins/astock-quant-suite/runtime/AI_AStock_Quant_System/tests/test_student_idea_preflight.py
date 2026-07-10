from __future__ import annotations

from pathlib import Path

from services.student_idea_preflight_service import StudentIdeaPreflightService


def test_student_idea_preflight_ready_for_complete_astock_idea(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentIdeaPreflightService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        session_id="alice",
        case_id="shenhua-weekly",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_STUDENT_WORKFLOW"
    assert result.artifacts["can_run_student_workflow"] is True
    assert result.artifacts["safe_to_copy"] is True
    assert "student-workflow" in result.artifacts["next_command"]
    assert "--session-id alice" in result.artifacts["next_command"]
    assert result.artifacts["parsed"]["resolved_symbol"] == "601088.SH"
    assert result.artifacts["backtest_plan"]["status"] == "VALID"
    assert Path(result.report_path, "STUDENT_IDEA_PREFLIGHT.md").exists()
    assert Path(result.report_path, "student_idea_cards.json").exists()


def test_student_idea_preflight_clarifies_vague_idea(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentIdeaPreflightService().run(idea="我想做神华")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "NEEDS_CLARIFICATION"
    assert result.artifacts["can_run_student_workflow"] is False
    assert "intake-chat" in result.artifacts["next_command"]
    assert result.artifacts["clarifying_questions"]
    assert any(item["id"] == "idea_incomplete" for item in result.artifacts["warnings"])


def test_student_idea_preflight_rejects_crypto_for_astock_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentIdeaPreflightService().run(idea="BTC 1小时突破策略，未来接交易所实盘")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "WRONG_ASSET_VERSION"
    assert result.artifacts["can_run_student_workflow"] is False
    assert any(item["id"] == "wrong_asset_version" for item in result.artifacts["blockers"])
    assert "数字货币版本需要单独 workflow" in result.artifacts["summary"]


def test_student_idea_preflight_blocks_invalid_archetype_timeframe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentIdeaPreflightService().run(idea="煤炭银行电力1小时轮动，按强弱切换，控制回撤")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_BACKTEST_PLAN"
    assert result.artifacts["can_run_student_workflow"] is False
    assert any("不支持 1h 周期" in item["message"] for item in result.artifacts["blockers"])
