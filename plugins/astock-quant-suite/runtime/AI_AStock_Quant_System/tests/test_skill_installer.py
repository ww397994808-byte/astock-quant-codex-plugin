import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_SOURCE = ROOT / "codex_skills" / "astock-quant-research"
INSTALLER = ROOT / "scripts" / "install_astock_skill.py"


def test_astock_skill_package_contains_required_files():
    required = [
        "SKILL.md",
        "agents/openai.yaml",
        "references/future_leak_rules.md",
        "references/workflow.md",
        "references/strategy_archetypes.md",
        "references/paper_observation.md",
        "references/qmt_gate.md",
        "scripts/run_astock_workflow.py",
    ]
    for name in required:
        assert (SKILL_SOURCE / name).is_file(), name

    skill_text = (SKILL_SOURCE / "SKILL.md").read_text(encoding="utf-8")
    helper_text = (SKILL_SOURCE / "scripts" / "run_astock_workflow.py").read_text(encoding="utf-8")
    assert "name: astock-quant-research" in skill_text
    assert "student-workflow" in helper_text
    assert "auto-refine" in helper_text
    assert "NEXT_ACTIONS.md" in skill_text


def test_installer_copies_skill_to_codex_home(tmp_path):
    codex_home = tmp_path / ".codex"
    proc = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--source",
            str(SKILL_SOURCE),
            "--codex-home",
            str(codex_home),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr

    installed = codex_home / "skills" / "astock-quant-research"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "scripts" / "run_astock_workflow.py").is_file()
    assert (installed / "project_root.txt").read_text(encoding="utf-8").strip() == str(ROOT)
    assert "Installed astock-quant-research" in proc.stdout


def test_installer_requires_force_before_replacing_existing_skill(tmp_path):
    codex_home = tmp_path / ".codex"
    first = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--source",
            str(SKILL_SOURCE),
            "--codex-home",
            str(codex_home),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--source",
            str(SKILL_SOURCE),
            "--codex-home",
            str(codex_home),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert second.returncode != 0
    assert "--force" in (second.stderr + second.stdout)

    forced = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--source",
            str(SKILL_SOURCE),
            "--codex-home",
            str(codex_home),
            "--force",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert forced.returncode == 0, forced.stderr
