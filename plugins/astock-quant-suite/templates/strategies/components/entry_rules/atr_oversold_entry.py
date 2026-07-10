from __future__ import annotations

from strategies.base import avg


class ATROversoldEntry:
    component_name = "ATROversoldEntry"

    def __init__(self, window: int = 14, atr_multiple: float = 1.5, **_: object) -> None:
        self.window = int(window)
        self.atr_multiple = float(atr_multiple)

    def check(self, history: list[dict]) -> tuple[bool, str, dict]:
        if len(history) < self.window + 1:
            return False, "ATR 超跌入场历史不足", {}
        true_ranges = []
        for prev, curr in zip(history[-self.window - 1 : -1], history[-self.window:]):
            high = float(curr["high"])
            low = float(curr["low"])
            prev_close = float(prev["close"])
            true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        atr = avg(true_ranges)
        close = float(history[-1]["close"])
        prev_close = float(history[-2]["close"])
        drop = prev_close - close
        return drop >= self.atr_multiple * atr, "单根下跌超过 ATR 阈值，超跌入场", {"atr": atr, "drop": drop}
