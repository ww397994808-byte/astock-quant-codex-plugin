from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median


CSV_PATHS = {
    "600160.SH": Path("/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_600160, 30.csv"),
    "603379.SH": Path("/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_603379, 30.csv"),
    "605020.SH": Path("/Users/shejishi/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/woziji741_18b5/temp/drag/SSE_DLY_605020, 30.csv"),
}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.strip())


def load_bars(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "time": row["time"],
                    "dt": parse_time(row["time"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                }
            )
    rows.sort(key=lambda item: item["dt"])
    for idx, row in enumerate(rows):
        row["idx"] = idx
        row["date"] = row["dt"].strftime("%Y-%m-%d")
        row["clock"] = row["dt"].strftime("%H:%M")
        for lookback in [1, 2, 4, 8, 16, 32]:
            row[f"ret_{lookback}b"] = (
                row["close"] / rows[idx - lookback]["close"] - 1 if idx >= lookback and rows[idx - lookback]["close"] else None
            )
        row["ma16"] = mean(r["close"] for r in rows[idx - 15 : idx + 1]) if idx >= 15 else None
        row["ma32"] = mean(r["close"] for r in rows[idx - 31 : idx + 1]) if idx >= 31 else None
    return rows


def align(data: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    by_time: dict[str, dict[str, dict]] = defaultdict(dict)
    for symbol, rows in data.items():
        for row in rows:
            by_time[row["time"]][symbol] = row
    return dict(sorted(by_time.items()))


def trade_return(rows: list[dict], signal_idx: int, entry_lag: int, hold_bars: int, exit_mode: str) -> float | None:
    entry_idx = signal_idx + entry_lag
    exit_idx = entry_idx + hold_bars - 1
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry = rows[entry_idx]["open"]
    exit_price = rows[exit_idx]["close"] if exit_mode == "close" else rows[exit_idx]["open"]
    return exit_price / entry - 1 if entry else None


def same_day_trade(rows: list[dict], signal_idx: int, entry_lag: int, hold_bars: int) -> bool:
    entry_idx = signal_idx + entry_lag
    exit_idx = entry_idx + hold_bars - 1
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return False
    return rows[signal_idx]["date"] == rows[entry_idx]["date"] == rows[exit_idx]["date"]


def trend_ok(row: dict, mode: str) -> bool:
    if mode == "none":
        return True
    if mode == "above_ma32":
        return row["ma32"] is not None and row["close"] >= row["ma32"]
    if mode == "not_extended_ma32":
        return row["ma32"] is not None and row["close"] >= row["ma32"] and row["close"] / row["ma32"] <= 1.08
    return True


def collect_events(
    data: dict[str, list[dict]],
    aligned: dict[str, dict[str, dict]],
    *,
    lookback: int,
    leader_ret: float,
    gap: float,
    candidate_max_ret: float,
    trend_mode: str,
    allowed_clocks: set[str],
    cooldown_bars: int,
) -> list[dict]:
    symbols = list(data)
    events: list[dict] = []
    last_pair_rank: dict[tuple[str, str], int] = {}
    times = list(aligned)
    time_rank = {time: i for i, time in enumerate(times)}
    ret_key = f"ret_{lookback}b"
    for time in times:
        daily = aligned[time]
        if allowed_clocks and time[11:16] not in allowed_clocks:
            continue
        if not all(symbol in daily for symbol in symbols):
            continue
        ranked = sorted(symbols, key=lambda symbol: daily[symbol].get(ret_key) or -99, reverse=True)
        leader = ranked[0]
        second = ranked[1]
        leader_ret_value = daily[leader].get(ret_key)
        second_ret = daily[second].get(ret_key)
        if leader_ret_value is None or second_ret is None:
            continue
        if leader_ret_value < leader_ret or leader_ret_value - second_ret < gap:
            continue
        if not trend_ok(daily[leader], "above_ma32"):
            continue
        leader_idx = daily[leader]["idx"]
        for candidate in ranked[1:]:
            candidate_ret = daily[candidate].get(ret_key)
            if candidate_ret is None:
                continue
            if leader_ret_value - candidate_ret < gap:
                continue
            if candidate_ret > candidate_max_ret:
                continue
            if not trend_ok(daily[candidate], trend_mode):
                continue
            pair = (leader, candidate)
            rank = time_rank[time]
            if cooldown_bars and pair in last_pair_rank and rank - last_pair_rank[pair] <= cooldown_bars:
                continue
            last_pair_rank[pair] = rank
            events.append(
                {
                    "time": time,
                    "leader": leader,
                    "candidate": candidate,
                    "leader_ret": leader_ret_value,
                    "candidate_ret": candidate_ret,
                    "leader_idx": leader_idx,
                    "candidate_idx": daily[candidate]["idx"],
                    "clock": time[11:16],
                }
            )
    return events


def describe(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg": None, "median": None, "win_rate": None, "min": None, "max": None, "profit_factor": None}
    gains = [value for value in values if value > 0]
    losses = [-value for value in values if value < 0]
    return {
        "count": len(values),
        "avg": mean(values),
        "median": median(values),
        "win_rate": len(gains) / len(values),
        "min": min(values),
        "max": max(values),
        "profit_factor": sum(gains) / sum(losses) if losses else None,
    }


def score(row: dict) -> float:
    avg = row["avg"] or -1
    med = row["median"] or -1
    wr = row["win_rate"] or 0
    pf = min(row["profit_factor"] or 0, 4)
    sample = min(row["count"] / 50, 1)
    return avg * 5 + med * 4 + (wr - 0.5) * 0.04 + pf * 0.004 + sample * 0.003


def main() -> int:
    data = {symbol: load_bars(path) for symbol, path in CSV_PATHS.items()}
    aligned = align(data)
    out = Path("reports/refrigerant_brothers_intraday_timing")
    out.mkdir(parents=True, exist_ok=True)

    clock_sets = {
        "all": set(),
        "morning": {"09:30", "10:00", "10:30", "11:00"},
        "afternoon": {"13:00", "13:30", "14:00", "14:30"},
        "not_close": {"09:30", "10:00", "10:30", "11:00", "13:00", "13:30", "14:00"},
    }
    results: list[dict] = []
    for lookback in [1, 2, 4, 8]:
        for leader_ret in [0.008, 0.012, 0.016, 0.02, 0.03]:
            for gap in [0.004, 0.008, 0.012]:
                for candidate_max_ret in [0.0, 0.005, 0.01, 0.02]:
                    for trend_mode in ["none", "above_ma32"]:
                        for clock_name, clocks in clock_sets.items():
                            if clock_name == "afternoon":
                                continue
                            for cooldown_bars in [4, 8]:
                                events = collect_events(
                                    data,
                                    aligned,
                                    lookback=lookback,
                                    leader_ret=leader_ret,
                                    gap=gap,
                                    candidate_max_ret=candidate_max_ret,
                                    trend_mode=trend_mode,
                                    allowed_clocks=clocks,
                                    cooldown_bars=cooldown_bars,
                                )
                                if len(events) < 20:
                                    continue
                                for entry_lag in range(1, 9):
                                    for hold_bars in [1, 2, 3, 4, 6, 8, 12, 16]:
                                        for same_day_only in [False, True]:
                                            trades = []
                                            for event in events:
                                                candidate_rows = data[event["candidate"]]
                                                if same_day_only and not same_day_trade(
                                                    candidate_rows, event["candidate_idx"], entry_lag, hold_bars
                                                ):
                                                    continue
                                                ret = trade_return(
                                                    candidate_rows,
                                                    event["candidate_idx"],
                                                    entry_lag,
                                                    hold_bars,
                                                    "close",
                                                )
                                                if ret is not None:
                                                    trades.append(ret)
                                            stats = describe(trades)
                                            if stats["count"] < 20:
                                                continue
                                            results.append(
                                                {
                                                    "lookback_bars": lookback,
                                                    "leader_ret": leader_ret,
                                                    "gap": gap,
                                                    "candidate_max_ret": candidate_max_ret,
                                                    "trend_mode": trend_mode,
                                                    "clock_set": clock_name,
                                                    "cooldown_bars": cooldown_bars,
                                                    "entry_lag_bars": entry_lag,
                                                    "hold_bars": hold_bars,
                                                    "same_day_only": same_day_only,
                                                    **stats,
                                                }
                                            )

    results.sort(key=score, reverse=True)
    top = results[:50]
    (out / "timing_grid_top.json").write_text(json.dumps(top, ensure_ascii=False, indent=2), encoding="utf-8")
    if top:
        with (out / "timing_grid_top.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(top[0]))
            writer.writeheader()
            writer.writerows(top)

    best = top[0] if top else None
    detail_rows: list[dict] = []
    if best:
        best_events = collect_events(
            data,
            aligned,
            lookback=best["lookback_bars"],
            leader_ret=best["leader_ret"],
            gap=best["gap"],
            candidate_max_ret=best["candidate_max_ret"],
            trend_mode=best["trend_mode"],
            allowed_clocks=clock_sets[best["clock_set"]],
            cooldown_bars=best["cooldown_bars"],
        )
        for event in best_events:
            candidate_rows = data[event["candidate"]]
            if best["same_day_only"] and not same_day_trade(
                candidate_rows, event["candidate_idx"], best["entry_lag_bars"], best["hold_bars"]
            ):
                continue
            ret = trade_return(candidate_rows, event["candidate_idx"], best["entry_lag_bars"], best["hold_bars"], "close")
            if ret is not None:
                detail_rows.append({**event, "trade_return": ret})
        if detail_rows:
            with (out / "best_rule_trades.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0]))
                writer.writeheader()
                writer.writerows(detail_rows)

    lines = ["# 制冷剂三兄弟 30min 时效网格", ""]
    if best:
        lines.extend(
            [
                "## 当前最优候选",
                "",
                f"- lookback_bars: {best['lookback_bars']}",
                f"- leader_ret: {best['leader_ret']:.2%}",
                f"- gap: {best['gap']:.2%}",
                f"- candidate_max_ret: {best['candidate_max_ret']:.2%}",
                f"- trend_mode: {best['trend_mode']}",
                f"- clock_set: {best['clock_set']}",
                f"- cooldown_bars: {best['cooldown_bars']}",
                f"- entry_lag_bars: {best['entry_lag_bars']}",
                f"- hold_bars: {best['hold_bars']}",
                f"- same_day_only: {best['same_day_only']}",
                f"- trade_count: {best['count']}",
                f"- avg: {best['avg']:.2%}",
                f"- median: {best['median']:.2%}",
                f"- win_rate: {best['win_rate']:.2%}",
                f"- min/max: {best['min']:.2%} / {best['max']:.2%}",
                f"- profit_factor: {(best['profit_factor'] or 0):.2f}",
                "",
            ]
        )
    lines.extend(["## Top 15", ""])
    for idx, row in enumerate(top[:15], start=1):
        lines.append(
            f"{idx}. lb={row['lookback_bars']}, ret>={row['leader_ret']:.2%}, gap>={row['gap']:.2%}, "
            f"cand<={row['candidate_max_ret']:.2%}, trend={row['trend_mode']}, clock={row['clock_set']}, "
            f"cool={row['cooldown_bars']}, lag={row['entry_lag_bars']}, hold={row['hold_bars']}, "
            f"same_day={row['same_day_only']}: n={row['count']}, avg={row['avg']:.2%}, "
            f"med={row['median']:.2%}, win={row['win_rate']:.2%}, pf={(row['profit_factor'] or 0):.2f}"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
