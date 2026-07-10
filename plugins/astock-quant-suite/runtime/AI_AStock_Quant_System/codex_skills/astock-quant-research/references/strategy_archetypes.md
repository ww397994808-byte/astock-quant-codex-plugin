# Strategy Archetypes

Use the archetype to decide the required data, template, and review risks.

## Single-Symbol Timing / Swing

Examples: Bollinger mean reversion, moving-average trend, weekly low-buy swing.

- Universe: one symbol.
- Typical timeframe: `1d`, `1w`, sometimes `1h`.
- Execution: signal after close, fill next bar open by default.
- Risks: same-bar close fill, ordinary qfq leak, too few trades.

## Grid

Examples: fixed price grid, volatility grid, mean-reversion grid.

- Universe: one symbol.
- Requires position accounting and repeated order state.
- Risks: assuming infinite capital, ignoring T+1, ignoring limit-up/down.
- Default runnable strategy: `grid`, using `GridTemplate` for level state and order intents.
- Paper gate: stricter than swing; require enough grid fills before QMT readonly.

## Rotation

Examples: coal vs bank, ETF rotation, sector momentum.

- Universe: multiple symbols.
- Requires point-in-time universe and synchronized calendars.
- Risks: full-sample ranking, survivorship bias, unavailable symbols.
- Current beginner workflow: classify and plan only unless a registered rotation strategy and point-in-time score table are provided.

## Stock Selection

Examples: high dividend low volatility, factor ranking, multi-stock screening.

- Universe: many symbols.
- Requires point-in-time factors, rebalance schedule, delist/suspension handling.
- Risks: future financial statements, final universe, cross-sectional normalization over unavailable stocks.
- Current beginner workflow: classify and plan only; first stage does not promote to QMT.

## Intraday A股

Examples: 1h timing, intraday breakout, VWAP-like rules.

- Requires complete intraday bars, lunch break handling, trading calendar, and market-rule checks.
- Must respect T+1 for stock selling.
- Do not promote to QMT without extended paper observation.
