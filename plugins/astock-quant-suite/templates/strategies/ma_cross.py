from __future__ import annotations

from core.order import Signal
from strategies.base import StrategyBase, avg


class MACrossStrategy(StrategyBase):
    name = "ma_cross"

    def validate_params(self) -> None:
        self.short_window = int(self.params.get("short_window", 5))
        self.long_window = int(self.params.get("long_window", 20))
        if self.short_window <= 0 or self.long_window <= self.short_window:
            raise ValueError("均线参数必须满足 0 < short_window < long_window")

    def generate_signal(self, history_data: list[dict]) -> Signal:
        row = history_data[-1]
        if len(history_data) < self.long_window + 1:
            return Signal(row["symbol"], row["date"], "HOLD", 0.0, "历史数据不足")
        closes = [r["close"] for r in history_data]
        prev_short = avg(closes[-self.short_window - 1:-1])
        prev_long = avg(closes[-self.long_window - 1:-1])
        curr_short = avg(closes[-self.short_window:])
        curr_long = avg(closes[-self.long_window:])
        if prev_short <= prev_long and curr_short > curr_long:
            return Signal(row["symbol"], row["date"], "BUY", 0.7, "短均线上穿长均线", target_percent=0.5)
        if prev_short >= prev_long and curr_short < curr_long:
            return Signal(row["symbol"], row["date"], "SELL", 0.7, "短均线下穿长均线", target_percent=0.0)
        return Signal(row["symbol"], row["date"], "HOLD", 0.0, "无交叉")

    def describe(self) -> str:
        return f"MA 均线策略 short={self.short_window}, long={self.long_window}"

