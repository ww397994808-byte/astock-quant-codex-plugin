from core.market_rules import MarketRules


def test_buy_quantity_must_be_100_lot():
    result = MarketRules().validate_lot("BUY", 50)
    assert not result.ok
    assert "100" in result.reason or "一手" in result.reason

