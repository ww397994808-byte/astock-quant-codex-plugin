from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from . import config
from .grid import simulate_symbol_grid
from .market import load_market, month_last_dates
from .metrics import annual_stats, daily_equity, max_drawdown, pct
from .params import make_param_pool


def score_param(equity: dict[str, float], dates: list[str], mode: str) -> float:
    values = [equity[d] / equity[dates[0]] for d in dates]
    returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    total = values[-1] - 1
    months = max(len(returns), 1)
    annual = (1 + total) ** (12 / months) - 1 if total > -1 else -1.0
    dd = abs(max_drawdown(values))
    recent3 = values[-1] / values[max(0, len(values) - 4)] - 1 if len(values) >= 4 else total
    recent6 = values[-1] / values[max(0, len(values) - 7)] - 1 if len(values) >= 7 else total
    worst = min(returns) if returns else 0.0
    if mode == "balanced":
        return annual - dd * 0.8 + worst * 0.5
    if mode == "recent3":
        return recent3 * 4 + annual * 0.3 - dd * 0.3
    if mode == "recent6":
        return recent6 * 2 + annual * 0.3 - dd * 0.4
    if mode == "return_only":
        return annual
    if mode == "calmar":
        return annual / dd if dd > 0 else annual * 10
    return annual - dd


def build_window_card(
    *,
    idx: int,
    month_dates: list[str],
    rule: config.FixedRule,
) -> dict[str, str | int]:
    param_train_dates = month_dates[idx - rule.param_lookback_months : idx + 1]
    symbol_train_start = month_dates[idx - rule.symbol_lookback_months]
    rebalance_date = month_dates[idx]
    next_date = month_dates[idx + 1]
    return {
        "param_train_start_date": param_train_dates[0],
        "param_train_end_date": param_train_dates[-1],
        "param_train_months": len(param_train_dates),
        "symbol_train_start_date": symbol_train_start,
        "symbol_train_end_date": rebalance_date,
        "decision_made_after": rebalance_date,
        "rebalance_date": rebalance_date,
        "test_start_date": next_date,
        "test_end_date": next_date,
        "next_date": next_date,
        "causality_rule": "param_train_end_date <= rebalance_date < test_start_date",
    }


def validate_window_card(card: dict[str, str | int], *, rule: config.FixedRule) -> list[str]:
    findings = []
    if card["param_train_end_date"] != card["rebalance_date"]:
        findings.append("参数训练窗口必须结束在调仓日，不能越过调仓日。")
    if card["symbol_train_end_date"] != card["rebalance_date"]:
        findings.append("品种强弱窗口必须结束在调仓日，不能越过调仓日。")
    if card["param_train_start_date"] > card["param_train_end_date"]:
        findings.append("参数训练窗口开始日期晚于结束日期。")
    if card["symbol_train_start_date"] > card["symbol_train_end_date"]:
        findings.append("品种强弱窗口开始日期晚于结束日期。")
    if card["rebalance_date"] >= card["test_start_date"]:
        findings.append("测试/持有期必须严格晚于调仓日。")
    if card["test_start_date"] != card["next_date"]:
        findings.append("测试开始日期必须等于下一期收益日期。")
    expected_months = rule.param_lookback_months + 1
    if card["param_train_months"] != expected_months:
        findings.append(f"参数训练窗口长度应为 {expected_months} 个月，实际为 {card['param_train_months']}。")
    return findings


def validate_walk_forward_result(result: dict, *, rule: config.FixedRule) -> dict:
    findings = []
    for row in result.get("decisions", []):
        findings.extend(validate_window_card(row, rule=rule))
        if row.get("causality_status") != "PASS":
            findings.append(f"{row.get('rebalance_date')}: causality_status 不是 PASS。")
    return {
        "status": "VALID" if not findings else "INVALID",
        "rule": "每次参数选择、品种排序只能使用调仓日及以前数据；持有期收益只能使用调仓日之后的下一期。",
        "decision_count": len(result.get("decisions", [])),
        "findings": findings,
    }


