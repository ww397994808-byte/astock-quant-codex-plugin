from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev


@dataclass
class PairRow:
    date: datetime
    a_close: float
    h_close: float
    ratio: float
    ratio_ma: float | None = None
    ratio_std: float | None = None
    ratio_z: float | None = None
    a_ret_1d: float | None = None
    h_ret_1d: float | None = None


def load_close_by_date(path: Path) -> dict[datetime, float]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        required = {"close"}
        missing = required - set(reader.fieldnames or [])
        if "time" not in fields and "datetime" not in fields and "date" not in fields:
            missing.add("time/datetime/date")
        if missing:
            raise ValueError(f"{path} 缺少字段：{', '.join(sorted(missing))}")
        out: dict[datetime, float] = {}
        for row in reader:
            raw_date = row.get("time") or row.get("datetime") or row.get("date") or ""
            out[datetime.strptime(raw_date[:10], "%Y-%m-%d")] = float(row["close"])
    return out


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1.0)
    return worst


def annualized_return(equity: list[float], days: int) -> float:
    if days <= 0 or not equity or equity[0] <= 0:
        return 0.0
    total = equity[-1] / equity[0] - 1.0
    return (1.0 + total) ** (252.0 / days) - 1.0


def sharpe(daily_returns: list[float]) -> float:
    values = [x for x in daily_returns if x is not None]
    if len(values) < 2:
        return 0.0
    sigma = stdev(values)
    if sigma == 0:
        return 0.0
    return mean(values) / sigma * math.sqrt(252)


def build_pair_rows(a_path: Path, h_path: Path, window: int) -> list[PairRow]:
    a = load_close_by_date(a_path)
    h = load_close_by_date(h_path)
    dates = sorted(set(a) & set(h))
    rows = [PairRow(date=d, a_close=a[d], h_close=h[d], ratio=a[d] / h[d]) for d in dates]
    rolling_sum = 0.0
    rolling_sumsq = 0.0
    for i, row in enumerate(rows):
        if i + 1 < len(rows):
            nxt = rows[i + 1]
            row.a_ret_1d = nxt.a_close / row.a_close - 1.0
            row.h_ret_1d = nxt.h_close / row.h_close - 1.0
        rolling_sum += row.ratio
        rolling_sumsq += row.ratio * row.ratio
        if i >= window:
            old = rows[i - window].ratio
            rolling_sum -= old
            rolling_sumsq -= old * old
        if i + 1 >= window:
            row.ratio_ma = rolling_sum / window
            variance = (rolling_sumsq - rolling_sum * rolling_sum / window) / (window - 1)
            sigma = math.sqrt(max(variance, 0.0))
            row.ratio_std = sigma
            row.ratio_z = (row.ratio - row.ratio_ma) / sigma if sigma else 0.0
    return rows


def forward_return_table(rows: list[PairRow], horizons: list[int], buckets: int) -> list[dict[str, object]]:
    usable = [r for r in rows if r.ratio_z is not None]
    ranked = sorted(usable, key=lambda r: r.ratio_z or 0.0)
    out: list[dict[str, object]] = []
    for bucket in range(buckets):
        start = int(len(ranked) * bucket / buckets)
        end = int(len(ranked) * (bucket + 1) / buckets)
        sample = ranked[start:end]
        item: dict[str, object] = {
            "bucket": bucket + 1,
            "count": len(sample),
            "z_min": min((r.ratio_z for r in sample if r.ratio_z is not None), default=float("nan")),
            "z_max": max((r.ratio_z for r in sample if r.ratio_z is not None), default=float("nan")),
        }
        index_by_date = {r.date: i for i, r in enumerate(rows)}
        for horizon in horizons:
            returns = []
            for r in sample:
                idx = index_by_date[r.date]
                if idx + horizon < len(rows):
                    returns.append(rows[idx + horizon].a_close / r.a_close - 1.0)
            item[f"a_fwd_{horizon}d_avg"] = mean(returns) if returns else float("nan")
            item[f"a_fwd_{horizon}d_win_rate"] = sum(1 for x in returns if x > 0) / len(returns) if returns else float("nan")
        out.append(item)
    return out


