from __future__ import annotations

from metrics.return_metrics import monthly_returns


def pct_returns(equity: list[float]) -> list[float]:
    return [curr / prev - 1 for prev, curr in zip(equity, equity[1:]) if prev]


def rolling_return(equity: list[float], window: int = 20) -> list[float]:
    return [equity[i] / equity[i - window] - 1 for i in range(window, len(equity)) if equity[i - window]]


def rolling_sharpe(equity: list[float], window: int = 20) -> list[float]:
    returns = pct_returns(equity)
    values = []
    for i in range(window, len(returns) + 1):
        sample = returns[i - window:i]
        mean = sum(sample) / len(sample)
        var = sum((r - mean) ** 2 for r in sample) / len(sample)
        values.append(mean / (var ** 0.5) * (252 ** 0.5) if var else 0.0)
    return values


def yearly_return_distribution(equity_rows: list[dict]) -> dict[str, float]:
    buckets: dict[str, tuple[float, float]] = {}
    for row in equity_rows:
        year = row["date"][:4]
        eq = float(row["equity"])
        buckets[year] = (buckets.get(year, (eq, eq))[0], eq)
    return {year: end / start - 1 if start else 0.0 for year, (start, end) in buckets.items()}


def monthly_win_rate(equity_rows: list[dict]) -> float:
    returns = monthly_returns(equity_rows)
    if not returns:
        return 0.0
    return sum(1 for value in returns.values() if value > 0) / len(returns)

