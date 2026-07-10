from __future__ import annotations

from datetime import datetime


def max_drawdown(values: list[float]) -> float:
    peak = values[0]
    mdd = 0.0
    for value in values:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1)
    return mdd


def pct(x: float) -> str:
    return f"{x:.2%}"


def annual_stats(rows: list[dict]) -> dict[str, dict]:
    grouped = {}
    for row in rows:
        grouped.setdefault(row["date"][:4], []).append(row)
    out = {}
    for year, items in sorted(grouped.items()):
        values = [x["equity"] for x in items]
        total = values[-1] / values[0] - 1
        days = max((datetime.fromisoformat(items[-1]["date"]) - datetime.fromisoformat(items[0]["date"])).days, 1)
        out[year] = {
            "total_return": total,
            "annual_return": (1 + total) ** (365.25 / days) - 1 if total > -1 else -1.0,
            "max_drawdown": max_drawdown(values),
        }
    return out


def daily_equity(result: dict) -> dict[str, float]:
    return {point["date"]: point["equity"] for point in result["points"]}
