from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


SYMBOL_PATHS = {
    "600160.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_600160, 3.csv",
    "603379.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_603379, 3.csv",
    "605020.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_605020, 3.csv",
}


def load_csv(path: str) -> dict[str, dict[str, float]]:
    rows = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["time"]] = {"open": float(row["open"]), "close": float(row["close"])}
    return rows


def max_drawdown(values: list[float]) -> float:
    peak = values[0]
    mdd = 0.0
    for value in values:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1)
    return mdd


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def total_qty(lots: list[dict]) -> float:
    return sum(lot["qty"] for lot in lots)


def sellable_qty(lots: list[dict], current_date: str) -> float:
    return sum(lot["qty"] for lot in lots if lot["buy_date"] < current_date)


def sell_from_lots(lots: list[dict], qty: float, current_date: str) -> float:
    remaining = qty
    sold = 0.0
    for lot in lots:
        if remaining <= 0:
            break
        if lot["buy_date"] >= current_date:
            continue
        take = min(lot["qty"], remaining)
        lot["qty"] -= take
        remaining -= take
        sold += take
    lots[:] = [lot for lot in lots if lot["qty"] > 1e-10]
    return sold


def portfolio_value(cash: float, lots_by_symbol: list[list[dict]], prices: np.ndarray) -> float:
    stock_value = 0.0
    for idx, lots in enumerate(lots_by_symbol):
        stock_value += total_qty(lots) * prices[idx]
    return cash + stock_value


