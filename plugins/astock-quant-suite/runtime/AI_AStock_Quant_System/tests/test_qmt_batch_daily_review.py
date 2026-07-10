from __future__ import annotations

import json
from pathlib import Path

from services.qmt_batch_daily_review_service import QMTBatchDailyReviewService


def _write_batch_lifecycle(tmp_path: Path, status: str, item_statuses: list[str]) -> Path:
    run_dir = tmp_path / "reports" / "qmt_batch_lifecycle_1"
    run_dir.mkdir(parents=True)
    items = []
    for index, item_status in enumerate(item_statuses, start=1):
        items.append({
            "row": index,
            "status": item_status,
            "order": {
                "symbol": "601088.SH" if index == 1 else "600000.SH",
                "action": "BUY" if index == 1 else "SELL",
                "quantity": 100 if index == 1 else 50,
            },
            "receipt": {"status": "DRY_RUN_RECORDED" if item_status != "BLOCKED_NO_TRACKING" else "NOT_SENT"},
            "observed_order": {"symbol": "x"} if item_status in {"ORDER_OBSERVED", "TRADE_OBSERVED"} else None,
            "observed_trade": {"symbol": "x"} if item_status == "TRADE_OBSERVED" else None,
        })
    summary = {
        "total_orders": len(items),
        "blocked": sum(1 for item in item_statuses if item == "BLOCKED_NO_TRACKING"),
        "dry_run_only": sum(1 for item in item_statuses if item == "DRY_RUN_ONLY"),
        "order_observed": sum(1 for item in item_statuses if item == "ORDER_OBSERVED"),
        "trade_observed": sum(1 for item in item_statuses if item == "TRADE_OBSERVED"),
        "not_observed": sum(1 for item in item_statuses if item == "NOT_OBSERVED_IN_QMT"),
    }
    data = {
        "status": status,
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "summary": summary,
        "items": items,
        "warnings": ["batch blocked"] if status == "BATCH_BLOCKED_NO_TRACKING" else [],
    }
    (run_dir / "QMT_BATCH_ORDER_LIFECYCLE.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return run_dir


def test_qmt_batch_daily_review_blocks_when_batch_lifecycle_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_batch_lifecycle(tmp_path, "BATCH_BLOCKED_NO_TRACKING", ["BLOCKED_NO_TRACKING"])

    result = QMTBatchDailyReviewService().run(str(lifecycle), trade_date="2026-06-29")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BATCH_BLOCKED_REVIEW"
    assert result.artifacts["next_day_gate"] == "STOP_BATCH_UNTIL_UPSTREAM_FIXED"
    assert any(item["gate"] == "STOP_ROW_UNTIL_EVIDENCE_FIXED" for item in result.artifacts["row_actions"])


def test_qmt_batch_daily_review_dry_run_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_batch_lifecycle(tmp_path, "BATCH_DRY_RUN_ONLY", ["DRY_RUN_ONLY", "DRY_RUN_ONLY"])

    result = QMTBatchDailyReviewService().run(str(lifecycle), notes="batch teaching")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_DRY_RUN_REVIEW"
    assert result.artifacts["next_day_gate"] == "CONTINUE_BATCH_DRY_RUN_ONLY"
    text = Path(result.report_path, "QMT_BATCH_DAILY_REVIEW.md").read_text(encoding="utf-8")
    assert "batch teaching" in text


def test_qmt_batch_daily_review_partial_observation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_batch_lifecycle(
        tmp_path,
        "BATCH_PARTIAL_OBSERVED",
        ["ORDER_OBSERVED", "NOT_OBSERVED_IN_QMT"],
    )

    result = QMTBatchDailyReviewService().run(str(lifecycle))

    assert result.status == "VALID"
    assert result.artifacts["next_day_gate"] == "RECONCILE_PARTIAL_BATCH_OBSERVATION"
    assert any(item["gate"] == "REQUIRE_QMT_RECONCILIATION" for item in result.artifacts["row_actions"])
    assert result.artifacts["anomalies"]


def test_qmt_batch_daily_review_trade_observed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lifecycle = _write_batch_lifecycle(tmp_path, "BATCH_TRADE_OBSERVED", ["TRADE_OBSERVED", "TRADE_OBSERVED"])

    result = QMTBatchDailyReviewService().run(str(lifecycle))

    assert result.status == "VALID"
    assert result.artifacts["next_day_gate"] == "REVIEW_BATCH_POSITION_AND_PNL"
    assert all(item["gate"] == "REQUIRE_POSITION_AND_PNL_REVIEW" for item in result.artifacts["row_actions"])
    assert Path(result.report_path, "batch_next_day_actions.csv").exists()
