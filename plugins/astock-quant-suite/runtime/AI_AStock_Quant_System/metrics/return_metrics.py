from __future__ import annotations


def total_return(equity: list[float]) -> float:
    return equity[-1] / equity[0] - 1 if len(equity) >= 2 and equity[0] else 0.0


def cagr(equity: list[float], periods_per_year: int = 252) -> float:
    if len(equity) < 2 or equity[0] <= 0:
        return 0.0
    years = max(1 / periods_per_year, len(equity) / periods_per_year)
    return (equity[-1] / equity[0]) ** (1 / years) - 1


def annual_return(equity: list[float]) -> float:
    return total_return(equity) * 252 / max(1, len(equity))


def monthly_returns(equity_rows: list[dict]) -> dict[str, float]:
    buckets: dict[str, tuple[float, float]] = {}
    for row in equity_rows:
        month = row["date"][:7]
        eq = float(row["equity"])
        buckets[month] = (buckets.get(month, (eq, eq))[0], eq)
    return {month: end / start - 1 if start else 0.0 for month, (start, end) in buckets.items()}

