from __future__ import annotations

import json
from pathlib import Path

from services.qmt_order_sandbox_service import QMTOrderSandboxService


def _write_handoff(tmp_path: Path, *, ready: bool = True, blockers: list[str] | None = None) -> Path:
    run_dir = tmp_path / "reports" / "qmt_handoff_1"
    run_dir.mkdir(parents=True)
    data = {
        "status": "DRAFT_READY" if ready else "BLOCKED_DRAFT_ONLY",
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "order": {
            "symbol": "601088.SH",
            "action": "BUY",
            "quantity": 100,
            "signal_time": "2026-06-29T09:35:00",
            "execute_time": "2026-06-30T09:35:00",
            "price": 25.5,
            "status": "PENDING",
            "reason": "manual_reviewed_signal",
            "timeframe": "1d",
        },
        "blockers": blockers or [],
    }
    path = run_dir / "QMT_HANDOFF_PACKAGE.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return run_dir


def test_qmt_order_sandbox_records_dry_run_receipt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handoff = _write_handoff(tmp_path)

    result = QMTOrderSandboxService().run(str(handoff))

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRY_RUN_RECORDED"
    assert result.artifacts["receipt"]["status"] == "DRY_RUN_RECORDED"
    assert result.artifacts["receipt"]["broker_status"] == "DRY_RUN"
    out = Path(result.report_path)
    assert (out / "QMT_ORDER_SANDBOX.md").exists()
    assert (out / "order_receipt.json").exists()


def test_qmt_order_sandbox_ignores_confirmation_and_stays_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handoff = _write_handoff(tmp_path)

    result = QMTOrderSandboxService().run(str(handoff), confirmation="CONFIRM_REAL_TRADE")

    assert result.status == "VALID"
    assert result.artifacts["receipt"]["confirmation_ignored"] is True
    text = Path(result.report_path, "QMT_ORDER_SANDBOX.md").read_text(encoding="utf-8")
    assert "只记录 dry-run" in text


def test_qmt_order_sandbox_blocks_unready_handoff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handoff = _write_handoff(tmp_path, ready=False, blockers=["pretrade_status 不是 VALID：INVALID"])

    result = QMTOrderSandboxService().run(str(handoff))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_SANDBOX_ONLY"
    assert any("QMT 交接草案未到 DRAFT_READY" in item for item in result.warnings)
    assert any("交接草案仍有阻断项" in item for item in result.warnings)
    assert result.artifacts["receipt"]["status"] == "NOT_SENT"


def test_qmt_order_sandbox_blocks_unsafe_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handoff = _write_handoff(tmp_path)
    config = tmp_path / "qmt_config.yaml"
    config.write_text("dry_run: false\nenable_real_trade: true\n", encoding="utf-8")

    result = QMTOrderSandboxService().run(str(handoff), config=str(config))

    assert result.status == "INVALID"
    assert any("dry_run=true" in item for item in result.warnings)
    assert any("enable_real_trade=false" in item for item in result.warnings)
