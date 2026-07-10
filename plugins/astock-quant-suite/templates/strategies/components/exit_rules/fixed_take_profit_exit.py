from __future__ import annotations


class FixedTakeProfitExit:
    component_name = "FixedTakeProfitExit"

    def __init__(self, take_profit: float = 0.08, **_: object) -> None:
        self.take_profit = float(take_profit)

    def check(self, history: list[dict], state: dict) -> tuple[bool, str, dict]:
        entry_price = state.get("entry_price")
        if not entry_price:
            return False, "尚无入场价，不能止盈", {}
        close = float(history[-1]["close"])
        gain = close / float(entry_price) - 1
        return gain >= self.take_profit, "达到固定止盈", {"gain": gain}
