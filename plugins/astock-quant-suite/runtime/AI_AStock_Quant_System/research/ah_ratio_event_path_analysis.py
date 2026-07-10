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
class ZoneEvent:
    name: str
    index: int
    date: datetime
    ratio: float
    ratio_z: float
    duration: int


def fmt_pct(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "NA"
    return f"{value * 100:.2f}%"


def fmt_num(value: float | None, digits: int = 2) -> str:
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


def event_duration(rows: list[PairRow], start: int, predicate) -> int:
    end = start
    while end < len(rows) and predicate(rows[end]):
        end += 1
    return end - start


def find_events(rows: list[PairRow], name: str, predicate) -> list[ZoneEvent]:
    events: list[ZoneEvent] = []
    was_in_zone = False
    for i, row in enumerate(rows):
        in_zone = predicate(row)
        if in_zone and not was_in_zone:
            events.append(
                ZoneEvent(
                    name=name,
                    index=i,
                    date=row.date,
                    ratio=row.ratio,
                    ratio_z=float(row.ratio_z or 0.0),
                    duration=event_duration(rows, i, predicate),
                )
            )
        was_in_zone = in_zone
    return events


def path_from_entry(rows: list[PairRow], index: int, wait_days: int, horizon: int) -> tuple[list[float], list[float]] | None:
    entry = index + wait_days
    if entry >= len(rows) or entry + horizon >= len(rows):
        return None
    base = rows[entry]
    a_path = [rows[j].a_close / base.a_close - 1.0 for j in range(entry + 1, entry + horizon + 1)]
    h_path = [rows[j].h_close / base.h_close - 1.0 for j in range(entry + 1, entry + horizon + 1)]
    pair_path = [a - h for a, h in zip(a_path, h_path)]
    return a_path, pair_path


def summarize_events(rows: list[PairRow], events: list[ZoneEvent], wait_days: int, horizon: int) -> dict[str, object]:
    a_end: list[float] = []
    pair_end: list[float] = []
    a_mfe: list[float] = []
    a_mae: list[float] = []
    pair_mfe: list[float] = []
    pair_mae: list[float] = []
    first_profit_days: list[int] = []
    valid_events = 0
    for event in events:
        path = path_from_entry(rows, event.index, wait_days, horizon)
        if path is None:
            continue
        valid_events += 1
        a_path, pair_path = path
        a_end.append(a_path[-1])
        pair_end.append(pair_path[-1])
        a_mfe.append(max(a_path))
        a_mae.append(min(a_path))
        pair_mfe.append(max(pair_path))
        pair_mae.append(min(pair_path))
        day = next((i + 1 for i, ret in enumerate(a_path) if ret > 0), horizon + 1)
        first_profit_days.append(day)
    return {
        "events": len(events),
        "valid_events": valid_events,
        "wait_days": wait_days,
        "horizon": horizon,
        "duration_avg": mean([e.duration for e in events]) if events else float("nan"),
        "duration_median": median([e.duration for e in events]) if events else float("nan"),
        "a_end_avg": mean(a_end) if a_end else float("nan"),
        "a_end_median": median(a_end) if a_end else float("nan"),
        "a_win_rate": sum(1 for x in a_end if x > 0) / len(a_end) if a_end else float("nan"),
        "a_mfe_avg": mean(a_mfe) if a_mfe else float("nan"),
        "a_mae_avg": mean(a_mae) if a_mae else float("nan"),
        "a_mae_worst": min(a_mae) if a_mae else float("nan"),
        "pair_end_avg": mean(pair_end) if pair_end else float("nan"),
        "pair_win_rate": sum(1 for x in pair_end if x > 0) / len(pair_end) if pair_end else float("nan"),
        "pair_mfe_avg": mean(pair_mfe) if pair_mfe else float("nan"),
        "pair_mae_avg": mean(pair_mae) if pair_mae else float("nan"),
        "first_profit_day_median": median(first_profit_days) if first_profit_days else float("nan"),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def table(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| 区间事件 | 等待天数 | 有效事件 | 区间持续中位数 | A60均值 | A60中位 | A胜率 | A平均最大上冲 | A平均最大下探 | A最差下探 | 多A空H60均值 | 胜率 | 首次转正中位天 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {name} | {wait} | {n} | {dur} | {aavg} | {amed} | {awin} | {amfe} | {amae} | {aworst} | {pavg} | {pwin} | {fp} |".format(
                name=row["zone"],
                wait=row["wait_days"],
                n=row["valid_events"],
                dur=fmt_num(float(row["duration_median"]), 1),
                aavg=fmt_pct(float(row["a_end_avg"])),
                amed=fmt_pct(float(row["a_end_median"])),
                awin=fmt_pct(float(row["a_win_rate"])),
                amfe=fmt_pct(float(row["a_mfe_avg"])),
                amae=fmt_pct(float(row["a_mae_avg"])),
                aworst=fmt_pct(float(row["a_mae_worst"])),
                pavg=fmt_pct(float(row["pair_end_avg"])),
                pwin=fmt_pct(float(row["pair_win_rate"])),
                fp=fmt_num(float(row["first_profit_day_median"]), 1),
            )
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze first-entry path after Shenhua A/H low-ratio zones")
    parser.add_argument("--a-csv", required=True)
    parser.add_argument("--h-csv", required=True)
    parser.add_argument("--out-dir", default="reports/ah_shenhua_event_path")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--window", type=int, default=252)
    args = parser.parse_args()

    rows = slice_rows(build_pair_rows(Path(args.a_csv), Path(args.h_csv), args.window), args.start_date)
    ratios = sorted(r.ratio for r in rows)
    ratio_p10 = percentile(ratios, 0.10)
    ratio_p25 = percentile(ratios, 0.25)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    predicates = {
        f"raw<=P10({fmt_num(ratio_p10, 3)})": lambda r: r.ratio <= ratio_p10,
        f"raw<=P25({fmt_num(ratio_p25, 3)})": lambda r: r.ratio <= ratio_p25,
        "z<=-1.0": lambda r: (r.ratio_z or 0.0) <= -1.0,
        "z<=-1.5": lambda r: (r.ratio_z or 0.0) <= -1.5,
    }
    all_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for name, predicate in predicates.items():
        events = find_events(rows, name, predicate)
        for event in events:
            event_rows.append({
                "zone": event.name,
                "date": event.date.strftime("%Y-%m-%d"),
                "ratio": event.ratio,
                "ratio_z": event.ratio_z,
                "duration": event.duration,
            })
        for wait in [0, 1, 2, 3, 5, 10, 20]:
            item = summarize_events(rows, events, wait_days=wait, horizon=60)
            item["zone"] = name
            all_rows.append(item)

    write_csv(out_dir / "zone_entry_events.csv", event_rows)
    write_csv(out_dir / "wait_day_path_summary.csv", all_rows)

    best_by_zone: list[dict[str, object]] = []
    for name in predicates:
        candidates = [r for r in all_rows if r["zone"] == name]
        best_by_zone.append(max(candidates, key=lambda r: (float(r["a_win_rate"]), float(r["a_end_avg"]))))

    latest = rows[-1]
    lines = [
        "# 中国神华 A/H 低比例进入事件路径分析",
        "",
        f"- 样本：{rows[0].date:%Y-%m-%d} 至 {rows[-1].date:%Y-%m-%d}",
        f"- 最新 A/H：{fmt_num(latest.ratio, 3)}，最新 z-score：{fmt_num(latest.ratio_z, 3)}",
        "- 事件定义：比例第一次进入某个低区间，只统计从区间外进入区间的那一天。",
        "- 观察目标：进入后等待 N 天再买，未来 60 日 A 股和多 A 空 H 的路径。",
        "",
        "## 各低区间最优等待天数，按 A 股 60 日胜率优先",
        "",
        *table(best_by_zone),
        "",
        "## 完整等待天数对比",
        "",
        *table(all_rows),
        "",
        "## 初步观察",
        "",
        "1. 如果只做多 A，低比例进入后不一定马上最佳，等待几天可能改善胜率或降低不利波动。",
        "2. `z<=-1.0` 和 `z<=-1.5` 是更适合做路径研究的动态区间；原始比例分位受长期估值中枢变化影响更大。",
        "3. 下一步应把“等待天数 + 最大不利波动 + 区间持续时间”转成入场规则，而不是单纯看到低比例就买。",
    ]
    (out_dir / "event_path_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "event_path_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
