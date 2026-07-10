from __future__ import annotations

import json
from pathlib import Path

from services.student_start_service import StudentStartService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def _minimal_project(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "data" / "sample").mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    (tmp_path / "codex_skills" / "astock-quant-research" / "scripts").mkdir(parents=True)
    (tmp_path / "cli.py").write_text("", encoding="utf-8")
    (tmp_path / "QUICK_START_FOR_STUDENTS.md").write_text("", encoding="utf-8")
    (tmp_path / "codex_skills" / "astock-quant-research" / "SKILL.md").write_text("", encoding="utf-8")
    (tmp_path / "codex_skills" / "astock-quant-research" / "scripts" / "run_astock_workflow.py").write_text("", encoding="utf-8")
    (tmp_path / "config" / "qmt_config.example.yaml").write_text("dry_run: true\nenable_real_trade: false\n", encoding="utf-8")
    (tmp_path / "config" / "qmt_config.yaml").write_text("dry_run: true\nenable_real_trade: false\n", encoding="utf-8")
    (tmp_path / "data" / "sample" / "601088.csv").write_text("date,open,high,low,close,volume\n", encoding="utf-8")
    registry = """
TASKS = {
    "student-workflow": object,
    "student-backtest-plan-precheck": object,
    "student-contract-check": object,
    "student-course-path": object,
    "student-first-run": object,
    "student-future-leak-precheck": object,
    "student-handoff-pack": object,
    "student-idea-preflight": object,
    "student-control-center": object,
    "student-run-next": object,
    "student-research-contract": object,
    "student-safe-loop": object,
    "student-session-index": object,
    "student-session-report": object,
    "student-start": object,
    "student-product-audit": object,
    "core5-walk-forward": object,
    "qmt-config-init": object,
    "qmt-config-status": object,
    "repair-dsl-backtest": object,
    "qmt-check": object,
    "qmt-readiness-dashboard": object,
    "stage-check": object,
}
"""
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "task_registry.py").write_text(registry, encoding="utf-8")


def test_student_start_creates_beginner_bundle_without_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _minimal_project(tmp_path)

    result = StudentStartService().run(include_session_index=False, preview_next=False)

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "NEEDS_MANUAL_INPUT"
    assert result.artifacts["sources"]["student_doctor"]["found"] is True
    assert result.artifacts["sources"]["student_control_center"]["found"] is True
    assert Path(result.report_path, "STUDENT_START.md").exists()
    assert Path(result.report_path, "student_start_cards.json").exists()


def test_student_start_previews_policy_action_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _minimal_project(tmp_path)
    workflow_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "session_id": "alice",
            "symbol": "601088.SH",
            "steps": [],
        },
    )
    _write_json(
        workflow_dir / "STUDENT_POLICY_ACTION_PLAN.json",
        {
            "status": "NEEDS_RESEARCH_REPAIR",
            "failed_metrics": ["trade_count"],
            "next_commands": [
                "python3 cli.py student-workflow --idea \"x\" --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq --auto-refine --session-id alice"
            ],
        },
    )

    result = StudentStartService().run(workflow=str(workflow_dir), session_id="alice", include_session_index=False)

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_SAFE_NEXT"
    assert result.artifacts["preview_allowed"] is True
    assert result.artifacts["preview_status"] == "DRY_RUN_READY"
    assert any(card["id"] == "safe_preview" for card in result.artifacts["cards"])


def test_student_start_surfaces_backtest_assumption_card(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _minimal_project(tmp_path)
    workflow_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "VALID",
            "session_id": "alice",
            "symbol": "601088.SH",
            "timeframe": "1h",
            "adjust": "point_in_time_qfq",
            "steps": [],
        },
    )
    _write_json(
        workflow_dir / "BACKTEST_ASSUMPTION_CARD.json",
        {
            "status": "WARN",
            "strategy_pattern": "intraday_timing",
            "timeframe": "1h",
            "execution_model": {"signal_timing": "bar_close", "fill_timing": "next_bar_open"},
            "learner_checks": [{"id": "intraday_data", "title": "分钟数据完整性", "status": "REQUIRED"}],
        },
    )

    result = StudentStartService().run(
        workflow=str(workflow_dir),
        session_id="alice",
        include_session_index=False,
        preview_next=False,
    )

    assumption_cards = [card for card in result.artifacts["cards"] if card["id"] == "backtest_assumption"]
    report = Path(result.report_path, "STUDENT_START.md").read_text(encoding="utf-8")

    assert assumption_cards
    assert assumption_cards[0]["status"] == "WARN"
    assert "intraday_timing" in assumption_cards[0]["why"]
    assert "回测假设卡" in report
