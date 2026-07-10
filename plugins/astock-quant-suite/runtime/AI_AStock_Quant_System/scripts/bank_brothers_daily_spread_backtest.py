from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from refrigerant_constant_exposure_spread_backtest import (
    buy_and_hold,
    max_drawdown,
    simulate,
    write_csv,
)


SYMBOL_PATHS = {
    "601939.SH": "data/ah_downloaded/data/601939_SSE_A.csv",
    "601288.SH": "data/ah_downloaded/data/601288_SSE_A.csv",
    "601398.SH": "data/ah_downloaded/data/601398_SSE_A.csv",
}


def load_daily(path: str) -> dict[str, dict[str, float]]:
    rows = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            time = row["datetime"]
            rows[time] = {"open": float(row["open"]), "close": float(row["close"])}
    return rows


def period_breakdown(
    times: list[str],
    close_px: np.ndarray,
    open_px: np.ndarray,
    equity_rows: list[dict],
) -> list[dict]:
    initial = 1_000_000.0
    cash = initial * 0.5
    shares = np.array([(initial / 6) / open_px[idx, 0] for idx in range(open_px.shape[0])])
    baseline_values = [cash + float((shares * close_px[:, bar]).sum()) for bar in range(len(times))]
    time_to_idx = {time: idx for idx, time in enumerate(times)}
    strat_times = [row["time"] for row in equity_rows]
    strat_values = [float(row["equity"]) for row in equity_rows]

    def one(label: str, start: str, end: str) -> dict | None:
        ids = [idx for idx, time in enumerate(strat_times) if start <= time[:10] <= end]
        if not ids:
            return None
        sv = [strat_values[idx] for idx in ids]
        bv = [baseline_values[time_to_idx[strat_times[idx]]] for idx in ids]
        strategy_return = sv[-1] / sv[0] - 1
        baseline_return = bv[-1] / bv[0] - 1
        return {
            "period": label,
            "start": strat_times[ids[0]],
            "end": strat_times[ids[-1]],
            "strategy_return": strategy_return,
            "baseline_return": baseline_return,
            "excess": strategy_return - baseline_return,
            "strategy_mdd": max_drawdown(sv),
            "baseline_mdd": max_drawdown(bv),
            "bars": len(ids),
        }

    periods = []
    for year in range(2011, 2027):
        row = one(str(year), f"{year}-01-01", f"{year}-12-31")
        if row:
            periods.append(row)
    for label, start, end in [
        ("2011_2015", "2011-01-01", "2015-12-31"),
        ("2016_2020", "2016-01-01", "2020-12-31"),
        ("2021_2026", "2021-01-01", "2026-12-31"),
    ]:
        row = one(label, start, end)
        if row:
            periods.append(row)
    return periods


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

    out = Path("reports/bank_brothers_daily_spread")
    out.mkdir(parents=True, exist_ok=True)
    baseline = buy_and_hold(times, open_px, close_px)
    results = []
    artifacts = {}
    for lookback in [5, 10, 20, 40, 60, 120]:
        for gap_threshold in [0.01, 0.015, 0.02, 0.03, 0.04, 0.05]:
            for step_weight in [1 / 96, 1 / 48, 1 / 24, 1 / 12]:
                for cooldown_bars in [5, 10, 20, 40]:
                    stats, trades, equity = simulate(
                        times,
                        symbols,
                        open_px,
                        close_px,
                        lookback=lookback,
                        gap_threshold=gap_threshold,
                        step_weight=step_weight,
                        max_symbol_weight=1 / 3,
                        cooldown_bars=cooldown_bars,
                        no_entry_after="99:99",
                        fee_rate=0.0003,
                    )
                    key = len(results)
                    stats["key"] = key
                    stats["excess_return_vs_hold"] = stats["total_return"] - baseline["total_return"]
                    stats["score"] = (
                        stats["excess_return_vs_hold"]
                        - max(0.0, abs(stats["max_drawdown"]) - abs(baseline["max_drawdown"])) * 2
                        - stats["trade_count"] / 1500 * 0.05
                    )
                    results.append(stats)
                    artifacts[key] = {"trades": trades, "equity": equity}

    results.sort(key=lambda row: row["score"], reverse=True)
    best = results[0]
    rows = [{k: v for k, v in row.items() if k != "key"} for row in results]
    write_csv(out / "grid_summary.csv", rows)
    write_csv(out / "best_trades.csv", artifacts[best["key"]]["trades"])
    write_csv(out / "best_equity.csv", artifacts[best["key"]]["equity"])
    periods = period_breakdown(times, close_px, open_px, artifacts[best["key"]]["equity"])
    write_csv(out / "best_periods.csv", periods)

    fee_rows = []
    params = {
        "lookback": best["lookback"],
        "gap_threshold": best["gap_threshold"],
        "step_weight": best["step_weight"],
        "max_symbol_weight": best["max_symbol_weight"],
        "cooldown_bars": best["cooldown_bars"],
        "no_entry_after": best["no_entry_after"],
    }
    for fee_rate in [0.0003, 0.0005, 0.001, 0.0015, 0.002]:
        stats, _, _ = simulate(times, symbols, open_px, close_px, fee_rate=fee_rate, **params)
        fee_rows.append(
            {
                "fee_rate": fee_rate,
                "total_return": stats["total_return"],
                "excess_return_vs_hold": stats["total_return"] - baseline["total_return"],
                "max_drawdown": stats["max_drawdown"],
                "trade_count": stats["trade_count"],
            }
        )
    write_csv(out / "fee_stress.csv", fee_rows)

    (out / "summary.json").write_text(
        json.dumps(
            {"sample": {"start": times[0], "end": times[-1], "bars": len(times)}, "baseline": baseline, "top": rows[:30]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# 银行三兄弟日线恒定暴露价差轮动",
        "",
        f"- sample_start: {times[0]}",
        f"- sample_end: {times[-1]}",
        f"- common_bars: {len(times)}",
        f"- baseline_return: {baseline['total_return']:.2%}",
        f"- baseline_mdd: {baseline['max_drawdown']:.2%}",
        "",
        "## Top 20 by Robust Score",
        "",
    ]
    for idx, row in enumerate(results[:20], start=1):
        lines.append(
            f"{idx}. lb={row['lookback']}, gap={row['gap_threshold']:.2%}, "
            f"step={row['step_weight']:.2%}, cooldown={row['cooldown_bars']}: "
            f"ret={row['total_return']:.2%}, excess={row['excess_return_vs_hold']:.2%}, "
            f"mdd={row['max_drawdown']:.2%}, trades={row['trade_count']}, "
            f"cash={row['final_cash_weight']:.2%}, score={row['score']:.3f}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
