from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

from ah_ratio_research import PairRow, annualized_return, build_pair_rows, max_drawdown, sharpe, write_csv


def moving_average(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= window:
            running -= values[i - window]
        out.append(running / window if i + 1 >= window else None)
    return out


def rolling_slope(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        start = values[i + 1 - window]
        out.append(values[i] / start - 1.0 if start else None)
    return out


def slice_from_start(rows: list[PairRow], start_date: str) -> list[PairRow]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    return [r for r in rows if r.date >= start]


def run_controlled_strategy(
    rows: list[PairRow],
    mode: str,
    entry_z: float,
    exit_z: float,
    weight: float,
    stop_loss: float,
    take_profit: float,
    max_hold: int,
    trend_window: int,
    trend_mode: str,
    cost_per_turnover: float,
    trend_ok_series: list[bool] | None = None,
) -> dict[str, object]:
    equity = [1.0]
    daily_returns = []
    position = 0.0
    entry_a = 0.0
    entry_equity = 1.0
    hold_days = 0
    trades = 0
    wins = 0
    completed = 0
    trade_log = []

    for i, row in enumerate(rows[:-1]):
        if row.ratio_z is None:
            daily_returns.append(0.0)
            equity.append(equity[-1])
            continue

        trend_ok = trend_ok_series[i] if trend_ok_series is not None else True

        desired = position
        reason = ""
        if position == 0 and row.ratio_z <= entry_z and trend_ok:
            desired = weight
            entry_a = row.a_close
            entry_equity = equity[-1]
            hold_days = 0
            reason = "入场：低 A/H 比例 + 趋势过滤通过"
        elif position > 0:
            hold_days += 1
            trade_return = equity[-1] / entry_equity - 1.0 if entry_equity else 0.0
            if row.ratio_z >= exit_z:
                desired = 0.0
                reason = "退出：比例回归"
            elif stop_loss > 0 and trade_return <= -stop_loss:
                desired = 0.0
                reason = "退出：组合止损"
            elif take_profit > 0 and trade_return >= take_profit:
                desired = 0.0
                reason = "退出：止盈"
            elif max_hold > 0 and hold_days >= max_hold:
                desired = 0.0
                reason = "退出：达到最大持仓天数"

        turnover_cost = abs(desired - position) * cost_per_turnover
        if desired != position:
            trades += 1
            action = "ENTER" if desired else "EXIT"
            if action == "EXIT":
                completed += 1
                wins += 1 if equity[-1] > entry_equity else 0
            trade_log.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "action": action,
                "a_close": row.a_close,
                "h_close": row.h_close,
                "ratio": row.ratio,
                "ratio_z": row.ratio_z,
                "equity": equity[-1],
                "reason": reason,
            })
        position = desired

        leg_ret = row.a_ret_1d or 0.0
        if mode == "long_a_short_h":
            leg_ret -= row.h_ret_1d or 0.0
        day_ret = position * leg_ret - turnover_cost
        daily_returns.append(day_ret)
        equity.append(equity[-1] * (1.0 + day_ret))

    mdd = max_drawdown(equity)
    ann = annualized_return(equity, len(daily_returns))
    return {
        "mode": mode,
        "entry_z": entry_z,
        "exit_z": exit_z,
        "weight": weight,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "max_hold": max_hold,
        "trend_window": trend_window,
        "trend_mode": trend_mode,
        "final_equity": equity[-1],
        "total_return": equity[-1] - 1.0,
        "annualized_return": ann,
        "max_drawdown": mdd,
        "return_over_drawdown": ann / abs(mdd) if mdd else 0.0,
        "sharpe": sharpe(daily_returns),
        "trades": trades,
        "completed_trades": completed,
        "win_rate": wins / completed if completed else 0.0,
        "exposure": sum(1 for x in daily_returns if abs(x) > 0) / len(daily_returns) if daily_returns else 0.0,
        "meets_target": ann >= 0.20 and mdd >= -0.05,
        "equity": equity,
        "trade_log": trade_log,
    }


def fmt_pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def fmt_num(value: object, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}"


