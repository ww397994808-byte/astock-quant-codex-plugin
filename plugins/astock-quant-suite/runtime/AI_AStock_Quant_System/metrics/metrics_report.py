from __future__ import annotations

import json
from pathlib import Path

from metrics.return_metrics import annual_return, cagr, monthly_returns, total_return
from metrics.risk_metrics import calmar, max_drawdown, recovery_time, sortino
from metrics.stability_metrics import monthly_win_rate, pct_returns, rolling_return, rolling_sharpe, yearly_return_distribution
from metrics.trade_metrics import trade_metrics


def build_metrics(equity_rows: list[dict], trades: list[dict]) -> dict:
    equity = [float(r["equity"]) for r in equity_rows]
    returns = pct_returns(equity)
    total_ret = total_return(equity)
    mdd = max_drawdown(equity)
    return {
        "return": {
            "CAGR": cagr(equity),
            "Annual Return": annual_return(equity),
            "Monthly Return": monthly_returns(equity_rows),
        },
        "risk": {
            "Max Drawdown": mdd,
            "Calmar": calmar(total_ret, mdd),
            "Sortino": sortino(returns),
            "Recovery Time": recovery_time(equity),
        },
        "trade": trade_metrics(trades),
        "stability": {
            "Rolling Sharpe": rolling_sharpe(equity)[-5:],
            "Rolling Return": rolling_return(equity)[-5:],
            "Yearly Return Distribution": yearly_return_distribution(equity_rows),
            "Monthly Win Rate": monthly_win_rate(equity_rows),
        },
    }


def write_metrics_report(path: str | Path, metrics: dict) -> None:
    lines = ["# Metrics Report", "", "```json", json.dumps(metrics, ensure_ascii=False, indent=2), "```"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

