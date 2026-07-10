from __future__ import annotations


def trade_metrics(trades: list[dict]) -> dict:
    sells = [t for t in trades if t.get("action") == "SELL"]
    if not sells:
        return {"win_rate": 0.0, "profit_factor": 0.0, "average_win": 0.0, "average_loss": 0.0}
    # First version approximates per-trade result from sell amount after fees.
    profits = [float(t.get("amount", 0)) - float(t.get("total_fee", 0)) for t in sells]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]
    return {
        "win_rate": len(wins) / len(profits) if profits else 0.0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses and sum(losses) else 0.0,
        "average_win": sum(wins) / len(wins) if wins else 0.0,
        "average_loss": sum(losses) / len(losses) if losses else 0.0,
    }

