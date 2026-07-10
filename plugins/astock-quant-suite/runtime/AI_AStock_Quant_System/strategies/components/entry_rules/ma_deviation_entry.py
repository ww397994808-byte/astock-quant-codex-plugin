from __future__ import annotations

from strategies.base import avg


class MADeviationEntry:
    component_name = "MADeviationEntry"

    def __init__(self, window: int = 20, deviation: float = 0.06, **_: object) -> None:
        self.window = int(window)
        self.deviation = float(deviation)

    def check(self, history: list[dict]) -> tuple[bool, str, dict]:
        if len(history) < self.window:
            return False, "均线偏离入场历史不足", {}
        closes = [float(row["close"]) for row in history[-self.window:]]
        ma = avg(closes)
        close = closes[-1]
        deviation = close / ma - 1 if ma else 0.0
        return deviation <= -self.deviation, "价格低于均线达到偏离阈值", {"ma": ma, "deviation": deviation}
