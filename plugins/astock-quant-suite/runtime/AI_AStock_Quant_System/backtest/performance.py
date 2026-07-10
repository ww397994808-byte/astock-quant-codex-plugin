from __future__ import annotations


def calculate_performance(equity_curve: list[dict], trades: list[dict], initial_cash: float) -> dict:
    if not equity_curve:
        return {}
    final_equity = float(equity_curve[-1]["equity"])
    total_return = final_equity / initial_cash - 1
    peaks = []
    peak = -1.0
    max_drawdown = 0.0
    for row in equity_curve:
        eq = float(row["equity"])
        peak = max(peak, eq)
        peaks.append(peak)
        if peak > 0:
            max_drawdown = min(max_drawdown, eq / peak - 1)
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    fees = sum(float(t.get("total_fee", 0)) for t in trades)
    stamp = sum(float(t.get("stamp_tax", 0)) for t in trades)
    return {
        "initial_cash": round(initial_cash, 6),
        "final_equity": round(final_equity, 6),
        "total_return": round(total_return, 6),
        "annual_return": round(total_return * 252 / max(1, len(equity_curve)), 6),
        "max_drawdown": round(max_drawdown, 6),
        "win_rate": 0.0,
        "profit_loss_ratio": 0.0,
        "trade_count": len(trades),
        "sell_trade_count": len(sell_trades),
        "total_fee": round(fees, 6),
        "total_stamp_tax": round(stamp, 6),
    }

