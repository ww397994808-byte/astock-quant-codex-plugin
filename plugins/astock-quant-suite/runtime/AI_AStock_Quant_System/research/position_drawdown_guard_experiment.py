from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core5_relative_strength_grid import config
from core5_relative_strength_grid.grid import buy_sell_multipliers, fee_buy, fee_sell, normalize_weights
from core5_relative_strength_grid.market import MarketData, load_market, ma_at, month_last_dates
from core5_relative_strength_grid.metrics import annual_stats, daily_equity, max_drawdown, pct
from core5_relative_strength_grid.params import make_param_pool
from core5_relative_strength_grid.walk_forward import score_param


SYMBOLS = ["601088.SH", "600900.SH", "601288.SH", "601398.SH", "601939.SH", "601225.SH"]
DATA_DIR = Path("/Users/shejishi/Desktop/30分钟股票数据")
OUT_DIR = Path("reports/position_drawdown_guard_experiment")
START_DATE = "2017-01-01"
END_DATE = "2026-06-26"
LIVE_START_YEAR = "2021"


@dataclass(frozen=True)
class Guard:
    peak_dd: float | None
    cost_dd: float | None
    recovery_ma: int
    derisk_cap: float | None
    name: str


@dataclass(frozen=True)
class SelectionRule:
    param_lookback_months: int = 12
    symbol_lookback_months: int = 2
    switch_gap: float = 0.03
    min_hold_months: int = 3
    portfolio_dd_guard: float = 0.08
    param_score_mode: str = "recent3"


def symbol_path(symbol: str) -> Path:
    code = symbol.split(".")[0]
    prefix = "SZSE" if symbol.endswith(".SZ") else "SSE"
    return DATA_DIR / f"{prefix}_DLY_{code}, 30.csv"


def load_markets() -> dict[str, MarketData]:
    markets = {}
    missing = []
    for symbol in SYMBOLS:
        path = symbol_path(symbol)
        if not path.exists():
            missing.append(str(path))
            continue
        markets[symbol] = load_market(symbol, str(path), START_DATE, END_DATE)
    if missing:
        raise FileNotFoundError("缺少真实行情文件：" + "; ".join(missing))
    return markets


def lot_shares(lots: list[list]) -> int:
    return sum(int(q) for q, *_ in lots)


def avg_cost(lots: list[list]) -> float | None:
    shares = lot_shares(lots)
    if shares <= 0:
        return None
    return sum(q * px for q, _d, px in lots) / shares


def sell_t1_cost_lots(lots: list[list], qty: int, date: str) -> tuple[list[list], int]:
    sold = 0
    remaining = qty
    new_lots = []
    for lot_qty, lot_date, lot_px in lots:
        if remaining > 0 and lot_date < date:
            take = min(lot_qty, remaining)
            sold += take
            lot_qty -= take
            remaining -= take
        if lot_qty > 0:
            new_lots.append([lot_qty, lot_date, lot_px])
    return new_lots, sold


def position_guard_active(market: MarketData, row_index: int, lots: list[list], peak_close: float | None, guard: Guard) -> bool:
    shares = lot_shares(lots)
    if shares <= 0 or guard.peak_dd is None or guard.cost_dd is None:
        return False
    row = market.rows[row_index]
    close = row["close"]
    recovery_ma = ma_at(market, row_index, guard.recovery_ma)
    below_recovery = recovery_ma is not None and close < recovery_ma
    peak_hit = peak_close is not None and close / peak_close - 1 <= -guard.peak_dd
    cost = avg_cost(lots)
    cost_hit = cost is not None and close / cost - 1 <= -guard.cost_dd
    return below_recovery and (peak_hit or cost_hit)


