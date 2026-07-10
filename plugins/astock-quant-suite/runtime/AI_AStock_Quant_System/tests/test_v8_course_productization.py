from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_course_demo_cli_runs():
    result = subprocess.run([sys.executable, "cli.py", "course-demo"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "课程演示已完成" in result.stdout
    report_path = None
    for line in result.stdout.splitlines():
        if line.startswith("report_path:"):
            report_path = ROOT / line.split(":", 1)[1].strip()
    assert report_path is not None
    assert (report_path / "COURSE_DEMO_SUMMARY.md").exists()


def test_v8_productization_docs_exist():
    for name in [
        "SYSTEM_CAPABILITY_MAP.md",
        "COURSE_DELIVERY_PLAN.md",
        "QUICK_START_FOR_STUDENTS.md",
        "SYSTEM_RISK_BOUNDARIES.md",
        "CODE_HEALTH_AUDIT.md",
        "FINAL_V8_ACCEPTANCE_REPORT.md",
    ]:
        assert (ROOT / name).exists()


def test_case_study_pack_has_five_cases():
    cases = [path for path in (ROOT / "CASE_STUDY_PACK").iterdir() if path.is_dir()]
    assert len(cases) >= 5
    for case in cases[:5]:
        for name in [
            "original_idea.md",
            "intake_result.md",
            "research_result.md",
            "optimize_loop_result.md",
            "final_explanation.md",
            "what_students_should_learn.md",
        ]:
            assert (case / name).exists()
