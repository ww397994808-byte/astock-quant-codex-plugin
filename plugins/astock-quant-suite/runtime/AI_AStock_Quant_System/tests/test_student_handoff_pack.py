from __future__ import annotations

import json
from pathlib import Path

from services.student_handoff_pack_service import StudentHandoffPackService


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_project(root: Path) -> None:
    for dirname in [
        "config",
        "data/sample",
        "reports",
        "codex_skills/astock-quant-research/scripts",
        "tasks",
    ]:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    _write(root / "cli.py", "print('ok')\n")
    _write(root / "QUICK_START_FOR_STUDENTS.md", "# quick\n")
    _write(root / "codex_skills/astock-quant-research/SKILL.md", "---\nname: astock\n---\n")
    _write(root / "codex_skills/astock-quant-research/scripts/run_astock_workflow.py", "print('ok')\n")
    _write(root / "data/sample/601088.csv", "date,open,high,low,close,volume\n")
    commands = [
        "student-workflow",
        "student-backtest-plan-precheck",
        "student-contract-check",
        "student-course-path",
        "student-first-run",
        "student-future-leak-precheck",
        "student-handoff-pack",
        "student-idea-preflight",
        "student-control-center",
        "student-run-next",
        "student-research-contract",
        "student-safe-loop",
        "student-session-index",
        "student-session-report",
        "student-start",
        "student-product-audit",
        "qmt-config-init",
        "qmt-config-status",
        "repair-dsl-backtest",
        "qmt-check",
        "qmt-readiness-dashboard",
        "stage-check",
    ]
    _write(root / "tasks/task_registry.py", "\n".join(f'"{name}": object,' for name in commands))
    safe_qmt = """
dry_run: true
enable_real_trade: false
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
"""
    _write(root / "config/qmt_config.example.yaml", safe_qmt)
    _write(root / "config/qmt_config.yaml", safe_qmt)
    workflow = root / "reports" / "student_workflow_20260629_1"
    workflow.mkdir(parents=True)
    _write(
        workflow / "workflow_manifest.json",
        json.dumps({"status": "VALID", "session_id": "alice", "symbol": "601088.SH"}, ensure_ascii=False),
    )
    _write(root / "reports" / "student_session_ledger.jsonl", json.dumps({"session_id": "alice", "allowed": True, "dry_run": True}, ensure_ascii=False) + "\n")


def test_student_handoff_pack_builds_read_only_bundle(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentHandoffPackService().run(
        workflow="reports/student_workflow_20260629_1",
        session_id="alice",
        include_product_audit=False,
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] in {"HANDOFF_READY", "HANDOFF_READY_WITH_WARNINGS"}
    assert result.artifacts["session_id"] == "alice"
    assert result.artifacts["sources"]["student_start"]["found"] is True
    assert result.artifacts["sources"]["student_session_report"]["found"] is True
    assert Path(result.report_path, "STUDENT_HANDOFF_PACK.md").exists()
    assert Path(result.report_path, "student_handoff_cards.json").exists()
    assert any(item["label"] == "学员启动包" for item in result.artifacts["report_links"])


def test_student_handoff_pack_can_skip_session_report(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentHandoffPackService().run(include_product_audit=False, include_session_report=False)

    assert result.artifacts["sources"]["student_session_report"]["found"] is False
    assert result.status in {"VALID", "INVALID"}