def write_optimizer_report(out_dir: Path, rows: list[PairRow], results: list[dict[str, object]], start_date: str) -> None:
    feasible = [r for r in results if r["meets_target"]]
    by_target = sorted(
        results,
        key=lambda r: (
            float(r["annualized_return"]) >= 0.20 and float(r["max_drawdown"]) >= -0.05,
            float(r["annualized_return"]),
            float(r["return_over_drawdown"]),
        ),
        reverse=True,
    )
    by_low_dd = sorted(results, key=lambda r: (float(r["max_drawdown"]), float(r["annualized_return"])), reverse=True)
    by_rod = sorted(results, key=lambda r: float(r["return_over_drawdown"]), reverse=True)

    def table(items: list[dict[str, object]]) -> list[str]:
        lines = [
            "| 模式 | 入场z | 出场z | 仓位 | 止损 | 止盈 | 最长持仓 | 趋势 | 年化 | 回撤 | 收益/回撤 | Sharpe | 交易 | 胜率 |",
            "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in items:
            lines.append(
                "| {mode} | {entry} | {exit} | {weight} | {sl} | {tp} | {hold} | {trend} | {ann} | {dd} | {rod} | {sharpe} | {trades} | {win} |".format(
                    mode="只做多A" if r["mode"] == "long_a" else "多A空H",
                    entry=fmt_num(r["entry_z"]),
                    exit=fmt_num(r["exit_z"]),
                    weight=fmt_pct(r["weight"]),
                    sl=fmt_pct(r["stop_loss"]),
                    tp=fmt_pct(r["take_profit"]),
                    hold=r["max_hold"],
                    trend=r["trend_mode"],
                    ann=fmt_pct(r["annualized_return"]),
                    dd=fmt_pct(r["max_drawdown"]),
                    rod=fmt_num(r["return_over_drawdown"]),
                    sharpe=fmt_num(r["sharpe"]),
                    trades=r["trades"],
                    win=fmt_pct(r["win_rate"]),
                )
            )
        return lines

    lines = [
        "# 中国神华 A/H 低回撤优化研究",
        "",
        f"- 研究起点：{start_date}",
        f"- 实际样本：{rows[0].date:%Y-%m-%d} 至 {rows[-1].date:%Y-%m-%d}，{len(rows)} 个共同交易日",
        "- 硬目标：年化收益 > 20%，最大回撤 < 5%",
        "- 本轮仍未纳入汇率、分红复权、融券成本、保证金占用和真实可借券约束。",
        "",
        f"## 是否达到硬目标：{'是' if feasible else '否'}",
        "",
    ]
    if feasible:
        lines += table(feasible[:20])
    else:
        lines += [
            "当前参数空间没有找到同时满足两个硬目标的结果。这是重要结论：不能为了目标硬拧参数。",
            "",
            "## 最接近硬目标的结果",
            "",
            *table(by_target[:10]),
        ]
    lines += [
        "",
        "## 收益/回撤比排名",
        "",
        *table(by_rod[:10]),
        "",
        "## 最低回撤排名",
        "",
        *table(by_low_dd[:10]),
        "",
        "## 下一步优化方向",
        "",
        "1. 先补复权和汇率，否则 2018 年以来的价格关系仍然不是严格 A/H 溢价。",
        "2. 如果坚持回撤低于 5%，需要考虑更多空仓等待、分批仓位、波动率目标仓位，或者引入股息/煤价/指数趋势过滤。",
        "3. 对任何接近目标的参数做年份拆分，必须确认不是 2021-2024 单段行情贡献。",
    ]
    (out_dir / "optimizer_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Low-drawdown optimizer for Shenhua A/H ratio")
    parser.add_argument("--a-csv", required=True)
    parser.add_argument("--h-csv", required=True)
    parser.add_argument("--out-dir", default="reports/ah_shenhua_low_dd")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--window", type=int, default=252)
    parser.add_argument("--cost", type=float, default=0.001)
    args = parser.parse_args()

    all_rows = build_pair_rows(Path(args.a_csv), Path(args.h_csv), args.window)
    rows = slice_from_start(all_rows, args.start_date)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trend_filters: dict[tuple[int, str], list[bool]] = {}
    a_closes = [r.a_close for r in rows]
    for trend_window in [20, 60, 120, 200]:
        ma = moving_average(a_closes, trend_window)
        slope = rolling_slope(a_closes, trend_window)
        trend_filters[(trend_window, "none")] = [True] * len(rows)
        trend_filters[(trend_window, "above_ma")] = [
            value is not None and rows[i].a_close >= float(value) for i, value in enumerate(ma)
        ]
        trend_filters[(trend_window, "ma_slope_up")] = [
            value is not None and float(value) > 0 for value in slope
        ]
        trend_filters[(trend_window, "above_ma_and_slope_up")] = [
            ma[i] is not None and slope[i] is not None and rows[i].a_close >= float(ma[i]) and float(slope[i]) > 0
            for i in range(len(rows))
        ]

    results: list[dict[str, object]] = []
    summary: list[dict[str, object]] = []
    for mode in ["long_a", "long_a_short_h"]:
        for entry_z in [-0.5, -1.0, -1.5]:
            for exit_z in [0.0, 0.5]:
                if exit_z <= entry_z:
                    continue
                for weight in [0.15, 0.25, 0.35, 0.5]:
                    for stop_loss in [0.015, 0.025, 0.04]:
                        for take_profit in [0.08, 0.12, 0.2]:
                            for max_hold in [20, 40, 60]:
                                for trend_window in [60, 120]:
                                    for trend_mode in ["none", "above_ma_and_slope_up"]:
                                        r = run_controlled_strategy(
                                            rows=rows,
                                            mode=mode,
                                            entry_z=entry_z,
                                            exit_z=exit_z,
                                            weight=weight,
                                            stop_loss=stop_loss,
                                            take_profit=take_profit,
                                            max_hold=max_hold,
                                            trend_window=trend_window,
                                            trend_mode=trend_mode,
                                            cost_per_turnover=args.cost,
                                            trend_ok_series=trend_filters[(trend_window, trend_mode)],
                                        )
                                        results.append(r)
                                        summary.append({k: v for k, v in r.items() if k not in {"equity", "trade_log"}})

    write_csv(out_dir / "optimizer_summary.csv", summary)
    write_optimizer_report(out_dir, rows, results, args.start_date)
    best = max(results, key=lambda r: (bool(r["meets_target"]), float(r["annualized_return"]), float(r["return_over_drawdown"])))
    write_csv(out_dir / "best_trade_log.csv", best["trade_log"])
    print(out_dir / "optimizer_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
