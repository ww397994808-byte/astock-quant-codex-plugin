from datetime import datetime, timedelta

import pytest

from core.position import PositionBook


def test_t_plus_1_buy_today_not_available_to_sell_today():
    book = PositionBook()
    today = datetime(2024, 1, 2)
    book.buy("601088.SH", 100, today)
    assert book.total("601088.SH") == 100
    assert book.available("601088.SH") == 0
    with pytest.raises(ValueError):
        book.sell("601088.SH", 100)
    book.release_after_close(today + timedelta(days=1))
    assert book.available("601088.SH") == 100

