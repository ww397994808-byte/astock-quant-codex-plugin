from core.market_rules import MarketRules


def test_limit_up_buy_blocked_for_main_board():
    rules = MarketRules()
    row = {"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0, "is_st": False, "board": "main"}
    assert rules.is_limit_up(10.0, row, 11.0)


def test_limit_down_sell_blocked_for_st():
    rules = MarketRules()
    row = {"open": 9.5, "high": 9.5, "low": 9.5, "close": 9.5, "is_st": True, "board": "main"}
    assert rules.is_limit_down(10.0, row, 9.5)

