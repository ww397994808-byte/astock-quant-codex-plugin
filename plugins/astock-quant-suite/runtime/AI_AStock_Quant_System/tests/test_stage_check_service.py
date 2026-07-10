from __future__ import annotations

import json
from pathlib import Path

from services.stage_check_service import StageCheckService


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


def test_stage_check_requires_backtest_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "reports" / "paper_1"
    run_dir.mkdir(parents=True)
    (tmp_path / "reports" / "latest.txt").write_text("paper_1", encoding="utf-8")
    (run_dir / "audit_report.md").write_text("# Audit Report\n\n状态：VALID\n", encoding="utf-8")

    result = StageCheckService().run("latest")

    assert result.status == "VALID"
    assert result.artifacts["stage_gate"]["stage"] == "RESEARCH_ONLY"
    assert "缺少 backtest_plan" in result.warnings[0]
    assert (run_dir / "stage_gate_report.md").exists()


def test_stage_check_promotes_to_qmt_readonly_ready(tmp_path, monkeypatch):
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
    (qmt_dir / "qmt_account_snapshot.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    result = StageCheckService().run("latest")

    assert result.status == "VALID"
    assert result.artifacts["stage_gate"]["stage"] == "QMT_READONLY_READY"
    assert "实盘前检查未通过" in result.warnings[0]
