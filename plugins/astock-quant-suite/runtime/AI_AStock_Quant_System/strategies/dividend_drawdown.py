from __future__ import annotations

from core.order import Signal
from strategies.base import StrategyBase


class DividendDrawdownStrategy(StrategyBase):
    name = "dividend_drawdown"

    def validate_params(self) -> None:
        self.lookback = int(self.params.get("lookback", 60))
        self.drawdown_threshold = float(self.params.get("drawdown_threshold", 0.12))
        self.rebound_threshold = float(self.params.get("rebound_threshold", 0.06))
        self.stop_loss = float(self.params.get("stop_loss", 0.08))
        if self.lookback <= 5:
            raise ValueError("lookback 必须大于 5")

    def generate_signal(self, history_data: list[dict]) -> Signal:
        row = history_data[-1]
        if len(history_data) < self.lookback:
            return Signal(row["symbol"], row["date"], "HOLD", 0.0, "历史数据不足")
        closes = [r["close"] for r in history_data[-self.lookback:]]
        high = max(closes)
        low = min(closes)
        close = row["close"]
        drawdown = (high - close) / high if high else 0
        rebound = (close - low) / low if low else 0
        metadata = {"lookback_high": high, "lookback_low": low, "drawdown": drawdown, "rebound": rebound}
        if drawdown >= self.drawdown_threshold:
            return Signal(row["symbol"], row["date"], "BUY", 0.6, "高股息标的回撤达到阈值", target_percent=0.4, metadata=metadata)
        if rebound >= self.rebound_threshold:
            return Signal(row["symbol"], row["date"], "SELL", 0.55, "回撤后反弹达到阈值", target_percent=0.0, metadata=metadata)
        return Signal(row["symbol"], row["date"], "HOLD", 0.0, "回撤/反弹未触发", metadata=metadata)

    def describe(self) -> str:
        return "红利股回撤买入策略"