def run_walk_forward(
    param_equities: dict[str, list[dict[str, float]]],
    *,
    rule: config.FixedRule,
    start_year: str,
) -> dict:
    common_dates = sorted(set.intersection(*(set(eq) for values in param_equities.values() for eq in values)))
    month_dates = month_last_dates(common_dates)
    first_idx = next(
        i
        for i, date in enumerate(month_dates)
        if date[:4] >= start_year
        and i >= rule.param_lookback_months
        and i >= rule.symbol_lookback_months
    )
    current = config.INITIAL_CASH
    rows = [{"date": month_dates[first_idx], "equity": current}]
    decisions = []

    for idx in range(first_idx, len(month_dates) - 1):
        window_card = build_window_card(idx=idx, month_dates=month_dates, rule=rule)
        window_findings = validate_window_card(window_card, rule=rule)
        if window_findings:
            raise ValueError(f"walk-forward 窗口存在未来函数风险：{'; '.join(window_findings)}")
        param_train_dates = month_dates[idx - rule.param_lookback_months : idx + 1]
        symbol_start = str(window_card["symbol_train_start_date"])
        rebalance_date = str(window_card["rebalance_date"])
        next_date = str(window_card["next_date"])

        selected_param_idx = {}
        symbol_scores = {}
        for symbol in config.CORE5:
            best_idx = max(
                range(len(param_equities[symbol])),
                key=lambda k: score_param(param_equities[symbol][k], param_train_dates, rule.param_score_mode),
            )
            selected_param_idx[symbol] = best_idx
            symbol_scores[symbol] = param_equities[symbol][best_idx][rebalance_date] / param_equities[symbol][best_idx][symbol_start] - 1

        ranked = sorted(config.CORE5, key=lambda s: symbol_scores[s], reverse=True)
        selected = ranked[: len(rule.top_weights)]
        weights = {symbol: weight for symbol, weight in zip(selected, rule.top_weights)}
        next_return = sum(
            weight
            * (
                param_equities[symbol][selected_param_idx[symbol]][next_date]
                / param_equities[symbol][selected_param_idx[symbol]][rebalance_date]
                - 1
            )
            for symbol, weight in weights.items()
        )
        current *= 1 + next_return
        rows.append({"date": next_date, "equity": current})
        decisions.append(
            {
                **window_card,
                "causality_status": "PASS",
                "rebalance_date": rebalance_date,
                "next_date": next_date,
                "selected": " ".join(selected),
                "next_return": next_return,
                **{f"param_rank_{s}": selected_param_idx[s] + 1 for s in config.CORE5},
                **{f"symbol_score_{s}": symbol_scores[s] for s in config.CORE5},
                **{s: weights.get(s, 0.0) for s in config.CORE5},
            }
        )

    values = [r["equity"] for r in rows]
    total = values[-1] / values[0] - 1
    years = (datetime.fromisoformat(rows[-1]["date"]) - datetime.fromisoformat(rows[0]["date"])).days / 365.25
    annual = (1 + total) ** (1 / years) - 1 if total > -1 else -1.0
    mdd = max_drawdown(values)
    result = {
        "rows": rows,
        "decisions": decisions,
        "annual_return": annual,
        "total_return": total,
        "max_drawdown": mdd,
        "calmar": annual / abs(mdd) if mdd < 0 else 0.0,
        "annuals": annual_stats(rows),
    }
    audit = validate_walk_forward_result(result, rule=rule)
    if audit["status"] != "VALID":
        raise ValueError(f"walk-forward 审计未通过：{audit['findings']}")
    result["walk_forward_audit"] = audit
    return result


def build_param_equities(rule: config.FixedRule, n_random: int = 297) -> tuple[list[dict], dict[str, list[dict[str, float]]]]:
    params = make_param_pool(n_random=n_random)
    missing = config.missing_market_files()
    if missing:
        details = "; ".join(f"{symbol}: {paths[0]}" for symbol, paths in missing.items())
        raise FileNotFoundError(
            "Core5 行情数据不完整。请把五只股票的 30m CSV 放入 data/core5_raw，"
            f"或设置 {config.ENV_DATA_DIR} 指向数据目录。缺失：{details}"
        )
    markets = {
        symbol: load_market(symbol, str(config.resolve_market_file(symbol)), rule.start_date, rule.end_date)
        for symbol in config.CORE5
    }
    param_equities = {symbol: [] for symbol in config.CORE5}
    for symbol in config.CORE5:
        for params_row in params:
            result = simulate_symbol_grid(markets[symbol], params_row, rule.dividend_factor, keep=True)
            param_equities[symbol].append(daily_equity(result))
    return params, param_equities


def decision_key(row: dict) -> tuple:
    return (
        row["rebalance_date"],
        row["next_date"],
        row["selected"],
        tuple(row[f"param_rank_{s}"] for s in config.CORE5),
        tuple(row[s] for s in config.CORE5),
    )


def compare_overlap(base: dict, other: dict) -> tuple[int, int]:
    base_map = {row["rebalance_date"]: decision_key(row) for row in base["decisions"]}
    other_map = {row["rebalance_date"]: decision_key(row) for row in other["decisions"]}
    common = sorted(set(base_map) & set(other_map))
    mismatches = sum(base_map[d] != other_map[d] for d in common)
    return len(common), mismatches


