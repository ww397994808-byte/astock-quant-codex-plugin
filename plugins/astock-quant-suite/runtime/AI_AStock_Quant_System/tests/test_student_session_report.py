from __future__ import annotations

import json
from pathlib import Path

from services.student_session_report_service import StudentSessionReportService


def test_student_session_report_blocks_without_ledger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentSessionReportService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "NO_LEDGER"
    assert Path(result.report_path, "STUDENT_SESSION_REPORT.md").exists()


def test_student_session_report_summarizes_ledger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ledger = tmp_path / "reports" / "student_session_ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    entries = [
        {
            "timestamp": "2026-06-29T10:00:00",
            "run_id": "student_next_step_1",
            "report_path": "reports/student_next_step_1",
            "status": "DRY_RUN_READY",
            "allowed": True,
            "dry_run": True,
            "command": "python3 cli.py repair-dsl-backtest --dsl a.yaml",
            "reason": "ok",
            "child_report_path": "",
            "session_id": "alice",
        },
        {
            "timestamp": "2026-06-29T10:01:00",
            "run_id": "student_next_step_2",
            "report_path": "reports/student_next_step_2",
            "status": "BLOCKED",
            "allowed": False,
            "dry_run": False,
            "command": "python3 cli.py pretrade-package --promotion p.json --qmt-run-id q",
            "reason": "必须人工执行",
            "child_report_path": "",
            "session_id": "bob",
        },
    ]
    ledger.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n", encoding="utf-8")

    result = StudentSessionReportService().run(limit=1)

    assert result.status == "VALID"
    assert result.artifacts["summary"]["allowed"] == 1
    assert result.artifacts["summary"]["blocked"] == 1
    assert result.artifacts["summary"]["dry_run"] == 1
    assert len(result.artifacts["recent_entries"]) == 1
    assert any("pretrade" in item for item in result.artifacts["risk_notes"])

    filtered = StudentSessionReportService().run(limit=20, session_id="alice")

    assert filtered.status == "VALID"
    assert filtered.artifacts["session_id"] == "alice"
    assert filtered.artifacts["total_entries"] == 1
    assert filtered.artifacts["summary"]["allowed"] == 1
    assert filtered.artifacts["summary"]["blocked"] == 0
