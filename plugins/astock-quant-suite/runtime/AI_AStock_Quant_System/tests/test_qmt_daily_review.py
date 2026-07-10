from __future__ import annotations

import json
from pathlib import Path

from services.qmt_daily_review_service import QMTDailyReviewService


def _write_lifecycle(tmp_path: Path, status: str, *, observed_order: bool = False, observed_trade: bool = False) -> Path:
    run_dir = tmp_path / "reports" / "qmt_order_lifecycle_1"
    run_dir.mkdir(parents=True)
    data = {
        "status": status,
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "observed_order": {"symbol": "601088.SH"} if observed_order else None,
        "observed_trade": {"symbol": "601088.SH"} if observed_trade else None,
        "timeline": [
            {"step": "sandbox", "status": "DRY_RUN_RECORDED"},
            {"step": "receipt", "status": "DRY_RUN_RECORDED"},
        ],
        "warnings": [],
    }
    if status == "BLOCKED_NO_TRACKING":
        data["warnings"] = ["沙盒未记录 dry-run 回执：BLOCKED_SANDBOX_ONLY"]
    path = run_dir / "QMT_ORDER_LIFECYCLE.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return run_dir


def test_qmt_daily_review_blocks_when_lifecycle_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_lifecycle(tmp_path, "BLOCKED_NO_TRACKING")

    result = QMTDailyReviewService().run(str(lifecycle), trade_date="2026-06-29")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_REVIEW"
    assert result.artifacts["next_day_gate"] == "STOP_UNTIL_UPSTREAM_FIXED"
    assert any(item["status"] == "blocked" for item in result.artifacts["next_actions"])


def test_qmt_daily_review_dry_run_only_keeps_next_day_sandbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_lifecycle(tmp_path, "DRY_RUN_ONLY")

    result = QMTDailyReviewService().run(str(lifecycle), notes="teaching dry run")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRY_RUN_REVIEW"
    assert result.artifacts["next_day_gate"] == "CONTINUE_DRY_RUN_ONLY"
    assert "teaching dry run" in Path(result.report_path, "QMT_DAILY_REVIEW.md").read_text(encoding="utf-8")


def test_qmt_daily_review_order_observed_requires_order_state_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_lifecycle(tmp_path, "ORDER_OBSERVED", observed_order=True)

    result = QMTDailyReviewService().run(str(lifecycle))

    assert result.status == "VALID"
    assert result.artifacts["status"] == "REVIEW_READY"
    assert result.artifacts["next_day_gate"] == "REQUIRE_TRADE_OR_CANCEL_REVIEW"
    assert any("已观察到委托但未观察到成交" in item for item in result.artifacts["anomalies"])


def test_qmt_daily_review_trade_observed_requires_position_pnl_review(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_lifecycle(tmp_path, "TRADE_OBSERVED", observed_order=True, observed_trade=True)

    result = QMTDailyReviewService().run(str(lifecycle))

    assert result.status == "VALID"
    assert result.artifacts["next_day_gate"] == "REQUIRE_POSITION_AND_PNL_REVIEW"
    assert any(item["type"] == "review_position_pnl" for item in result.artifacts["next_actions"])
    assert Path(result.report_path, "next_day_actions.json").exists()
