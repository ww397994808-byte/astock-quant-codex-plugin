from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from refrigerant_constant_exposure_spread_backtest import (
    buy_and_hold,
    load_csv,
    simulate,
    write_csv,
)


DEFAULT_SYMBOL_PATHS = {
    "600160.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_600160, 30.csv",
    "603379.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_603379, 30.csv",
    "605020.SH": "/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_605020, 30.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="30m constant-exposure spread rotation for refrigerant brothers.")
    parser.add_argument("--path-600160", default=DEFAULT_SYMBOL_PATHS["600160.SH"])
    parser.add_argument("--path-603379", default=DEFAULT_SYMBOL_PATHS["603379.SH"])
    parser.add_argument("--path-605020", default=DEFAULT_SYMBOL_PATHS["605020.SH"])
    parser.add_argument("--out", default="reports/refrigerant_brothers_constant_exposure_spread_30m")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol_paths = {
        "600160.SH": args.path_600160,
        "603379.SH": args.path_603379,
        "605020.SH": args.path_605020,
    }
    missing = [path for path in symbol_paths.values() if not Path(path).exists()]
    if missing:
        print("Missing 30m csv files:")
        for path in missing:
            print(path)
        return 2

    raw = {symbol: load_csv(path) for symbol, path in symbol_paths.items()}
    symbols = list(symbol_paths)
    times = sorted(set.intersection(*(set(rows) for rows in raw.values())))
    open_px = np.zeros((len(symbols), len(times)))
    close_px = np.zeros((len(symbols), len(times)))
    for i, time in enumerate(times):
        for j, symbol in enumerate(symbols):
            open_px[j, i] = raw[symbol][time]["open"]
            close_px[j, i] = raw[symbol][time]["close"]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    baseline = buy_and_hold(times, open_px, close_px)
    results = []
    artifacts = {}
    for lookback in [4, 8, 16, 32, 64]:
        for gap_threshold in [0.01, 0.015, 0.02, 0.03, 0.04]:
            for step_weight in [1 / 48, 1 / 24, 1 / 12]:
                for cooldown_bars in [8, 16, 32, 40]:
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
        json.dumps(
            {
                "sample": {"start": times[0], "end": times[-1], "bars": len(times)},
                "baseline": baseline,
                "top": rows[:30],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# 制冷剂三兄弟 30min 恒定股票暴露价差轮动",
        "",
        f"- sample_start: {times[0]}",
        f"- sample_end: {times[-1]}",
        f"- common_bars: {len(times)}",
        f"- baseline_return: {baseline['total_return']:.2%}",
        f"- baseline_mdd: {baseline['max_drawdown']:.2%}",
        "",
        "## Top 20",
        "",
    ]
    for idx, row in enumerate(results[:20], start=1):
        lines.append(
            f"{idx}. lb={row['lookback']}, gap={row['gap_threshold']:.2%}, "
            f"step={row['step_weight']:.2%}, cooldown={row['cooldown_bars']}: "
            f"ret={row['total_return']:.2%}, excess={row['excess_return_vs_hold']:.2%}, "
            f"mdd={row['max_drawdown']:.2%}, trades={row['trade_count']}, "
            f"cash={row['final_cash_weight']:.2%}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
