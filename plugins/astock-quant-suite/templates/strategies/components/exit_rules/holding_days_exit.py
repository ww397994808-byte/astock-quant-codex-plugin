from __future__ import annotations


class HoldingDaysExit:
    component_name = "HoldingDaysExit"

    def __init__(self, max_holding_bars: int = 20, **_: object) -> None:
        self.max_holding_bars = int(max_holding_bars)

    def check(self, history: list[dict], state: dict) -> tuple[bool, str, dict]:
        bars = int(state.get("holding_bars", 0))
        return bars >= self.max_holding_bars, "达到最大持仓周期", {"holding_bars": bars}
