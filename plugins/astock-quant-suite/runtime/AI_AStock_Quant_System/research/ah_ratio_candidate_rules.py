from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev

from ah_ratio_research import PairRow, annualized_return, build_pair_rows, max_drawdown


def fmt_pct(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "NA"
    return f"{value * 100:.2f}%"


def fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None or math.isnan(value):
        return "NA"
    return f"{value:.{digits}f}"


def slice_rows(rows: list[PairRow], start_date: str) -> list[PairRow]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    return [r for r in rows if r.date >= start and r.ratio_z is not None]


def rolling_ma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= window:
            total -= values[i - window]
        out.append(total / window if i + 1 >= window else None)
    return out


def rolling_vol(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        sample = values[i + 1 - window : i + 1]
        out.append(stdev(sample) * math.sqrt(252) if len(sample) > 1 else None)
    return out


def sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    sigma = stdev(daily_returns)
    if sigma == 0:
        return 0.0
    return mean(daily_returns) / sigma * math.sqrt(252)


def should_enter(
    rows: list[PairRow],
    index: int,
    trigger_z: float,
    wait_days: int,
    confirm_z: float,
    confirm_mode: str,
    ma60: list[float | None],
) -> tuple[bool, str]:
    trigger = index - wait_days
    if trigger < 1:
        return False, ""
    prev = rows[trigger - 1]
    event = rows[trigger]
    row = rows[index]
    if (prev.ratio_z or 0.0) <= trigger_z or (event.ratio_z or 0.0) > trigger_z:
        return False, ""
    if (row.ratio_z or 0.0) > confirm_z:
        return False, ""
    if confirm_mode == "none":
        return True, "低估触发后等待确认"
    if confirm_mode == "a_not_lower":
        return row.a_close >= event.a_close, "等待后 A 股不低于触发日"
    if confirm_mode == "a_above_ma60":
        return ma60[index] is not None and row.a_close >= float(ma60[index]), "等待后 A 股站上 MA60"
    if confirm_mode == "z_rebound":
        return (row.ratio_z or 0.0) > (event.ratio_z or 0.0), "等待后 z-score 反弹"
    if confirm_mode == "z_rebound_or_a_not_lower":
        return (row.ratio_z or 0.0) > (event.ratio_z or 0.0) or row.a_close >= event.a_close, "等待后 z 反弹或 A 不创新低"
    raise ValueError(f"未知确认模式：{confirm_mode}")


def run_rule(
    rows: list[PairRow],
    mode: str,
    trigger_z: float,
    wait_days: int,
    confirm_z: float,
    confirm_mode: str,
    exit_z: float,
    max_hold: int,
    stop_loss: float,
    take_profit: float,
    weight: float,
    ma60: list[float | None],
) -> dict[str, object]:
    equity = [1.0]
    daily_returns: list[float] = []
    position = 0.0
    entry_equity = 1.0
    hold_days = 0
    trade_log: list[dict[str, object]] = []
    completed_returns: list[float] = []
    entry_date = ""

    for i, row in enumerate(rows[:-1]):
        desired = position
        reason = ""
        if position == 0:
            ok, reason = should_enter(rows, i, trigger_z, wait_days, confirm_z, confirm_mode, ma60)
            if ok:
                desired = weight
                entry_equity = equity[-1]
                hold_days = 0
                entry_date = row.date.strftime("%Y-%m-%d")
        else:
            hold_days += 1
            trade_return = equity[-1] / entry_equity - 1.0 if entry_equity else 0.0
            if (row.ratio_z or 0.0) >= exit_z:
                desired = 0.0
                reason = "z-score 回归退出"
            elif max_hold > 0 and hold_days >= max_hold:
                desired = 0.0
                reason = "达到最大持仓天数"
            elif stop_loss > 0 and trade_return <= -stop_loss:
                desired = 0.0
                reason = "组合止损"
            elif take_profit > 0 and trade_return >= take_profit:
                desired = 0.0
                reason = "组合止盈"

        if desired != position:
            action = "ENTER" if desired else "EXIT"
            if action == "EXIT":
                completed_returns.append(equity[-1] / entry_equity - 1.0)
            trade_log.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "action": action,
                "entry_date": entry_date if action == "EXIT" else row.date.strftime("%Y-%m-%d"),
                "a_close": row.a_close,
                "h_close": row.h_close,
                "ratio": row.ratio,
                "ratio_z": row.ratio_z,
                "equity": equity[-1],
                "reason": reason,
            })
        position = desired

        leg_return = row.a_ret_1d or 0.0
        if mode == "long_a_short_h":
            leg_return -= row.h_ret_1d or 0.0
        cost = abs(desired - position) * 0.0
        day_return = position * leg_return - cost
        daily_returns.append(day_return)
        equity.append(equity[-1] * (1.0 + day_return))

    mdd = max_drawdown(equity)
    ann = annualized_return(equity, len(daily_returns))
    completed = len(completed_returns)
    return {
        "mode": mode,
        "trigger_z": trigger_z,
        "wait_days": wait_days,
        "confirm_z": confirm_z,
        "confirm_mode": confirm_mode,
        "exit_z": exit_z,
        "max_hold": max_hold,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "weight": weight,
        "final_equity": equity[-1],
        "annualized_return": ann,
        "total_return": equity[-1] - 1.0,
        "max_drawdown": mdd,
        "sharpe": sharpe(daily_returns),
        "trade_count": len(trade_log),
        "completed_trades": completed,
        "win_rate": sum(1 for x in completed_returns if x > 0) / completed if completed else 0.0,
        "avg_trade_return": mean(completed_returns) if completed_returns else 0.0,
        "median_trade_return": median(completed_returns) if completed_returns else 0.0,
        "worst_trade_return": min(completed_returns) if completed_returns else 0.0,
        "exposure": sum(1 for x in daily_returns if abs(x) > 0) / len(daily_returns) if daily_returns else 0.0,
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


def result_table(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| 模式 | 触发z | 等待 | 确认 | 退出z | 持仓 | 止损 | 止盈 | 仓位 | 年化 | 回撤 | Sharpe | 完成交易 | 胜率 | 单笔中位 | 最差单笔 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            "| {mode} | {trigger} | {wait} | {confirm} | {exit} | {hold} | {sl} | {tp} | {w} | {ann} | {dd} | {sh} | {trades} | {win} | {med} | {worst} |".format(
                mode="只做多A" if r["mode"] == "long_a" else "多A空H",
                trigger=fmt_num(float(r["trigger_z"]), 1),
                wait=r["wait_days"],
                confirm=r["confirm_mode"],
                exit=fmt_num(float(r["exit_z"]), 1),
                hold=r["max_hold"],
                sl=fmt_pct(float(r["stop_loss"])),
                tp=fmt_pct(float(r["take_profit"])),
                w=fmt_pct(float(r["weight"])),
                ann=fmt_pct(float(r["annualized_return"])),
                dd=fmt_pct(float(r["max_drawdown"])),
                sh=fmt_num(float(r["sharpe"])),
                trades=r["completed_trades"],
                win=fmt_pct(float(r["win_rate"])),
                med=fmt_pct(float(r["median_trade_return"])),
                worst=fmt_pct(float(r["worst_trade_return"])),
            )
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate candidate rules from Shenhua A/H event path patterns")
    parser.add_argument("--a-csv", required=True)
    parser.add_argument("--h-csv", required=True)
    parser.add_argument("--out-dir", default="reports/ah_shenhua_candidate_rules")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--window", type=int, default=252)
    args = parser.parse_args()

    rows = slice_rows(build_pair_rows(Path(args.a_csv), Path(args.h_csv), args.window), args.start_date)
    ma60 = rolling_ma([r.a_close for r in rows], 60)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for mode in ["long_a", "long_a_short_h"]:
        for trigger_z in [-1.0, -1.5]:
            for wait_days in [0, 2, 3]:
                for confirm_z in [trigger_z, -0.5]:
                    if confirm_z < trigger_z:
                        continue
                    for confirm_mode in ["none", "a_not_lower", "z_rebound_or_a_not_lower"]:
                        for exit_z in [0.0, 0.5]:
                            for max_hold in [40, 60]:
                                for stop_loss in [0.025, 0.04, 0.06]:
                                    for take_profit in [0.08, 0.12, 0.2]:
                                        for weight in [0.25, 0.35, 0.5, 0.7]:
                                            result = run_rule(
                                                rows=rows,
                                                mode=mode,
                                                trigger_z=trigger_z,
                                                wait_days=wait_days,
                                                confirm_z=confirm_z,
                                                confirm_mode=confirm_mode,
                                                exit_z=exit_z,
                                                max_hold=max_hold,
                                                stop_loss=stop_loss,
                                                take_profit=take_profit,
                                                weight=weight,
                                                ma60=ma60,
                                            )
                                            results.append(result)

    summary = [{k: v for k, v in r.items() if k != "trade_log"} for r in results]
    write_csv(out_dir / "candidate_rule_summary.csv", summary)
    robust = [r for r in results if int(r["completed_trades"]) >= 8]
    by_low_dd = sorted(robust, key=lambda r: (float(r["max_drawdown"]), float(r["annualized_return"])), reverse=True)
    by_sharpe = sorted(robust, key=lambda r: float(r["sharpe"]), reverse=True)
    by_target = sorted(robust, key=lambda r: (float(r["max_drawdown"]) >= -0.05, float(r["annualized_return"]), float(r["sharpe"])), reverse=True)
    best = by_target[0] if by_target else results[0]
    write_csv(out_dir / "best_rule_trades.csv", best["trade_log"])

    latest = rows[-1]
    lines = [
        "# 中国神华 A/H 候选规则验证",
        "",
        f"- 样本：{rows[0].date:%Y-%m-%d} 至 {rows[-1].date:%Y-%m-%d}",
        f"- 最新 A/H：{fmt_num(latest.ratio, 3)}，最新 z-score：{fmt_num(latest.ratio_z, 3)}",
        "- 规则来自上一轮事件路径：低 z-score 触发，等待 0/2/3/5 天，确认后入场。",
        "- 本轮仍是研究验证，不是实盘建议；未纳入汇率、复权、真实交易成本与融券约束。",
        "",
        "## 回撤小于 5% 内，年化优先",
        "",
        *result_table([r for r in by_target if float(r["max_drawdown"]) >= -0.05][:12]),
        "",
        "## Sharpe 排名",
        "",
        *result_table(by_sharpe[:12]),
        "",
        "## 最低回撤排名",
        "",
        *result_table(by_low_dd[:12]),
        "",
        "## 当前规则化观察",
        "",
        "1. 等待确认能减少冲动入场，但样本数会进一步下降，所以必须看完成交易数。",
        "2. 多 A 空 H 往往更适合表达相对错价，单做 A 更依赖煤炭股自身趋势。",
        "3. 若低回撤规则收益仍不够，下一步应做年份拆分与行情环境分类，而不是继续盲目加参数。",
    ]
    (out_dir / "candidate_rule_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "candidate_rule_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
