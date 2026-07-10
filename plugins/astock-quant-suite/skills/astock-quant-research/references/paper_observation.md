# Paper Observation

Paper observation is not one universal threshold. Load the policy from `backtest_plan.yaml` by passing `--plan-run-id`.

```bash
python3 cli.py paper --strategy <策略名> --symbol <代码> --timeframe <周期> --adjust point_in_time_qfq --plan-run-id <intake_run_id>
```

## Current Policies

- Daily timing/swing: at least 20 observed days, 3 trades, and 1 completed buy/sell round.
- Weekly timing/swing: at least 20 observed bars, 1 trade, and 1 completed buy/sell round.
- Intraday timing/swing: at least 20 observed bars, 6 trades, and 3 completed buy/sell rounds.
- Grid: at least 20 to 30 observed bars, 8 trades, and 3 completed buy/sell rounds.
- Rotation / portfolio rebalance: at least 24 to 60 observed bars, 4 trades, and 2 completed buy/sell rounds.
- Stock selection: at least 36 to 90 observed bars, 5 trades, and 3 completed buy/sell rounds; first stage still does not use it as QMT permission.

All policies also enforce the max drawdown limit and rejected order rate limit in `paper_observation.json`.

The paper command writes `paper_observation_policy_card.json`. Use this card when explaining the gate to beginners: each requirement has actual value, required value, comparator, and PASS/FAIL status.

## Interpretation

If paper observation is `INVALID`, do not run QMT promotion steps. Explain the exact missing evidence, usually not enough observations, not enough trades, not enough completed buy/sell rounds, excessive drawdown, or too many rejected simulated orders.

If paper observation is `VALID`, it only permits the next gate, QMT readonly. It does not permit real trading.
