from __future__ import annotations

import json
from pathlib import Path

from services.student_control_center_service import StudentControlCenterService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def test_student_control_center_no_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentControlCenterService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "NO_WORKFLOW"
    assert "student-workflow" in result.artifacts["next_command"]
    assert result.artifacts["safe_to_copy"] is False
    assert Path(result.report_path, "STUDENT_CONTROL_CENTER.md").exists()


def test_student_control_center_uses_repair_dsl_when_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "symbol": "601088.SH",
            "timeframe": "1d",
            "adjust": "point_in_time_qfq",
            "next_actions": [],
        },
    )
    (run_dir / "STUDENT_REPAIR_DSL.yaml").write_text("pattern: timing\n", encoding="utf-8")

    result = StudentControlCenterService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_RESEARCH_STEP"
    assert "repair-dsl-backtest" in result.artifacts["next_command"]
    assert "--paper-observation --stage-check" in result.artifacts["next_command"]
    assert result.artifacts["safe_to_copy"] is True


def test_student_control_center_points_to_diagnostics_when_workflow_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {"status": "INVALID", "symbol": "601088.SH", "next_actions": [{"type": "fix_exit"}]},
    )

    result = StudentControlCenterService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "WORKFLOW_BLOCKED"
    assert "NEXT_ACTIONS.md" in result.artifacts["next_action"]
    assert any(card["id"] == "open_student_workflow" for card in result.artifacts["action_cards"])


def test_student_control_center_surfaces_paper_policy_card(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_dir = tmp_path / "reports" / "paper_20260629_1"
    _write_json(
        paper_dir / "paper_observation_policy_card.json",
        {
            "status": "INVALID",
            "strategy_pattern": "timing",
            "timeframe": "1d",
            "requirements": [
                {"metric": "observed_days", "actual": 100, "required": 20, "status": "PASS"},
                {"metric": "trade_count", "actual": 2, "required": 3, "status": "FAIL"},
                {"metric": "completed_rounds", "actual": 1, "required": 1, "status": "PASS"},
            ],
            "can_continue_qmt_readonly": False,
            "learner_message": "模拟观察证据还不够，先补齐失败项，不要进入 QMT 或实盘。",
        },
    )
    _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "symbol": "601088.SH",
            "steps": [
                {"step": "paper", "status": "INVALID", "report_path": str(paper_dir)},
            ],
        },
    )

    result = StudentControlCenterService().run()
    policy_cards = [card for card in result.artifacts["action_cards"] if card["id"] == "paper_observation_policy"]
    report = Path(result.report_path, "STUDENT_CONTROL_CENTER.md").read_text(encoding="utf-8")

    assert policy_cards
    assert policy_cards[0]["status"] == "INVALID"
    assert "trade_count" in policy_cards[0]["why"]
    assert policy_cards[0]["repair_hints"][0]["metric"] == "trade_count"
    assert "触发条件" in policy_cards[0]["repair_hints"][0]["advice"]
    assert result.artifacts["paper_observation_policy_card"]["can_continue_qmt_readonly"] is False
    assert result.artifacts["sources"]["paper_observation_policy_card"]["found"] is True
    assert "模拟观察政策卡" in report


def test_student_control_center_surfaces_backtest_assumption_card(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workflow_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "VALID",
            "session_id": "alice",
            "symbol": "601088.SH",
            "timeframe": "30m",
            "adjust": "point_in_time_qfq",
            "steps": [],
        },
    )
    _write_json(
        workflow_dir / "BACKTEST_ASSUMPTION_CARD.json",
        {
            "status": "WARN",
            "strategy_pattern": "intraday_timing",
            "timeframe": "30m",
            "execution_model": {
                "signal_timing": "bar_close",
                "fill_timing": "next_bar_open",
            },
            "learner_checks": [
                {"id": "intraday_data", "title": "分钟数据完整性", "status": "REQUIRED"},
                {"id": "astock_rules", "title": "A股交易规则", "status": "REQUIRED"},
            ],
            "promotion_policy": {"qmt_readonly_required": True},
        },
    )

    result = StudentControlCenterService().run(workflow=str(workflow_dir))
    assumption_cards = [card for card in result.artifacts["action_cards"] if card["id"] == "backtest_assumption"]
    report = Path(result.report_path, "STUDENT_CONTROL_CENTER.md").read_text(encoding="utf-8")

    assert assumption_cards
    assert assumption_cards[0]["status"] == "WARN"
    assert "intraday_timing" in assumption_cards[0]["why"]
    assert "分钟数据完整性" in assumption_cards[0]["learner_checks"]
    assert result.artifacts["backtest_assumption_card"]["strategy_pattern"] == "intraday_timing"
    assert result.artifacts["sources"]["backtest_assumption_card"]["found"] is True
    assert "回测假设卡" in report


