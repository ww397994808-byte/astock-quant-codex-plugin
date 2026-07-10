from __future__ import annotations

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent
from core.portfolio import Portfolio


class TimingTemplate(BaseBacktestTemplate):
    template_name = "timing"

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        signal = self.strategy.generate_signal(history_data)
        if signal.action == "HOLD":
            return []
        return [OrderIntent(signal.symbol, signal.signal_time, signal.action, signal.reason, signal.target_position, signal.target_percent, signal.confidence, signal.metadata)]

