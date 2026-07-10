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
    rows: dict[str, dict[str, float]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["time"]] = {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
    return rows


def corr(x: np.ndarray, y: np.ndarray) -> float | None:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 5:
        return None
    xs = x[mask]
    ys = y[mask]
    if float(xs.std()) == 0.0 or float(ys.std()) == 0.0:
        return None
    return float(np.corrcoef(xs, ys)[0, 1])


def safe_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def safe_float(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def rolling_corr_summary(ret: np.ndarray, window: int) -> dict[str, dict[str, float | None]]:
    symbols = list(SYMBOL_PATHS)
    output: dict[str, dict[str, float | None]] = {}
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            values = []
            for end in range(window, ret.shape[1] + 1):
                value = corr(ret[i, end - window : end], ret[j, end - window : end])
                if value is not None:
                    values.append(value)
            arr = np.array(values, dtype=float)
            key = f"{symbols[i]}__{symbols[j]}"
            output[key] = {
                "count": int(len(arr)),
                "mean": float(arr.mean()) if len(arr) else None,
                "median": float(np.median(arr)) if len(arr) else None,
                "p10": float(np.percentile(arr, 10)) if len(arr) else None,
                "p90": float(np.percentile(arr, 90)) if len(arr) else None,
                "positive_ratio": float((arr > 0).mean()) if len(arr) else None,
                "above_0_3_ratio": float((arr > 0.3).mean()) if len(arr) else None,
            }
    return output


def pair_matrix(ret: np.ndarray) -> dict[str, dict[str, float | None]]:
    symbols = list(SYMBOL_PATHS)
    matrix: dict[str, dict[str, float | None]] = {}
    for i, left in enumerate(symbols):
        matrix[left] = {}
        for j, right in enumerate(symbols):
            matrix[left][right] = corr(ret[i], ret[j])
    return matrix


def comove_stats(ret: np.ndarray) -> dict[str, float | int]:
    valid = np.isfinite(ret).all(axis=0)
    rr = ret[:, valid]
    up = rr > 0
    down = rr < 0
    return {
        "bar_count": int(rr.shape[1]),
        "all_up_ratio": float(up.all(axis=0).mean()),
        "all_down_ratio": float(down.all(axis=0).mean()),
        "same_direction_ratio": float((up.all(axis=0) | down.all(axis=0)).mean()),
        "two_or_more_up_ratio": float((up.sum(axis=0) >= 2).mean()),
        "two_or_more_down_ratio": float((down.sum(axis=0) >= 2).mean()),
    }


def lead_lag_stats(ret: np.ndarray, max_lag: int) -> list[dict]:
    symbols = list(SYMBOL_PATHS)
    rows = []
    for lag in range(1, max_lag + 1):
        for i, leader in enumerate(symbols):
            for j, follower in enumerate(symbols):
                if i == j:
                    continue
                value = corr(ret[i, :-lag], ret[j, lag:])
                rows.append(
                    {
                        "leader": leader,
                        "follower": follower,
                        "lag_bars": lag,
                        "corr": value,
                    }
                )
    rows.sort(key=lambda item: item["corr"] if item["corr"] is not None else -999, reverse=True)
    return rows


def spread_reversion_stats(close: np.ndarray, lookbacks: list[int], thresholds: list[float], horizons: list[int]) -> list[dict]:
    symbols = list(SYMBOL_PATHS)
    rows = []
    for lookback in lookbacks:
        ret = np.full(close.shape, np.nan)
        ret[:, lookback:] = close[:, lookback:] / close[:, :-lookback] - 1.0
        group = np.nanmean(ret, axis=0)
        spread = ret - group
        for threshold in thresholds:
            for symbol_idx, symbol in enumerate(symbols):
                event_idx = np.where(spread[symbol_idx] <= threshold)[0]
                event_idx = event_idx[event_idx + max(horizons) < close.shape[1]]
                if len(event_idx) == 0:
                    continue
                row = {
                    "symbol": symbol,
                    "lookback_bars": lookback,
                    "threshold": threshold,
                    "event_count": int(len(event_idx)),
                    "entry_spread_median": float(np.nanmedian(spread[symbol_idx, event_idx])),
                }
                reversion_times = []
                for idx in event_idx:
                    for step in range(1, max(horizons) + 1):
                        if spread[symbol_idx, idx + step] >= 0:
                            reversion_times.append(step)
                            break
                row["revert_within_max_ratio"] = float(len(reversion_times) / len(event_idx))
                row["median_revert_bars"] = float(np.median(reversion_times)) if reversion_times else None
                for horizon in horizons:
                    valid = event_idx + horizon < close.shape[1]
                    idxs = event_idx[valid]
                    if len(idxs) == 0:
                        row[f"revert_{horizon}b_ratio"] = None
                        row[f"spread_change_{horizon}b_median"] = None
                        continue
                    future_spread = spread[symbol_idx, idxs + horizon]
                    row[f"revert_{horizon}b_ratio"] = float((future_spread >= 0).mean())
                    row[f"spread_change_{horizon}b_median"] = float(np.nanmedian(future_spread - spread[symbol_idx, idxs]))
                rows.append(row)
    rows.sort(key=lambda item: (item["revert_within_max_ratio"], item["event_count"]), reverse=True)
    return rows


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
    times = sorted(set.intersection(*(set(rows) for rows in raw.values())))
    symbols = list(SYMBOL_PATHS)
    close = np.zeros((len(symbols), len(times)))
    for time_idx, time in enumerate(times):
        for symbol_idx, symbol in enumerate(symbols):
            close[symbol_idx, time_idx] = raw[symbol][time]["close"]

    out = Path("reports/refrigerant_brothers_correlation_stats")
    out.mkdir(parents=True, exist_ok=True)

    horizons = [1, 2, 3, 5, 10, 20, 40, 80]
    correlation_by_horizon = {}
    comove_by_horizon = {}
    for horizon in horizons:
        ret = np.full(close.shape, np.nan)
        ret[:, horizon:] = close[:, horizon:] / close[:, :-horizon] - 1.0
        correlation_by_horizon[f"{horizon}b"] = pair_matrix(ret)
        comove_by_horizon[f"{horizon}b"] = comove_stats(ret)

    base_ret = np.full(close.shape, np.nan)
    base_ret[:, 1:] = close[:, 1:] / close[:, :-1] - 1.0
    rolling = {
        "80b": rolling_corr_summary(base_ret, 80),
        "400b": rolling_corr_summary(base_ret, 400),
    }
    lead_lag = lead_lag_stats(base_ret, max_lag=20)
    spread_reversion = spread_reversion_stats(
        close,
        lookbacks=[2, 3, 5, 10, 20, 40],
        thresholds=[-0.005, -0.01, -0.015, -0.02, -0.03],
        horizons=[5, 10, 20, 40, 80],
    )

    payload = {
        "sample": {
            "start": times[0],
            "end": times[-1],
            "common_bars": len(times),
            "symbols": symbols,
        },
        "correlation_by_horizon": correlation_by_horizon,
        "comove_by_horizon": comove_by_horizon,
        "rolling_corr": rolling,
        "lead_lag_top": lead_lag[:30],
        "spread_reversion_top": spread_reversion[:50],
    }
    (out / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out / "lead_lag.csv", lead_lag)
    write_csv(out / "spread_reversion.csv", spread_reversion)

    lines = [
        "# 制冷剂三兄弟相关性统计",
        "",
        "## 样本",
        "",
        f"- start: {times[0]}",
        f"- end: {times[-1]}",
        f"- common_bars: {len(times)}",
        f"- symbols: {', '.join(symbols)}",
        "",
        "## 收益率相关矩阵",
        "",
    ]
    for horizon in horizons:
        key = f"{horizon}b"
        lines.append(f"### {key}")
        matrix = correlation_by_horizon[key]
        for left in symbols:
            values = ", ".join(f"{right}: {safe_float(matrix[left][right])}" for right in symbols)
            lines.append(f"- {left}: {values}")
        cm = comove_by_horizon[key]
        lines.append(
            f"- 同涨同跌比例: {safe_pct(cm['same_direction_ratio'])}; "
            f"全涨: {safe_pct(cm['all_up_ratio'])}; 全跌: {safe_pct(cm['all_down_ratio'])}"
        )
        lines.append("")

    lines.extend(["## 滚动相关稳定性", ""])
    for window, pairs in rolling.items():
        lines.append(f"### {window}")
        for pair, stats in pairs.items():
            lines.append(
                f"- {pair}: mean={safe_float(stats['mean'])}, median={safe_float(stats['median'])}, "
                f"p10={safe_float(stats['p10'])}, p90={safe_float(stats['p90'])}, "
                f"positive={safe_pct(stats['positive_ratio'])}, >0.3={safe_pct(stats['above_0_3_ratio'])}"
            )
        lines.append("")

    lines.extend(["## Lead-Lag 相关 Top 10", ""])
    for item in lead_lag[:10]:
        lines.append(
            f"- {item['leader']} -> {item['follower']} lag={item['lag_bars']} bars: corr={safe_float(item['corr'])}"
        )
    lines.append("")

    lines.extend(["## 负差额回归 Top 10", ""])
    for item in spread_reversion[:10]:
        lines.append(
            f"- {item['symbol']} lookback={item['lookback_bars']} threshold={item['threshold']:.2%}: "
            f"events={item['event_count']}, max_horizon_revert={safe_pct(item['revert_within_max_ratio'])}, "
            f"median_revert_bars={safe_float(item['median_revert_bars'])}, "
            f"80b_revert={safe_pct(item.get('revert_80b_ratio'))}"
        )

    lines.extend(
        [
            "",
            "## 统计解释",
            "",
            "- 如果收益率相关在多个 horizon 上为正，说明三只股票存在同向共振。",
            "- 如果滚动相关大部分时间为正，说明相关性不是单一事件造成。",
            "- 如果 lead-lag 相关为正，只能说明存在先后联动倾向，不能直接等同交易胜率。",
            "- 如果负差额后高比例回到 0 以上，说明相对差额有回归倾向。",
        ]
    )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
