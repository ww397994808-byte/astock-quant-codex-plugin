from core.fees import FeeCalculator


def test_fee_calculation_not_zero():
    fee = FeeCalculator().calculate("BUY", 10.0, 100)
    assert fee.total > 0
    assert fee.commission >= 5.0


def test_stamp_tax_only_sell():
    buy = FeeCalculator().calculate("BUY", 10.0, 1000)
    sell = FeeCalculator().calculate("SELL", 10.0, 1000)
    assert buy.stamp_tax == 0
    assert sell.stamp_tax > 0

