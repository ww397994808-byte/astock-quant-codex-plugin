from __future__ import annotations


class VolatilityFilter:
    component_name = "VolatilityFilter"

    def __init__(self, max_range: float = 0.12, **_: object) -> None:
        self.max_range = float(max_range)

    def allow(self, history: list[dict]) -> tuple[bool, str, dict]:
        row = history[-1]
        low = float(row["low"])
        high = float(row["high"])
        close = float(row["close"])
        intrabar_range = (high - low) / close if close else 0.0
        return intrabar_range <= self.max_range, "波动过滤：单根波动未超阈值", {"intrabar_range": intrabar_range}
