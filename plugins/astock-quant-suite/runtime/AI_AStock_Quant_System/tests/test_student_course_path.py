from __future__ import annotations

from pathlib import Path

from services.student_course_path_service import StudentCoursePathService


def _minimal_project(root: Path) -> None:
    for dirname in [
        "config",
        "data/sample",
        "reports",
        "codex_skills/astock-quant-research/scripts",
        "tasks",
    ]:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    (root / "cli.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "QUICK_START_FOR_STUDENTS.md").write_text("# quick\n", encoding="utf-8")
    (root / "codex_skills/astock-quant-research/SKILL.md").write_text("---\nname: astock\n---\n", encoding="utf-8")
    (root / "codex_skills/astock-quant-research/scripts/run_astock_workflow.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "data/sample/601088.csv").write_text("date,open,high,low,close,volume\n", encoding="utf-8")
    from services.student_doctor_service import StudentDoctorService

    (root / "tasks/task_registry.py").write_text(
        "\n".join(f'"{name}": object,' for name in StudentDoctorService.REQUIRED_COMMANDS),
        encoding="utf-8",
    )
    safe_qmt = """
dry_run: true
enable_real_trade: false
account_id: "demo"
mini_qmt_path: "/tmp/mini_qmt"
"""
    (root / "config/qmt_config.example.yaml").write_text(safe_qmt, encoding="utf-8")
    (root / "config/qmt_config.yaml").write_text(safe_qmt, encoding="utf-8")


def test_student_course_path_ready_without_strategy_code(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentCoursePathService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        session_id="alice",
    )

    assert result.status == "VALID"
    assert result.artifacts["status"] == "COURSE_PATH_READY"
    assert result.artifacts["safe_to_copy"] is True
    assert "student-workflow" in result.artifacts["next_command"]
    assert result.artifacts["sources"]["student_future_leak_precheck"]["found"] is False
    assert any(item["id"] == "future_leak_not_run" for item in result.artifacts["warnings"])
    assert Path(result.report_path, "STUDENT_COURSE_PATH.md").exists()
    assert Path(result.report_path, "student_course_path_cards.json").exists()


def test_student_course_path_blocks_future_leak_code(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentCoursePathService().run(
        idea="中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究",
        code="signal = close.shift(-1) > close",
        session_id="alice",
    )

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "COURSE_PATH_BLOCKED"
    assert any(item["id"] == "future_leak_blocked" for item in result.artifacts["blockers"])
    assert result.artifacts["sources"]["student_future_leak_precheck"]["found"] is True


def test_student_course_path_blocks_missing_idea(tmp_path, monkeypatch):
    _minimal_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = StudentCoursePathService().run()

    assert result.status == "INVALID"
    assert result.artifacts["status"] == "COURSE_PATH_BLOCKED"
    assert any(item["id"] in {"idea_blocked", "plan_blocked"} for item in result.artifacts["blockers"])
