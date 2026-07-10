from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from statistics import mean

from ah_ratio_research import PairRow, build_pair_rows
from ah_universe_analyzer import UniverseItem, locate_csv, read_universe, z_bucket


def grouped_bucket(value: float | None) -> str:
    if value is None:
        return "NA"
    if value < -0.5:
        return "low"
    if value > 0.5:
        return "high"
    return "mid"


def fmt_pct(value: object) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "NA"


def fmt_num(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "NA"


def summarize_group(rows: list[PairRow], group_name: str, horizon: int) -> dict[str, float]:
    a_vals: list[float] = []
    pair_vals: list[float] = []
    max_downs: list[float] = []
    for i, row in enumerate(rows):
        if grouped_bucket(row.ratio_z) != group_name:
            continue
        if i + horizon >= len(rows):
            continue
        future = rows[i + horizon]
        a_ret = future.a_close / row.a_close - 1.0
        h_ret = future.h_close / row.h_close - 1.0
        pair_ret = a_ret - h_ret
        a_vals.append(a_ret)
        pair_vals.append(pair_ret)
        path = [rows[j].a_close / row.a_close - 1.0 for j in range(i + 1, i + horizon + 1)]
        max_downs.append(min(path))
    return {
        f"{group_name}_sample": len(a_vals),
        f"{group_name}_a_avg": mean(a_vals) if a_vals else float("nan"),
        f"{group_name}_a_win": sum(1 for x in a_vals if x > 0) / len(a_vals) if a_vals else float("nan"),
        f"{group_name}_pair_avg": mean(pair_vals) if pair_vals else float("nan"),
        f"{group_name}_pair_win": sum(1 for x in pair_vals if x > 0) / len(pair_vals) if pair_vals else float("nan"),
        f"{group_name}_avg_max_down": mean(max_downs) if max_downs else float("nan"),
    }


def ok(value: float) -> bool:
    return not math.isnan(value)


def classify(row: dict[str, object]) -> tuple[str, str, float]:
    low_sample = int(row["low_sample"])
    high_sample = int(row["high_sample"])
    low_avg = float(row["low_a_avg"])
    high_avg = float(row["high_a_avg"])
    low_win = float(row["low_a_win"])
    high_win = float(row["high_a_win"])
    low_down = float(row["low_avg_max_down"])
    high_down = float(row["high_avg_max_down"])
    low_pair = float(row["low_pair_avg"])
    low_pair_win = float(row["low_pair_win"])
    high_pair = float(row["high_pair_avg"])
    high_pair_win = float(row["high_pair_win"])

    low_valid = low_sample >= 80 and ok(low_avg) and low_avg >= 0.03 and low_win >= 0.56 and low_down >= -0.10
    high_valid = high_sample >= 80 and ok(high_avg) and high_avg >= 0.03 and high_win >= 0.56 and high_down >= -0.10
    low_pair_valid = low_sample >= 80 and ok(low_pair) and low_pair >= 0.02 and low_pair_win >= 0.56
    high_pair_valid = high_sample >= 80 and ok(high_pair) and high_pair >= 0.02 and high_pair_win >= 0.56

    score = 0.0
    label = "无明显A/H效应"
    logic = "observe"
    if low_valid and (not high_valid or low_avg >= high_avg):
        label = "低比例做多A有效"
        logic = "long_a_when_low"
        score = low_avg * 100 + (low_win - 0.5) * 20 + low_down * 30
    if high_valid and high_avg > max(low_avg, 0):
        candidate_score = high_avg * 100 + (high_win - 0.5) * 20 + high_down * 30
        if candidate_score > score:
            label = "高比例做多A有效"
            logic = "long_a_when_high"
            score = candidate_score
    if low_pair_valid:
        candidate_score = low_pair * 100 + (low_pair_win - 0.5) * 20
        if candidate_score > score:
            label = "低比例多A空H有效"
            logic = "long_a_short_h_when_low"
            score = candidate_score
    if high_pair_valid:
        candidate_score = high_pair * 100 + (high_pair_win - 0.5) * 20
        if candidate_score > score:
            label = "高比例多A空H有效"
            logic = "long_a_short_h_when_high"
            score = candidate_score
    if low_sample >= 80 and high_sample >= 80 and low_avg < 0 and high_avg < 0:
        label = "A/H区间偏无效或反向"
        logic = "avoid"
        score = min(low_avg, high_avg) * 100
    return label, logic, score


def current_signal(row: dict[str, object]) -> str:
    z = float(row["latest_z"])
    logic = row["preferred_logic"]
    if z < -0.5 and logic in {"long_a_when_low", "long_a_short_h_when_low"}:
        return "当前触发低比例候选"
    if z > 0.5 and logic in {"long_a_when_high", "long_a_short_h_when_high"}:
        return "当前触发高比例候选"
    return "未触发"


def analyze_item(item: UniverseItem, a_csv: Path, h_csv: Path, start_date: str, window: int, horizon: int) -> dict[str, object]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    rows = [r for r in build_pair_rows(a_csv, h_csv, window) if r.date >= start and r.ratio_z is not None]
    if len(rows) < 260:
        raise ValueError(f"样本不足：{len(rows)}")
    latest = rows[-1]
    result: dict[str, object] = {
        "name": item.name,
        "sector": item.sector,
        "a_symbol": item.a_symbol,
        "h_symbol": item.h_symbol,
        "a_market": item.a_market,
        "start_date": rows[0].date.strftime("%Y-%m-%d"),
        "end_date": rows[-1].date.strftime("%Y-%m-%d"),
        "sample_days": len(rows),
        "latest_ratio": latest.ratio,
        "latest_z": latest.ratio_z,
        "latest_z_bucket": z_bucket(latest.ratio_z),
    }
    for group in ["low", "mid", "high"]:
        result.update(summarize_group(rows, group, horizon))
    label, logic, score = classify(result)
    result["effect_class"] = label
    result["preferred_logic"] = logic
    result["class_score"] = score
    result["current_signal"] = current_signal(result)
    return result


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(out_dir: Path, rows: list[dict[str, object]], errors: list[dict[str, object]], horizon: int) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["effect_class"]] = counts.get(row["effect_class"], 0) + 1
    triggered = [r for r in rows if r["current_signal"] != "未触发"]
    triggered.sort(key=lambda r: float(r["class_score"]), reverse=True)
    ranked = sorted(rows, key=lambda r: float(r["class_score"]), reverse=True)
    lines = [
        "# A/H 比例有效性分层报告",
        "",
        f"- 已分析标的：{len(rows)}",
        f"- 失败/样本不足：{len(errors)}",
        f"- 观察窗口：后 {horizon} 个共同交易日",
        "",
        "## 分层数量",
        "",
        "| 类型 | 数量 |",
        "|---|---:|",
    ]
    for label, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {label} | {count} |")
    lines += [
        "",
        "## 当前触发候选",
        "",
        "| 名称 | A股 | H股 | 类型 | 当前z | 逻辑 | 低区间A均值 | 低区间胜率 | 高区间A均值 | 高区间胜率 | 多A空H低区间 | 得分 |",
        "|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in triggered[:40]:
        lines.append(
            "| {name} | {a} | {h} | {cls} | {z} | {logic} | {low} | {loww} | {high} | {highw} | {pair} | {score} |".format(
                name=r["name"],
                a=r["a_symbol"],
                h=r["h_symbol"],
                cls=r["effect_class"],
                z=fmt_num(r["latest_z"]),
                logic=r["preferred_logic"],
                low=fmt_pct(r["low_a_avg"]),
                loww=fmt_pct(r["low_a_win"]),
                high=fmt_pct(r["high_a_avg"]),
                highw=fmt_pct(r["high_a_win"]),
                pair=fmt_pct(r["low_pair_avg"]),
                score=fmt_num(r["class_score"]),
            )
        )
    lines += [
        "",
        "## 全部标的分层排名 Top 50",
        "",
        "| 排名 | 名称 | A股 | H股 | 类型 | 当前z | 低区间A均值 | 高区间A均值 | 低区间多A空H | 得分 |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(ranked[:50], 1):
        lines.append(
            "| {rank} | {name} | {a} | {h} | {cls} | {z} | {low} | {high} | {pair} | {score} |".format(
                rank=i,
                name=r["name"],
                a=r["a_symbol"],
                h=r["h_symbol"],
                cls=r["effect_class"],
                z=fmt_num(r["latest_z"]),
                low=fmt_pct(r["low_a_avg"]),
                high=fmt_pct(r["high_a_avg"]),
                pair=fmt_pct(r["low_pair_avg"]),
                score=fmt_num(r["class_score"]),
            )
        )
    if errors:
        lines += ["", "## 未纳入标的", "", "| 名称 | A股 | H股 | 原因 |", "|---|---|---|---|"]
        for e in errors:
            lines.append(f"| {e['name']} | {e['a_symbol']} | {e['h_symbol']} | {e['error']} |")
    (out_dir / "ah_universe_classification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify A/H ratio effectiveness by symbol")
    parser.add_argument("--universe", default="config/ah_universe.csv")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", default="reports/ah_universe_classification")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--window", type=int, default=252)
    parser.add_argument("--horizon", type=int, default=60)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for item in read_universe(Path(args.universe)):
        if not item.enabled:
            continue
        a_csv = locate_csv(Path(args.data_dir), item, "a")
        h_csv = locate_csv(Path(args.data_dir), item, "h")
        if not a_csv or not h_csv:
            errors.append({"name": item.name, "a_symbol": item.a_symbol, "h_symbol": item.h_symbol, "error": "missing csv"})
            continue
        try:
            results.append(analyze_item(item, a_csv, h_csv, args.start_date, args.window, args.horizon))
        except Exception as exc:  # noqa: BLE001
            errors.append({"name": item.name, "a_symbol": item.a_symbol, "h_symbol": item.h_symbol, "error": str(exc)})
    write_csv(out_dir / "ah_universe_classification.csv", results)
    write_csv(out_dir / "ah_universe_classification_errors.csv", errors)
    write_report(out_dir, results, errors, args.horizon)
    print(out_dir / "ah_universe_classification_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
