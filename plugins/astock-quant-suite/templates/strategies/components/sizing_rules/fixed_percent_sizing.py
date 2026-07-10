from __future__ import annotations


class FixedPercentSizing:
    component_name = "FixedPercentSizing"

    def __init__(self, percent: float = 0.5, **_: object) -> None:
        self.percent = float(percent)

    def target_percent(self, history: list[dict], state: dict) -> float:
        return self.percent
