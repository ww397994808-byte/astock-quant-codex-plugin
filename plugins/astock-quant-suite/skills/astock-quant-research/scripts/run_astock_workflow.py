#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import os
from pathlib import Path


def default_project() -> Path:
    env_project = os.environ.get("ASTOCK_QUANT_PROJECT")
    if env_project:
        return Path(env_project).expanduser()
    marker = Path(__file__).resolve().parents[1] / "project_root.txt"
    if marker.is_file():
        text = marker.read_text(encoding="utf-8").strip()
        if text:
            return Path(text).expanduser()
    bundled_runtime = Path(__file__).resolve().parents[3] / "runtime" / "AI_AStock_Quant_System"
    if (bundled_runtime / "cli.py").is_file():
        return bundled_runtime
    return Path.cwd()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the beginner A股 research-to-paper workflow.")
    parser.add_argument("--project", default=str(default_project()))
    parser.add_argument("--idea", required=True)
    parser.add_argument("--symbol", default="")
    parser.add_argument("--strategy", default="")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--adjust", default="point_in_time_qfq")
    parser.add_argument("--data", default="__auto_fetch__")
    parser.add_argument("--include-qmt", action="store_true")
    parser.add_argument("--auto-refine", action="store_true")
    parser.add_argument("--max-refinements", type=int, default=1)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--case-id", default="")
    return parser.parse_args()


def require_project(project: Path) -> None:
    if not (project / "cli.py").exists():
        raise SystemExit(f"Project root is invalid: {project}")


def main() -> int:
    ns = parse_args()
    project = Path(ns.project).expanduser().resolve()
    require_project(project)

    args = [
        sys.executable,
        "cli.py",
        "student-workflow",
        "--idea",
        ns.idea,
        "--timeframe",
        ns.timeframe,
        "--adjust",
        ns.adjust,
    ]
    if ns.symbol:
        args.extend(["--symbol", ns.symbol])
    if ns.strategy:
        args.extend(["--strategy", ns.strategy])
    if ns.data:
        args.extend(["--data", ns.data])
    if ns.include_qmt:
        args.append("--include-qmt")
    if ns.auto_refine:
        args.extend(["--auto-refine", "--max-refinements", str(ns.max_refinements)])
    if ns.session_id:
        args.extend(["--session-id", ns.session_id])
    if ns.case_id:
        args.extend(["--case-id", ns.case_id])

    proc = subprocess.run(args, cwd=project, text=True)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
