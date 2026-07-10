from __future__ import annotations


class CooldownFilter:
    component_name = "CooldownFilter"

    def __init__(self, cooldown_bars: int = 3, **_: object) -> None:
        self.cooldown_bars = int(cooldown_bars)

    def allow(self, history: list[dict], state: dict | None = None) -> tuple[bool, str, dict]:
        state = state or {}
        bars = int(state.get("bars_since_signal", self.cooldown_bars))
        return bars >= self.cooldown_bars, "冷却过滤：距离上次信号足够远", {"bars_since_signal": bars}
