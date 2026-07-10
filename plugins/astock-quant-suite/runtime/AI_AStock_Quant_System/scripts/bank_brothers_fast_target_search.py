from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from bank_brothers_risk_control_research import load_daily, simulate as strict_simulate
from refrigerant_constant_exposure_spread_backtest import max_drawdown, write_csv


SYMBOL_PATHS = {
    "601939.SH": "data/ah_downloaded/data/601939_SSE_A.csv",
    "601288.SH": "data/ah_downloaded/data/601288_SSE_A.csv",
    "601398.SH": "data/ah_downloaded/data/601398_SSE_A.csv",
}


def ann(values: list[float]) -> float:
    years = len(values) / 252
    return (values[-1] / values[0]) ** (1 / years) - 1 if years > 0 else 0.0


def fast_simulate(
    close_px: np.ndarray,
    *,
    lookback: int,
    gap_threshold: float,
    tilt: float,
    cooldown: int,
    trend_ma: int,
    fast_ma: int,
    on_weight: float,
    off_weight: float,
    brake_weight: float,
    dd_brake: float,
    fee_rate: float,
) -> dict:
    basket = close_px.mean(axis=0)
    weights = np.zeros(close_px.shape[0])
    equity = 1.0
    values = []
    peak = 1.0
    last_pair = {}
    trades = 0
    start = max(lookback, trend_ma, fast_ma) + 1
    for bar in range(start, close_px.shape[1] - 1):
        peak = max(peak, equity)
        equity_dd = equity / peak - 1
        slow = basket[bar - trend_ma + 1 : bar + 1].mean()
        fast = basket[bar - fast_ma + 1 : bar + 1].mean()
        prev_slow = basket[bar - trend_ma : bar].mean()
        trend_on = basket[bar] > slow and fast > slow and slow >= prev_slow
        target_exposure = on_weight if trend_on else off_weight
        if equity_dd <= -dd_brake:
            target_exposure = min(target_exposure, brake_weight)
        target = np.repeat(target_exposure / close_px.shape[0], close_px.shape[0])

        rel = close_px[:, bar] / close_px[:, bar - lookback] - 1
        spread = rel - rel.mean()
        high = int(np.argmax(spread))
        low = int(np.argmin(spread))
        gap = float(spread[high] - spread[low])
        pair = (high, low)
        if gap >= gap_threshold and (pair not in last_pair or bar - last_pair[pair] >= cooldown):
            move = min(tilt, target[high], 0.5 - target[low])
            target[high] -= move
            target[low] += move
            last_pair[pair] = bar

        turnover = float(np.abs(target - weights).sum())
        if turnover > 0.004:
            equity *= 1 - turnover * fee_rate
            trades += 1
        weights = target
        next_ret = close_px[:, bar + 1] / close_px[:, bar] - 1
        equity *= 1 + float((weights * next_ret).sum())
        values.append(equity)
    return {
        "lookback": lookback,
        "gap_threshold": gap_threshold,
        "tilt": tilt,
        "cooldown": cooldown,
        "trend_ma": trend_ma,
        "fast_ma": fast_ma,
        "on_weight": on_weight,
        "off_weight": off_weight,
        "brake_weight": brake_weight,
        "dd_brake": dd_brake,
        "annual_return_fast": ann(values),
        "total_return_fast": values[-1] / values[0] - 1,
        "max_drawdown_fast": max_drawdown(values),
        "trade_count_fast": trades,
        "meets_target_fast": ann(values) >= 0.20 and max_drawdown(values) >= -0.08,
    }


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

    out = Path("reports/bank_brothers_fast_target_search")
    out.mkdir(parents=True, exist_ok=True)
    fast_rows = []
    for lookback in [5, 10, 20, 40, 60]:
        for gap_threshold in [0.01, 0.015, 0.02, 0.03, 0.04]:
            for tilt in [0.0, 1 / 96, 1 / 48, 1 / 24, 1 / 12]:
                for cooldown in [5, 10, 20, 40]:
                    for trend_ma in [40, 60, 120, 200]:
                        for fast_ma in [5, 10, 20]:
                            for on_weight in [0.5, 0.8, 1.0, 1.2]:
                                for off_weight in [0.0, 0.1, 0.2, 0.3, 0.5]:
                                    for brake_weight in [0.0, 0.1, 0.2, 0.3]:
                                        if brake_weight > off_weight and off_weight == 0:
                                            pass
                                        row = fast_simulate(
                                            close_px,
                                            lookback=lookback,
                                            gap_threshold=gap_threshold,
                                            tilt=tilt,
                                            cooldown=cooldown,
                                            trend_ma=trend_ma,
                                            fast_ma=fast_ma,
                                            on_weight=on_weight,
                                            off_weight=off_weight,
                                            brake_weight=brake_weight,
                                            dd_brake=0.06,
                                            fee_rate=0.0003,
                                        )
                                        row["score"] = (
                                            row["annual_return_fast"]
                                            - max(0.0, abs(row["max_drawdown_fast"]) - 0.08) * 4
                                            - row["trade_count_fast"] / 1000 * 0.01
                                        )
                                        fast_rows.append(row)
    fast_rows.sort(key=lambda row: (row["meets_target_fast"], row["score"]), reverse=True)
    write_csv(out / "fast_grid_summary.csv", fast_rows)

    strict_rows = []
    seen = set()
    for row in fast_rows[:80]:
        key = (
            row["lookback"],
            row["gap_threshold"],
            row["tilt"],
            row["cooldown"],
            row["trend_ma"],
            row["fast_ma"],
            row["on_weight"],
            row["off_weight"],
            row["brake_weight"],
        )
        if key in seen:
            continue
        seen.add(key)
        stats, equity, trades = strict_simulate(
            times,
            open_px,
            close_px,
            lookback=int(row["lookback"]),
            gap_threshold=float(row["gap_threshold"]),
            step_tilt=float(row["tilt"]),
            cooldown_bars=int(row["cooldown"]),
            trend_ma=int(row["trend_ma"]),
            fast_ma=int(row["fast_ma"]),
            on_weight=float(row["on_weight"]),
            off_weight=float(row["off_weight"]),
            brake_weight=float(row["brake_weight"]),
            dd_brake=0.06,
            max_symbol_weight=0.5,
            fee_rate=0.0003,
        )
        stats["source_fast_annual"] = row["annual_return_fast"]
        stats["source_fast_mdd"] = row["max_drawdown_fast"]
        stats["meets_target"] = stats["annual_return"] >= 0.20 and stats["max_drawdown"] >= -0.08
        stats["strict_score"] = (
            stats["annual_return"]
            - max(0.0, abs(stats["max_drawdown"]) - 0.08) * 4
            - stats["trade_count"] / 1000 * 0.01
        )
        strict_rows.append(stats)
    strict_rows.sort(key=lambda row: (row["meets_target"], row["strict_score"]), reverse=True)
    write_csv(out / "strict_candidate_summary.csv", strict_rows)
    (out / "summary.json").write_text(
        json.dumps(
            {
                "sample": {"start": times[0], "end": times[-1], "bars": len(times)},
                "fast_target_count": sum(1 for row in fast_rows if row["meets_target_fast"]),
                "strict_target_count_top80": sum(1 for row in strict_rows if row["meets_target"]),
                "fast_top": fast_rows[:30],
                "strict_top": strict_rows[:30],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# 银行三兄弟 20%年化/8%回撤目标搜索",
        "",
        f"- sample_start: {times[0]}",
        f"- sample_end: {times[-1]}",
        f"- common_bars: {len(times)}",
        f"- fast_target_count: {sum(1 for row in fast_rows if row['meets_target_fast'])}",
        f"- strict_target_count_top80: {sum(1 for row in strict_rows if row['meets_target'])}",
        "",
        "## Strict Top 20",
        "",
    ]
    for idx, row in enumerate(strict_rows[:20], start=1):
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