def simulate(
    times: list[str],
    symbols: list[str],
    open_px: np.ndarray,
    close_px: np.ndarray,
    *,
    lookback: int,
    gap_threshold: float,
    step_weight: float,
    max_symbol_weight: float,
    min_cash_weight: float,
    cooldown_bars: int,
    no_entry_after: str,
    fee_rate: float,
) -> tuple[dict, list[dict], list[dict]]:
    initial = 1_000_000.0
    cash = initial * 0.5
    lots_by_symbol: list[list[dict]] = []
    start_date = times[0][:10]
    for idx in range(len(symbols)):
        qty = (initial / 6) / open_px[idx, 0]
        lots_by_symbol.append([{"qty": qty, "buy_date": "1900-01-01"}])

    trades = []
    equity_rows = []
    last_pair_trade: dict[tuple[int, int], int] = {}

    for bar in range(lookback, len(times) - 1):
        current_date = times[bar][:10]
        mark = close_px[:, bar]
        equity = portfolio_value(cash, lots_by_symbol, mark)
        weights = np.array([total_qty(lots_by_symbol[idx]) * mark[idx] / equity for idx in range(len(symbols))])
        equity_rows.append(
            {
                "time": times[bar],
                "equity": equity,
                "cash": cash,
                "cash_weight": cash / equity,
                **{f"weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
            }
        )

        if times[bar][11:16] > no_entry_after:
            continue

        ret = close_px[:, bar] / close_px[:, bar - lookback] - 1
        spread = ret - float(ret.mean())
        high = int(np.argmax(spread))
        low = int(np.argmin(spread))
        gap = float(spread[high] - spread[low])
        if gap < gap_threshold:
            continue
        pair = (high, low)
        if pair in last_pair_trade and bar - last_pair_trade[pair] < cooldown_bars:
            continue

        trade_bar = bar + 1
        trade_time = times[trade_bar]
        trade_date = trade_time[:10]
        trade_prices = open_px[:, trade_bar]
        trade_equity = portfolio_value(cash, lots_by_symbol, trade_prices)
        step_value = trade_equity * step_weight
        min_trade_value = trade_equity * 0.005
        traded = False

        high_price = trade_prices[high]
        available_qty = sellable_qty(lots_by_symbol[high], trade_date)
        sell_value = min(step_value, available_qty * high_price)
        if sell_value >= min_trade_value:
            qty_target = sell_value / high_price
            qty_sold = sell_from_lots(lots_by_symbol[high], qty_target, trade_date)
            actual_value = qty_sold * high_price
            if actual_value >= min_trade_value:
                cash += actual_value * (1 - fee_rate)
                traded = True
                trades.append(
                    {
                        "time": trade_time,
                        "side": "SELL",
                        "symbol": symbols[high],
                        "price": float(high_price),
                        "quantity": float(qty_sold),
                        "value": float(actual_value),
                        "spread": float(spread[high]),
                        "spread_gap": gap,
                        "reason": "sell_high_t1_lot",
                    }
                )

        low_price = trade_prices[low]
        current_low_value = total_qty(lots_by_symbol[low]) * low_price
        max_low_value = trade_equity * max_symbol_weight
        reserved_cash = trade_equity * min_cash_weight
        buy_value = min(step_value, max_low_value - current_low_value, max(0.0, cash - reserved_cash))
        if buy_value >= min_trade_value:
            qty = buy_value * (1 - fee_rate) / low_price
            lots_by_symbol[low].append({"qty": qty, "buy_date": trade_date})
            cash -= buy_value
            traded = True
            trades.append(
                {
                    "time": trade_time,
                    "side": "BUY",
                    "symbol": symbols[low],
                    "price": float(low_price),
                    "quantity": float(qty),
                    "value": float(buy_value),
                    "spread": float(spread[low]),
                    "spread_gap": gap,
                    "reason": "buy_low_cash_t1_lot",
                }
            )

        if traded:
            last_pair_trade[pair] = bar

    final = len(times) - 1
    equity = portfolio_value(cash, lots_by_symbol, close_px[:, final])
    weights = np.array([total_qty(lots_by_symbol[idx]) * close_px[idx, final] / equity for idx in range(len(symbols))])
    equity_rows.append(
        {
            "time": times[final],
            "equity": equity,
            "cash": cash,
            "cash_weight": cash / equity,
            **{f"weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
        }
    )
    values = [row["equity"] for row in equity_rows]
    stats = {
        "lookback": lookback,
        "gap_threshold": gap_threshold,
        "step_weight": step_weight,
        "max_symbol_weight": max_symbol_weight,
        "min_cash_weight": min_cash_weight,
        "cooldown_bars": cooldown_bars,
        "no_entry_after": no_entry_after,
        "total_return": values[-1] / values[0] - 1,
        "max_drawdown": max_drawdown(values),
        "trade_count": len(trades),
        "buy_count": sum(1 for item in trades if item["side"] == "BUY"),
        "sell_count": sum(1 for item in trades if item["side"] == "SELL"),
        "final_cash_weight": cash / equity,
        **{f"final_weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
    }
    return stats, trades, equity_rows


def buy_and_hold(times: list[str], open_px: np.ndarray, close_px: np.ndarray) -> dict:
    initial = 1_000_000.0
    cash = initial * 0.5
    shares = np.array([(initial / 6) / open_px[idx, 0] for idx in range(open_px.shape[0])])
    values = [cash + float((shares * close_px[:, bar]).sum()) for bar in range(len(times))]
    return {"total_return": values[-1] / values[0] - 1, "max_drawdown": max_drawdown(values)}


def main() -> int:
    raw = {symbol: load_csv(path) for symbol, path in SYMBOL_PATHS.items()}
    symbols = list(SYMBOL_PATHS)
    times = sorted(set.intersection(*(set(rows) for rows in raw.values())))
    open_px = np.zeros((len(symbols), len(times)))
    close_px = np.zeros((len(symbols), len(times)))
    for i, time in enumerate(times):
        for j, symbol in enumerate(symbols):
            open_px[j, i] = raw[symbol][time]["open"]
            close_px[j, i] = raw[symbol][time]["close"]

    out = Path("reports/refrigerant_brothers_cash_add_t1_lot")
    out.mkdir(parents=True, exist_ok=True)
    baseline = buy_and_hold(times, open_px, close_px)
    results = []
    artifacts = {}
    for cooldown_bars in [10, 20, 40, 80]:
        for no_entry_after in ["11:00", "14:00"]:
            stats, trades, equity = simulate(
                times,
                symbols,
                open_px,
                close_px,
                lookback=20,
                gap_threshold=0.015,
                step_weight=1 / 12,
                max_symbol_weight=0.5,
                min_cash_weight=0.05,
                cooldown_bars=cooldown_bars,
                no_entry_after=no_entry_after,
                fee_rate=0.0003,
            )
            key = len(results)
            stats["key"] = key
            stats["excess_return_vs_hold"] = stats["total_return"] - baseline["total_return"]
            results.append(stats)
            artifacts[key] = {"trades": trades, "equity": equity}

    results.sort(key=lambda row: (row["total_return"], -abs(row["max_drawdown"])), reverse=True)
    best = results[0]
    top_rows = [{k: v for k, v in row.items() if k != "key"} for row in results]
    write_csv(out / "grid_summary.csv", top_rows)
    write_csv(out / "best_trades.csv", artifacts[best["key"]]["trades"])
    write_csv(out / "best_equity.csv", artifacts[best["key"]]["equity"])
    (out / "summary.json").write_text(
        json.dumps({"baseline": baseline, "top": top_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# 制冷剂三兄弟现金加仓 T+1 lot 严格回测",
        "",
        f"- baseline_return: {baseline['total_return']:.2%}",
        f"- baseline_mdd: {baseline['max_drawdown']:.2%}",
        "",
        "## Top",
        "",
    ]
    for idx, row in enumerate(results, start=1):
        lines.append(
            f"{idx}. cooldown={row['cooldown_bars']}, no_entry_after={row['no_entry_after']}: "
            f"ret={row['total_return']:.2%}, excess={row['excess_return_vs_hold']:.2%}, "
            f"mdd={row['max_drawdown']:.2%}, trades={row['trade_count']}, "
            f"buy={row['buy_count']}, sell={row['sell_count']}, cash={row['final_cash_weight']:.2%}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
