from __future__ import annotations

import math


def max_drawdown(equity: list[float]) -> float:
    peak = -math.inf
    mdd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            mdd = min(mdd, value / peak - 1)
    return mdd


def calmar(total_ret: float, mdd: float) -> float:
    return total_ret / abs(mdd) if mdd else 0.0


def sortino(returns: list[float]) -> float:
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return 0.0
    downside_dev = (sum(r * r for r in downside) / len(downside)) ** 0.5
    return mean / downside_dev * (252 ** 0.5) if downside_dev else 0.0


def recovery_time(equity: list[float]) -> int:
    peak = -math.inf
    underwater = 0
    max_recovery = 0
    for value in equity:
        if value >= peak:
            peak = value
            underwater = 0
        else:
            underwater += 1
            max_recovery = max(max_recovery, underwater)
    return max_recovery

