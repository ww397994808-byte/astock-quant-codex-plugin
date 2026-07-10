# Beginner Workflow

This workflow is designed for a learner with no quant engineering background.

## Stage Order

1. Intake: turn a natural-language idea into structured requirements and `backtest_plan.yaml`.
2. Data: fetch or verify symbol, timeframe, adjustment mode, and data quality.
3. Backtest: run the strategy using the template that matches its archetype.
4. Audit: check future leak, A股 trading rules, data quality, and adjustment safety.
5. Paper: run simulated observation and require enough observed bars/trades before promotion.
6. Stage check: summarize evidence and blockers.
7. QMT readonly: confirm account/cash/positions/orders/trades can be read.
8. Pretrade: only after all previous gates; still requires manual confirmation.

## Command Map

Use these commands from the project root:

One-command beginner path:

```bash
python3 cli.py student-workflow --idea "中国神华日线布林低吸波段，控制回撤" --timeframe 1d --adjust point_in_time_qfq
```

For a more guided beginner run:

```bash
python3 cli.py student-workflow --idea "中国神华日线布林低吸波段，控制回撤" --timeframe 1d --adjust point_in_time_qfq --auto-refine
```

Add `--strategy <策略名>` only when the learner already knows which registered strategy to use.
Add `--symbol <代码或名称>` only when the idea text does not contain a recognizable symbol name.
Add `--data <路径>` only for a teacher-provided dataset; otherwise let the workflow fetch/prepare local data.
Auto selection currently supports `boll_mean_reversion`, `ma_cross`, `dividend_drawdown`, and `grid`.

If the result is `INVALID`, read `NEXT_ACTIONS.md`. It converts blockers into concrete edits to the next version of the strategy idea and gives a rerun command. Then read `STUDENT_DIAGNOSTICS.md` to distinguish whether the blocker is short observation, too few signals, excessive drawdown, rejected simulated orders, or QMT readonly. With `--auto-refine`, the report also records the original idea, the refined idea, and each attempt. If `STUDENT_EXPERIMENTS.md` exists, use it only as a ranked research queue; every candidate still needs audit, paper observation, stage-check, QMT readonly, and pretrade gates.

Candidate commands may include `--strategy-params '{"window":15,"num_std":1.8}'`. Preserve that JSON exactly when rerunning the candidate.

Manual path:

```bash
python3 cli.py intake --idea "<策略想法>"
python3 cli.py intake-chat --idea "<策略想法>"
python3 cli.py data-status --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq
python3 cli.py fetch-data --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq
python3 cli.py backtest --strategy boll_mean_reversion --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq
python3 cli.py audit --run-id latest
python3 cli.py paper --strategy boll_mean_reversion --symbol 601088.SH --timeframe 1d --adjust point_in_time_qfq --plan-run-id <intake_run_id>
python3 cli.py stage-check --run-id latest --plan-run-id <intake_run_id>
python3 cli.py qmt-check
python3 cli.py pretrade-check --strategy <策略名> --symbol <代码> --run-id <paper_run_id> --plan-run-id <intake_run_id> --qmt-run-id <qmt_run_id>
```

## Promotion Rule

Only promote when the current report says the next stage is allowed. Never infer permission from profitability alone.

If `stage-check` says:

- `RESEARCH_ONLY`: explain the missing evidence and keep researching.
- `BACKTEST_VALID`: require readiness and paper observation.
- `PAPER_READY`: run or extend paper observation using the policy selected from the backtest plan.
- `PAPER_OBSERVED`: run QMT readonly.
- `QMT_READONLY_READY`: run pretrade checks.
- `PRETRADE_VALID`: require explicit human confirmation before any live candidate discussion.
- `INVALID`: stop promotion and fix the blocker.
