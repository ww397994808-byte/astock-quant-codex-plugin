from __future__ import annotations

import json
from pathlib import Path

from services.qmt_readiness_dashboard_service import QMTReadinessDashboardService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def test_qmt_readiness_dashboard_no_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = QMTReadinessDashboardService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "NO_EVIDENCE"
    assert "pretrade-package" in result.artifacts["next_command"]
    assert Path(result.report_path, "QMT_READINESS_DASHBOARD.md").exists()
    assert Path(result.report_path, "QMT_NEXT_ACTIONS.md").exists()
    assert Path(result.report_path, "qmt_action_cards.json").exists()
    assert result.artifacts["action_cards"][0]["id"] == "primary_next_step"
    assert result.artifacts["learner_mode"]["live_trade_allowed"] is False


def test_qmt_readiness_dashboard_reports_blocked_chain(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / "reports" / "pretrade_package_1" / "PRETRADE_READINESS_PACKAGE.json",
        {
            "status": "BLOCKED_BEFORE_PRETRADE",
            "stage": "PAPER_OBSERVED",
            "pretrade_status": "INVALID",
            "candidate_run_id": "repair_candidate_1",
            "qmt_run_id": "qmt_readonly_1",
            "warnings": ["stop_trading=True"],
        },
    )
    _write_json(
        tmp_path / "reports" / "qmt_handoff_wizard_1" / "QMT_HANDOFF_WIZARD.json",
        {"status": "BLOCKED_AT_HANDOFF", "steps": [{"name": "qmt-handoff"}], "warnings": ["handoff blocked"]},
    )

    result = QMTReadinessDashboardService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED"
    assert "阻断" in result.artifacts["summary"]
    assert any(item["name"] == "pretrade_package" and item["found"] for item in result.artifacts["evidence"])
    assert any("handoff blocked" in warning for warning in result.warnings)
    assert any(item["source"] == "pretrade_package" for item in result.artifacts["blocker_checklist"])
    assert any(card["id"] == "first_unresolved_blocker" for card in result.artifacts["action_cards"])
    assert Path(result.report_path, "qmt_blocker_checklist.json").exists()


def test_qmt_readiness_dashboard_prefers_latest_review_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(
        tmp_path / "reports" / "pretrade_package_1" / "PRETRADE_READINESS_PACKAGE.json",
        {
            "status": "READY_FOR_PRETRADE_CHECK",
            "stage": "QMT_READONLY_READY",
            "pretrade_status": "VALID",
        },
    )
    _write_json(
        tmp_path / "reports" / "qmt_daily_review_20260628_100000" / "QMT_DAILY_REVIEW.json",
        {"status": "BLOCKED_REVIEW", "next_day_gate": "STOP_UNTIL_UPSTREAM_FIXED"},
    )
    _write_json(
        tmp_path / "reports" / "qmt_daily_review_20260629_100000" / "QMT_DAILY_REVIEW.json",
        {"status": "DRY_RUN_REVIEW", "next_day_gate": "CONTINUE_DRY_RUN_ONLY"},
    )

    result = QMTReadinessDashboardService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRY_RUN_ONLY"
    assert "dry-run" in result.artifacts["summary"]
    assert result.artifacts["learner_mode"]["can_continue_qmt_dry_run"] is True
    assert result.artifacts["learner_mode"]["live_trade_allowed"] is False
    assert "实盘" in Path(result.report_path, "QMT_READINESS_DASHBOARD.md").read_text(encoding="utf-8")
