from __future__ import annotations


class VolumeFilter:
    component_name = "VolumeFilter"

    def __init__(self, min_volume: float = 1.0, **_: object) -> None:
        self.min_volume = float(min_volume)

    def allow(self, history: list[dict]) -> tuple[bool, str, dict]:
        volume = float(history[-1].get("volume", 0))
        return volume >= self.min_volume, "成交量过滤：成交量满足阈值", {"volume": volume}
