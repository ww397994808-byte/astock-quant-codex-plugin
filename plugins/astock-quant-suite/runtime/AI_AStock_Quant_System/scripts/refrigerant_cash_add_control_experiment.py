from __future__ import annotations

import csv
import json
import random
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


def run_sim(
    times: list[str],
    symbols: list[str],
    open_px: np.ndarray,
    close_px: np.ndarray,
    *,
    mode: str,
    seed: int = 0,
    lookback: int = 20,
    gap_threshold: float = 0.015,
    step_weight: float = 1 / 12,
    max_symbol_weight: float = 0.5,
    min_cash_weight: float = 0.05,
    cooldown_bars: int = 80,
    no_entry_after: str = "14:00",
    fee_rate: float = 0.0003,
) -> tuple[dict, list[dict], list[dict]]:
    rng = random.Random(seed)
    initial = 1_000_000.0
    cash = initial * 0.5
    lots = [[{"qty": (initial / 6) / open_px[idx, 0], "buy_date": "1900-01-01"}] for idx in range(len(symbols))]
    last_pair_trade: dict[tuple[int, int], int] = {}
    trades: list[dict] = []
    equity_rows: list[dict] = []

    for bar in range(lookback, len(times) - 1):
        date = times[bar][:10]
        equity = portfolio_value(cash, lots, close_px[:, bar])
        weights = np.array([total_qty(lots[idx]) * close_px[idx, bar] / equity for idx in range(len(symbols))])
        equity_rows.append(
            {
                "time": times[bar],
                "equity": equity,
                "cash_weight": cash / equity,
                **{f"weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
            }
        )
        if times[bar][11:16] > no_entry_after:
            continue

        ret = close_px[:, bar] / close_px[:, bar - lookback] - 1
        spread = ret - float(ret.mean())
        high = int(np.argmax(spread))
        low_by_spread = int(np.argmin(spread))
        gap = float(spread[high] - spread[low_by_spread])
        if gap < gap_threshold:
            continue

        if mode == "spread_low":
            low = low_by_spread
        elif mode == "equal_lowest_weight":
            low = int(np.argmin(weights))
        elif mode == "random":
            low = rng.randrange(len(symbols))
        elif mode == "momentum_high":
            low = high
        else:
            raise ValueError(f"unknown mode: {mode}")

        pair = (high, low)
        if pair in last_pair_trade and bar - last_pair_trade[pair] < cooldown_bars:
            continue

        trade_bar = bar + 1
        trade_time = times[trade_bar]
        trade_date = trade_time[:10]
        trade_prices = open_px[:, trade_bar]
        trade_equity = portfolio_value(cash, lots, trade_prices)
        step_value = trade_equity * step_weight
        min_trade_value = trade_equity * 0.005
        traded = False

        # Sell high if possible. This keeps the rebalance/take-profit component
        # identical across modes.
        high_price = trade_prices[high]
        sell_value = min(step_value, sellable_qty(lots[high], trade_date) * high_price)
        if sell_value >= min_trade_value:
            qty = sell_from_lots(lots[high], sell_value / high_price, trade_date)
            actual = qty * high_price
            if actual >= min_trade_value:
                cash += actual * (1 - fee_rate)
                traded = True
                trades.append(
                    {
                        "time": trade_time,
                        "mode": mode,
                        "side": "SELL",
                        "symbol": symbols[high],
                        "value": float(actual),
                        "spread": float(spread[high]),
                        "spread_gap": gap,
                    }
                )

        low_price = trade_prices[low]
        current_low_value = total_qty(lots[low]) * low_price
        max_low_value = trade_equity * max_symbol_weight
        reserved_cash = trade_equity * min_cash_weight
        buy_value = min(step_value, max_low_value - current_low_value, max(0.0, cash - reserved_cash))
        if buy_value >= min_trade_value:
            qty = buy_value * (1 - fee_rate) / low_price
            lots[low].append({"qty": qty, "buy_date": trade_date})
            cash -= buy_value
            traded = True
            trades.append(
                {
                    "time": trade_time,
                    "mode": mode,
                    "side": "BUY",
                    "symbol": symbols[low],
                    "value": float(buy_value),
                    "spread": float(spread[low]),
                    "spread_gap": gap,
                }
            )
        if traded:
            last_pair_trade[pair] = bar

    final = len(times) - 1
    equity = portfolio_value(cash, lots, close_px[:, final])
    weights = np.array([total_qty(lots[idx]) * close_px[idx, final] / equity for idx in range(len(symbols))])
    equity_rows.append(
        {
            "time": times[final],
            "equity": equity,
            "cash_weight": cash / equity,
            **{f"weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
        }
    )
    values = [row["equity"] for row in equity_rows]
    stats = {
        "mode": mode,
        "seed": seed,
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
    return {"mode": "buy_hold", "total_return": values[-1] / values[0] - 1, "max_drawdown": max_drawdown(values)}


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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

    out = Path("reports/refrigerant_brothers_cash_add_controls")
    out.mkdir(parents=True, exist_ok=True)

    baseline = buy_and_hold(times, open_px, close_px)
    rows = [baseline]
    artifacts = {}
    for mode in ["spread_low", "equal_lowest_weight", "momentum_high"]:
        stats, trades, equity = run_sim(times, symbols, open_px, close_px, mode=mode)
        rows.append(stats)
        artifacts[mode] = {"trades": trades, "equity": equity}
    random_rows = []
    for seed in range(20):
        stats, trades, equity = run_sim(times, symbols, open_px, close_px, mode="random", seed=seed)
        random_rows.append(stats)
        if seed == 0:
            artifacts["random_seed0"] = {"trades": trades, "equity": equity}
    rows.extend(random_rows)

    random_returns = np.array([row["total_return"] for row in random_rows])
    random_summary = {
        "mode": "random_summary_20",
        "total_return_mean": float(random_returns.mean()),
        "total_return_median": float(np.median(random_returns)),
        "total_return_min": float(random_returns.min()),
        "total_return_max": float(random_returns.max()),
    }

    write_csv(out / "control_summary.csv", rows)
    (out / "random_summary.json").write_text(json.dumps(random_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, data in artifacts.items():
        write_csv(out / f"{name}_trades.csv", data["trades"])
        write_csv(out / f"{name}_equity.csv", data["equity"])

    spread_row = next(row for row in rows if row["mode"] == "spread_low")
    equal_row = next(row for row in rows if row["mode"] == "equal_lowest_weight")
    momentum_row = next(row for row in rows if row["mode"] == "momentum_high")
    lines = [
        "# 制冷剂三兄弟现金加仓对照实验",
        "",
        "同样的触发节奏、T+1 lot 账本、冷却和尾盘过滤；只改变买入对象。",
        "",
        f"- buy_hold: ret={baseline['total_return']:.2%}, mdd={baseline['max_drawdown']:.2%}",
        f"- spread_low: ret={spread_row['total_return']:.2%}, mdd={spread_row['max_drawdown']:.2%}, trades={spread_row['trade_count']}",
        f"- equal_lowest_weight: ret={equal_row['total_return']:.2%}, mdd={equal_row['max_drawdown']:.2%}, trades={equal_row['trade_count']}",
        f"- momentum_high: ret={momentum_row['total_return']:.2%}, mdd={momentum_row['max_drawdown']:.2%}, trades={momentum_row['trade_count']}",
        f"- random mean: ret={random_summary['total_return_mean']:.2%}",
        f"- random median: ret={random_summary['total_return_median']:.2%}",
        f"- random min/max: {random_summary['total_return_min']:.2%} / {random_summary['total_return_max']:.2%}",
        "",
        "## 解释",
        "",
        "- `spread_low`: 买相对负差额最大的落后股。",
        "- `equal_lowest_weight`: 不看差额，买当前组合权重最低的股票。",
        "- `momentum_high`: 买相对最强的股票。",
        "- `random`: 触发时随机买一只股票，重复 20 次。",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
