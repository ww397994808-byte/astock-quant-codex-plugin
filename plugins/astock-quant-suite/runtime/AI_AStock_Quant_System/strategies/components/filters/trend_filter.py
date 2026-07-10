from __future__ import annotations

from strategies.base import avg


class TrendFilter:
    component_name = "TrendFilter"

    def __init__(self, window: int = 20, **_: object) -> None:
        self.window = int(window)

    def allow(self, history: list[dict]) -> tuple[bool, str, dict]:
        if len(history) < self.window:
            return True, "趋势过滤历史不足，默认允许", {}
        ma = avg([float(row["close"]) for row in history[-self.window:]])
        close = float(history[-1]["close"])
        return close >= ma * 0.95, "趋势过滤：价格未明显破坏趋势", {"ma": ma}
