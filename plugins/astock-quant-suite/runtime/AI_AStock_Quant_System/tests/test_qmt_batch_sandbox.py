from __future__ import annotations

import json
from pathlib import Path

from services.qmt_batch_sandbox_service import QMTBatchSandboxService


def _write_batch_handoff(tmp_path: Path, *, ready: bool = True) -> Path:
    run_dir = tmp_path / "reports" / "qmt_batch_handoff_1"
    run_dir.mkdir(parents=True)
    drafts = [
        {
            "row": 1,
            "status": "DRAFT_READY" if ready else "BLOCKED_DRAFT_ONLY",
            "order": {
                "symbol": "601088.SH",
                "action": "BUY",
                "quantity": 100,
                "signal_time": "2026-06-29T09:35:00",
                "execute_time": "2026-06-30T09:35:00",
                "price": 25.5,
                "status": "PENDING",
                "reason": "buy_leg",
                "timeframe": "1d",
            },
            "blockers": [] if ready else ["pretrade_status 不是 VALID：INVALID"],
        },
        {
            "row": 2,
            "status": "DRAFT_READY" if ready else "BLOCKED_DRAFT_ONLY",
            "order": {
                "symbol": "600000.SH",
                "action": "SELL",
                "quantity": 50,
                "signal_time": "2026-06-29T09:35:00",
                "execute_time": "2026-06-30T09:35:00",
                "price": 10.1,
                "status": "PENDING",
                "reason": "sell_leg",
                "timeframe": "1d",
            },
            "blockers": [] if ready else ["pretrade_status 不是 VALID：INVALID"],
        },
    ]
    data = {
        "status": "BATCH_DRAFT_READY" if ready else "BATCH_BLOCKED_DRAFT_ONLY",
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "drafts": drafts,
        "blockers": [] if ready else ["row 1: pretrade_status 不是 VALID：INVALID"],
    }
    (run_dir / "QMT_BATCH_HANDOFF_PACKAGE.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return run_dir


def test_qmt_batch_sandbox_records_all_dry_run_receipts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    batch = _write_batch_handoff(tmp_path)

    result = QMTBatchSandboxService().run(str(batch))

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_DRY_RUN_RECORDED"
    assert result.artifacts["recorded_orders"] == 2
    assert all(item["receipt"]["status"] == "DRY_RUN_RECORDED" for item in result.artifacts["receipts"])
    assert Path(result.report_path, "batch_order_receipts.csv").exists()


def test_qmt_batch_sandbox_ignores_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    batch = _write_batch_handoff(tmp_path)

    result = QMTBatchSandboxService().run(str(batch), confirmation="CONFIRM_REAL_TRADE")

    assert result.status == "VALID"
    assert all(item["receipt"]["confirmation_ignored"] is True for item in result.artifacts["receipts"])


def test_qmt_batch_sandbox_blocks_unready_batch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    batch = _write_batch_handoff(tmp_path, ready=False)

    result = QMTBatchSandboxService().run(str(batch))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BATCH_BLOCKED_SANDBOX_ONLY"
    assert result.artifacts["recorded_orders"] == 0
    assert all(item["receipt"]["status"] == "NOT_SENT" for item in result.artifacts["receipts"])
    assert any("批量交接草案未到 BATCH_DRAFT_READY" in item for item in result.warnings)


def test_qmt_batch_sandbox_blocks_unsafe_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    batch = _write_batch_handoff(tmp_path)
    config = tmp_path / "qmt_config.yaml"
    config.write_text("dry_run: false\nenable_real_trade: true\n", encoding="utf-8")

    result = QMTBatchSandboxService().run(str(batch), config=str(config))

    assert result.status == "INVALID"
    assert any("dry_run=true" in item for item in result.warnings)
    assert any("enable_real_trade=false" in item for item in result.warnings)
