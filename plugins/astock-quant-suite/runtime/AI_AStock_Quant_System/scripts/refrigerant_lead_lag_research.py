from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from io import StringIO
from pathlib import Path
from statistics import mean


SYMBOL_NAMES = {
    "600160.SH": "巨化股份",
    "603379.SH": "三美股份",
    "605020.SH": "永和股份",
}


def parse_date(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("empty date")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10]


def to_float(row: dict, *names: str) -> float | None:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:
                return None
    return None


def read_csv_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "gbk", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8-sig", errors="replace")


def csv_from_header(text: str) -> StringIO:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if (
            "date" in lowered
            or "datetime" in lowered
            or "trade_date" in lowered
            or "交易日期" in line
        ) and ("close" in lowered or "收盘价" in line):
            return StringIO("\n".join(lines[idx:]))
    return StringIO(text)


def load_bars(path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_from_header(read_csv_text(path)) as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            date_value = raw.get("date") or raw.get("datetime") or raw.get("trade_date") or raw.get("交易日期")
            if not date_value:
                continue
            close = to_float(raw, "close", "收盘", "收盘价")
            volume = to_float(raw, "volume", "vol", "成交量")
            if close is None:
                continue
            rows.append({"date": parse_date(date_value), "close": close, "volume": volume or 0.0})
    rows.sort(key=lambda item: item["date"])
    return rows


def enrich(rows: list[dict]) -> list[dict]:
    for idx, row in enumerate(rows):
        prev = rows[idx - 1]["close"] if idx >= 1 else None
        prev3 = rows[idx - 3]["close"] if idx >= 3 else None
        prev20 = rows[idx - 20]["close"] if idx >= 20 else None
        row["ret_1d"] = row["close"] / prev - 1 if prev else None
        row["ret_3d"] = row["close"] / prev3 - 1 if prev3 else None
        row["rs_20d"] = row["close"] / prev20 - 1 if prev20 else None
        if idx >= 20:
            avg_vol = mean(item["volume"] for item in rows[idx - 20:idx])
            row["volume_ratio"] = row["volume"] / avg_vol if avg_vol else None
        else:
            row["volume_ratio"] = None
    return rows


def align_by_date(data: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    aligned: dict[str, dict[str, dict]] = defaultdict(dict)
    for symbol, rows in data.items():
        for row in rows:
            aligned[row["date"]][symbol] = row
    return dict(sorted(aligned.items()))


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = mean(xs)
    my = mean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx <= 0 or dy <= 0:
        return None
    return numerator / (dx ** 0.5 * dy ** 0.5)


def build_correlation_matrix(aligned: dict[str, dict[str, dict]], symbols: list[str]) -> dict:
    matrix: dict[str, dict[str, float | None]] = {}
    for left in symbols:
        matrix[left] = {}
        for right in symbols:
            xs: list[float] = []
            ys: list[float] = []
            for daily in aligned.values():
                left_ret = daily.get(left, {}).get("ret_1d")
                right_ret = daily.get(right, {}).get("ret_1d")
                if left_ret is not None and right_ret is not None:
                    xs.append(left_ret)
                    ys.append(right_ret)
            matrix[left][right] = correlation(xs, ys)
    return matrix


def forward_return(rows: list[dict], date: str, days: int) -> float | None:
    index = {row["date"]: idx for idx, row in enumerate(rows)}
    start_idx = index.get(date)
    if start_idx is None or start_idx + days >= len(rows):
        return None
    start = rows[start_idx]["close"]
    end = rows[start_idx + days]["close"]
    return end / start - 1 if start else None


def find_events(
    data: dict[str, list[dict]],
    aligned: dict[str, dict[str, dict]],
    symbols: list[str],
    leader_ret: float,
    volume_ratio: float,
    gap: float,
    candidate_max_ret: float,
    horizons: list[int],
) -> list[dict]:
    events: list[dict] = []
    for date, daily in aligned.items():
        if not all(symbol in daily for symbol in symbols):
            continue
        ranked = sorted(
            ((symbol, daily[symbol].get("ret_1d")) for symbol in symbols),
            key=lambda item: item[1] if item[1] is not None else -999,
            reverse=True,
        )
        leader, best_ret = ranked[0]
        second_ret = ranked[1][1]
        leader_volume = daily[leader].get("volume_ratio")
        if best_ret is None or second_ret is None or leader_volume is None:
            continue
        if best_ret < leader_ret or leader_volume < volume_ratio or best_ret - second_ret < gap:
            continue
        for candidate, candidate_ret in ranked[1:]:
            if candidate_ret is None:
                continue
            if best_ret - candidate_ret < gap or candidate_ret > candidate_max_ret:
                continue
            item = {
                "date": date,
                "leader": leader,
                "leader_name": SYMBOL_NAMES.get(leader, leader),
                "candidate": candidate,
                "candidate_name": SYMBOL_NAMES.get(candidate, candidate),
                "leader_ret_1d": best_ret,
                "candidate_ret_1d": candidate_ret,
                "leader_volume_ratio": leader_volume,
            }
            for horizon in horizons:
                item[f"candidate_fwd_{horizon}d"] = forward_return(data[candidate], date, horizon)
            events.append(item)
    return events


def summarize_events(events: list[dict], horizons: list[int]) -> dict:
    summary: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    groups["ALL"] = events
    for item in events:
        groups[f"leader:{item['leader']}"].append(item)
        groups[f"candidate:{item['candidate']}"].append(item)
    for group, rows in groups.items():
        group_summary = {"event_count": len(rows)}
        for horizon in horizons:
            key = f"candidate_fwd_{horizon}d"
            returns = [row[key] for row in rows if row.get(key) is not None]
            group_summary[f"avg_fwd_{horizon}d"] = mean(returns) if returns else None
            group_summary[f"win_rate_{horizon}d"] = (
                sum(1 for value in returns if value > 0) / len(returns) if returns else None
            )
        summary[group] = group_summary
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_csv_args(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"CSV 参数必须是 SYMBOL=PATH 格式：{value}")
        symbol, path = value.split("=", 1)
        result[symbol.strip()] = Path(path).expanduser()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="制冷剂三兄弟领涨-补涨统计研究")
    parser.add_argument("--csv", action="append", required=True, help="SYMBOL=PATH，可重复传入三次")
    parser.add_argument("--out", default="reports/refrigerant_brothers_lead_lag")
    parser.add_argument("--leader-ret", type=float, default=0.03)
    parser.add_argument("--volume-ratio", type=float, default=1.5)
    parser.add_argument("--gap", type=float, default=0.015)
    parser.add_argument("--candidate-max-ret", type=float, default=0.04)
    parser.add_argument("--horizons", default="1,3,5")
    args = parser.parse_args()

    csv_paths = parse_csv_args(args.csv)
    symbols = list(csv_paths.keys())
    horizons = [int(item.strip()) for item in args.horizons.split(",") if item.strip()]
    data = {symbol: enrich(load_bars(path)) for symbol, path in csv_paths.items()}
    aligned = align_by_date(data)
    matrix = build_correlation_matrix(aligned, symbols)
    events = find_events(
        data,
        aligned,
        symbols,
        args.leader_ret,
        args.volume_ratio,
        args.gap,
        args.candidate_max_ret,
        horizons,
    )
    summary = summarize_events(events, horizons)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "lead_lag_events.csv", events)
    (out / "correlation_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 制冷剂三兄弟领涨-补涨研究结果",
        "",
        f"- 股票池：{', '.join(symbols)}",
        f"- 领涨阈值：{args.leader_ret:.2%}",
        f"- 成交量放大：{args.volume_ratio:.2f}x",
        f"- 补涨差距：{args.gap:.2%}",
        f"- 事件数：{len(events)}",
        "",
        "## 汇总",
        "",
    ]
    for group, values in summary.items():
        lines.append(f"### {group}")
        lines.append(f"- event_count: {values['event_count']}")
        for horizon in horizons:
            avg_value = values.get(f"avg_fwd_{horizon}d")
            win_value = values.get(f"win_rate_{horizon}d")
            avg_text = "N/A" if avg_value is None else f"{avg_value:.2%}"
            win_text = "N/A" if win_value is None else f"{win_value:.2%}"
            lines.append(f"- {horizon}d avg / win_rate: {avg_text} / {win_text}")
        lines.append("")
    lines.extend([
        "## 文件",
        "",
        "- lead_lag_events.csv：逐笔领涨-补涨事件",
        "- correlation_matrix.json：三股票日收益相关性矩阵",
        "- summary.json：按领涨股和候选股分组的统计结果",
    ])
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"研究完成：{out / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
