# QMT Gate

QMT integration must be treated as a staged safety process.

## Readonly First

Run:

```bash
python3 cli.py qmt-check
```

Readonly is valid only when the system can read:

- connection state
- account information
- cash
- positions
- today orders
- today trades
- dry-run safety default

Readonly does not mean real trading is allowed.

## Before Pretrade

Require:

- valid backtest plan
- valid audit
- readiness at least `PAPER_READY`
- valid paper observation
- valid QMT readonly snapshot

Then run:

```bash
python3 cli.py pretrade-check --strategy <策略名> --symbol <代码> --run-id <paper_run_id> --plan-run-id <intake_run_id> --qmt-run-id <qmt_run_id>
```

If `pretrade-check` is invalid, stop. Do not help the learner edit config just to force a pass; explain the failing safety item.

## Manual Confirmation

Real-trade discussion requires explicit human confirmation in the tool's supported confirmation field. Keep real order wiring outside beginner workflow unless the user deliberately asks for advanced implementation.
