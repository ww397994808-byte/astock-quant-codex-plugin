from __future__ import annotations


class ReducedPositionSizing:
    component_name = "ReducedPositionSizing"

    def __init__(self, percent: float = 0.2, **_: object) -> None:
        self.percent = float(percent)

    def target_percent(self, history: list[dict], state: dict) -> float:
        return self.percent
