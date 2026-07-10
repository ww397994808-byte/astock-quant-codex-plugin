from __future__ import annotations

from datetime import time

from . import config
from .market import MarketData, completed_ma_before, ma_at


def fee_buy(amount: float) -> float:
    return max(amount * config.COMMISSION, 5.0) + amount * config.TRANSFER_FEE


def fee_sell(amount: float) -> float:
    return max(amount * config.COMMISSION, 5.0) + amount * config.TRANSFER_FEE + amount * config.STAMP_TAX


def normalize_weights(weights: list[float]) -> list[float]:
    total = sum(weights)
    return [x / total for x in weights] if total else [0.25] * 4


def sell_t1(lots: list[list], qty: int, date: str) -> tuple[list[list], int]:
    sold = 0
    remaining = qty
    new_lots = []
    for lot_qty, lot_date in lots:
        if remaining > 0 and lot_date < date:
            take = min(lot_qty, remaining)
            sold += take
            lot_qty -= take
            remaining -= take
        if lot_qty > 0:
            new_lots.append([lot_qty, lot_date])
    return new_lots, sold


def buy_sell_multipliers(market: MarketData, row_index: int, strategy: dict) -> tuple[float, float, float]:
    filt = strategy["filter"]
    if filt["mode"] == "none":
        return 1.0, 1.0, 1.0
    row = market.rows[row_index]
    close = row["close"]
    if filt["mode"] == "long_ma_guard":
        mult = 1.0
        long_ma = ma_at(market, row_index, filt["long_ma"])
        if long_ma and close < long_ma:
            mult *= filt["below_long_mult"]
        now = completed_ma_before(market, row["date"], filt["long_ma"], 0)
        past = completed_ma_before(market, row["date"], filt["long_ma"], filt["slope_days"])
        if now and past and now < past:
            mult *= filt["down_slope_mult"]
        return mult, 1.0, 1.0
    if filt["mode"] == "trend_regime":
        strong_ma = ma_at(market, row_index, filt["strong_ma"])
        weak_ma = ma_at(market, row_index, filt["weak_ma"])
        strong_now = completed_ma_before(market, row["date"], filt["strong_ma"], 0)
        strong_past = completed_ma_before(market, row["date"], filt["strong_ma"], filt["strong_slope_days"])
        weak_now = completed_ma_before(market, row["date"], filt["weak_ma"], 0)
        weak_past = completed_ma_before(market, row["date"], filt["weak_ma"], filt["weak_slope_days"])
        strong = strong_ma and strong_now and strong_past and close > strong_ma and strong_now > strong_past
        weak = weak_ma and weak_now and weak_past and (close < weak_ma or weak_now < weak_past)
        if strong:
            return filt["strong_buy_mult"], filt["strong_sell_qty_mult"], filt["strong_sell_widen"]
        if weak:
            return filt["weak_buy_mult"], filt["weak_sell_qty_mult"], 1.0
    return 1.0, 1.0, 1.0


