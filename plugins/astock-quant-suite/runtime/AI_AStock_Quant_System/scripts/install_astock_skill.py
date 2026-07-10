#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


SKILL_NAME = "astock-quant-research"
REQUIRED_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/future_leak_rules.md",
    "references/workflow.md",
    "references/strategy_archetypes.md",
    "references/paper_observation.md",
    "references/qmt_gate.md",
    "scripts/run_astock_workflow.py",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Install the {SKILL_NAME} Codex skill.")
    parser.add_argument("--source", default=str(repo_root() / "codex_skills" / SKILL_NAME))
    parser.add_argument("--codex-home", default=str(default_codex_home()))
    parser.add_argument("--force", action="store_true", help="Replace an existing installed skill.")
    return parser.parse_args()


def validate_skill(source: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (source / name).is_file()]
    if missing:
        raise SystemExit("Skill package is incomplete. Missing: " + ", ".join(missing))
    text = (source / "SKILL.md").read_text(encoding="utf-8")
    if f"name: {SKILL_NAME}" not in text:
        raise SystemExit(f"SKILL.md must declare name: {SKILL_NAME}")
    script = source / "scripts" / "run_astock_workflow.py"
    if "student-workflow" not in script.read_text(encoding="utf-8"):
        raise SystemExit("Helper script must delegate to cli.py student-workflow")


def install(source: Path, codex_home: Path, force: bool) -> Path:
    validate_skill(source)
    dest = codex_home / "skills" / SKILL_NAME
    if dest.exists():
        if not force:
            raise SystemExit(f"{dest} already exists. Re-run with --force to replace it.")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    (dest / "project_root.txt").write_text(str(repo_root()), encoding="utf-8")
    helper = dest / "scripts" / "run_astock_workflow.py"
    helper.chmod(helper.stat().st_mode | 0o111)
    return dest


def main() -> int:
    ns = parse_args()
    source = Path(ns.source).expanduser().resolve()
    codex_home = Path(ns.codex_home).expanduser().resolve()
    dest = install(source, codex_home, ns.force)
    print(f"Installed {SKILL_NAME} to {dest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
