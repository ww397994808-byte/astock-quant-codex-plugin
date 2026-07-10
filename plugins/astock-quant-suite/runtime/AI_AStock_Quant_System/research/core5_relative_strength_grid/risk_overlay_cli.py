from __future__ import annotations

import argparse
from pathlib import Path

from .risk_overlay import run_overlay_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply simple cash-buffer risk overlays to Core5 fixed-rule decisions.")
    parser.add_argument("--base", default="reports/core5_relative_strength_grid_package", help="Directory containing start_YYYY_decisions.csv files.")
    parser.add_argument("--out", default="reports/core5_relative_strength_grid_risk_overlay", help="Output directory.")
    parser.add_argument("--starts", default="2018,2019,2020,2021", help="Comma-separated start years.")
    args = parser.parse_args()

    start_years = tuple(x.strip() for x in args.starts.split(",") if x.strip())
    run_overlay_report(base_decision_dir=Path(args.base), out_dir=Path(args.out), start_years=start_years)
    print(Path(args.out).resolve() / "report.md")


if __name__ == "__main__":
    main()
