from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median


CSV_PATHS = {
    "600160.SH": Path("/Volumes/GUO HANG/右侧逻辑/historical_data/Astock/日线stock/sh600160.csv"),
    "603379.SH": Path("/Volumes/GUO HANG/右侧逻辑/historical_data/Astock/日线stock/sh603379.csv"),
    "605020.SH": Path("/Volumes/GUO HANG/右侧逻辑/historical_data/Astock/日线stock/sh605020.csv"),
}


def parse_date(value: str) -> str:
    return datetime.strptime(value.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")


def load_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="gbk")
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("股票代码,"))
    rows: list[dict] = []
    reader = csv.DictReader(lines[header_index:])
    for raw in reader:
        rows.append(
            {
                "date": parse_date(raw["交易日期"]),
                "open": float(raw["开盘价"]),
                "high": float(raw["最高价"]),
                "low": float(raw["最低价"]),
                "close": float(raw["收盘价"]),
                "prev_close": float(raw["前收盘价"]),
                "volume": float(raw["成交量"]),
            }
        )
    rows.sort(key=lambda item: item["date"])
    return rows


def enrich(rows: list[dict]) -> list[dict]:
    for idx, row in enumerate(rows):
        row["idx"] = idx
        row["ret_1d"] = row["close"] / rows[idx - 1]["close"] - 1 if idx >= 1 else None
        row["gap_open"] = row["open"] / rows[idx - 1]["close"] - 1 if idx >= 1 else None
        row["ma5"] = mean(r["close"] for r in rows[idx - 4 : idx + 1]) if idx >= 4 else None
        row["ma10"] = mean(r["close"] for r in rows[idx - 9 : idx + 1]) if idx >= 9 else None
        row["ma20"] = mean(r["close"] for r in rows[idx - 19 : idx + 1]) if idx >= 19 else None
        row["rs20"] = row["close"] / rows[idx - 20]["close"] - 1 if idx >= 20 else None
        avg_vol = mean(r["volume"] for r in rows[idx - 20 : idx]) if idx >= 20 else None
        row["volume_ratio"] = row["volume"] / avg_vol if avg_vol else None
    return rows


