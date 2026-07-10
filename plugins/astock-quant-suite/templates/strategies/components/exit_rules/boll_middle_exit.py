from __future__ import annotations

from strategies.base import avg


class BollMiddleExit:
    component_name = "BollMiddleExit"

    def __init__(self, window: int = 20, **_: object) -> None:
        self.window = int(window)

    def check(self, history: list[dict], state: dict) -> tuple[bool, str, dict]:
        if len(history) < self.window:
            return False, "布林中轨退出历史不足", {}
        middle = avg([float(row["close"]) for row in history[-self.window:]])
        close = float(history[-1]["close"])
        return close >= middle, "价格回到布林中轨", {"middle": middle}
