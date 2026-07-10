from __future__ import annotations

import json
from pathlib import Path

from services.qmt_handoff_service import QMTHandoffService


def _write_package(tmp_path: Path, *, ready: bool = True, pretrade_valid: bool = True, blocked: bool = False) -> Path:
    reports = tmp_path / "reports"
    package_dir = reports / "pretrade_package_1"
    package_dir.mkdir(parents=True)
    package = {
        "status": "READY_FOR_PRETRADE_CHECK" if ready else "BLOCKED_BEFORE_PRETRADE",
        "candidate_run_id": "repair_candidate_1",
        "qmt_run_id": "qmt_readonly_1",
        "stage": "QMT_READONLY_READY" if ready else "PAPER_OBSERVED",
        "pretrade_status": "VALID" if pretrade_valid else "INVALID",
        "strategy": "compiled_repair_dsl",
        "symbol": "601088.SH",
        "fix_plan": [],
        "hard_boundary": "pretrade-check VALID 且人工确认前，不允许真实下单。",
    }
    if blocked:
        package["fix_plan"].append({
            "title": "标的不可交易或停牌",
            "failure": "标的不可交易或停牌",
            "status": "blocked",
            "stop_trading": True,
        })
    path = package_dir / "PRETRADE_READINESS_PACKAGE.json"
    path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
    return package_dir


def test_qmt_handoff_generates_order_draft(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package_dir = _write_package(tmp_path)

    result = QMTHandoffService().run(
        str(package_dir),
        action="BUY",
        quantity=100,
        price=25.5,
        signal_time="2026-06-29T09:35:00",
        execute_time="2026-06-30T09:35:00",
        reason="manual_reviewed_signal",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRAFT_READY"
    assert result.artifacts["blockers"] == []
    out = Path(result.report_path)
    assert (out / "QMT_HANDOFF_PACKAGE.md").exists()
    assert (out / "order_draft.csv").exists()
    assert "manual_reviewed_signal" in (out / "QMT_HANDOFF_PACKAGE.md").read_text(encoding="utf-8")


def test_qmt_handoff_blocks_when_pretrade_or_stop_trading_not_clear(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package_dir = _write_package(tmp_path, pretrade_valid=False, blocked=True)

    result = QMTHandoffService().run(
        str(package_dir),
        action="BUY",
        quantity=100,
        signal_time="2026-06-29T09:35:00",
        execute_time="2026-06-30T09:35:00",
    )

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_DRAFT_ONLY"
    assert any("pretrade_status 不是 VALID" in item for item in result.warnings)
    assert any("停止推进事项未解除" in item for item in result.warnings)


def test_qmt_handoff_blocks_invalid_lot_and_same_bar_execution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package_dir = _write_package(tmp_path)

    result = QMTHandoffService().run(
        str(package_dir),
        action="BUY",
        quantity=50,
        signal_time="2026-06-29T09:35:00",
        execute_time="2026-06-29T09:35:00",
    )

    assert result.status == "INVALID"
    assert "买入数量必须是 100 股整数倍" in result.warnings
    assert any("禁止同一根 K 线内信号即成交" in item for item in result.warnings)