def write_result_files(out_dir: Path, start_year: str, result: dict) -> None:
    with (out_dir / f"start_{start_year}_equity.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "equity"])
        writer.writeheader()
        writer.writerows(result["rows"])
    with (out_dir / f"start_{start_year}_decisions.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "param_train_start_date",
            "param_train_end_date",
            "param_train_months",
            "symbol_train_start_date",
            "symbol_train_end_date",
            "decision_made_after",
            "rebalance_date",
            "test_start_date",
            "test_end_date",
            "next_date",
            "causality_rule",
            "causality_status",
            "selected",
            "next_return",
        ]
        fields += [f"param_rank_{s}" for s in config.CORE5]
        fields += [f"symbol_score_{s}" for s in config.CORE5]
        fields += config.CORE5
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["decisions"])
    (out_dir / f"start_{start_year}_walk_forward_audit.json").write_text(
        json.dumps(result["walk_forward_audit"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_report(out_dir: Path, rule: config.FixedRule, results: dict[str, dict]) -> None:
    rows = []
    for start_year, result in results.items():
        row = {
            "start_year": start_year,
            "annual_return": result["annual_return"],
            "total_return": result["total_return"],
            "max_drawdown": result["max_drawdown"],
            "calmar": result["calmar"],
            "years_above_20": sum(item["annual_return"] >= 0.20 for item in result["annuals"].values()),
            "years_count": len(result["annuals"]),
            "weakest_year_annualized": min(item["annual_return"] for item in result["annuals"].values()),
        }
        for year, item in result["annuals"].items():
            row[f"{year}_ann"] = item["annual_return"]
            row[f"{year}_dd"] = item["max_drawdown"]
        rows.append(row)

    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Core5 Relative Strength Grid Fixed Rule Backtest",
        "",
        "- same rule for every start year",
        "- no per-start-year best setting selection",
        f"- fixed rule: {rule}",
        "- each month chooses params and symbols using only prior data",
        "- strict walk-forward guard: param_train_end_date <= rebalance_date < test_start_date; any violation raises INVALID before writing evidence",
        "- single-symbol engine includes T+1 sells, buy-first inside each 30m interval, fees, and implemented dividends",
        "",
        "## Walk-Forward Causality Guard",
        "",
        "每个月只允许用调仓日及以前的数据选择参数和排序品种，下一期收益必须从调仓日之后的下一期开始计算。",
    ]
    for start_year in sorted(results):
        audit = results[start_year]["walk_forward_audit"]
        lines.append(f"- start {start_year}: audit={audit['status']}, decisions={audit['decision_count']}")
    lines.extend(
        [
            "",
        ]
    )
    base_year = sorted(results)[0]
    base = results[base_year]
    lines.append(f"## Overlap Decision Consistency vs Start {base_year}")
    for start_year in sorted(results):
        if start_year == base_year:
            continue
        common, mismatches = compare_overlap(base, results[start_year])
        lines.append(f"- start {start_year}: common_months={common}, mismatches={mismatches}")
    lines.append("")

    for start_year in sorted(results):
        result = results[start_year]
        lines.extend(
            [
                f"## Start {start_year}",
                f"- annual_return: {pct(result['annual_return'])}",
                f"- total_return: {pct(result['total_return'])}",
                f"- max_drawdown: {pct(result['max_drawdown'])}",
                f"- calmar: {result['calmar']:.2f}",
                f"- years_above_20: {sum(item['annual_return'] >= 0.20 for item in result['annuals'].values())}/{len(result['annuals'])}",
                f"- weakest_year_annualized: {pct(min(item['annual_return'] for item in result['annuals'].values()))}",
                "",
                "### Annual",
            ]
        )
        for year, item in result["annuals"].items():
            lines.append(f"- {year}: total={pct(item['total_return'])}, annualized={pct(item['annual_return'])}, dd={pct(item['max_drawdown'])}")
        lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run_fixed_rule_start_check(
    *,
    out_dir: str | Path,
    rule: config.FixedRule | None = None,
    start_years: tuple[str, ...] = ("2018", "2019", "2020", "2021"),
    n_random: int = 297,
) -> dict[str, dict]:
    rule = rule or config.default_rule()
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    _, param_equities = build_param_equities(rule, n_random=n_random)
    results = {}
    for start_year in start_years:
        results[start_year] = run_walk_forward(param_equities, rule=rule, start_year=start_year)
        write_result_files(out_path, start_year, results[start_year])
    write_report(out_path, rule, results)
    return results
