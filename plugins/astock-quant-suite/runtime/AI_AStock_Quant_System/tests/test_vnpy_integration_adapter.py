from datetime import datetime

from core.order import Order, Trade
from core.portfolio import Portfolio
from integrations.vnpy.vnpy_event_adapter import VnpyEventAdapter, VnpyLikeEvent
from integrations.vnpy.vnpy_order_mapper import VnpyOrderMapper


def test_vnpy_event_adapter_dispatches_without_vnpy_dependency():
    adapter = VnpyEventAdapter()
    seen = []
    adapter.register("EVENT_ORDER", lambda event: seen.append(event.data))
    adapter.put(VnpyLikeEvent("EVENT_ORDER", {"id": 1}))
    assert adapter.drain() == 1
    assert seen == [{"id": 1}]


def test_vnpy_order_mapper_order():
    order = Order("601088.SH", "BUY", 100, datetime(2024, 1, 1), datetime(2024, 1, 2), price=10, status="FILLED")
    mapped = VnpyOrderMapper().to_vnpy_order(order)
    assert mapped.symbol == "601088"
    assert mapped.exchange == "SH"
    assert mapped.direction == "LONG"
    assert mapped.traded == 100


def test_vnpy_order_mapper_trade():
    trade = Trade("601088.SH", "SELL", 100, 10, 1000, datetime(2024, 1, 1), datetime(2024, 1, 2), 5, 0.5, 0.01, 5.51)
    mapped = VnpyOrderMapper().to_vnpy_trade(trade)
    assert mapped.offset == "CLOSE"
    assert mapped.direction == "SHORT"


def test_vnpy_position_mapper_uses_t_plus_1_available_as_yd_volume():
    p = Portfolio(100000)
    p.positions.buy("601088.SH", 100, datetime(2024, 1, 1))
    p.positions.release_after_close(datetime(2024, 1, 2))
    mapped = VnpyOrderMapper().to_vnpy_position(p, "601088.SH")
    assert mapped.volume == 100
    assert mapped.yd_volume == 100