def test_student_control_center_uses_policy_action_plan_when_no_repair_dsl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workflow_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "symbol": "601088.SH",
            "steps": [],
        },
    )
    _write_json(
        workflow_dir / "STUDENT_POLICY_ACTION_PLAN.json",
        {
            "status": "NEEDS_RESEARCH_REPAIR",
            "failed_metrics": ["trade_count"],
            "repair_hints": [{"metric": "trade_count", "advice": "调触发条件"}],
            "next_commands": [
                "python3 cli.py student-workflow --idea \"x\" --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq --auto-refine"
            ],
        },
    )

    result = StudentControlCenterService().run(workflow=str(workflow_dir))

    assert result.status == "VALID"
    assert result.artifacts["current_stage"] == "POLICY_ACTION_PLAN_READY"
    assert result.artifacts["safe_to_copy"] is True
    assert "student-workflow" in result.artifacts["next_command"]
    assert any(card["id"] == "student_policy_action_plan" for card in result.artifacts["action_cards"])


def test_student_control_center_explicit_workflow_overrides_latest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    older = _write_json(
        tmp_path / "reports" / "student_workflow_20260628_1" / "workflow_manifest.json",
        {"status": "INVALID", "symbol": "601088.SH", "timeframe": "1d", "adjust": "point_in_time_qfq"},
    )
    (older / "STUDENT_REPAIR_DSL.yaml").write_text("pattern: timing\n", encoding="utf-8")
    _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {"status": "VALID", "symbol": "600000.SH"},
    )

    result = StudentControlCenterService().run(workflow=str(older))

    assert result.artifacts["current_stage"] == "REPAIR_DSL_READY"
    assert "student_workflow_20260628_1" in result.artifacts["next_command"]
    assert result.artifacts["sources"]["student_workflow"]["run_dir"].endswith("student_workflow_20260628_1")


def test_student_control_center_explicit_workflow_does_not_mix_unscoped_latest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workflow = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {"status": "INVALID", "symbol": "601088.SH"},
    )
    _write_json(
        tmp_path / "reports" / "repair_dsl_backtest_20260629_1" / "REPAIR_DSL_PROMOTION.json",
        {"status": "READY_FOR_QMT_READONLY", "session_id": "other"},
    )
    _write_json(
        tmp_path / "reports" / "qmt_readiness_dashboard_20260629_1" / "QMT_READINESS_DASHBOARD.json",
        {"status": "BLOCKED", "session_id": "other", "summary": "other session blocker"},
    )

    result = StudentControlCenterService().run(workflow=str(workflow))

    assert result.artifacts["sources"]["repair_dsl_promotion"]["found"] is False
    assert result.artifacts["sources"]["qmt_readiness_dashboard"]["found"] is False
    assert all(card["id"] != "open_qmt_next_actions" for card in result.artifacts["action_cards"])


def test_student_control_center_filters_latest_by_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session_run = _write_json(
        tmp_path / "reports" / "student_workflow_20260628_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "session_id": "alice",
            "symbol": "601088.SH",
            "timeframe": "1d",
            "adjust": "point_in_time_qfq",
        },
    )
    (session_run / "STUDENT_REPAIR_DSL.yaml").write_text("pattern: timing\n", encoding="utf-8")
    _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "VALID",
            "session_id": "bob",
            "symbol": "600000.SH",
        },
    )

    result = StudentControlCenterService().run(session_id="alice")

    assert result.status == "VALID"
    assert result.artifacts["session_id"] == "alice"
    assert "student_workflow_20260628_1" in result.artifacts["next_command"]
    assert result.artifacts["sources"]["student_workflow"]["session_id"] == "alice"
