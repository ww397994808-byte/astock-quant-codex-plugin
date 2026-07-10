from __future__ import annotations

from strategies.base import avg, stddev


class BollLowerEntry:
    component_name = "BollLowerEntry"

    def __init__(self, window: int = 20, num_std: float = 2.0, **_: object) -> None:
        self.window = int(window)
        self.num_std = float(num_std)

    def check(self, history: list[dict]) -> tuple[bool, str, dict]:
        if len(history) < self.window:
            return False, "布林入场历史不足", {}
        closes = [float(row["close"]) for row in history[-self.window:]]
        middle = avg(closes)
        lower = middle - self.num_std * stddev(closes)
        close = float(history[-1]["close"])
        return close < lower, "收盘价跌破布林下轨", {"middle": middle, "lower": lower}
