from __future__ import annotations

import json
from pathlib import Path

from services.student_next_step_runner_service import StudentNextStepRunnerService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def test_student_next_step_runner_blocks_placeholder_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentNextStepRunnerService().run(dry_run=True)

    assert result.status == "INVALID"
    assert result.artifacts["allowed"] is False
    assert "safe_to_copy=false" in result.artifacts["reason"]
    assert Path(result.report_path, "STUDENT_NEXT_STEP_RUN.md").exists()
    assert Path(result.report_path, "execution_decision.json").exists()
    ledger = tmp_path / "reports" / "student_session_ledger.jsonl"
    assert ledger.exists()
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["allowed"] is False
    assert entry["status"] == "BLOCKED"


def test_student_next_step_runner_accepts_safe_repair_command_in_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workflow_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "symbol": "601088.SH",
            "timeframe": "1d",
            "adjust": "point_in_time_qfq",
        },
    )
    (workflow_dir / "STUDENT_REPAIR_DSL.yaml").write_text("pattern: timing\n", encoding="utf-8")

    result = StudentNextStepRunnerService().run(workflow=str(workflow_dir), dry_run=True, timeout_seconds=7, session_id="alice")

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRY_RUN_READY"
    assert result.artifacts["allowed"] is True
    assert result.artifacts["timeout_seconds"] == 7
    assert result.artifacts["returncode"] is None
    assert "repair-dsl-backtest" in result.artifacts["command"]
    decision = json.loads(Path(result.report_path, "execution_decision.json").read_text(encoding="utf-8"))
    assert decision["allowed"] is True
    assert decision["timeout_seconds"] == 7
    ledger = tmp_path / "reports" / "student_session_ledger.jsonl"
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["session_id"] == "alice"


def test_student_next_step_runner_accepts_policy_research_command_in_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workflow_dir = _write_json(
        tmp_path / "reports" / "student_workflow_20260629_1" / "workflow_manifest.json",
        {
            "status": "INVALID",
            "symbol": "601088.SH",
            "steps": [],
        },
    )
    _write_json(
        workflow_dir / "STUDENT_POLICY_ACTION_PLAN.json",
        {
            "status": "NEEDS_RESEARCH_REPAIR",
            "failed_metrics": ["trade_count"],
            "next_commands": [
                "python3 cli.py student-workflow --idea \"x\" --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq --auto-refine"
            ],
        },
    )

    result = StudentNextStepRunnerService().run(workflow=str(workflow_dir), dry_run=True)

    assert result.status == "VALID"
    assert result.artifacts["allowed"] is True
    assert result.artifacts["status"] == "DRY_RUN_READY"
    assert "student-workflow" in result.artifacts["command"]


def test_student_next_step_runner_rejects_pretrade_even_if_concrete():
    service = StudentNextStepRunnerService()

    decision = service._validate_command(
        "python3 cli.py pretrade-package --promotion reports/r/REPAIR_DSL_PROMOTION.json --qmt-run-id qmt_1",
        True,
    )

    assert decision["allowed"] is False
    assert "必须人工执行" in decision["reason"]
