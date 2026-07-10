from __future__ import annotations

import json
from pathlib import Path

from core.result import TaskResult
from services.student_safe_loop_service import StudentSafeLoopService


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path.parent


def test_student_safe_loop_blocks_without_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentSafeLoopService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED"
    assert result.artifacts["steps"][0]["allowed"] is False
    assert Path(result.report_path, "STUDENT_SAFE_LOOP.md").exists()


def test_student_safe_loop_dry_run_previews_one_safe_step(tmp_path, monkeypatch):
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

    result = StudentSafeLoopService().run(workflow=str(workflow_dir), max_steps=5)

    assert result.status == "VALID"
    assert result.artifacts["status"] == "DRY_RUN_READY"
    assert result.artifacts["execute"] is False
    assert len(result.artifacts["steps"]) == 1
    assert result.artifacts["steps"][0]["allowed"] is True
    assert "repair-dsl-backtest" in result.artifacts["steps"][0]["command"]
    assert result.artifacts["session_report_path"]


def test_student_safe_loop_execute_stops_before_repeating_same_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls: list[bool] = []

    def fake_run(self, **kwargs):
        dry_run = kwargs.get("dry_run", False)
        calls.append(dry_run)
        status = "DRY_RUN_READY" if dry_run else "EXECUTED_VALID"
        return TaskResult(
            status="VALID",
            message="fake",
            run_id=f"student_next_step_{len(calls)}",
            report_path=f"reports/student_next_step_{len(calls)}",
            artifacts={
                "status": status,
                "allowed": True,
                "dry_run": dry_run,
                "command": "python3 cli.py qmt-readiness-dashboard",
                "reason": "ok",
                "child_report_path": "reports/qmt_readiness_dashboard_1" if not dry_run else "",
            },
        )

    monkeypatch.setattr("services.student_safe_loop_service.StudentNextStepRunnerService.run", fake_run)

    result = StudentSafeLoopService().run(execute=True, max_steps=3)

    assert result.status == "VALID"
    assert result.artifacts["status"] == "LOOP_STOPPED"
    assert result.artifacts["steps"][-1]["status"] == "DUPLICATE_NEXT_COMMAND"
    assert result.artifacts["stop_reason"].startswith("下一步命令与本轮已执行命令重复")
    assert calls == [True, False, True]
