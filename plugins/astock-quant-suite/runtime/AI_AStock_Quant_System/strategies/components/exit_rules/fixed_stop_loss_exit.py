from __future__ import annotations


class FixedStopLossExit:
    component_name = "FixedStopLossExit"

    def __init__(self, stop_loss: float = 0.08, **_: object) -> None:
        self.stop_loss = float(stop_loss)

    def check(self, history: list[dict], state: dict) -> tuple[bool, str, dict]:
        entry_price = state.get("entry_price")
        if not entry_price:
            return False, "尚无入场价，不能止损", {}
        close = float(history[-1]["close"])
        loss = close / float(entry_price) - 1
        return loss <= -self.stop_loss, "触发固定止损", {"loss": loss}
