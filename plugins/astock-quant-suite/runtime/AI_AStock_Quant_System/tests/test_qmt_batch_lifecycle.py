from __future__ import annotations

import json
from pathlib import Path

from services.qmt_batch_lifecycle_service import QMTBatchLifecycleService


def _write_batch_sandbox(tmp_path: Path, *, recorded: bool = True) -> Path:
    run_dir = tmp_path / "reports" / "qmt_batch_sandbox_1"
    run_dir.mkdir(parents=True)
    receipts = [
        {
            "row": 1,
            "order": {"symbol": "601088.SH", "action": "BUY", "quantity": 100},
            "receipt": {"status": "DRY_RUN_RECORDED" if recorded else "NOT_SENT", "order_id": "DRYRUN-1" if recorded else ""},
        },
        {
            "row": 2,
            "order": {"symbol": "600000.SH", "action": "SELL", "quantity": 50},
            "receipt": {"status": "DRY_RUN_RECORDED" if recorded else "NOT_SENT", "order_id": "DRYRUN-2" if recorded else ""},
        },
    ]
    data = {
        "status": "BATCH_DRY_RUN_RECORDED" if recorded else "BATCH_BLOCKED_SANDBOX_ONLY",
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "receipts": receipts,
        "warnings": [] if recorded else ["batch sandbox 阻断"],
    }
    (run_dir / "QMT_BATCH_ORDER_SANDBOX.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return run_dir


def _write_qmt_snapshot(tmp_path: Path, *, orders: list[dict] | None = None, trades: list[dict] | None = None) -> None:
    qmt_dir = tmp_path / "reports" / "qmt_readonly_1"
    qmt_dir.mkdir(parents=True)
    data = {
        "ok": True,
        "connected": True,
        "orders_today": orders or [],
        "trades_today": trades or [],
    }
    (qmt_dir / "qmt_account_snapshot.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_qmt_batch_lifecycle_dry_run_only_without_qmt_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_batch_sandbox(tmp_path)

    result = QMTBatchLifecycleService().run(str(sandbox), qmt_run_id="")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_DRY_RUN_ONLY"
    assert result.artifacts["summary"]["dry_run_only"] == 2
    assert Path(result.report_path, "batch_lifecycle_timeline.csv").exists()


def test_qmt_batch_lifecycle_blocks_when_sandbox_not_recorded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_batch_sandbox(tmp_path, recorded=False)

    result = QMTBatchLifecycleService().run(str(sandbox), qmt_run_id="")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BATCH_BLOCKED_NO_TRACKING"
    assert result.artifacts["summary"]["blocked"] == 2
    assert any("批量沙盒未记录 dry-run 回执" in item for item in result.warnings)


def test_qmt_batch_lifecycle_observes_batch_orders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_batch_sandbox(tmp_path)
    _write_qmt_snapshot(
        tmp_path,
        orders=[
            {"symbol": "601088.SH", "action": "BUY", "quantity": 100},
            {"stock_code": "600000.SH", "direction": "卖出", "order_volume": 50},
        ],
    )

    result = QMTBatchLifecycleService().run(str(sandbox), qmt_run_id="qmt_readonly_1")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_ORDER_OBSERVED"
    assert result.artifacts["summary"]["order_observed"] == 2


def test_qmt_batch_lifecycle_observes_batch_trades(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_batch_sandbox(tmp_path)
    _write_qmt_snapshot(
        tmp_path,
        orders=[
            {"symbol": "601088.SH", "action": "BUY", "quantity": 100},
            {"symbol": "600000.SH", "action": "SELL", "quantity": 50},
        ],
        trades=[
            {"symbol": "601088.SH", "action": "BUY", "quantity": 100},
            {"symbol": "600000.SH", "action": "SELL", "quantity": 50},
        ],
    )

    result = QMTBatchLifecycleService().run(str(sandbox), qmt_run_id="qmt_readonly_1")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_TRADE_OBSERVED"
    assert result.artifacts["summary"]["trade_observed"] == 2
