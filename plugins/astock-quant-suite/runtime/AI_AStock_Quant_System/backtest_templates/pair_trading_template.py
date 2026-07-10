from __future__ import annotations

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent
from core.portfolio import Portfolio


class PairTradingTemplate(BaseBacktestTemplate):
    template_name = "pair_trading"
    BLOCKER = "A股第一版不支持裸卖空或融资融券；本模板不能做真正市场中性配对交易，只能用于做多强弱轮动或 A/H 择强研究骨架。"

    def pair_intents(self, plan_time, long_symbol: str, short_symbol: str, z_score: float, hedge_ratio: float) -> list[OrderIntent]:
        if abs(z_score) < 2:
            return []
        return [
            OrderIntent(long_symbol, plan_time, "BUY", "配对交易多头腿", target_percent=0.3, metadata={"z_score": z_score, "hedge_ratio": hedge_ratio}),
            OrderIntent(short_symbol, plan_time, "SELL", "配对交易空头腿占位；A股第一版不做空，执行层会阻断无持仓卖出", target_percent=0.0, metadata={"z_score": z_score, "hedge_ratio": hedge_ratio}),
        ]

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        return []