def run_strategy(
    rows: list[PairRow],
    mode: str,
    entry_z: float,
    exit_z: float,
    cost_per_turnover: float,
) -> dict[str, object]:
    equity = [1.0]
    daily_returns = []
    position = 0
    trades = 0
    trade_log = []
    for i, row in enumerate(rows[:-1]):
        next_ret = row.a_ret_1d or 0.0
        if mode == "long_a_short_h":
            next_ret -= row.h_ret_1d or 0.0

        desired = position
        reason = ""
        if row.ratio_z is not None:
            if position == 0 and row.ratio_z <= entry_z:
                desired = 1
                reason = "A/H 比例低位，做多 A" if mode == "long_a" else "A/H 比例低位，做多 A 同时做空 H"
            elif position == 1 and row.ratio_z >= exit_z:
                desired = 0
                reason = "比例回到退出区间"

        turnover_cost = abs(desired - position) * cost_per_turnover
        if desired != position:
            trades += 1
            trade_log.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "action": "ENTER" if desired else "EXIT",
                "ratio": row.ratio,
                "ratio_z": row.ratio_z,
                "reason": reason,
            })
        position = desired
        day_ret = position * next_ret - turnover_cost
        daily_returns.append(day_ret)
        equity.append(equity[-1] * (1.0 + day_ret))
    invested_days = sum(1 for r in daily_returns if abs(r) > 0)
    return {
        "mode": mode,
        "entry_z": entry_z,
        "exit_z": exit_z,
        "final_equity": equity[-1],
        "total_return": equity[-1] - 1.0,
        "annualized_return": annualized_return(equity, len(daily_returns)),
        "max_drawdown": max_drawdown(equity),
        "sharpe": sharpe(daily_returns),
        "trades": trades,
        "invested_days": invested_days,
        "exposure": invested_days / len(daily_returns) if daily_returns else 0.0,
        "equity": equity,
        "trade_log": trade_log,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
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


def build_report(
    out_dir: Path,
    rows: list[PairRow],
    forward_table: list[dict[str, object]],
    strategy_results: list[dict[str, object]],
    window: int,
) -> None:
    ratios = sorted(r.ratio for r in rows)
    best = sorted(strategy_results, key=lambda x: float(x["sharpe"]), reverse=True)[:6]
    lines = [
        "# 中国神华 A/H 比例策略第一轮研究",
        "",
        "## 研究对象",
        "",
        f"- 共同交易日：{len(rows)} 天",
        f"- 起止日期：{rows[0].date:%Y-%m-%d} 至 {rows[-1].date:%Y-%m-%d}",
        f"- 比例定义：A 股收盘价 / H 股收盘价，滚动窗口 {window} 日计算 z-score",
        "- 注意：本轮没有纳入 HKD/CNY 汇率、分红复权、融券成本和实际借券约束，所以结论只能作为研究线索。",
        "",
        "## A/H 比例分布",
        "",
        f"- 最小值：{fmt_num(ratios[0])}",
        f"- 25% 分位：{fmt_num(percentile(ratios, 0.25))}",
        f"- 中位数：{fmt_num(median(ratios))}",
        f"- 75% 分位：{fmt_num(percentile(ratios, 0.75))}",
        f"- 最大值：{fmt_num(ratios[-1])}",
        f"- 最新值：{fmt_num(rows[-1].ratio)}",
        f"- 最新 z-score：{fmt_num(rows[-1].ratio_z)}",
        "",
        "## 比例区间与 A 股后续收益",
        "",
        "| z-score 分组 | 样本数 | z区间 | A股后5日均值 | 胜率 | A股后20日均值 | 胜率 | A股后60日均值 | 胜率 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in forward_table:
        lines.append(
            "| {bucket} | {count} | {z_min} ~ {z_max} | {r5} | {w5} | {r20} | {w20} | {r60} | {w60} |".format(
                bucket=item["bucket"],
                count=item["count"],
                z_min=fmt_num(item["z_min"], 2),
                z_max=fmt_num(item["z_max"], 2),
                r5=fmt_pct(item["a_fwd_5d_avg"]),
                w5=fmt_pct(item["a_fwd_5d_win_rate"]),
                r20=fmt_pct(item["a_fwd_20d_avg"]),
                w20=fmt_pct(item["a_fwd_20d_win_rate"]),
                r60=fmt_pct(item["a_fwd_60d_avg"]),
                w60=fmt_pct(item["a_fwd_60d_win_rate"]),
            )
        )
    lines += [
        "",
        "## 策略网格结果，按 Sharpe 排名前 6",
        "",
        "| 模式 | 入场z | 出场z | 总收益 | 年化 | 最大回撤 | Sharpe | 交易次数 | 暴露天数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in best:
        lines.append(
            "| {mode} | {entry} | {exit} | {total} | {ann} | {dd} | {sharpe} | {trades} | {exposure} |".format(
                mode="只做多A" if item["mode"] == "long_a" else "多A空H",
                entry=fmt_num(item["entry_z"], 2),
                exit=fmt_num(item["exit_z"], 2),
                total=fmt_pct(item["total_return"]),
                ann=fmt_pct(item["annualized_return"]),
                dd=fmt_pct(item["max_drawdown"]),
                sharpe=fmt_num(item["sharpe"], 2),
                trades=item["trades"],
                exposure=fmt_pct(item["exposure"]),
            )
        )
    lines += [
        "",
        "## 下一步研究问题",
        "",
        "1. 加入 HKD/CNY 汇率，改成真实 A/H 溢价。",
        "2. 加入前复权或总回报数据，尤其要处理神华高分红对长期价格序列的影响。",
        "3. 对低比例买入、高比例买入都做方向性验证，避免只验证一种叙事。",
        "4. 将通过第一轮筛选的参数接入正式回测模板，补交易规则审计、分段样本和过拟合检查。",
    ]
    (out_dir / "research_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="A/H ratio research for Shenhua")
    parser.add_argument("--a-csv", required=True)
    parser.add_argument("--h-csv", required=True)
    parser.add_argument("--out-dir", default="reports/ah_shenhua_research")
    parser.add_argument("--window", type=int, default=252)
    parser.add_argument("--cost", type=float, default=0.001)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_pair_rows(Path(args.a_csv), Path(args.h_csv), args.window)
    forward_table = forward_return_table(rows, horizons=[5, 20, 60], buckets=5)

    pair_csv = [
        {
            "date": r.date.strftime("%Y-%m-%d"),
            "a_close": r.a_close,
            "h_close": r.h_close,
            "ratio": r.ratio,
            "ratio_ma": r.ratio_ma,
            "ratio_std": r.ratio_std,
            "ratio_z": r.ratio_z,
            "a_ret_1d_next": r.a_ret_1d,
            "h_ret_1d_next": r.h_ret_1d,
        }
        for r in rows
    ]
    write_csv(out_dir / "aligned_ah_ratio.csv", pair_csv)
    write_csv(out_dir / "forward_return_by_ratio_bucket.csv", forward_table)

    strategy_results = []
    summary_rows = []
    for mode in ["long_a", "long_a_short_h"]:
        for entry_z in [-0.5, -1.0, -1.5, -2.0]:
            for exit_z in [0.0, 0.5, 1.0]:
                result = run_strategy(rows, mode, entry_z, exit_z, args.cost)
                strategy_results.append(result)
                summary_rows.append({k: v for k, v in result.items() if k not in {"equity", "trade_log"}})
                write_csv(out_dir / f"trades_{mode}_entry{entry_z}_exit{exit_z}.csv", result["trade_log"])
    write_csv(out_dir / "strategy_grid_summary.csv", summary_rows)
    build_report(out_dir, rows, forward_table, strategy_results, args.window)
    print(out_dir / "research_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
