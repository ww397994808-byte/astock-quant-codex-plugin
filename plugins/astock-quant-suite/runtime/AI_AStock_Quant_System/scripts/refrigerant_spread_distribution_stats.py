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


def load_csv(path: str) -> dict[str, float]:
    rows = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["time"]] = float(row["close"])
    return rows


def pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def num(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def summarize_reversion(
    times: list[str],
    spread: np.ndarray,
    symbol_idx: int,
    event_idx: np.ndarray,
    horizons: list[int],
    max_horizon: int,
) -> dict:
    event_idx = event_idx[event_idx + max_horizon < spread.shape[1]]
    if len(event_idx) == 0:
        return {}

    reversion_times = []
    for idx in event_idx:
        path = spread[symbol_idx, idx + 1 : idx + max_horizon + 1]
        hit = np.where(path >= 0)[0]
        if len(hit):
            reversion_times.append(int(hit[0] + 1))

    reversion_arr = np.array(reversion_times, dtype=float)
    row = {
        "event_count": int(len(event_idx)),
        "entry_spread_mean": float(np.nanmean(spread[symbol_idx, event_idx])),
        "entry_spread_median": float(np.nanmedian(spread[symbol_idx, event_idx])),
        "revert_max_ratio": float(len(reversion_arr) / len(event_idx)),
        "revert_time_p25": float(np.percentile(reversion_arr, 25)) if len(reversion_arr) else None,
        "revert_time_median": float(np.median(reversion_arr)) if len(reversion_arr) else None,
        "revert_time_p75": float(np.percentile(reversion_arr, 75)) if len(reversion_arr) else None,
    }
    for horizon in horizons:
        idxs = event_idx[event_idx + horizon < spread.shape[1]]
        future = spread[symbol_idx, idxs + horizon]
        current = spread[symbol_idx, idxs]
        row[f"revert_{horizon}b_ratio"] = float((future >= 0).mean()) if len(idxs) else None
        row[f"spread_change_{horizon}b_mean"] = float(np.nanmean(future - current)) if len(idxs) else None
        row[f"spread_change_{horizon}b_median"] = float(np.nanmedian(future - current)) if len(idxs) else None
    return row


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    raw = {symbol: load_csv(path) for symbol, path in SYMBOL_PATHS.items()}
    symbols = list(SYMBOL_PATHS)
    times = sorted(set.intersection(*(set(rows) for rows in raw.values())))
    close = np.zeros((len(symbols), len(times)))
    months = np.array([time[:7] for time in times])
    for time_idx, time in enumerate(times):
        for symbol_idx, symbol in enumerate(symbols):
            close[symbol_idx, time_idx] = raw[symbol][time]

    out = Path("reports/refrigerant_brothers_spread_distribution")
    out.mkdir(parents=True, exist_ok=True)

    lookbacks = [2, 3, 5, 10, 20, 40, 80]
    thresholds = [-0.005, -0.01, -0.015, -0.02, -0.03]
    horizons = [5, 10, 20, 40, 80]
    max_horizon = max(horizons)

    overall_rows = []
    monthly_rows = []
    depth_rows = []

    for lookback in lookbacks:
        ret = np.full(close.shape, np.nan)
        ret[:, lookback:] = close[:, lookback:] / close[:, :-lookback] - 1
        group = np.nanmean(ret, axis=0)
        spread = ret - group

        for threshold in thresholds:
            all_event_idx = []
            for symbol_idx, symbol in enumerate(symbols):
                event_idx = np.where(spread[symbol_idx] <= threshold)[0]
                summary = summarize_reversion(times, spread, symbol_idx, event_idx, horizons, max_horizon)
                if summary:
                    overall_rows.append(
                        {
                            "symbol": symbol,
                            "lookback_bars": lookback,
                            "threshold": threshold,
                            **summary,
                        }
                    )
                    all_event_idx.extend([(symbol_idx, idx) for idx in event_idx if idx + max_horizon < spread.shape[1]])

                for month in sorted(set(months)):
                    month_mask = months == month
                    month_event_idx = event_idx[month_mask[event_idx]] if len(event_idx) else event_idx
                    summary = summarize_reversion(times, spread, symbol_idx, month_event_idx, horizons, max_horizon)
                    if summary and summary["event_count"] >= 5:
                        monthly_rows.append(
                            {
                                "month": month,
                                "symbol": symbol,
                                "lookback_bars": lookback,
                                "threshold": threshold,
                                **summary,
                            }
                        )

            if all_event_idx:
                values = np.array([spread[symbol_idx, idx] for symbol_idx, idx in all_event_idx], dtype=float)
                depth_rows.append(
                    {
                        "lookback_bars": lookback,
                        "threshold": threshold,
                        "event_count": int(len(values)),
                        "spread_p01": float(np.percentile(values, 1)),
                        "spread_p05": float(np.percentile(values, 5)),
                        "spread_p10": float(np.percentile(values, 10)),
                        "spread_median": float(np.median(values)),
                    }
                )

    overall_rows.sort(
        key=lambda row: (
            row["lookback_bars"],
            row["threshold"],
            row["symbol"],
        )
    )
    monthly_rows.sort(key=lambda row: (row["lookback_bars"], row["threshold"], row["month"], row["symbol"]))

    write_csv(out / "spread_reversion_overall.csv", overall_rows)
    write_csv(out / "spread_reversion_monthly.csv", monthly_rows)
    write_csv(out / "spread_depth_distribution.csv", depth_rows)
    (out / "summary.json").write_text(
        json.dumps(
            {
                "sample": {
                    "start": times[0],
                    "end": times[-1],
                    "common_bars": len(times),
                    "symbols": symbols,
                },
                "overall_rows": overall_rows,
                "monthly_rows": monthly_rows,
                "depth_rows": depth_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Select compact evidence tables for the markdown report.
    preferred = [
        row
        for row in overall_rows
        if row["lookback_bars"] in {5, 10, 20}
        and row["threshold"] in {-0.005, -0.01, -0.02}
    ]
    preferred.sort(
        key=lambda row: (
            row["lookback_bars"],
            row["threshold"],
            -row["event_count"],
        )
    )
    stable_monthly = [
        row
        for row in monthly_rows
        if row["lookback_bars"] == 10 and row["threshold"] == -0.01
    ]

    lines = [
        "# 制冷剂三兄弟负差额回归分布统计",
        "",
        "## 样本",
        "",
        f"- start: {times[0]}",
        f"- end: {times[-1]}",
        f"- common_bars: {len(times)}",
        f"- symbols: {', '.join(symbols)}",
        "",
        "## 核心口径",
        "",
        "- `ret_i = close_i / close_i.shift(lookback) - 1`",
        "- `group_ret = 三只股票 ret 均值`",
        "- `spread_i = ret_i - group_ret`",
        "- 负差额事件：`spread_i <= threshold`",
        "- 回归：未来某一根 K 线 `spread_i >= 0`",
        "",
        "## 总体分布摘录",
        "",
    ]
    for row in preferred:
        lines.append(
            f"- {row['symbol']} lookback={row['lookback_bars']} threshold={row['threshold']:.2%}: "
            f"events={row['event_count']}, median_spread={row['entry_spread_median']:.2%}, "
            f"max_revert={pct(row['revert_max_ratio'])}, median_revert_bars={num(row['revert_time_median'])}, "
            f"10b={pct(row.get('revert_10b_ratio'))}, 20b={pct(row.get('revert_20b_ratio'))}, "
            f"40b={pct(row.get('revert_40b_ratio'))}, 80b={pct(row.get('revert_80b_ratio'))}"
        )

    lines.extend(["", "## 月度稳定性摘录：lookback=10 threshold=-1%", ""])
    for row in stable_monthly[:80]:
        lines.append(
            f"- {row['month']} {row['symbol']}: events={row['event_count']}, "
            f"max_revert={pct(row['revert_max_ratio'])}, median_revert_bars={num(row['revert_time_median'])}, "
            f"20b={pct(row.get('revert_20b_ratio'))}, 80b={pct(row.get('revert_80b_ratio'))}"
        )

    lines.extend(
        [
            "",
            "## 文件",
            "",
            "- `spread_reversion_overall.csv`: 全样本按标的/窗口/阈值统计",
            "- `spread_reversion_monthly.csv`: 月度稳定性统计",
            "- `spread_depth_distribution.csv`: 负差额深度分布",
            "- `summary.json`: 完整结构化结果",
        ]
    )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
