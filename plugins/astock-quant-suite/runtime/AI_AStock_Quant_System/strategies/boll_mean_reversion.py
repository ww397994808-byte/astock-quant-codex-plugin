from __future__ import annotations

from core.order import Signal
from strategies.base import StrategyBase, avg, stddev


class BollMeanReversionStrategy(StrategyBase):
    name = "boll_mean_reversion"

    def validate_params(self) -> None:
        self.window = int(self.params.get("window", 20))
        self.num_std = float(self.params.get("num_std", 2.0))
        self.stop_loss = float(self.params.get("stop_loss", 0.08))
        if self.window <= 2 or self.num_std <= 0 or not (0 < self.stop_loss < 1):
            raise ValueError("布林线参数错误：window>2, num_std>0, 0<stop_loss<1")

    def generate_signal(self, history_data: list[dict]) -> Signal:
        row = history_data[-1]
        if len(history_data) < self.window:
            return Signal(row["symbol"], row["date"], "HOLD", 0.0, "历史数据不足")
        closes = [r["close"] for r in history_data[-self.window:]]
        middle = avg(closes)
        sigma = stddev(closes)
        lower = middle - self.num_std * sigma
        close = row["close"]
        metadata = {"middle": middle, "lower": lower, "stop_loss": self.stop_loss}
        if close < lower:
            return Signal(row["symbol"], row["date"], "BUY", 0.65, "收盘价跌破布林下轨，低吸信号", target_percent=0.5, metadata=metadata)
        if close >= middle:
            return Signal(row["symbol"], row["date"], "SELL", 0.6, "收盘价回到布林中轨，卖出信号", target_percent=0.0, metadata=metadata)
        return Signal(row["symbol"], row["date"], "HOLD", 0.0, "布林区间内观望", metadata=metadata)

    def describe(self) -> str:
        return f"布林线低吸策略 window={self.window}, num_std={self.num_std}, stop_loss={self.stop_loss}"

