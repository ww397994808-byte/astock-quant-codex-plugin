from __future__ import annotations


class TrailingStopExit:
    component_name = "TrailingStopExit"

    def __init__(self, trail_percent: float = 0.05, **_: object) -> None:
        self.trail_percent = float(trail_percent)

    def check(self, history: list[dict], state: dict) -> tuple[bool, str, dict]:
        close = float(history[-1]["close"])
        peak = max(float(state.get("peak_price", close)), close)
        state["peak_price"] = peak
        drawdown = close / peak - 1 if peak else 0.0
        return drawdown <= -self.trail_percent, "触发移动止盈/回撤退出", {"peak_price": peak, "trail_drawdown": drawdown}
