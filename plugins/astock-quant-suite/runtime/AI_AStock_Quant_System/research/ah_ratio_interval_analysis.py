from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, median

from ah_ratio_research import PairRow, build_pair_rows


HORIZONS = [1, 5, 10, 20, 40, 60, 120]


def fmt_pct(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "NA"
    return f"{value * 100:.2f}%"


def fmt_num(value: float | None, digits: int = 3) -> str:
    if value is None or math.isnan(value):
        return "NA"
    return f"{value:.{digits}f}"


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def slice_rows(rows: list[PairRow], start_date: str) -> list[PairRow]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    return [r for r in rows if r.date >= start and r.ratio_z is not None]


def label_for(value: float, bounds: list[float], prefix: str) -> str:
    for i in range(len(bounds) - 1):
        if bounds[i] <= value < bounds[i + 1]:
            return f"{prefix}{i + 1}: {fmt_num(bounds[i])}~{fmt_num(bounds[i + 1])}"
    return f"{prefix}{len(bounds) - 1}: {fmt_num(bounds[-2])}~{fmt_num(bounds[-1])}"


def z_label(value: float | None) -> str:
    if value is None:
        return "NA"
    if value < -1.5:
        return "Z1: < -1.5"
    if value < -1.0:
        return "Z2: -1.5~-1.0"
    if value < -0.5:
        return "Z3: -1.0~-0.5"
    if value < 0.0:
        return "Z4: -0.5~0"
    if value < 0.5:
        return "Z5: 0~0.5"
    if value < 1.0:
        return "Z6: 0.5~1.0"
    if value < 1.5:
        return "Z7: 1.0~1.5"
    return "Z8: >= 1.5"


def future_returns(rows: list[PairRow], i: int, horizon: int) -> tuple[float, float, float] | None:
    if i + horizon >= len(rows):
        return None
    row = rows[i]
    future = rows[i + horizon]
    a_ret = future.a_close / row.a_close - 1.0
    h_ret = future.h_close / row.h_close - 1.0
    pair_ret = a_ret - h_ret
    return a_ret, h_ret, pair_ret


def path_stats(rows: list[PairRow], indexes: list[int], horizon: int = 60) -> dict[str, float]:
    a_end: list[float] = []
    pair_end: list[float] = []
    a_max_up: list[float] = []
    a_max_down: list[float] = []
    pair_max_up: list[float] = []
    pair_max_down: list[float] = []
    for i in indexes:
        if i + horizon >= len(rows):
            continue
        row = rows[i]
        a_path = [rows[j].a_close / row.a_close - 1.0 for j in range(i + 1, i + horizon + 1)]
        h_path = [rows[j].h_close / row.h_close - 1.0 for j in range(i + 1, i + horizon + 1)]
        pair_path = [a - h for a, h in zip(a_path, h_path)]
        a_end.append(a_path[-1])
        pair_end.append(pair_path[-1])
        a_max_up.append(max(a_path))
        a_max_down.append(min(a_path))
        pair_max_up.append(max(pair_path))
        pair_max_down.append(min(pair_path))
    return {
        "samples": len(a_end),
        "a_60d_avg": mean(a_end) if a_end else float("nan"),
        "a_60d_median": median(a_end) if a_end else float("nan"),
        "a_60d_win": sum(1 for x in a_end if x > 0) / len(a_end) if a_end else float("nan"),
        "a_60d_avg_max_up": mean(a_max_up) if a_max_up else float("nan"),
        "a_60d_avg_max_down": mean(a_max_down) if a_max_down else float("nan"),
        "pair_60d_avg": mean(pair_end) if pair_end else float("nan"),
        "pair_60d_median": median(pair_end) if pair_end else float("nan"),
        "pair_60d_win": sum(1 for x in pair_end if x > 0) / len(pair_end) if pair_end else float("nan"),
        "pair_60d_avg_max_up": mean(pair_max_up) if pair_max_up else float("nan"),
        "pair_60d_avg_max_down": mean(pair_max_down) if pair_max_down else float("nan"),
    }


def grouped_horizon_table(rows: list[PairRow], groups: dict[str, list[int]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for label, indexes in groups.items():
        item: dict[str, object] = {"group": label, "count": len(indexes)}
        for horizon in HORIZONS:
            a_vals: list[float] = []
            h_vals: list[float] = []
            pair_vals: list[float] = []
            for i in indexes:
                ret = future_returns(rows, i, horizon)
                if ret is None:
                    continue
                a_ret, h_ret, pair_ret = ret
                a_vals.append(a_ret)
                h_vals.append(h_ret)
                pair_vals.append(pair_ret)
            item[f"a_{horizon}d_avg"] = mean(a_vals) if a_vals else float("nan")
            item[f"a_{horizon}d_med"] = median(a_vals) if a_vals else float("nan")
            item[f"a_{horizon}d_win"] = sum(1 for x in a_vals if x > 0) / len(a_vals) if a_vals else float("nan")
            item[f"h_{horizon}d_avg"] = mean(h_vals) if h_vals else float("nan")
            item[f"pair_{horizon}d_avg"] = mean(pair_vals) if pair_vals else float("nan")
            item[f"pair_{horizon}d_win"] = sum(1 for x in pair_vals if x > 0) / len(pair_vals) if pair_vals else float("nan")
        out.append(item)
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compact_table(rows: list[dict[str, object]], horizons: list[int]) -> list[str]:
    lines = [
        "| 区间 | 样本 | A后20日 | 胜率 | A后60日 | 胜率 | A后120日 | 胜率 | 多A空H后60日 | 胜率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            "| {g} | {c} | {a20} | {w20} | {a60} | {w60} | {a120} | {w120} | {p60} | {pw60} |".format(
                g=r["group"],
                c=r["count"],
                a20=fmt_pct(float(r["a_20d_avg"])),
                w20=fmt_pct(float(r["a_20d_win"])),
                a60=fmt_pct(float(r["a_60d_avg"])),
                w60=fmt_pct(float(r["a_60d_win"])),
                a120=fmt_pct(float(r["a_120d_avg"])),
                w120=fmt_pct(float(r["a_120d_win"])),
                p60=fmt_pct(float(r["pair_60d_avg"])),
                pw60=fmt_pct(float(r["pair_60d_win"])),
            )
        )
    return lines


def path_table(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| 区间 | 样本 | A60日均值 | A60日中位 | A胜率 | A期间平均最大涨幅 | A期间平均最大跌幅 | 多A空H60日均值 | 胜率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            "| {g} | {samples} | {aavg} | {amed} | {awin} | {aup} | {adown} | {pavg} | {pwin} |".format(
                g=r["group"],
                samples=r["samples"],
                aavg=fmt_pct(float(r["a_60d_avg"])),
                amed=fmt_pct(float(r["a_60d_median"])),
                awin=fmt_pct(float(r["a_60d_win"])),
                aup=fmt_pct(float(r["a_60d_avg_max_up"])),
                adown=fmt_pct(float(r["a_60d_avg_max_down"])),
                pavg=fmt_pct(float(r["pair_60d_avg"])),
                pwin=fmt_pct(float(r["pair_60d_win"])),
            )
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Shenhua A/H ratio intervals and future paths")
    parser.add_argument("--a-csv", required=True)
    parser.add_argument("--h-csv", required=True)
    parser.add_argument("--out-dir", default="reports/ah_shenhua_interval_analysis")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--window", type=int, default=252)
    args = parser.parse_args()

    rows = slice_rows(build_pair_rows(Path(args.a_csv), Path(args.h_csv), args.window), args.start_date)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ratios = sorted(r.ratio for r in rows)
    ratio_bounds = [percentile(ratios, q) for q in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]]
    ratio_bounds[-1] += 1e-12

    ratio_groups: dict[str, list[int]] = {}
    z_groups: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        ratio_groups.setdefault(label_for(row.ratio, ratio_bounds, "R"), []).append(i)
        z_groups.setdefault(z_label(row.ratio_z), []).append(i)

    ratio_table = grouped_horizon_table(rows, dict(sorted(ratio_groups.items())))
    z_table = grouped_horizon_table(rows, dict(sorted(z_groups.items())))
    ratio_path = [{"group": label, **path_stats(rows, indexes)} for label, indexes in sorted(ratio_groups.items())]
    z_path = [{"group": label, **path_stats(rows, indexes)} for label, indexes in sorted(z_groups.items())]

    write_csv(out_dir / "raw_ratio_interval_forward_returns.csv", ratio_table)
    write_csv(out_dir / "zscore_interval_forward_returns.csv", z_table)
    write_csv(out_dir / "raw_ratio_interval_60d_path.csv", ratio_path)
    write_csv(out_dir / "zscore_interval_60d_path.csv", z_path)

    latest = rows[-1]
    lines = [
        "# 中国神华 A/H 比例区间与后续走势分析",
        "",
        f"- 样本：{rows[0].date:%Y-%m-%d} 至 {rows[-1].date:%Y-%m-%d}",
        f"- 共同交易日：{len(rows)}",
        f"- 比例定义：A 股收盘价 / H 股收盘价；z-score 使用 {args.window} 日滚动窗口。",
        "- 本报告仍未纳入 HKD/CNY 汇率和复权分红，先用于观察规律。",
        "",
        "## 当前比例位置",
        "",
        f"- 最新日期：{latest.date:%Y-%m-%d}",
        f"- 最新 A/H：{fmt_num(latest.ratio)}",
        f"- 最新 z-score：{fmt_num(latest.ratio_z)}",
        f"- 2018 年以来原始比例分位：10%={fmt_num(ratio_bounds[1])}，25%={fmt_num(ratio_bounds[2])}，50%={fmt_num(ratio_bounds[3])}，75%={fmt_num(ratio_bounds[4])}，90%={fmt_num(ratio_bounds[5])}",
        "",
        "## 原始比例区间：后续收益",
        "",
        *compact_table(ratio_table, HORIZONS),
        "",
        "## z-score 区间：后续收益",
        "",
        *compact_table(z_table, HORIZONS),
        "",
        "## 原始比例区间：未来 60 日路径特征",
        "",
        *path_table(ratio_path),
        "",
        "## z-score 区间：未来 60 日路径特征",
        "",
        *path_table(z_path),
        "",
        "## 初步观察",
        "",
        "1. 先看 A 股绝对收益，低比例/低 z-score 区间通常更有利；高 z-score 区间通常偏弱。",
        "2. 多 A 空 H 的优势不等同于 A 股上涨，它更依赖 A 股相对 H 股走强，因此需要单独看 pair 列。",
        "3. 如果目标是低回撤，下一步应优先找“低比例后路径中平均最大跌幅较小”的区间，而不是只看最终收益。",
    ]
    (out_dir / "interval_analysis_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "interval_analysis_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
