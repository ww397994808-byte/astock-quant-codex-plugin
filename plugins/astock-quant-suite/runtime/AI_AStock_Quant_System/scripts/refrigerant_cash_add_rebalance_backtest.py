from __future__ import annotations

import csv
import json
from collections import defaultdict
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


def perf(equity_rows: list[dict], trades: list[dict]) -> dict:
    values = [row["equity"] for row in equity_rows]
    return {
        "start_equity": values[0],
        "end_equity": values[-1],
        "total_return": values[-1] / values[0] - 1,
        "max_drawdown": max_drawdown(values),
        "trade_count": len(trades),
        "buy_count": sum(1 for item in trades if item["side"] == "BUY"),
        "sell_count": sum(1 for item in trades if item["side"] == "SELL"),
    }


def simulate(
    times: list[str],
    symbols: list[str],
    open_px: np.ndarray,
    close_px: np.ndarray,
    unlock_date_by_bar: list[str | None],
    *,
    lookback: int,
    gap_threshold: float,
    step_weight: float,
    max_symbol_weight: float,
    min_cash_weight: float,
    fee_rate: float,
) -> tuple[dict, list[dict], list[dict]]:
    initial_equity = 1_000_000.0
    base_weight = 1 / 6
    cash = initial_equity * 0.5
    shares = np.array([(initial_equity * base_weight) / open_px[idx, 0] for idx in range(len(symbols))])
    sellable = shares.copy()
    pending_unlocks: dict[str, list[tuple[int, float]]] = defaultdict(list)
    trades: list[dict] = []
    equity_rows: list[dict] = []

    for bar in range(lookback, len(times) - 1):
        date = times[bar][:10]
        if date in pending_unlocks:
            for symbol_idx, qty in pending_unlocks.pop(date):
                sellable[symbol_idx] += qty

        mark_prices = close_px[:, bar]
        equity = cash + float((shares * mark_prices).sum())
        weights = shares * mark_prices / equity
        equity_rows.append(
            {
                "time": times[bar],
                "equity": equity,
                "cash": cash,
                "cash_weight": cash / equity,
                **{f"weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
            }
        )

        ret = close_px[:, bar] / close_px[:, bar - lookback] - 1
        group_ret = float(ret.mean())
        spread = ret - group_ret
        high_idx = int(np.argmax(spread))
        low_idx = int(np.argmin(spread))
        spread_gap = float(spread[high_idx] - spread[low_idx])
        if spread_gap < gap_threshold:
            continue

        trade_bar = bar + 1
        unlock_date = unlock_date_by_bar[trade_bar]
        trade_equity = cash + float((shares * open_px[:, trade_bar]).sum())
        step_value = trade_equity * step_weight
        min_trade_value = trade_equity * 0.002

        # Optional sell-high leg. It may fail if no sellable shares remain.
        high_price = open_px[high_idx, trade_bar]
        sell_value = min(step_value, sellable[high_idx] * high_price)
        if sell_value >= min_trade_value:
            qty = sell_value / high_price
            shares[high_idx] -= qty
            sellable[high_idx] -= qty
            cash += sell_value * (1 - fee_rate)
            trades.append(
                {
                    "time": times[trade_bar],
                    "side": "SELL",
                    "symbol": symbols[high_idx],
                    "price": float(high_price),
                    "quantity": float(qty),
                    "value": float(sell_value),
                    "spread": float(spread[high_idx]),
                    "spread_gap": spread_gap,
                    "reason": "sell_high_if_available",
                }
            )

        # Cash-add low leg. This can deploy idle cash even if sell-high did not
        # fund the trade, which is the behavior we want to inspect separately.
        low_price = open_px[low_idx, trade_bar]
        current_low_value = shares[low_idx] * low_price
        max_low_value = trade_equity * max_symbol_weight
        reserved_cash = trade_equity * min_cash_weight
        buy_value = min(step_value, max_low_value - current_low_value, max(0.0, cash - reserved_cash))
        if buy_value >= min_trade_value and unlock_date:
            qty = (buy_value * (1 - fee_rate)) / low_price
            shares[low_idx] += qty
            cash -= buy_value
            pending_unlocks[unlock_date].append((low_idx, qty))
            trades.append(
                {
                    "time": times[trade_bar],
                    "side": "BUY",
                    "symbol": symbols[low_idx],
                    "price": float(low_price),
                    "quantity": float(qty),
                    "value": float(buy_value),
                    "spread": float(spread[low_idx]),
                    "spread_gap": spread_gap,
                    "reason": "buy_low_with_cash",
                }
            )

    final_bar = len(times) - 1
    equity = cash + float((shares * close_px[:, final_bar]).sum())
    weights = shares * close_px[:, final_bar] / equity
    equity_rows.append(
        {
            "time": times[final_bar],
            "equity": equity,
            "cash": cash,
            "cash_weight": cash / equity,
            **{f"weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
        }
    )
    stats = perf(equity_rows, trades)
    stats.update(
        {
            "lookback": lookback,
            "gap_threshold": gap_threshold,
            "step_weight": step_weight,
            "max_symbol_weight": max_symbol_weight,
            "min_cash_weight": min_cash_weight,
            "fee_rate": fee_rate,
            "final_cash_weight": cash / equity,
            **{f"final_weight_{symbols[idx]}": float(weights[idx]) for idx in range(len(symbols))},
        }
    )
    return stats, trades, equity_rows


def buy_and_hold(times: list[str], symbols: list[str], open_px: np.ndarray, close_px: np.ndarray) -> dict:
    initial_equity = 1_000_000.0
    cash = initial_equity * 0.5
    shares = np.array([(initial_equity / 6) / open_px[idx, 0] for idx in range(len(symbols))])
    values = [cash + float((shares * close_px[:, bar]).sum()) for bar in range(len(times))]
    return {
        "start_equity": values[0],
        "end_equity": values[-1],
        "total_return": values[-1] / values[0] - 1,
        "max_drawdown": max_drawdown(values),
    }


def main() -> int:
    raw = {symbol: load_csv(path) for symbol, path in SYMBOL_PATHS.items()}
    symbols = list(SYMBOL_PATHS)
    times = sorted(set.intersection(*(set(rows) for rows in raw.values())))
    open_px = np.zeros((len(symbols), len(times)))
    close_px = np.zeros((len(symbols), len(times)))
    for time_idx, time in enumerate(times):
        for symbol_idx, symbol in enumerate(symbols):
            open_px[symbol_idx, time_idx] = raw[symbol][time]["open"]
            close_px[symbol_idx, time_idx] = raw[symbol][time]["close"]

    dates = [time[:10] for time in times]
    unlock_date_by_bar: list[str | None] = [None] * len(times)
    next_seen: str | None = None
    for idx in range(len(times) - 1, -1, -1):
        if idx < len(times) - 1 and dates[idx + 1] != dates[idx]:
            next_seen = dates[idx + 1]
        unlock_date_by_bar[idx] = next_seen

    out = Path("reports/refrigerant_brothers_cash_add_rebalance")
    out.mkdir(parents=True, exist_ok=True)
    baseline = buy_and_hold(times, symbols, open_px, close_px)

    results = []
    artifacts = {}
    for lookback in [10, 20]:
        for gap_threshold in [0.015, 0.02]:
            for step_weight in [1 / 12, 1 / 6]:
                for max_symbol_weight in [1 / 3, 0.5]:
                    stats, trades, equity = simulate(
                        times,
                        symbols,
                        open_px,
                        close_px,
                        unlock_date_by_bar,
                        lookback=lookback,
                        gap_threshold=gap_threshold,
                        step_weight=step_weight,
                        max_symbol_weight=max_symbol_weight,
                        min_cash_weight=0.05,
                        fee_rate=0.0003,
                    )
                    key = len(results)
                    stats["key"] = key
                    stats["excess_return_vs_hold"] = stats["total_return"] - baseline["total_return"]
                    results.append(stats)
                    artifacts[key] = {"trades": trades, "equity": equity}

    results.sort(key=lambda row: (row["total_return"], -abs(row["max_drawdown"])), reverse=True)
    best = results[0]
    best_artifacts = artifacts[best["key"]]
    top_rows = [{k: v for k, v in row.items() if k != "key"} for row in results[:50]]
    write_csv(out / "grid_summary.csv", top_rows)
    write_csv(out / "best_trades.csv", best_artifacts["trades"])
    write_csv(out / "best_equity.csv", best_artifacts["equity"])
    (out / "summary.json").write_text(
        json.dumps(
            {
                "sample": {
                    "start": times[0],
                    "end": times[-1],
                    "common_bars": len(times),
                    "symbols": symbols,
                },
                "baseline": baseline,
                "top": top_rows[:20],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# 制冷剂三兄弟现金加仓再平衡回测",
        "",
        "## 基准：三只各 1/6 + 现金 1/2 持有不动",
        "",
        f"- total_return: {baseline['total_return']:.2%}",
        f"- max_drawdown: {baseline['max_drawdown']:.2%}",
        "",
        "## 当前最优参数",
        "",
        f"- lookback: {best['lookback']} bars",
        f"- gap_threshold: {best['gap_threshold']:.2%}",
        f"- step_weight: {best['step_weight']:.2%}",
        f"- max_symbol_weight: {best['max_symbol_weight']:.2%}",
        f"- min_cash_weight: {best['min_cash_weight']:.2%}",
        f"- total_return: {best['total_return']:.2%}",
        f"- excess_return_vs_hold: {best['excess_return_vs_hold']:.2%}",
        f"- max_drawdown: {best['max_drawdown']:.2%}",
        f"- trade_count: {best['trade_count']}",
        f"- final_cash_weight: {best['final_cash_weight']:.2%}",
        f"- final_weight_600160: {best['final_weight_600160.SH']:.2%}",
        f"- final_weight_603379: {best['final_weight_603379.SH']:.2%}",
        f"- final_weight_605020: {best['final_weight_605020.SH']:.2%}",
        "",
        "## Top 15",
        "",
    ]
    for idx, row in enumerate(results[:15], start=1):
        lines.append(
            f"{idx}. lb={row['lookback']}, gap={row['gap_threshold']:.2%}, "
            f"step={row['step_weight']:.2%}, maxW={row['max_symbol_weight']:.2%}: "
            f"ret={row['total_return']:.2%}, excess={row['excess_return_vs_hold']:.2%}, "
            f"mdd={row['max_drawdown']:.2%}, trades={row['trade_count']}, cash={row['final_cash_weight']:.2%}"
        )
    lines.extend(
        [
            "",
            "## 解释",
            "",
            "这个版本允许用闲置现金买入相对落后股，因此收益改善可能来自两个来源：",
            "",
            "- 差额修复带来的再平衡收益。",
            "- 在上涨行情里把原本 50% 现金逐步投入股票，提升了整体股票仓位。",
            "",
            "因此它不能和严格配对卖高买低混为一谈。",
            "",
            "## 文件",
            "",
            "- `grid_summary.csv`: 参数网格汇总",
            "- `best_trades.csv`: 最优参数逐笔买卖",
            "- `best_equity.csv`: 最优参数权益曲线",
            "- `summary.json`: 结构化摘要",
        ]
    )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
