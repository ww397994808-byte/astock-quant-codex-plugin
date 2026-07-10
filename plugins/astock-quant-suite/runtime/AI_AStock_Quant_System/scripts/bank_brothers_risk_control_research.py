from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from refrigerant_constant_exposure_spread_backtest import max_drawdown, write_csv


SYMBOL_PATHS = {
    "601939.SH": "data/ah_downloaded/data/601939_SSE_A.csv",
    "601288.SH": "data/ah_downloaded/data/601288_SSE_A.csv",
    "601398.SH": "data/ah_downloaded/data/601398_SSE_A.csv",
}


def load_daily(path: str) -> dict[str, dict[str, float]]:
    rows = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["datetime"]] = {
                "open": float(row["open"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0) or 0),
            }
    return rows


def annualized_return(values: list[float], bars: int) -> float:
    if not values or values[0] <= 0:
        return 0.0
    years = bars / 252
    if years <= 0:
        return 0.0
    return (values[-1] / values[0]) ** (1 / years) - 1


def sell_lots(lots: list[dict], qty: float, date: str) -> float:
    remain = qty
    sold = 0.0
    for lot in lots:
        if remain <= 1e-12:
            break
        if lot["buy_date"] >= date:
            continue
        take = min(lot["qty"], remain)
        lot["qty"] -= take
        sold += take
        remain -= take
    lots[:] = [lot for lot in lots if lot["qty"] > 1e-10]
    return sold


def total_qty(lots: list[dict]) -> float:
    return sum(lot["qty"] for lot in lots)


def trade_toward_values(
    cash: float,
    lots: list[list[dict]],
    prices: np.ndarray,
    target_values: np.ndarray,
    date: str,
    fee_rate: float,
    min_trade_value: float,
) -> tuple[float, int, int]:
    current = np.array([total_qty(lots[i]) * prices[i] for i in range(len(lots))])
    sell_count = 0
    buy_count = 0
    for i in np.argsort(target_values - current):
        diff = target_values[i] - current[i]
        if diff >= -min_trade_value:
            continue
        sell_value = min(-diff, current[i])
        qty = sell_lots(lots[i], sell_value / prices[i], date)
        proceeds = qty * prices[i]
        if proceeds >= min_trade_value:
            cash += proceeds * (1 - fee_rate)
            sell_count += 1
    current = np.array([total_qty(lots[i]) * prices[i] for i in range(len(lots))])
    for i in np.argsort(target_values - current)[::-1]:
        diff = target_values[i] - current[i]
        if diff <= min_trade_value:
            continue
        buy_value = min(diff, cash)
        if buy_value < min_trade_value:
            continue
        qty = buy_value * (1 - fee_rate) / prices[i]
        lots[i].append({"qty": qty, "buy_date": date})
        cash -= buy_value
        buy_count += 1
    return cash, buy_count, sell_count


def compute_target_exposure(
    basket: np.ndarray,
    bar: int,
    *,
    trend_ma: int,
    fast_ma: int,
    on_weight: float,
    off_weight: float,
    brake_weight: float,
    dd_brake: float,
    equity_dd: float,
) -> float:
    if bar < max(trend_ma, fast_ma) + 1:
        return off_weight
    slow = float(basket[bar - trend_ma + 1 : bar + 1].mean())
    fast = float(basket[bar - fast_ma + 1 : bar + 1].mean())
    prev_slow = float(basket[bar - trend_ma : bar].mean())
    trend_on = basket[bar] > slow and fast > slow and slow >= prev_slow
    target = on_weight if trend_on else off_weight
    if equity_dd <= -dd_brake:
        target = min(target, brake_weight)
    return target


