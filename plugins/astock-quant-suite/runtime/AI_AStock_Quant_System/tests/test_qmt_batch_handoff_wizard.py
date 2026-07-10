from __future__ import annotations

import csv
import json
from pathlib import Path

from services.qmt_batch_handoff_wizard_service import QMTBatchHandoffWizardService


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
    (package_dir / "PRETRADE_READINESS_PACKAGE.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return package_dir


def _write_orders(tmp_path: Path) -> Path:
    path = tmp_path / "orders.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "action", "quantity", "price", "signal_time", "execute_time", "reason"])
        writer.writeheader()
        writer.writerow({
            "symbol": "601088.SH",
            "action": "BUY",
            "quantity": "100",
            "price": "25.5",
            "signal_time": "2026-06-29T09:35:00",
            "execute_time": "2026-06-30T09:35:00",
            "reason": "batch_wizard",
        })
    return path


def _run_wizard(package: Path, orders: Path, **kwargs):
    params = {
        "package": str(package),
        "orders": str(orders),
        "trade_date": "2026-06-29",
    }
    params.update(kwargs)
    return QMTBatchHandoffWizardService().run(**params)


def test_qmt_batch_handoff_wizard_blocks_at_handoff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path, ready=False)
    orders = _write_orders(tmp_path)

    result = _run_wizard(package, orders)

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_AT_BATCH_HANDOFF"
    assert [step["name"] for step in result.artifacts["steps"]] == ["qmt-batch-handoff"]


def test_qmt_batch_handoff_wizard_runs_full_dry_run_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path)
    orders = _write_orders(tmp_path)

    result = _run_wizard(package, orders, qmt_run_id="")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "BATCH_WIZARD_REVIEW_READY"
    assert [step["name"] for step in result.artifacts["steps"]] == [
        "qmt-batch-handoff",
        "qmt-batch-sandbox",
        "qmt-batch-lifecycle",
        "qmt-batch-daily-review",
    ]
    assert result.artifacts["steps"][-1]["artifacts_status"] == "BATCH_DRY_RUN_REVIEW"


def test_qmt_batch_handoff_wizard_blocks_at_sandbox_for_unsafe_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path)
    orders = _write_orders(tmp_path)
    config = tmp_path / "qmt_config.yaml"
    config.write_text("dry_run: false\nenable_real_trade: true\n", encoding="utf-8")

    result = _run_wizard(package, orders, config=str(config))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_AT_BATCH_SANDBOX"
    assert [step["name"] for step in result.artifacts["steps"]] == ["qmt-batch-handoff", "qmt-batch-sandbox"]
    assert any("dry_run=true" in warning for warning in result.warnings)
