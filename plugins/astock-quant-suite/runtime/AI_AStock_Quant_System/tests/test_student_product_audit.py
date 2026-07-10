from __future__ import annotations

import json
from pathlib import Path

from services.student_product_audit_service import StudentProductAuditService


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, ensure_ascii=False))


def _minimal_product_project(root: Path, qmt_config: str | None = None) -> None:
    for dirname in [
        "config",
        "data/sample",
        "reports",
        "codex_skills/astock-quant-research/scripts",
        "codex_skills/astock-quant-research/references",
        "tasks",
        "tests",
    ]:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    _write(root / "cli.py", "print('ok')\n")
    for path in StudentProductAuditService.REQUIRED_DOCS:
        _write(root / path, f"# {path}\n")
    for path in StudentProductAuditService.REQUIRED_SKILL_FILES:
        _write(root / path, f"# {path}\n")
    for path in StudentProductAuditService.REQUIRED_TEST_FILES:
        _write(root / path, "def test_placeholder():\n    assert True\n")
    _write(root / "data/sample/601088.csv", "date,open,high,low,close,volume\n")
    _write(
        root / "tasks/task_registry.py",
        "\n".join(f'"{name}": object,' for name in StudentProductAuditService.REQUIRED_PRODUCT_COMMANDS),
    )
    safe_qmt = """
dry_run: true
enable_real_trade: false
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
"""
    _write(root / "config/qmt_config.example.yaml", safe_qmt)
    _write(root / "config/qmt_config.yaml", qmt_config or safe_qmt)
    workflow = root / "reports" / "student_workflow_20260629_1"
    workflow.mkdir(parents=True)
    _write_json(
        workflow / "workflow_manifest.json",
        {
            "status": "VALID",
            "session_id": "student001",
            "symbol": "601088.SH",
            "timeframe": "1d",
            "adjust": "point_in_time_qfq",
        },
    )
    for name in [
        "STUDENT_WORKFLOW_SUMMARY.md",
        "NEXT_ACTIONS.md",
        "STUDENT_ACCEPTANCE_CHECKLIST.md",
        "STUDENT_DIAGNOSTICS.md",
        "BACKTEST_ASSUMPTION_CARD.md",
    ]:
        _write(workflow / name, f"# {name}\n")
    _write_json(workflow / "BACKTEST_ASSUMPTION_CARD.json", {"status": "VALID", "strategy_pattern": "swing"})
    _write(
        root / "reports" / "student_session_ledger.jsonl",
        json.dumps({"session_id": "student001", "allowed": True, "dry_run": True}, ensure_ascii=False) + "\n",
    )


def test_student_product_audit_ready_for_complete_product_project(tmp_path, monkeypatch):
    _minimal_product_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentProductAuditService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "PRODUCT_READY"
    assert result.artifacts["can_deliver_to_students"] is True
    assert result.artifacts["can_touch_live_trade"] is False
    assert Path(result.report_path, "STUDENT_PRODUCT_AUDIT.md").exists()
    assert Path(result.report_path, "student_product_cards.json").exists()
    assert all(item["status"] == "PASS" for item in result.artifacts["checks"])


def test_student_product_audit_blocks_unsafe_qmt_config(tmp_path, monkeypatch):
    _minimal_product_project(
        tmp_path,
        qmt_config="""
dry_run: false
enable_real_trade: true
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
""",
    )
    monkeypatch.chdir(tmp_path)

    result = StudentProductAuditService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_PRODUCT_DELIVERY"
    blocker_ids = {item["id"] for item in result.artifacts["blockers"]}
    assert "qmt_config:dry_run" in blocker_ids
    assert "qmt_config:enable_real_trade" in blocker_ids
