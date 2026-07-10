from __future__ import annotations

import json
from pathlib import Path

from services.qmt_handoff_wizard_service import QMTHandoffWizardService


def _write_package(tmp_path: Path, *, ready: bool = True) -> Path:
    package_dir = tmp_path / "reports" / "pretrade_package_1"
    package_dir.mkdir(parents=True)
    package = {
        "status": "READY_FOR_PRETRADE_CHECK" if ready else "BLOCKED_BEFORE_PRETRADE",
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "stage": "QMT_READONLY_READY" if ready else "PAPER_OBSERVED",
        "pretrade_status": "VALID" if ready else "INVALID",
        "symbol": "601088.SH",
        "fix_plan": [],
    }
    (package_dir / "PRETRADE_READINESS_PACKAGE.json").write_text(
        json.dumps(package, ensure_ascii=False), encoding="utf-8"
    )
    return package_dir


def _run_wizard(package: Path, **kwargs):
    params = {
        "package": str(package),
        "action": "BUY",
        "quantity": 100,
        "price": 25.5,
        "signal_time": "2026-06-29T09:35:00",
        "execute_time": "2026-06-30T09:35:00",
        "trade_date": "2026-06-29",
    }
    params.update(kwargs)
    return QMTHandoffWizardService().run(**params)


def test_qmt_handoff_wizard_blocks_at_handoff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path, ready=False)

    result = _run_wizard(package)

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_AT_HANDOFF"
    assert [step["name"] for step in result.artifacts["steps"]] == ["qmt-handoff"]
    assert Path(result.report_path, "QMT_HANDOFF_WIZARD.md").exists()


def test_qmt_handoff_wizard_runs_full_dry_run_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path)

    result = _run_wizard(package, qmt_run_id="")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "WIZARD_REVIEW_READY"
    assert [step["name"] for step in result.artifacts["steps"]] == [
        "qmt-handoff",
        "qmt-order-sandbox",
        "qmt-order-lifecycle",
        "qmt-daily-review",
    ]
    assert result.artifacts["steps"][-1]["artifacts_status"] == "DRY_RUN_REVIEW"


def test_qmt_handoff_wizard_blocks_at_sandbox_for_unsafe_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = _write_package(tmp_path)
    config = tmp_path / "qmt_config.yaml"
    config.write_text("dry_run: false\nenable_real_trade: true\n", encoding="utf-8")

    result = _run_wizard(package, config=str(config))

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_AT_SANDBOX"
    assert [step["name"] for step in result.artifacts["steps"]] == ["qmt-handoff", "qmt-order-sandbox"]
    assert any("dry_run=true" in warning for warning in result.warnings)
