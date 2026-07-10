from __future__ import annotations

from core.order import Signal
from strategies.base import StrategyBase


class GridStrategy(StrategyBase):
    name = "grid"

    def validate_params(self) -> None:
        self.grid_step = float(self.params.get("grid_step", 0.03))
        self.levels = int(self.params.get("levels", 3))
        self.layer_percent = float(self.params.get("layer_percent", 0.1))
        if self.grid_step <= 0 or self.levels <= 0 or not (0 < self.layer_percent <= 1):
            raise ValueError("网格参数错误：grid_step>0, levels>0, 0<layer_percent<=1")

    def generate_signal(self, history_data: list[dict]) -> Signal:
        row = history_data[-1]
        return Signal(row["symbol"], row["date"], "HOLD", 0.0, "网格策略由 GridTemplate 管理层级和订单意图")

    def describe(self) -> str:
        return f"网格策略 grid_step={self.grid_step}, levels={self.levels}, layer_percent={self.layer_percent}"
