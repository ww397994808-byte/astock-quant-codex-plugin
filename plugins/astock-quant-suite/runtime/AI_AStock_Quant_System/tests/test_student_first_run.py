from __future__ import annotations

from pathlib import Path

from services.student_first_run_service import StudentFirstRunService


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_project(root: Path, cli_body: str = "") -> None:
    for dirname in [
        "config",
        "data/sample",
        "reports",
        "codex_skills/astock-quant-research/scripts",
        "tasks",
    ]:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    _write(root / "cli.py", cli_body or "print('ok')\n")
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
        "core5-walk-forward",
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


def test_student_first_run_prepares_workflow_without_execution(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentFirstRunService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        session_id="alice",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_TO_EXECUTE"
    assert result.artifacts["execute"] is False
    assert result.artifacts["returncode"] is None
    assert "student-workflow" in result.artifacts["command"]
    assert Path(result.report_path, "STUDENT_FIRST_RUN.md").exists()


def test_student_first_run_blocks_vague_idea(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentFirstRunService().run(idea="我想做神华")

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED"
    assert "预检未达到" in result.artifacts["reason"]


def test_student_first_run_can_execute_safe_student_workflow(tmp_path, monkeypatch):
    cli_body = """
from pathlib import Path
import sys
if 'student-workflow' in sys.argv:
    out = Path('reports/fake_student_workflow')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'workflow_manifest.json').write_text('{}', encoding='utf-8')
    print('fake workflow ok')
    print('status: VALID')
    print('report_path: reports/fake_student_workflow')
else:
    print('ok')
"""
    _minimal_project(tmp_path, cli_body=cli_body)
    monkeypatch.chdir(tmp_path)

    result = StudentFirstRunService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        execute=True,
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "EXECUTED_VALID"
    assert result.artifacts["returncode"] == 0
    assert result.artifacts["child_report_path"] == "reports/fake_student_workflow"
