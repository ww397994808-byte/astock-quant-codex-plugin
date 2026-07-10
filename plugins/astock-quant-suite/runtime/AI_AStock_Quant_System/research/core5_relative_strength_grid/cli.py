from __future__ import annotations

import argparse
from pathlib import Path

from .config import FixedRule
from .walk_forward import run_fixed_rule_start_check


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Core5 relative-strength grid fixed-rule backtest.")
    parser.add_argument("--out", default="reports/core5_relative_strength_grid_package", help="Output report directory.")
    parser.add_argument("--starts", default="2018,2019,2020,2021", help="Comma-separated start years.")
    parser.add_argument("--n-random", type=int, default=297, help="Number of generic random parameter candidates.")
    args = parser.parse_args()

    start_years = tuple(x.strip() for x in args.starts.split(",") if x.strip())
    rule = FixedRule()
    results = run_fixed_rule_start_check(out_dir=Path(args.out), rule=rule, start_years=start_years, n_random=args.n_random)
    print(Path(args.out).resolve() / "report.md")
    for start_year in start_years:
        result = results[start_year]
        print(
            f"{start_year}: annual={result['annual_return']:.2%}, "
            f"max_dd={result['max_drawdown']:.2%}, "
            f"years_above_20={sum(x['annual_return'] >= 0.20 for x in result['annuals'].values())}/{len(result['annuals'])}"
        )


if __name__ == "__main__":
    main()
