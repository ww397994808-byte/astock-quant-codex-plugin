from __future__ import annotations


class VolatilityAdjustedSizing:
    component_name = "VolatilityAdjustedSizing"

    def __init__(self, base_percent: float = 0.3, max_range: float = 0.1, **_: object) -> None:
        self.base_percent = float(base_percent)
        self.max_range = float(max_range)

    def target_percent(self, history: list[dict], state: dict) -> float:
        row = history[-1]
        close = float(row["close"])
        intrabar_range = (float(row["high"]) - float(row["low"])) / close if close else 0.0
        scale = max(0.3, 1 - intrabar_range / max(self.max_range, 1e-9))
        return round(self.base_percent * scale, 6)
