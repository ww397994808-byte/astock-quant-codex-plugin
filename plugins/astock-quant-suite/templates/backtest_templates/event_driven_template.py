from __future__ import annotations

from datetime import timedelta

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent
from core.portfolio import Portfolio


class EventDrivenTemplate(BaseBacktestTemplate):
    template_name = "event_driven"
    BLOCKER = "事件驱动模板需要稳定事件数据源，包括事件日期、事件类型、公告/财报/分红字段和可复核来源；第一版只保留事件窗口骨架。"

    def __init__(self, strategy, symbol: str, initial_cash: float = 1000000, events: list[dict] | None = None, buy_window_days: int = 0, exit_window_days: int = 5) -> None:
        super().__init__(strategy, symbol, initial_cash)
        self.events = events or []
        self.buy_window_days = buy_window_days
        self.exit_window_days = exit_window_days

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        row = history_data[-1]
        intents: list[OrderIntent] = []
        for event in self.events:
            event_date = event["date"]
            if row["date"].date() == (event_date - timedelta(days=self.buy_window_days)).date():
                intents.append(OrderIntent(self.symbol, row["date"], "BUY", f"事件驱动买入：{event.get('reason', '')}", target_percent=0.3, metadata=event))
            if row["date"].date() == (event_date + timedelta(days=self.exit_window_days)).date():
                intents.append(OrderIntent(self.symbol, row["date"], "SELL", f"事件窗口退出：{event.get('reason', '')}", target_percent=0.0, metadata=event))
        return intents
