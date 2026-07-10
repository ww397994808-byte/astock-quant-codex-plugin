from __future__ import annotations

import json
from pathlib import Path

from services.pretrade_service import PreTradeService


def _write_valid_plan(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "status: VALID",
                "blockers: []",
                "promotion_policy:",
                "  qmt_allowed: true",
                "  requires_paper_observation: true",
                "  requires_qmt_readonly: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_pretrade_requires_qmt_readonly_stage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "reports" / "paper_1"
    run_dir.mkdir(parents=True)
    (tmp_path / "reports" / "latest.txt").write_text("paper_1", encoding="utf-8")
    _write_valid_plan(run_dir / "backtest_plan.yaml")
    (run_dir / "audit_report.md").write_text("# Audit Report\n\n状态：VALID\n", encoding="utf-8")
    (run_dir / "readiness_report.md").write_text("readiness: PAPER_READY\n", encoding="utf-8")
    (run_dir / "paper_observation.json").write_text(json.dumps({"status": "VALID"}), encoding="utf-8")

    result = PreTradeService().run("boll_mean_reversion", "601088.SH", confirmation="CONFIRM_REAL_TRADE")

    assert result.status == "INVALID"
    assert "阶段未达到 QMT_READONLY_READY" in result.warnings[0]
    assert Path(result.report_path, "pretrade_report.md").exists()


def test_pretrade_reads_qmt_snapshot_but_keeps_other_safety_checks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    run_dir = reports / "paper_1"
    qmt_dir = reports / "qmt_readonly_1"
    run_dir.mkdir(parents=True)
    qmt_dir.mkdir(parents=True)
    (reports / "latest.txt").write_text("paper_1", encoding="utf-8")
    _write_valid_plan(run_dir / "backtest_plan.yaml")
    (run_dir / "audit_report.md").write_text("# Audit Report\n\n状态：VALID\n", encoding="utf-8")
    (run_dir / "readiness_report.md").write_text("readiness: PAPER_READY\n", encoding="utf-8")
    (run_dir / "paper_observation.json").write_text(json.dumps({"status": "VALID"}), encoding="utf-8")
    (qmt_dir / "qmt_account_snapshot.json").write_text(
        json.dumps({"ok": True, "connected": True, "checks": {"qmt_connected": True, "account_available": True}}),
        encoding="utf-8",
    )

    result = PreTradeService().run(
        "boll_mean_reversion",
        "601088.SH",
        confirmation="CONFIRM_REAL_TRADE",
        qmt_run_id="qmt_readonly_1",
    )

    assert result.status == "INVALID"
    assert result.artifacts["stage"] == "QMT_READONLY_READY"
    assert "QMT 未连接" not in result.warnings
    assert "账户不可用" not in result.warnings
    assert "enable_real_trade 未开启" in result.warnings
