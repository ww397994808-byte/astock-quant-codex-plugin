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


def total_qty(lots: list[dict]) -> float:
    return sum(lot["qty"] for lot in lots)


def sellable_qty(lots: list[dict], date: str) -> float:
    return sum(lot["qty"] for lot in lots if lot["buy_date"] < date)


def sell_from_lots(lots: list[dict], qty: float, date: str) -> float:
    remaining = qty
    sold = 0.0
    for lot in lots:
        if remaining <= 0:
            break
        if lot["buy_date"] >= date:
            continue
        take = min(lot["qty"], remaining)
        lot["qty"] -= take
        sold += take
        remaining -= take
    lots[:] = [lot for lot in lots if lot["qty"] > 1e-10]
    return sold


def portfolio_value(cash: float, lots: list[list[dict]], prices: np.ndarray) -> float:
    return cash + float(sum(total_qty(lots[idx]) * prices[idx] for idx in range(len(lots))))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    cooldown_bars: int,
    no_entry_after: str,
    fee_rate: float = 0.0003,
) -> tuple[dict, list[dict], list[dict]]:
    initial = 1_000_000.0
    cash = initial * 0.5
    lots = [[{"qty": (initial / 6) / open_px[idx, 0], "buy_date": "1900-01-01"}] for idx in range(len(symbols))]
    trades: list[dict] = []
    equity_rows: list[dict] = []
    last_pair_trade: dict[tuple[int, int], int] = {}

    for bar in range(lookback, len(times) - 1):
        date = times[bar][:10]
        equity = portfolio_value(cash, lots, close_px[:, bar])
        stock_value = equity - cash
        weights = np.array([total_qty(lots[idx]) * close_px[idx, bar] / equity for idx in range(len(symbols))])
        equity_rows.append(
            {
                "time": times[bar],
                "equity": equity,
                "cash_weight": cash / equity,
                "stock_weight": stock_value / equity,
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
        trade_date = times[trade_bar][:10]
        prices = open_px[:, trade_bar]
        trade_equity = portfolio_value(cash, lots, prices)
        step_value = trade_equity * step_weight
        min_trade_value = trade_equity * 0.005
        low_current_value = total_qty(lots[low]) * prices[low]
        low_max_value = trade_equity * max_symbol_weight

        sell_value = min(step_value, sellable_qty(lots[high], trade_date) * prices[high])
        buy_capacity = max(0.0, low_max_value - low_current_value)
        paired_value = min(sell_value, buy_capacity)
        if paired_value < min_trade_value:
            continue

        high_qty = sell_from_lots(lots[high], paired_value / prices[high], trade_date)
        actual_sell_value = high_qty * prices[high]
        if actual_sell_value < min_trade_value:
            continue
        cash += actual_sell_value * (1 - fee_rate)
        trades.append(
            {
                "time": times[trade_bar],
                "side": "SELL",
                "symbol": symbols[high],
                "value": float(actual_sell_value),
                "spread": float(spread[high]),
                "spread_gap": gap,
            }
        )

        buy_value = min(actual_sell_value * (1 - fee_rate), buy_capacity)
        low_qty = buy_value * (1 - fee_rate) / prices[low]
        lots[low].append({"qty": low_qty, "buy_date": trade_date})
        cash -= buy_value
        trades.append(
            {
                "time": times[trade_bar],
                "side": "BUY",
                "symbol": symbols[low],
                "value": float(buy_value),
                "spread": float(spread[low]),
                "spread_gap": gap,
            }
        )
        last_pair_trade[pair] = bar

    final = len(times) - 1
    equity = portfolio_value(cash, lots, close_px[:, final])
    values = [row["equity"] for row in equity_rows] + [equity]
    final_weights = np.array([total_qty(lots[idx]) * close_px[idx, final] / equity for idx in range(len(symbols))])
    stats = {
        "lookback": lookback,
        "gap_threshold": gap_threshold,
        "step_weight": step_weight,
        "max_symbol_weight": max_symbol_weight,
        "cooldown_bars": cooldown_bars,
        "no_entry_after": no_entry_after,
        "total_return": values[-1] / values[0] - 1,
        "max_drawdown": max_drawdown(values),
        "trade_count": len(trades),
        "final_cash_weight": cash / equity,
        **{f"final_weight_{symbols[idx]}": float(final_weights[idx]) for idx in range(len(symbols))},
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

    out = Path("reports/refrigerant_brothers_constant_exposure_spread")
    out.mkdir(parents=True, exist_ok=True)
    baseline = buy_and_hold(times, open_px, close_px)
    results = []
    artifacts = {}
    for lookback in [10, 20, 40]:
        for gap_threshold in [0.015, 0.02, 0.03]:
            for step_weight in [1 / 24, 1 / 12, 1 / 6]:
                stats, trades, equity = simulate(
                    times,
                    symbols,
                    open_px,
                    close_px,
                    lookback=lookback,
                    gap_threshold=gap_threshold,
                    step_weight=step_weight,
                    max_symbol_weight=1 / 3,
                    cooldown_bars=80,
                    no_entry_after="14:00",
                )
                key = len(results)
                stats["key"] = key
                stats["excess_return_vs_hold"] = stats["total_return"] - baseline["total_return"]
                results.append(stats)
                artifacts[key] = {"trades": trades, "equity": equity}
    results.sort(key=lambda row: (row["total_return"], -abs(row["max_drawdown"])), reverse=True)
    best = results[0]
    rows = [{k: v for k, v in row.items() if k != "key"} for row in results]
    write_csv(out / "grid_summary.csv", rows)
    write_csv(out / "best_trades.csv", artifacts[best["key"]]["trades"])
    write_csv(out / "best_equity.csv", artifacts[best["key"]]["equity"])
    (out / "summary.json").write_text(
        json.dumps({"baseline": baseline, "top": rows[:20]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# 制冷剂三兄弟恒定股票暴露价差轮动",
        "",
        f"- baseline_return: {baseline['total_return']:.2%}",
        f"- baseline_mdd: {baseline['max_drawdown']:.2%}",
        "",
        "## Top 15",
        "",
    ]
    for idx, row in enumerate(results[:15], start=1):
        lines.append(
            f"{idx}. lb={row['lookback']}, gap={row['gap_threshold']:.2%}, step={row['step_weight']:.2%}: "
            f"ret={row['total_return']:.2%}, excess={row['excess_return_vs_hold']:.2%}, "
            f"mdd={row['max_drawdown']:.2%}, trades={row['trade_count']}, cash={row['final_cash_weight']:.2%}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