def simulate_symbol_grid(market: MarketData, strategy: dict, dividend_factor: float = 1.0, keep: bool = False) -> dict:
    cash = config.INITIAL_CASH
    first_price = market.rows[0]["open"]
    lots: list[list] = []
    init_frac = strategy["initial_position_fraction"]
    if init_frac > 0:
        qty = int((config.INITIAL_CASH * init_frac) / first_price / 100) * 100
        if qty >= 100:
            lots.append([qty, "1900-01-01"])
            cash -= qty * first_price

    trades = []
    points = []
    dividends = []
    today = None
    today_fluent_money = 0.0
    buy_weights = normalize_weights(strategy["buy_weights"])
    dividend_by_date = config.DIVIDENDS.get(market.symbol, {})

    for i, row in enumerate(market.rows):
        if row["date"] != today:
            today = row["date"]
            today_fluent_money = 0.0
            dividend = dividend_by_date.get(today)
            if dividend:
                shares = sum(q for q, _ in lots)
                amount = shares * dividend * dividend_factor
                if amount:
                    cash += amount
                    dividends.append({"symbol": market.symbol, "date": today, "shares": shares, "dividend_per_share": dividend, "cash": amount})

        shares = sum(q for q, _ in lots)
        points.append({"dt": row["dt"], "date": row["date"], "equity": cash + shares * row["close"]})

        if row["time"] < time(9, 30) or (time(11, 30) < row["time"] < time(13, 0)) or row["time"] > time(15, 0):
            continue
        if row["time"].minute % strategy["refresh_minutes"] != 0:
            continue
        ma = ma_at(market, i, strategy["ma_period"])
        if ma is None:
            continue

        close = row["close"]
        buy_mult, sell_qty_mult, sell_widen = buy_sell_multipliers(market, i, strategy)
        atr_factor = market.atr_factors[row["date"]] * strategy["atr_mult"]
        buy_levels = [round(ma * (1 - p * atr_factor), 3) for p in strategy["buy_discounts"]]
        sell_levels = [round(ma * (1 + p * atr_factor * sell_widen), 3) for p in strategy["sell_premiums"]]
        buy_levels = [min(px, close) for px in buy_levels]
        sell_levels = [max(px, close) for px in sell_levels]

        next_rows = []
        j = i + 1
        while j < len(market.rows) and market.rows[j]["date"] == row["date"]:
            next_rows.append(market.rows[j])
            if market.rows[j]["time"].minute % strategy["refresh_minutes"] == 0 and market.rows[j]["dt"] > row["dt"]:
                break
            j += 1
        if not next_rows:
            continue

        def do_sells(low: float, high: float) -> None:
            nonlocal cash, lots, today_fluent_money
            for level_no, px in reversed(list(enumerate(sell_levels, start=1))):
                old_shares_now = sum(q for q, d in lots if d < row["date"])
                qty = int((old_shares_now / strategy["position_slices"] * sell_qty_mult) // 100 * 100)
                if high >= px and qty >= 100:
                    lots, sold = sell_t1(lots, qty, row["date"])
                    if sold >= 100:
                        amount = sold * px
                        cash += amount - fee_sell(amount)
                        today_fluent_money += amount
                        if keep:
                            trades.append({"symbol": market.symbol, "datetime": row["dt"].isoformat(sep=" "), "date": row["date"], "action": "SELL", "level": level_no, "qty": sold, "price": px})

        def do_buys(low: float, high: float) -> None:
            nonlocal cash, lots
            if buy_mult <= 0:
                return
            for level_no, px in enumerate(buy_levels, start=1):
                if low <= px:
                    lever_money_qty = int((cash / close / strategy["cash_slices"]) // 100 * 100)
                    reinvest_qty = int((today_fluent_money * buy_weights[level_no - 1] / close) // 100 * 100)
                    qty = int((lever_money_qty + reinvest_qty) * buy_mult // 100 * 100)
                    affordable = int(cash / (px * 1.00031) // 100 * 100)
                    qty = min(qty, affordable)
                    if qty >= 100:
                        amount = qty * px
                        cash -= amount + fee_buy(amount)
                        lots.append([qty, row["date"]])
                        if keep:
                            trades.append({"symbol": market.symbol, "datetime": row["dt"].isoformat(sep=" "), "date": row["date"], "action": "BUY", "level": level_no, "qty": qty, "price": px})

        for bar in next_rows:
            do_buys(bar["low"], bar["high"])
            do_sells(bar["low"], bar["high"])

    final_shares = sum(q for q, _ in lots)
    final_equity = cash + final_shares * market.rows[-1]["close"]
    points.append({"dt": market.rows[-1]["dt"], "date": market.rows[-1]["date"], "equity": final_equity})
    total = final_equity / config.INITIAL_CASH - 1
    result = {
        "symbol": market.symbol,
        "total_return": total,
        "final_equity": final_equity,
        "trade_count": len(trades) if keep else None,
        "dividend_cash": sum(x["cash"] for x in dividends),
    }
    if keep:
        result["points"] = points
        result["trades"] = trades
        result["dividends"] = dividends
    return result
