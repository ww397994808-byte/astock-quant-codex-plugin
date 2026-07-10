#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_RUNTIME = PLUGIN_ROOT / "runtime" / "AI_AStock_Quant_System"
DEFAULT_TARGET = Path.home() / ".codex" / "astock-quant-suite" / "AI_AStock_Quant_System"


EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "reports",
    "data_lake",
    "handoff_packages",
    "archives",
}
EXCLUDED_FILES = {
    ".DS_Store",
    "config/qmt_config.yaml",
}


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def should_skip(path: Path, root: Path) -> bool:
    rel = relative_path(path, root)
    if rel in EXCLUDED_FILES:
        return True
    return any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts)


def copy_runtime(source: Path, target: Path, force: bool) -> None:
    if not (source / "cli.py").is_file():
        raise SystemExit(f"Bundled runtime is incomplete: {source}")
    if target.exists() and any(target.iterdir()) and not force:
        raise SystemExit(f"Target already exists. Re-run with --force: {target}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if should_skip(item, source):
            continue
        dest = target / item.relative_to(source)
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
    for dirname in ("reports", "data_lake", "handoff_packages", "data/raw", "data/processed"):
        (target / dirname).mkdir(parents=True, exist_ok=True)


def run_cli(target: Path, *args: str) -> int:
    cmd = [sys.executable, "cli.py", *args]
    return subprocess.run(cmd, cwd=target, text=True).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the bundled A-share quant runtime safely.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Destination runtime directory.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing target tree.")
    parser.add_argument("--skip-doctor", action="store_true", help="Copy only; do not run checks.")
    parser.add_argument("--init-qmt-config", action="store_true", help="Create safe local QMT config.")
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    target = Path(ns.target).expanduser().resolve()
    copy_runtime(BUNDLED_RUNTIME, target, ns.force)

    if ns.init_qmt_config:
        code = run_cli(target, "qmt-config-init")
        if code != 0:
            return code

    if not ns.skip_doctor:
        code = run_cli(target, "student-doctor")
        if code != 0:
            return code

    marker = PLUGIN_ROOT / "skills" / "astock-quant-research" / "project_root.txt"
    marker.write_text(str(target) + "\n", encoding="utf-8")
    print(f"Installed AStock Quant runtime: {target}")
    print("Real trading remains disabled unless the local guarded workflow explicitly allows later gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
