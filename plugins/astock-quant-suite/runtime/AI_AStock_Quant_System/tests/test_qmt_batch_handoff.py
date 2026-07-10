from __future__ import annotations

import csv
import json
from pathlib import Path

from services.qmt_batch_handoff_service import QMTBatchHandoffService


def _write_package(tmp_path: Path, *, ready: bool = True) -> Path:
    package_dir = tmp_path / "reports" / "pretrade_package_1"
    package_dir.mkdir(parents=True)
    data = {
        "status": "READY_FOR_PRETRADE_CHECK" if ready else "BLOCKED_BEFORE_PRETRADE",
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "stage": "QMT_READONLY_READY" if ready else "PAPER_OBSERVED",
        "pretrade_status": "VALID" if ready else "INVALID",
        "fix_plan": [],
    }
    (package_dir / "PRETRADE_READINESS_PACKAGE.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return package_dir


def _write_orders(path: Path, rows: list[dict]) -> Path:
    fieldnames = ["symbol", "action", "quantity", "price", "signal_time", "execute_time", "reason"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_qmt_batch_handoff_generates_ready_batch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path)
    orders = _write_orders(tmp_path / "orders.csv", [
        {
            "symbol": "601088.SH",
            "action": "BUY",
            "quantity": "100",
            "price": "25.5",
            "signal_time": "2026-06-29T09:35:00",
            "execute_time": "2026-06-30T09:35:00",
            "reason": "buy_leg",
        },
        {
            "symbol": "600000.SH",
            "action": "SELL",
            "quantity": "50",
            "price": "10.1",
            "signal_time": "2026-06-29T09:35:00",
            "execute_time": "2026-06-30T09:35:00",
            "reason": "sell_odd_lot_allowed",
        },
    ])

    result = QMTBatchHandoffService().run(str(package), str(orders))

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_DRAFT_READY"
    assert result.artifacts["ready_orders"] == 2
    assert Path(result.report_path, "batch_order_drafts.csv").exists()


def test_qmt_batch_handoff_blocks_invalid_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path)
    orders = _write_orders(tmp_path / "orders.csv", [
        {
            "symbol": "601088.SH",
            "action": "BUY",
            "quantity": "50",
            "price": "25.5",
            "signal_time": "2026-06-29T09:35:00",
            "execute_time": "2026-06-29T09:35:00",
            "reason": "bad_lot_and_time",
        },
    ])

    result = QMTBatchHandoffService().run(str(package), str(orders))

    assert result.status == "INVALID"
    assert result.artifacts["blocked_orders"] == 1
    assert any("row 1: 买入数量必须是 100 股整数倍" in item for item in result.warnings)
    assert any("禁止同一根 K 线内信号即成交" in item for item in result.warnings)


def test_qmt_batch_handoff_blocks_when_package_not_ready(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path, ready=False)
    orders = _write_orders(tmp_path / "orders.csv", [
        {
            "symbol": "601088.SH",
            "action": "BUY",
            "quantity": "100",
            "price": "25.5",
            "signal_time": "2026-06-29T09:35:00",
            "execute_time": "2026-06-30T09:35:00",
            "reason": "blocked_package",
        },
    ])

    result = QMTBatchHandoffService().run(str(package), str(orders))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BATCH_BLOCKED_DRAFT_ONLY"
    assert any("盘前证据包未到 READY_FOR_PRETRADE_CHECK" in item for item in result.warnings)