def simulate(
    times: list[str],
    open_px: np.ndarray,
    close_px: np.ndarray,
    *,
    lookback: int,
    gap_threshold: float,
    step_tilt: float,
    cooldown_bars: int,
    trend_ma: int,
    fast_ma: int,
    on_weight: float,
    off_weight: float,
    brake_weight: float,
    dd_brake: float,
    max_symbol_weight: float,
    fee_rate: float = 0.0003,
) -> tuple[dict, list[dict], list[dict]]:
    initial = 1_000_000.0
    cash = initial
    lots = [[] for _ in range(open_px.shape[0])]
    equity_rows = []
    trade_rows = []
    last_pair: dict[tuple[int, int], int] = {}
    basket = close_px.mean(axis=0)
    peak = initial

    for bar in range(max(lookback, trend_ma, fast_ma) + 1, len(times) - 1):
        close_values = np.array([total_qty(lots[i]) * close_px[i, bar] for i in range(open_px.shape[0])])
        equity = cash + float(close_values.sum())
        peak = max(peak, equity)
        equity_dd = equity / peak - 1
        weights = close_values / equity if equity > 0 else np.zeros(open_px.shape[0])
        equity_rows.append(
            {
                "time": times[bar],
                "equity": equity,
                "cash_weight": cash / equity,
                "stock_weight": float(weights.sum()),
                "drawdown": equity_dd,
            }
        )

        target_exposure = compute_target_exposure(
            basket,
            bar,
            trend_ma=trend_ma,
            fast_ma=fast_ma,
            on_weight=on_weight,
            off_weight=off_weight,
            brake_weight=brake_weight,
            dd_brake=dd_brake,
            equity_dd=equity_dd,
        )
        target_weights = np.repeat(target_exposure / open_px.shape[0], open_px.shape[0])

        rel_ret = close_px[:, bar] / close_px[:, bar - lookback] - 1
        spread = rel_ret - float(rel_ret.mean())
        high = int(np.argmax(spread))
        low = int(np.argmin(spread))
        gap = float(spread[high] - spread[low])
        pair = (high, low)
        if gap >= gap_threshold and (pair not in last_pair or bar - last_pair[pair] >= cooldown_bars):
            tilt = min(step_tilt, target_weights[high], max_symbol_weight - target_weights[low])
            if tilt > 0:
                target_weights[high] -= tilt
                target_weights[low] += tilt
                last_pair[pair] = bar

        target_weights = np.minimum(target_weights, max_symbol_weight)
        target_exposure = float(target_weights.sum())
        if target_exposure > 0 and target_weights.sum() > target_exposure:
            target_weights *= target_exposure / target_weights.sum()

        trade_bar = bar + 1
        trade_date = times[trade_bar][:10]
        prices = open_px[:, trade_bar]
        trade_values = np.array([total_qty(lots[i]) * prices[i] for i in range(open_px.shape[0])])
        trade_equity = cash + float(trade_values.sum())
        min_trade_value = trade_equity * 0.002
        cash, buys, sells = trade_toward_values(
            cash,
            lots,
            prices,
            trade_equity * target_weights,
            trade_date,
            fee_rate,
            min_trade_value,
        )
        if buys or sells:
            trade_rows.append(
                {
                    "time": times[trade_bar],
                    "target_exposure": target_exposure,
                    "gap": gap,
                    "buy_count": buys,
                    "sell_count": sells,
                    "cash_weight_after": cash
                    / (cash + float(sum(total_qty(lots[i]) * prices[i] for i in range(open_px.shape[0])))),
                }
            )

    final_values = np.array([total_qty(lots[i]) * close_px[i, -1] for i in range(open_px.shape[0])])
    final_equity = cash + float(final_values.sum())
    values = [row["equity"] for row in equity_rows] + [final_equity]
    stats = {
        "lookback": lookback,
        "gap_threshold": gap_threshold,
        "step_tilt": step_tilt,
        "cooldown_bars": cooldown_bars,
        "trend_ma": trend_ma,
        "fast_ma": fast_ma,
        "on_weight": on_weight,
        "off_weight": off_weight,
        "brake_weight": brake_weight,
        "dd_brake": dd_brake,
        "total_return": values[-1] / values[0] - 1,
        "annual_return": annualized_return(values, len(values)),
        "max_drawdown": max_drawdown(values),
        "trade_count": len(trade_rows),
        "final_cash_weight": cash / final_equity,
    }
    return stats, equity_rows, trade_rows


