from __future__ import annotations

from core.fees import FeeCalculator
from core.market_rules import MarketRules
from core.order import Order, Signal, Trade
from core.portfolio import Portfolio
from core.risk_manager import RiskManager


class ExecutionEngine:
    def __init__(self, market_rules: MarketRules | None = None, fee_calculator: FeeCalculator | None = None) -> None:
        self.market_rules = market_rules or MarketRules()
        self.fee_calculator = fee_calculator or FeeCalculator()
        self.risk_manager = RiskManager(self.market_rules)

    def signal_to_order(self, signal: Signal, portfolio: Portfolio, execute_row: dict) -> Order | None:
        if signal.action == "HOLD":
            return None
        price = float(execute_row["open"])
        current_qty = portfolio.positions.total(signal.symbol)
        if signal.target_position is not None:
            target_qty = signal.target_position
        elif signal.target_percent is not None:
            equity = portfolio.equity(signal.symbol, price)
            target_value = equity * signal.target_percent
            target_qty = int(target_value // (price * self.market_rules.lot_size)) * self.market_rules.lot_size
        else:
            return None
        delta = target_qty - current_qty
        if signal.action == "BUY" and delta <= 0:
            return None
        if signal.action == "SELL":
            sell_qty = current_qty if target_qty <= 0 else max(0, current_qty - target_qty)
            if sell_qty <= 0:
                return None
            delta = -sell_qty
        action = "BUY" if delta > 0 else "SELL"
        return Order(signal.symbol, action, abs(delta), signal.signal_time, execute_row["datetime"], price=price, reason=signal.reason, timeframe=execute_row.get("timeframe", signal.timeframe))

    def execute(self, order: Order, portfolio: Portfolio, execute_row: dict, prev_close: float) -> tuple[Order, Trade | None]:
        tradable = self.market_rules.is_tradable_bar(execute_row)
        if not tradable.ok:
            order.status = "REJECTED"
            order.reason = tradable.reason
            return order, None
        price = float(execute_row["open"])
        if order.action == "BUY" and self.market_rules.is_limit_up(prev_close, execute_row, price):
            order.status = "REJECTED"
            order.reason = "涨停价禁止买入"
            return order, None
        if order.action == "SELL" and self.market_rules.is_limit_down(prev_close, execute_row, price):
            order.status = "REJECTED"
            order.reason = "跌停价禁止卖出"
            return order, None
        fees = self.fee_calculator.calculate(order.action, price, order.quantity)
        risk = self.risk_manager.check_order(order, portfolio, price, fees.total)
        if not risk.ok:
            order.status = "REJECTED"
            order.reason = risk.reason
            return order, None
        amount = price * order.quantity
        if order.action == "BUY":
            portfolio.cash -= amount + fees.total
            portfolio.positions.buy(order.symbol, order.quantity, order.execute_time)
        else:
            portfolio.cash += amount - fees.total
            portfolio.positions.sell(order.symbol, order.quantity)
        portfolio.ensure_non_negative()
        order.status = "FILLED"
        trade = Trade(
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            price=price,
            amount=amount,
            signal_time=order.signal_time,
            execute_time=order.execute_time,
            commission=fees.commission,
            stamp_tax=fees.stamp_tax,
            transfer_fee=fees.transfer_fee,
            total_fee=fees.total,
            reason=order.reason,
            timeframe=order.timeframe,
        )
        return order, trade
