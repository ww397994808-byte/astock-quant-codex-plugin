# Future Leak Rules

Use these rules as hard audit criteria for A股 strategy research.

## Core Causality Rule

For a signal produced at bar `t`, all signal inputs must be known no later than bar `t`. Allowed inputs include OHLCV, trading calendar, market rule state, and point-in-time corporate action data available at or before `t`.

Any reference to bar `t+1` or later inside signal generation is a future leak.

## Common Invalid Patterns

- `shift(-1)`, `shift(periods=-1)`, `pct_change(-1)`, `diff(-1)`, `lead`, `future_return`, `next_close`, `next_open`, `tomorrow`, `label`, or target columns used as signal inputs.
- Centered rolling windows, including `rolling(..., center=True)`.
- Forward joins or event alignment, including `merge_asof(..., direction="forward")`.
- Using final full-sample ranks, quantiles, normalization, or z-scores when simulating historical signals.
- Filling an order at the same bar close when the signal also depends on that close. Default execution should be next-bar open.
- Same-bar execution is invalid by timeframe bucket: daily signals cannot execute on the same trading day, weekly signals cannot execute in the same ISO week, and intraday signals cannot execute inside the same minute/hour bucket.
- Using ordinary pre-adjusted prices if the adjustment embeds future dividends, splits, or corporate actions. Prefer raw or point-in-time adjusted data.
- Selecting the trading universe using future membership, future fundamentals, or survivorship-only lists.
- Optimizing parameters on the full sample and reporting the same sample as final evidence.

## Review Procedure

1. Locate signal creation code and mark the signal timestamp.
2. Trace every feature used by that signal.
3. Check whether each feature is known at the signal timestamp.
4. Check fill timing. Signal on bar close means earliest default fill is next bar open.
5. If any input is not point-in-time safe, mark the run `INVALID`.

When unsure, choose the conservative result and keep the strategy in research-only mode.
