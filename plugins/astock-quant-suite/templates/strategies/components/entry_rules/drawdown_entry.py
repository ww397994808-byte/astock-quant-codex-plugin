from __future__ import annotations


class DrawdownEntry:
    component_name = "DrawdownEntry"

    def __init__(self, lookback: int = 20, drawdown_threshold: float = 0.08, **_: object) -> None:
        self.lookback = int(lookback)
        self.drawdown_threshold = float(drawdown_threshold)

    def check(self, history: list[dict]) -> tuple[bool, str, dict]:
        if len(history) < self.lookback:
            return False, "回撤入场历史不足", {}
        closes = [float(row["close"]) for row in history[-self.lookback:]]
        high = max(closes)
        close = closes[-1]
        drawdown = close / high - 1 if high else 0.0
        return drawdown <= -self.drawdown_threshold, "距离近期高点回撤达到阈值", {"drawdown": drawdown, "lookback_high": high}
