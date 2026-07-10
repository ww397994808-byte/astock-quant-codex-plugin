from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median

from ah_ratio_research import PairRow, build_pair_rows


@dataclass
class UniverseItem:
    h_symbol: str
    a_symbol: str
    a_market: str
    name: str
    sector: str
    enabled: bool


def read_universe(path: Path) -> list[UniverseItem]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    items = []
    for row in rows:
        enabled = str(row.get("enabled", "1")).strip().lower() in {"1", "true", "yes", "y", "是"}
        items.append(
            UniverseItem(
                h_symbol=str(row["h_symbol"]).zfill(4),
                a_symbol=str(row["a_symbol"]).zfill(6),
                a_market=str(row.get("a_market") or "SSE").upper(),
                name=row.get("name", ""),
                sector=row.get("sector", ""),
                enabled=enabled,
            )
        )
    return items


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def z_bucket(value: float | None) -> str:
    if value is None:
        return "NA"
    if value < -1.5:
        return "<-1.5"
    if value < -1.0:
        return "-1.5~-1.0"
    if value < -0.5:
        return "-1.0~-0.5"
    if value < 0:
        return "-0.5~0"
    if value < 0.5:
        return "0~0.5"
    if value < 1:
        return "0.5~1.0"
    if value < 1.5:
        return "1.0~1.5"
    return ">=1.5"


def future_return(rows: list[PairRow], i: int, horizon: int) -> tuple[float, float, float] | None:
    if i + horizon >= len(rows):
        return None
    current = rows[i]
    future = rows[i + horizon]
    a_ret = future.a_close / current.a_close - 1.0
    h_ret = future.h_close / current.h_close - 1.0
    return a_ret, h_ret, a_ret - h_ret


