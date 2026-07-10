#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PLUGIN_ROOT / "runtime" / "AI_AStock_Quant_System"
REQUIRED_COMMANDS = [
    "student-doctor",
    "student-start",
    "student-course-path",
    "student-research-contract",
    "student-workflow",
    "student-future-leak-precheck",
    "stage-check",
    "qmt-config-init",
    "qmt-config-status",
    "qmt-check",
    "pretrade-package",
    "pretrade-check",
]


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def main() -> int:
    checks: list[dict[str, str]] = []
    status = "PASS"

    def add(name: str, result: bool, detail: str) -> None:
        nonlocal status
        checks.append({"name": name, "status": "PASS" if result else "FAIL", "detail": detail})
        if not result:
            status = "FAIL"

    add("plugin manifest", (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").is_file(), ".codex-plugin/plugin.json")
    add("skill", (PLUGIN_ROOT / "skills" / "astock-quant-research" / "SKILL.md").is_file(), "astock-quant-research")
    add("runtime cli", (RUNTIME / "cli.py").is_file(), str(RUNTIME / "cli.py"))
    add("qmt private config excluded", not (RUNTIME / "config" / "qmt_config.yaml").exists(), "config/qmt_config.yaml must be user-local")

    if (RUNTIME / "cli.py").is_file():
        help_result = run([sys.executable, "cli.py", "--help"], RUNTIME)
        help_text = help_result.stdout + help_result.stderr
        add("cli help", help_result.returncode == 0, "cli.py --help")
        for command in REQUIRED_COMMANDS:
            add(f"command {command}", command in help_text, "registered")

        doctor_result = run([sys.executable, "cli.py", "student-doctor"], RUNTIME)
        add("student doctor", doctor_result.returncode == 0, doctor_result.stdout.strip().splitlines()[0] if doctor_result.stdout else "no output")

    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
