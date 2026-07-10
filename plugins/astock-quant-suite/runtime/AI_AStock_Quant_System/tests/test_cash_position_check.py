from datetime import datetime

from core.order import Order
from core.portfolio import Portfolio
from core.risk_manager import RiskManager


def test_cannot_buy_with_negative_cash_risk():
    p = Portfolio(1000)
    order = Order("601088.SH", "BUY", 1000, datetime(2024, 1, 1), datetime(2024, 1, 2))
    decision = RiskManager().check_order(order, p, price=10.0, fees_total=5.0)
    assert not decision.ok
    assert "现金" in decision.reason


def test_cannot_sell_more_than_available():
    p = Portfolio(100000)
    order = Order("601088.SH", "SELL", 100, datetime(2024, 1, 1), datetime(2024, 1, 2))
    decision = RiskManager().check_order(order, p, price=10.0, fees_total=5.0)
    assert not decision.ok
    assert "持仓" in decision.reason