def main() -> int:
    raw = {symbol: load_daily(path) for symbol, path in SYMBOL_PATHS.items()}
    symbols = list(SYMBOL_PATHS)
    times = sorted(set.intersection(*(set(rows) for rows in raw.values())))
    open_px = np.zeros((len(symbols), len(times)))
    close_px = np.zeros((len(symbols), len(times)))
    for i, time in enumerate(times):
        for j, symbol in enumerate(symbols):
            open_px[j, i] = raw[symbol][time]["open"]
            close_px[j, i] = raw[symbol][time]["close"]

    out = Path("reports/bank_brothers_risk_control_research")
    out.mkdir(parents=True, exist_ok=True)
    results = []
    artifacts = {}
    key = 0
    for lookback in [5, 10, 20, 40]:
        for gap_threshold in [0.01, 0.015, 0.02, 0.03]:
            for step_tilt in [1 / 96, 1 / 48, 1 / 24]:
                for cooldown_bars in [5, 10, 20]:
                    for trend_ma in [60, 120, 200]:
                        for fast_ma in [10, 20]:
                            for on_weight in [0.5, 0.8, 1.0]:
                                for off_weight in [0.0, 0.1, 0.2, 0.3]:
                                    for brake_weight in [0.0, 0.1, 0.2]:
                                        stats, equity, trades = simulate(
                                            times,
                                            open_px,
                                            close_px,
                                            lookback=lookback,
                                            gap_threshold=gap_threshold,
                                            step_tilt=step_tilt,
                                            cooldown_bars=cooldown_bars,
                                            trend_ma=trend_ma,
                                            fast_ma=fast_ma,
                                            on_weight=on_weight,
                                            off_weight=off_weight,
                                            brake_weight=brake_weight,
                                            dd_brake=0.06,
                                            max_symbol_weight=0.5,
                                        )
                                        stats["key"] = key
                                        stats["score"] = (
                                            stats["annual_return"]
                                            - max(0.0, abs(stats["max_drawdown"]) - 0.08) * 3
                                            - stats["trade_count"] / 1000 * 0.02
                                        )
                                        stats["meets_target"] = (
                                            stats["annual_return"] >= 0.20 and stats["max_drawdown"] >= -0.08
                                        )
                                        results.append(stats)
                                        if len(artifacts) < 20 or stats["meets_target"] or stats["score"] > 0.08:
                                            artifacts[key] = {"equity": equity, "trades": trades}
                                        key += 1
    results.sort(key=lambda row: (row["meets_target"], row["score"]), reverse=True)
    rows = [{k: v for k, v in row.items() if k != "key"} for row in results]
    write_csv(out / "grid_summary.csv", rows)
    best = results[0]
    best_key = best["key"]
    if best_key not in artifacts:
        stats, equity, trades = simulate(
            times,
            open_px,
            close_px,
            lookback=best["lookback"],
            gap_threshold=best["gap_threshold"],
            step_tilt=best["step_tilt"],
            cooldown_bars=best["cooldown_bars"],
            trend_ma=best["trend_ma"],
            fast_ma=best["fast_ma"],
            on_weight=best["on_weight"],
            off_weight=best["off_weight"],
            brake_weight=best["brake_weight"],
            dd_brake=best["dd_brake"],
            max_symbol_weight=0.5,
        )
        artifacts[best_key] = {"equity": equity, "trades": trades}
    write_csv(out / "best_equity.csv", artifacts[best_key]["equity"])
    write_csv(out / "best_trades.csv", artifacts[best_key]["trades"])
    (out / "summary.json").write_text(
        json.dumps(
            {
                "sample": {"start": times[0], "end": times[-1], "bars": len(times)},
                "target": {"annual_return_min": 0.20, "max_drawdown_floor": -0.08},
                "target_count": sum(1 for row in results if row["meets_target"]),
                "top": rows[:50],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# 银行三兄弟收益/回撤目标研究",
        "",
        f"- sample_start: {times[0]}",
        f"- sample_end: {times[-1]}",
        f"- common_bars: {len(times)}",
        "- target: annual_return >= 20%, max_drawdown >= -8%",
        f"- target_count: {sum(1 for row in results if row['meets_target'])}",
        "",
        "## Top 30",
        "",
    ]
    for idx, row in enumerate(results[:30], start=1):
        lines.append(
            f"{idx}. ann={row['annual_return']:.2%}, ret={row['total_return']:.2%}, "
            f"mdd={row['max_drawdown']:.2%}, trades={row['trade_count']}, "
            f"lb={row['lookback']}, gap={row['gap_threshold']:.2%}, tilt={row['step_tilt']:.2%}, "
            f"cool={row['cooldown_bars']}, ma={row['fast_ma']}/{row['trend_ma']}, "
            f"on/off/brake={row['on_weight']:.0%}/{row['off_weight']:.0%}/{row['brake_weight']:.0%}, "
            f"meets={row['meets_target']}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
