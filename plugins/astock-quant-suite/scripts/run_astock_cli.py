#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_RUNTIME = PLUGIN_ROOT / "runtime" / "AI_AStock_Quant_System"


def default_project() -> Path:
    env_project = os.environ.get("ASTOCK_QUANT_PROJECT")
    if env_project:
        return Path(env_project).expanduser()
    marker = PLUGIN_ROOT / "skills" / "astock-quant-research" / "project_root.txt"
    if marker.is_file():
        text = marker.read_text(encoding="utf-8").strip()
        if text:
            return Path(text).expanduser()
    return BUNDLED_RUNTIME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bundled AStock Quant CLI.")
    parser.add_argument("--project", default=str(default_project()), help="Runtime directory containing cli.py.")
    parser.add_argument("cli_args", nargs=argparse.REMAINDER, help="Arguments passed to cli.py.")
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    project = Path(ns.project).expanduser().resolve()
    if not (project / "cli.py").is_file():
        raise SystemExit(f"Project root is invalid: {project}")
    args = list(ns.cli_args)
    if args and args[0] == "--":
        args = args[1:]
    return subprocess.run([sys.executable, "cli.py", *args], cwd=project, text=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())
