# Core5 Relative Strength Grid

This package freezes the current no-future-function research logic for the 5-symbol high-dividend grid basket.

## Fixed Rule

- Parameter scoring: `recent3`
- Parameter lookback: prior 12 months
- Symbol relative-strength lookback: prior 2 months
- Monthly holding: top 1 symbol, 100%
- Single-symbol execution: 30-minute grid, T+1 sell rule, buy-first inside each 30m interval, fees, lot size, and implemented dividends
- No per-start-year best setting selection

## Run

```bash
python3 -m research.core5_relative_strength_grid.cli \
  --out reports/core5_relative_strength_grid_package \
  --starts 2018,2019,2020,2021
```

Outputs:

- `report.md`
- `summary.csv`
- `start_YYYY_equity.csv`
- `start_YYYY_decisions.csv`

## Important Caveat

The package removes parameter-level future leakage by selecting parameters each month using only prior data. Portfolio-level monthly capital rotation is modeled from symbol equity curves; extra cross-symbol rebalance slippage is not separately charged.