def align(data: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    for symbol, rows in data.items():
        for row in rows:
            by_date[row["date"]][symbol] = row
    return dict(sorted(by_date.items()))


def future_trade_return(
    data: dict[str, list[dict]],
    symbol: str,
    signal_date: str,
    entry_lag: int,
    hold_days: int,
) -> float | None:
    rows = data[symbol]
    index = {row["date"]: i for i, row in enumerate(rows)}
    signal_idx = index.get(signal_date)
    if signal_idx is None:
        return None
    entry_idx = signal_idx + entry_lag
    exit_idx = entry_idx + hold_days - 1
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_open = rows[entry_idx]["open"]
    exit_close = rows[exit_idx]["close"]
    return exit_close / entry_open - 1 if entry_open else None


def has_trend(row: dict, mode: str) -> bool:
    if mode == "none":
        return True
    if row.get("ma20") is None:
        return False
    if mode == "above_ma20":
        return row["close"] >= row["ma20"]
    if mode == "not_extended":
        return row["close"] >= row["ma20"] and row["close"] / row["ma20"] <= 1.12
    return True


def collect_events(
    data: dict[str, list[dict]],
    aligned: dict[str, dict[str, dict]],
    *,
    leader_ret: float,
    volume_ratio: float,
    gap: float,
    candidate_max_ret: float,
    trend_mode: str,
    cooldown: int,
) -> list[dict]:
    symbols = list(data)
    events: list[dict] = []
    last_date_idx: dict[tuple[str, str], int] = {}
    ordered_dates = list(aligned)
    date_rank = {date: i for i, date in enumerate(ordered_dates)}
    for date in ordered_dates:
        daily = aligned[date]
        if not all(symbol in daily for symbol in symbols):
            continue
        ranked = sorted(symbols, key=lambda s: daily[s].get("ret_1d") or -99, reverse=True)
        leader = ranked[0]
        second = ranked[1]
        leader_row = daily[leader]
        leader_day_ret = leader_row.get("ret_1d")
        leader_vol = leader_row.get("volume_ratio")
        second_ret = daily[second].get("ret_1d")
        if leader_day_ret is None or leader_vol is None or second_ret is None:
            continue
        if leader_day_ret < leader_ret or leader_vol < volume_ratio or leader_day_ret - second_ret < gap:
            continue
        if not has_trend(leader_row, "above_ma20"):
            continue
        for candidate in ranked[1:]:
            candidate_row = daily[candidate]
            candidate_ret = candidate_row.get("ret_1d")
            if candidate_ret is None:
                continue
            if leader_day_ret - candidate_ret < gap:
                continue
            if candidate_ret > candidate_max_ret:
                continue
            if not has_trend(candidate_row, trend_mode):
                continue
            pair = (leader, candidate)
            current_rank = date_rank[date]
            if cooldown and pair in last_date_idx and current_rank - last_date_idx[pair] <= cooldown:
                continue
            last_date_idx[pair] = current_rank
            events.append(
                {
                    "date": date,
                    "leader": leader,
                    "candidate": candidate,
                    "leader_ret": leader_day_ret,
                    "candidate_ret": candidate_ret,
                    "leader_volume_ratio": leader_vol,
                }
            )
    return events


def describe(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "min": None,
            "max": None,
            "profit_factor": None,
        }
    gains = [v for v in values if v > 0]
    losses = [-v for v in values if v < 0]
    return {
        "count": len(values),
        "avg": mean(values),
        "median": median(values),
        "win_rate": len(gains) / len(values),
        "min": min(values),
        "max": max(values),
        "profit_factor": sum(gains) / sum(losses) if losses else None,
    }


def main() -> int:
    data = {symbol: enrich(load_csv(path)) for symbol, path in CSV_PATHS.items()}
    aligned = align(data)
    results: list[dict] = []
    detail_rows: list[dict] = []

    for leader_ret in [0.02, 0.03, 0.04, 0.05, 0.06]:
        for volume_ratio in [1.0, 1.2, 1.5, 2.0]:
            for gap in [0.005, 0.01, 0.015, 0.02, 0.03]:
                for candidate_max_ret in [0.0, 0.02, 0.04, 0.06]:
                    for trend_mode in ["none", "above_ma20", "not_extended"]:
                        for cooldown in [0, 3, 5]:
                            events = collect_events(
                                data,
                                aligned,
                                leader_ret=leader_ret,
                                volume_ratio=volume_ratio,
                                gap=gap,
                                candidate_max_ret=candidate_max_ret,
                                trend_mode=trend_mode,
                                cooldown=cooldown,
                            )
                            if len(events) < 15:
                                continue
                            for entry_lag in [1, 2, 3, 4, 5]:
                                for hold_days in range(1, 11):
                                    trades = []
                                    for event in events:
                                        ret = future_trade_return(
                                            data,
                                            event["candidate"],
                                            event["date"],
                                            entry_lag,
                                            hold_days,
                                        )
                                        if ret is not None:
                                            trades.append(ret)
                                    stats = describe(trades)
                                    if stats["count"] < 15:
                                        continue
                                    item = {
                                        "leader_ret": leader_ret,
                                        "volume_ratio": volume_ratio,
                                        "gap": gap,
                                        "candidate_max_ret": candidate_max_ret,
                                        "trend_mode": trend_mode,
                                        "cooldown": cooldown,
                                        "entry_lag": entry_lag,
                                        "hold_days": hold_days,
                                        **stats,
                                    }
                                    results.append(item)

    def score(row: dict) -> float:
        avg = row["avg"] or -1
        med = row["median"] or -1
        wr = row["win_rate"] or 0
        pf = row["profit_factor"] or 0
        count_penalty = min(row["count"] / 40, 1)
        return avg * 4 + med * 2 + (wr - 0.5) * 0.03 + min(pf, 3) * 0.005 + count_penalty * 0.003

    results.sort(key=score, reverse=True)
    top = results[:30]

    out = Path("reports/refrigerant_brothers_timing_grid")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "timing_grid_top.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(top[0].keys()) if top else [])
        if top:
            writer.writeheader()
            writer.writerows(top)
    (out / "timing_grid_top.json").write_text(json.dumps(top, ensure_ascii=False, indent=2), encoding="utf-8")

    best = top[0] if top else {}
    if best:
        best_events = collect_events(
            data,
            aligned,
            leader_ret=best["leader_ret"],
            volume_ratio=best["volume_ratio"],
            gap=best["gap"],
            candidate_max_ret=best["candidate_max_ret"],
            trend_mode=best["trend_mode"],
            cooldown=best["cooldown"],
        )
        for event in best_events:
            ret = future_trade_return(data, event["candidate"], event["date"], best["entry_lag"], best["hold_days"])
            if ret is not None:
                detail_rows.append({**event, "trade_return": ret})
        with (out / "best_rule_trades.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()) if detail_rows else [])
            if detail_rows:
                writer.writeheader()
                writer.writerows(detail_rows)

    lines = ["# 制冷剂三兄弟时效网格结果", ""]
    if best:
        lines.extend(
            [
                "## 当前最优候选",
                "",
                f"- leader_ret: {best['leader_ret']:.2%}",
                f"- volume_ratio: {best['volume_ratio']:.2f}",
                f"- gap: {best['gap']:.2%}",
                f"- candidate_max_ret: {best['candidate_max_ret']:.2%}",
                f"- trend_mode: {best['trend_mode']}",
                f"- cooldown: {best['cooldown']}",
                f"- entry_lag: 信号后第 {best['entry_lag']} 个交易日开盘买",
                f"- hold_days: 持有 {best['hold_days']} 个交易日，收盘卖",
                f"- trade_count: {best['count']}",
                f"- avg: {best['avg']:.2%}",
                f"- median: {best['median']:.2%}",
                f"- win_rate: {best['win_rate']:.2%}",
                f"- min/max: {best['min']:.2%} / {best['max']:.2%}",
                f"- profit_factor: {best['profit_factor']:.2f}" if best["profit_factor"] is not None else "- profit_factor: N/A",
                "",
            ]
        )
    lines.extend(["## Top 10", ""])
    for idx, row in enumerate(top[:10], start=1):
        lines.append(
            f"{idx}. ret>={row['leader_ret']:.0%}, vol>={row['volume_ratio']:.1f}, gap>={row['gap']:.1%}, "
            f"candidate<={row['candidate_max_ret']:.0%}, trend={row['trend_mode']}, cooldown={row['cooldown']}, "
            f"lag={row['entry_lag']}, hold={row['hold_days']}: "
            f"n={row['count']}, avg={row['avg']:.2%}, med={row['median']:.2%}, "
            f"win={row['win_rate']:.2%}, pf={(row['profit_factor'] or 0):.2f}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