def simulate_symbol_grid_with_position_guard(market: MarketData, strategy: dict, guard: Guard, keep: bool = False) -> dict:
    cash = config.INITIAL_CASH
    first_price = market.rows[0]["open"]
    lots: list[list] = []
    init_frac = strategy["initial_position_fraction"]
    if init_frac > 0:
        qty = int((config.INITIAL_CASH * init_frac) / first_price / 100) * 100
        if qty >= 100:
            lots.append([qty, "1900-01-01", first_price])
            cash -= qty * first_price

    trades = []
    points = []
    today = None
    today_fluent_money = 0.0
    buy_weights = normalize_weights(strategy["buy_weights"])
    peak_close: float | None = None
    blocked_buys = 0
    derisk_sells = 0

    for i, row in enumerate(market.rows):
        if row["date"] != today:
            today = row["date"]
            today_fluent_money = 0.0

        shares = lot_shares(lots)
        if shares > 0:
            peak_close = row["close"] if peak_close is None else max(peak_close, row["close"])
        else:
            peak_close = None
        points.append({"dt": row["dt"], "date": row["date"], "equity": cash + shares * row["close"]})

        if row["time"].hour < 9 or row["time"].hour > 15:
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

        guard_active = position_guard_active(market, i, lots, peak_close, guard)

        def do_sells(low: float, high: float) -> None:
            nonlocal cash, lots, today_fluent_money
            for level_no, px in reversed(list(enumerate(sell_levels, start=1))):
                old_shares_now = sum(q for q, d, _px in lots if d < row["date"])
                qty = int((old_shares_now / strategy["position_slices"] * sell_qty_mult) // 100 * 100)
                if high >= px and qty >= 100:
                    lots, sold = sell_t1_cost_lots(lots, qty, row["date"])
                    if sold >= 100:
                        amount = sold * px
                        cash += amount - fee_sell(amount)
                        today_fluent_money += amount
                        if keep:
                            trades.append({"symbol": market.symbol, "datetime": row["dt"].isoformat(sep=" "), "date": row["date"], "action": "SELL", "level": level_no, "qty": sold, "price": px})

        def do_buys(low: float, high: float) -> None:
            nonlocal cash, lots, blocked_buys
            for level_no, px in enumerate(buy_levels, start=1):
                if low <= px:
                    if guard_active or buy_mult <= 0:
                        blocked_buys += 1
                        continue
                    lever_money_qty = int((cash / close / strategy["cash_slices"]) // 100 * 100)
                    reinvest_qty = int((today_fluent_money * buy_weights[level_no - 1] / close) // 100 * 100)
                    qty = int((lever_money_qty + reinvest_qty) * buy_mult // 100 * 100)
                    affordable = int(cash / (px * 1.00031) // 100 * 100)
                    qty = min(qty, affordable)
                    if qty >= 100:
                        amount = qty * px
                        cash -= amount + fee_buy(amount)
                        lots.append([qty, row["date"], px])
                        if keep:
                            trades.append({"symbol": market.symbol, "datetime": row["dt"].isoformat(sep=" "), "date": row["date"], "action": "BUY", "level": level_no, "qty": qty, "price": px})

        def do_derisk(exec_row: dict) -> None:
            nonlocal cash, lots, derisk_sells
            if not guard_active or guard.derisk_cap is None:
                return
            shares_now = lot_shares(lots)
            if shares_now < 100:
                return
            exec_price = exec_row["open"]
            equity_now = cash + shares_now * exec_price
            current_weight = shares_now * exec_price / equity_now if equity_now > 0 else 0.0
            if current_weight <= guard.derisk_cap:
                return
            target_qty = int((equity_now * guard.derisk_cap / exec_price) // 100 * 100)
            qty = int((shares_now - target_qty) // 100 * 100)
            if qty < 100:
                return
            lots, sold = sell_t1_cost_lots(lots, qty, row["date"])
            if sold >= 100:
                amount = sold * exec_price
                cash += amount - fee_sell(amount)
                derisk_sells += 1
                if keep:
                    trades.append({"symbol": market.symbol, "datetime": exec_row["dt"].isoformat(sep=" "), "date": row["date"], "action": "DERISK_SELL", "level": 0, "qty": sold, "price": exec_price})

        do_derisk(next_rows[0])
        for bar in next_rows:
            do_buys(bar["low"], bar["high"])
            do_sells(bar["low"], bar["high"])

    final_shares = lot_shares(lots)
    final_equity = cash + final_shares * market.rows[-1]["close"]
    points.append({"dt": market.rows[-1]["dt"], "date": market.rows[-1]["date"], "equity": final_equity})
    result = {
        "symbol": market.symbol,
        "total_return": final_equity / config.INITIAL_CASH - 1,
        "final_equity": final_equity,
        "trade_count": len(trades) if keep else None,
        "blocked_buys": blocked_buys,
        "derisk_sells": derisk_sells,
    }
    if keep:
        result["points"] = points
        result["trades"] = trades
    return result


def build_param_equities(markets: dict[str, MarketData], params: list[dict], guard: Guard) -> tuple[dict[str, list[dict[str, float]]], dict[str, int], dict[str, int]]:
    param_equities = {symbol: [] for symbol in SYMBOLS}
    blocked = {symbol: 0 for symbol in SYMBOLS}
    derisk = {symbol: 0 for symbol in SYMBOLS}
    for symbol in SYMBOLS:
        for params_row in params:
            result = simulate_symbol_grid_with_position_guard(markets[symbol], params_row, guard, keep=True)
            param_equities[symbol].append(daily_equity(result))
            blocked[symbol] += int(result["blocked_buys"])
            derisk[symbol] += int(result["derisk_sells"])
    return param_equities, blocked, derisk


def run_walk_forward(param_equities: dict[str, list[dict[str, float]]], rule: SelectionRule) -> dict:
    common_dates = sorted(set.intersection(*(set(eq) for values in param_equities.values() for eq in values)))
    month_dates = month_last_dates(common_dates)
    first_idx = next(
        i for i, date in enumerate(month_dates)
        if date[:4] >= LIVE_START_YEAR and i >= rule.param_lookback_months and i >= rule.symbol_lookback_months
    )
    current = config.INITIAL_CASH
    peak = current
    current_symbol = None
    held_months = 0
    rows = [{"date": month_dates[first_idx], "equity": current}]
    decisions = []

    for idx in range(first_idx, len(month_dates) - 1):
        param_train_dates = month_dates[idx - rule.param_lookback_months : idx + 1]
        symbol_start = month_dates[idx - rule.symbol_lookback_months]
        rebalance_date = month_dates[idx]
        next_date = month_dates[idx + 1]
        selected_param_idx = {}
        symbol_scores = {}
        for symbol in SYMBOLS:
            best_idx = max(
                range(len(param_equities[symbol])),
                key=lambda k: score_param(param_equities[symbol][k], param_train_dates, rule.param_score_mode),
            )
            selected_param_idx[symbol] = best_idx
            symbol_scores[symbol] = param_equities[symbol][best_idx][rebalance_date] / param_equities[symbol][best_idx][symbol_start] - 1

        ranked = sorted(SYMBOLS, key=lambda s: symbol_scores[s], reverse=True)
        desired = ranked[0]
        switched = False
        if current_symbol is None:
            selected = desired
            switched = True
            held_months = 1
        else:
            lead = symbol_scores[desired] - symbol_scores[current_symbol]
            if desired != current_symbol and lead >= rule.switch_gap and held_months >= rule.min_hold_months:
                selected = desired
                switched = True
                held_months = 1
            else:
                selected = current_symbol
                held_months += 1
        current_symbol = selected

        next_return = (
            param_equities[selected][selected_param_idx[selected]][next_date]
            / param_equities[selected][selected_param_idx[selected]][rebalance_date]
            - 1
        )
        portfolio_exposure = 0.5 if current / peak - 1 <= -rule.portfolio_dd_guard else 1.0
        next_return *= portfolio_exposure
        current *= 1 + next_return
        peak = max(peak, current)
        rows.append({"date": next_date, "equity": current})
        decisions.append({
            "rebalance_date": rebalance_date,
            "next_date": next_date,
            "selected": selected,
            "desired": desired,
            "switched": switched,
            "held_months": held_months,
            "next_return": next_return,
            "portfolio_exposure": portfolio_exposure,
            **{f"score_{s}": symbol_scores[s] for s in SYMBOLS},
        })

    values = [r["equity"] for r in rows]
    total = values[-1] / values[0] - 1
    years = (datetime.fromisoformat(rows[-1]["date"]) - datetime.fromisoformat(rows[0]["date"])).days / 365.25
    annual = (1 + total) ** (1 / years) - 1 if total > -1 else -1.0
    mdd = max_drawdown(values)
    return {
        "rows": rows,
        "decisions": decisions,
        "annual_return": annual,
        "total_return": total,
        "max_drawdown": mdd,
        "calmar": annual / abs(mdd) if mdd < 0 else 0.0,
        "annuals": annual_stats(rows),
        "switches": sum(1 for d in decisions if d["switched"]),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    markets = load_markets()
    params = make_param_pool(n_random=0)[:12]
    rule = SelectionRule()
    guards = [Guard(None, None, 5, None, "baseline_no_position_guard")]
    for peak_dd in [0.04, 0.06, 0.08]:
        for cost_dd in [0.03]:
            for recovery_ma in [5, 10]:
                guards.append(Guard(peak_dd, cost_dd, recovery_ma, None, f"pause_peak{peak_dd:.0%}_cost{cost_dd:.0%}_ma{recovery_ma}"))
    for peak_dd in [0.06, 0.08]:
        for cap in [0.6, 0.7, 0.8]:
            guards.append(Guard(peak_dd, 0.03, 10, cap, f"derisk_peak{peak_dd:.0%}_cost3%_ma10_cap{cap:.0%}"))

    summary = []
    detail = {}
    for guard in guards:
        print(f"running {guard.name}", flush=True)
        param_equities, blocked, derisk = build_param_equities(markets, params, guard)
        result = run_walk_forward(param_equities, rule)
        years20 = sum(1 for row in result["annuals"].values() if row["annual_return"] >= 0.20)
        row = {
            "guard": guard.name,
            "peak_dd": guard.peak_dd,
            "cost_dd": guard.cost_dd,
            "recovery_ma": guard.recovery_ma,
            "annual_return": result["annual_return"],
            "max_drawdown": result["max_drawdown"],
            "calmar": result["calmar"],
            "years20": years20,
            "switches": result["switches"],
            "blocked_buys": sum(blocked.values()),
            "derisk_sells": sum(derisk.values()),
        }
        summary.append(row)
        detail[guard.name] = {"result": result, "blocked_by_symbol": blocked, "derisk_by_symbol": derisk}

    summary.sort(key=lambda r: (r["max_drawdown"] >= -0.10, r["annual_return"] >= 0.20, r["calmar"], r["annual_return"]), reverse=True)
    write_csv(OUT_DIR / "summary.csv", summary)
    best = summary[0]
    best_detail = detail[best["guard"]]
    write_csv(OUT_DIR / "best_equity.csv", best_detail["result"]["rows"])
    write_csv(OUT_DIR / "best_decisions.csv", best_detail["result"]["decisions"])
    (OUT_DIR / "best_annuals.json").write_text(json.dumps(best_detail["result"]["annuals"], ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Position Drawdown Guard Experiment",
        "",
        "- no dividends",
        "- no future data: parameter and symbol selection use month-end and earlier data only",
        "- same 30m grid touch execution inside each symbol parameter test",
        "- same conservative intrabar order as prior audit: buy check before sell check; T+1 sell only old lots",
        "- added rule: when held symbol is below recovery MA and either held-period peak drawdown or cost drawdown is breached, pause new grid buys; derisk variants also sell old T+1-eligible shares to a cap at next 30m open",
        "",
        "## Best Rows",
    ]
    for row in summary[:15]:
        lines.append(
            f"- {row['guard']}: annual={pct(row['annual_return'])}, maxDD={pct(row['max_drawdown'])}, "
            f"calmar={row['calmar']:.2f}, years20={row['years20']}/6, "
            f"blocked_buys={row['blocked_buys']}, derisk_sells={row['derisk_sells']}"
        )
    lines.extend(["", "## Best Annual Detail"])
    for year, row in best_detail["result"]["annuals"].items():
        lines.append(f"- {year}: annual={pct(row['annual_return'])}, dd={pct(row['max_drawdown'])}")
    lines.extend([
        "",
        "## Causality Notes",
        "- The guard observes only the current and prior bars of the held symbol.",
        "- It does not use next-month returns, future highs/lows, future rankings, or completed-year statistics.",
        "- It is a position risk brake, not a sector timing switch.",
    ])
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_DIR / "report.md")


if __name__ == "__main__":
    main()
