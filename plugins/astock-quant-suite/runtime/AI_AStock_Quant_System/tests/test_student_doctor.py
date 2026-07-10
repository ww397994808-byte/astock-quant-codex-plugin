from __future__ import annotations

import importlib.util
from pathlib import Path

from services.student_doctor_service import StudentDoctorService


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_minimal_project(root: Path, qmt_config: str | None = None) -> None:
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
    _write(
        root / "tasks/task_registry.py",
        "\n".join(f'"{name}": object,' for name in StudentDoctorService.REQUIRED_COMMANDS),
    )
    safe_qmt = """
dry_run: true
enable_real_trade: false
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
"""
    _write(root / "config/qmt_config.example.yaml", safe_qmt)
    _write(root / "config/qmt_config.yaml", qmt_config or safe_qmt)


def test_student_doctor_blocks_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = StudentDoctorService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "BLOCKED_ENVIRONMENT"
    assert result.artifacts["can_start_research"] is False
    assert Path(result.report_path, "STUDENT_DOCTOR.md").exists()


def test_student_doctor_ready_for_minimal_safe_project(tmp_path, monkeypatch):
    _make_minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    original_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: object() if name in StudentDoctorService.REQUIRED_IMPORTS else original_find_spec(name),
    )

    result = StudentDoctorService().run()

    assert result.status == "VALID"
    assert result.artifacts["status"] == "READY_FOR_STUDENT_WORKFLOW"
    assert result.artifacts["can_start_research"] is True
    assert "student-workflow" in result.artifacts["next_commands"][-1]


def test_student_doctor_blocks_unsafe_qmt_config(tmp_path, monkeypatch):
    _make_minimal_project(
        tmp_path,
        qmt_config="""
dry_run: false
enable_real_trade: true
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
""",
    )
    monkeypatch.chdir(tmp_path)

    result = StudentDoctorService().run()

    assert result.status == "INVALID"
    blocker_ids = {item["id"] for item in result.artifacts["blockers"]}
    assert "qmt_config:dry_run" in blocker_ids
    assert "qmt_config:enable_real_trade" in blocker_ids
