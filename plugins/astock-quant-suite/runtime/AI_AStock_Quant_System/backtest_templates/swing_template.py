from __future__ import annotations

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent
from core.portfolio import Portfolio


class SwingTemplate(BaseBacktestTemplate):
    template_name = "swing"

    def __init__(self, strategy, symbol: str, initial_cash: float = 1000000, max_holding_days: int | None = None) -> None:
        super().__init__(strategy, symbol, initial_cash)
        self.entry_index: int | None = None
        self.max_holding_days = max_holding_days

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        signal = self.strategy.generate_signal(history_data)
        holding = portfolio.positions.total(self.symbol) > 0
        if signal.action == "BUY" and not holding:
            self.entry_index = index
        if holding and self.max_holding_days is not None and self.entry_index is not None and index - self.entry_index >= self.max_holding_days:
            row = history_data[-1]
            signal.action = "SELL"
            signal.reason = "达到最大持仓周期，时间退出"
            signal.target_percent = 0.0
        if signal.action == "HOLD":
            return []
        return [OrderIntent(signal.symbol, signal.signal_time, signal.action, signal.reason, signal.target_position, signal.target_percent, signal.confidence, signal.metadata)]