def stats(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return float("nan"), float("nan"), float("nan")
    return mean(values), median(values), sum(1 for x in values if x > 0) / len(values)


def interval_effect(rows: list[PairRow], bucket: str, horizon: int) -> dict[str, float]:
    a_vals: list[float] = []
    pair_vals: list[float] = []
    max_downs: list[float] = []
    for i, row in enumerate(rows):
        if z_bucket(row.ratio_z) != bucket:
            continue
        ret = future_return(rows, i, horizon)
        if ret is None:
            continue
        a_ret, _, pair_ret = ret
        a_vals.append(a_ret)
        pair_vals.append(pair_ret)
        path = [rows[j].a_close / row.a_close - 1.0 for j in range(i + 1, min(i + horizon + 1, len(rows)))]
        if path:
            max_downs.append(min(path))
    a_avg, a_med, a_win = stats(a_vals)
    pair_avg, pair_med, pair_win = stats(pair_vals)
    return {
        "sample": len(a_vals),
        "a_avg": a_avg,
        "a_med": a_med,
        "a_win": a_win,
        "pair_avg": pair_avg,
        "pair_med": pair_med,
        "pair_win": pair_win,
        "a_avg_max_down": mean(max_downs) if max_downs else float("nan"),
    }


def locate_csv(data_dir: Path, item: UniverseItem, side: str) -> Path | None:
    search_dirs = [data_dir, *[p for p in data_dir.iterdir() if p.is_dir()]] if data_dir.exists() else [data_dir]
    if side == "h":
        patterns = [
            f"HKEX_DLY_{int(item.h_symbol)}, 1D.csv",
            f"HKEX_DLY_{item.h_symbol}, 1D.csv",
            f"{int(item.h_symbol):05d}_HKEX_H.csv",
            f"{item.h_symbol.zfill(5)}_HKEX_H.csv",
            f"*{item.h_symbol}*1D.csv",
        ]
    else:
        prefix = "SSE" if item.a_market == "SSE" else "SZSE"
        patterns = [
            f"{prefix}_DLY_{int(item.a_symbol)}, 1D.csv",
            f"{prefix}_DLY_{item.a_symbol}, 1D.csv",
            f"{item.a_symbol}_{prefix}_A.csv",
            f"*{item.a_symbol}*1D.csv",
        ]
    for directory in search_dirs:
        for pattern in patterns:
            matches = sorted(directory.glob(pattern))
            if matches:
                return matches[0]
    return None


def analyze_one(item: UniverseItem, a_csv: Path, h_csv: Path, start_date: str, window: int) -> dict[str, object]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    rows = [r for r in build_pair_rows(a_csv, h_csv, window) if r.date >= start and r.ratio_z is not None]
    if len(rows) < 260:
        raise ValueError(f"样本不足：{len(rows)}")
    ratios = sorted(r.ratio for r in rows)
    latest = rows[-1]
    low = interval_effect(rows, "-1.5~-1.0", 60)
    very_low = interval_effect(rows, "<-1.5", 60)
    high = interval_effect(rows, ">=1.5", 60)
    current_bucket = z_bucket(latest.ratio_z)
    current_effect = interval_effect(rows, current_bucket, 60)
    score = 0.0
    if not math.isnan(current_effect["a_avg"]):
        score += current_effect["a_avg"] * 100
    if not math.isnan(current_effect["a_win"]):
        score += (current_effect["a_win"] - 0.5) * 20
    if not math.isnan(current_effect["a_avg_max_down"]):
        score += current_effect["a_avg_max_down"] * 50
    if latest.ratio_z is not None and latest.ratio_z < -0.5:
        score += 1.0
    effective = (
        current_effect["sample"] >= 30
        and current_effect["a_avg"] > 0.02
        and current_effect["a_win"] > 0.55
        and current_effect["a_avg_max_down"] > -0.08
    )
    return {
        "name": item.name,
        "sector": item.sector,
        "h_symbol": item.h_symbol,
        "a_symbol": item.a_symbol,
        "a_market": item.a_market,
        "start_date": rows[0].date.strftime("%Y-%m-%d"),
        "end_date": rows[-1].date.strftime("%Y-%m-%d"),
        "sample_days": len(rows),
        "latest_ratio": latest.ratio,
        "latest_z": latest.ratio_z,
        "latest_bucket": current_bucket,
        "ratio_p10": percentile(ratios, 0.1),
        "ratio_p25": percentile(ratios, 0.25),
        "ratio_p50": percentile(ratios, 0.5),
        "ratio_p75": percentile(ratios, 0.75),
        "ratio_p90": percentile(ratios, 0.9),
        "current_bucket_sample": current_effect["sample"],
        "current_bucket_a_60d_avg": current_effect["a_avg"],
        "current_bucket_a_60d_win": current_effect["a_win"],
        "current_bucket_pair_60d_avg": current_effect["pair_avg"],
        "current_bucket_pair_60d_win": current_effect["pair_win"],
        "current_bucket_a_60d_avg_max_down": current_effect["a_avg_max_down"],
        "low_z_a_60d_avg": low["a_avg"],
        "low_z_a_60d_win": low["a_win"],
        "very_low_z_a_60d_avg": very_low["a_avg"],
        "very_low_z_a_60d_win": very_low["a_win"],
        "high_z_a_60d_avg": high["a_avg"],
        "high_z_a_60d_win": high["a_win"],
        "effectiveness_score": score,
        "effective_now": effective,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: object) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "NA"


def fmt_num(value: object, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "NA"


def write_report(out_dir: Path, results: list[dict[str, object]], errors: list[dict[str, object]]) -> None:
    ranked = sorted(results, key=lambda r: float(r["effectiveness_score"]), reverse=True)
    lines = [
        "# A/H 比例全市场监控研究",
        "",
        f"- 已分析标的：{len(results)}",
        f"- 缺数据/失败标的：{len(errors)}",
        "- 排名不是交易指令，只是提示当前比例区间在该标的历史上是否更有利。",
        "",
        "## 当前候选排名",
        "",
        "| 排名 | 名称 | A股 | H股 | 当前比例 | z-score | 当前区间 | 区间样本 | A后60日均值 | 胜率 | 平均最大下探 | 多A空H60日 | 得分 |",
        "|---:|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(ranked[:30], 1):
        lines.append(
            "| {rank} | {name} | {a} | {h} | {ratio} | {z} | {bucket} | {sample} | {a60} | {win} | {down} | {pair} | {score} |".format(
                rank=i,
                name=r["name"],
                a=r["a_symbol"],
                h=r["h_symbol"],
                ratio=fmt_num(r["latest_ratio"]),
                z=fmt_num(r["latest_z"]),
                bucket=r["latest_bucket"],
                sample=r["current_bucket_sample"],
                a60=fmt_pct(r["current_bucket_a_60d_avg"]),
                win=fmt_pct(r["current_bucket_a_60d_win"]),
                down=fmt_pct(r["current_bucket_a_60d_avg_max_down"]),
                pair=fmt_pct(r["current_bucket_pair_60d_avg"]),
                score=fmt_num(r["effectiveness_score"], 2),
            )
        )
    if errors:
        lines += ["", "## 未分析标的", "", "| 名称 | A股 | H股 | 原因 |", "|---|---|---|---|"]
        for err in errors:
            lines.append(f"| {err['name']} | {err['a_symbol']} | {err['h_symbol']} | {err['error']} |")
    (out_dir / "ah_universe_monitor_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze A/H ratio effectiveness across a universe")
    parser.add_argument("--universe", default="config/ah_universe.csv")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", default="reports/ah_universe_monitor")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--window", type=int, default=252)
    args = parser.parse_args()

    universe = read_universe(Path(args.universe))
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for item in universe:
        if not item.enabled:
            continue
        a_csv = locate_csv(data_dir, item, "a")
        h_csv = locate_csv(data_dir, item, "h")
        if not a_csv or not h_csv:
            errors.append({
                "name": item.name,
                "a_symbol": item.a_symbol,
                "h_symbol": item.h_symbol,
                "error": "missing A/H csv",
            })
            continue
        try:
            results.append(analyze_one(item, a_csv, h_csv, args.start_date, args.window))
        except Exception as exc:  # noqa: BLE001 - report per-symbol failures without stopping the batch
            errors.append({
                "name": item.name,
                "a_symbol": item.a_symbol,
                "h_symbol": item.h_symbol,
                "error": str(exc),
            })
    write_csv(out_dir / "ah_universe_scores.csv", results)
    write_csv(out_dir / "ah_universe_errors.csv", errors)
    write_report(out_dir, results, errors)
    print(out_dir / "ah_universe_monitor_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
