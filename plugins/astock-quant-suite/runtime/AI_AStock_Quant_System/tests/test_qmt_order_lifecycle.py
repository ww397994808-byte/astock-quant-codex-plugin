from __future__ import annotations

import json
from pathlib import Path

from services.qmt_order_lifecycle_service import QMTOrderLifecycleService


def _write_sandbox(tmp_path: Path, *, recorded: bool = True) -> Path:
    run_dir = tmp_path / "reports" / "qmt_order_sandbox_1"
    run_dir.mkdir(parents=True)
    data = {
        "status": "DRY_RUN_RECORDED" if recorded else "BLOCKED_SANDBOX_ONLY",
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
        "receipt": {
            "status": "DRY_RUN_RECORDED" if recorded else "NOT_SENT",
            "order_id": "DRYRUN-601088.SH-20260630093500" if recorded else "",
        },
        "warnings": [] if recorded else ["sandbox 阻断"],
    }
    path = run_dir / "QMT_ORDER_SANDBOX.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return run_dir


def _write_qmt_snapshot(tmp_path: Path, *, orders: list[dict] | None = None, trades: list[dict] | None = None, ok: bool = True) -> None:
    qmt_dir = tmp_path / "reports" / "qmt_readonly_1"
    qmt_dir.mkdir(parents=True)
    snapshot = {
        "ok": ok,
        "connected": ok,
        "orders_today": orders or [],
        "trades_today": trades or [],
        "checks": {"qmt_connected": ok},
    }
    (qmt_dir / "qmt_account_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")


def test_qmt_order_lifecycle_dry_run_only_without_qmt_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_sandbox(tmp_path)

    result = QMTOrderLifecycleService().run(str(sandbox), qmt_run_id="")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRY_RUN_ONLY"
    assert result.artifacts["observed_order"] is None
    assert Path(result.report_path, "QMT_ORDER_LIFECYCLE.md").exists()


def test_qmt_order_lifecycle_blocks_when_sandbox_not_recorded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_sandbox(tmp_path, recorded=False)

    result = QMTOrderLifecycleService().run(str(sandbox), qmt_run_id="")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_NO_TRACKING"
    assert any("沙盒未记录 dry-run 回执" in item for item in result.warnings)


def test_qmt_order_lifecycle_observes_order_from_qmt_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_sandbox(tmp_path)
    _write_qmt_snapshot(tmp_path, orders=[{"symbol": "601088.SH", "action": "BUY", "quantity": 100}])

    result = QMTOrderLifecycleService().run(str(sandbox), qmt_run_id="qmt_readonly_1")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "ORDER_OBSERVED"
    assert result.artifacts["observed_order"]["symbol"] == "601088.SH"
    assert result.artifacts["observed_trade"] is None


def test_qmt_order_lifecycle_observes_trade_from_qmt_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sandbox = _write_sandbox(tmp_path)
    _write_qmt_snapshot(
        tmp_path,
        orders=[{"stock_code": "601088.SH", "direction": "买入", "order_volume": 100}],
        trades=[{"stock_code": "601088.SH", "direction": "买入", "traded_volume": 100}],
    )

    result = QMTOrderLifecycleService().run(str(sandbox), qmt_run_id="qmt_readonly_1")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "TRADE_OBSERVED"
    assert result.artifacts["observed_trade"]["stock_code"] == "601088.SH"
    timeline = Path(result.report_path, "lifecycle_timeline.json")
    assert timeline.exists()
