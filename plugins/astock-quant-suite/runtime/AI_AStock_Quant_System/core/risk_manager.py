from __future__ import annotations

from dataclasses import dataclass

from core.market_rules import MarketRules
from core.order import Order
from core.portfolio import Portfolio


@dataclass
class RiskDecision:
    ok: bool
    reason: str = ""


class RiskManager:
    def __init__(self, market_rules: MarketRules | None = None) -> None:
        self.market_rules = market_rules or MarketRules()

    def check_order(self, order: Order, portfolio: Portfolio, price: float, fees_total: float) -> RiskDecision:
        lot_decision = self.market_rules.validate_lot(order.action, order.quantity)
        if not lot_decision.ok:
            return RiskDecision(False, lot_decision.reason)
        if order.execute_time <= order.signal_time:
            return RiskDecision(False, "成交时间必须晚于信号时间")
        amount = price * order.quantity
        if order.action == "BUY":
            if portfolio.cash < amount + fees_total:
                return RiskDecision(False, "现金不足，禁止买入")
        elif order.action == "SELL":
            if portfolio.positions.available(order.symbol) < order.quantity:
                return RiskDecision(False, "可用持仓不足，禁止卖出")
        else:
            return RiskDecision(False, "未知订单方向")
        return RiskDecision(True)

