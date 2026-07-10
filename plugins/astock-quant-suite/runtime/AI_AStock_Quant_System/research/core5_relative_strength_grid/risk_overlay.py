from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config
from .metrics import annual_stats, max_drawdown, pct


@dataclass(frozen=True)
class OverlayRule:
    name: str
    kind: str
    dd_trigger: float = 0.12
    weak_invest: float = 0.40
    lo: float = 0.02
    hi: float = 0.08
    min_invest: float = 0.20
    max_invest: float = 0.90


BASE_RULE = OverlayRule(name="base_no_overlay", kind="base")
PORTFOLIO_DD_GUARD = OverlayRule(name="portfolio_dd_12pct_invest_40pct", kind="portfolio_dd", dd_trigger=0.12, weak_invest=0.40)
SCORE_LINEAR_GUARD = OverlayRule(name="score_linear_2pct_8pct_invest_20pct_90pct", kind="score_linear", lo=0.02, hi=0.08, min_invest=0.20, max_invest=0.90)


def load_decisions(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def investment_fraction(rule: OverlayRule, decision: dict, current_equity: float, peak_equity: float) -> float:
    if rule.kind == "base":
        return 1.0
    if rule.kind == "portfolio_dd":
        portfolio_dd = current_equity / peak_equity - 1
        return rule.weak_invest if portfolio_dd < -rule.dd_trigger else 1.0
    if rule.kind == "score_linear":
        selected = decision["selected"].split()[0]
        score = float(decision[f"symbol_score_{selected}"])
        if score <= rule.lo:
            return rule.min_invest
        if score >= rule.hi:
            return rule.max_invest
        return rule.min_invest + (score - rule.lo) / (rule.hi - rule.lo) * (rule.max_invest - rule.min_invest)
    raise ValueError(f"unknown overlay rule kind: {rule.kind}")


def apply_overlay(decisions: list[dict], rule: OverlayRule) -> dict:
    current = config.INITIAL_CASH
    peak = current
    rows = [{"date": decisions[0]["rebalance_date"], "equity": current}]
    out_decisions = []
    for decision in decisions:
        before_dd = current / peak - 1
        invest = investment_fraction(rule, decision, current, peak)
        base_return = float(decision["next_return"])
        overlay_return = invest * base_return
        current *= 1 + overlay_return
        peak = max(peak, current)
        rows.append({"date": decision["next_date"], "equity": current})
        out_decisions.append(
            {
                **decision,
                "base_return": base_return,
                "invest_fraction": invest,
                "overlay_return": overlay_return,
                "portfolio_dd_before": before_dd,
            }
        )

    values = [row["equity"] for row in rows]
    total = values[-1] / values[0] - 1
    years = (datetime.fromisoformat(rows[-1]["date"]) - datetime.fromisoformat(rows[0]["date"])).days / 365.25
    annual = (1 + total) ** (1 / years) - 1 if total > -1 else -1.0
    mdd = max_drawdown(values)
    return {
        "rows": rows,
        "decisions": out_decisions,
        "annual_return": annual,
        "total_return": total,
        "max_drawdown": mdd,
        "calmar": annual / abs(mdd) if mdd < 0 else 0.0,
        "annuals": annual_stats(rows),
    }


def write_overlay_files(out_dir: Path, start_year: str, rule: OverlayRule, result: dict) -> None:
    prefix = f"start_{start_year}_{rule.name}"
    with (out_dir / f"{prefix}_equity.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "equity"])
        writer.writeheader()
        writer.writerows(result["rows"])
    fields = list(result["decisions"][0])
    with (out_dir / f"{prefix}_decisions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["decisions"])


def run_overlay_report(
    *,
    base_decision_dir: str | Path,
    out_dir: str | Path,
    start_years: tuple[str, ...] = ("2018", "2019", "2020", "2021"),
    rules: tuple[OverlayRule, ...] = (BASE_RULE, PORTFOLIO_DD_GUARD, SCORE_LINEAR_GUARD),
) -> dict[tuple[str, str], dict]:
    base_path = Path(base_decision_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    results = {}
    summary_rows = []
    for start_year in start_years:
        decisions = load_decisions(base_path / f"start_{start_year}_decisions.csv")
        for rule in rules:
            result = apply_overlay(decisions, rule)
            results[(start_year, rule.name)] = result
            write_overlay_files(out_path, start_year, rule, result)
            row = {
                "start_year": start_year,
                "overlay": rule.name,
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
            summary_rows.append(row)

    fields = []
    for row in summary_rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with (out_path / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    lines = [
        "# Core5 Relative Strength Grid Risk Overlay",
        "",
        "- applies portfolio-level cash buffer to the fixed-rule decisions",
        "- does not change single-symbol grid execution, parameter selection, or symbol selection",
        "- cash earns 0% in this test",
        "",
    ]
    for start_year in start_years:
        lines.append(f"## Start {start_year}")
        for rule in rules:
            result = results[(start_year, rule.name)]
            lines.extend(
                [
                    f"### {rule.name}",
                    f"- annual_return: {pct(result['annual_return'])}",
                    f"- total_return: {pct(result['total_return'])}",
                    f"- max_drawdown: {pct(result['max_drawdown'])}",
                    f"- calmar: {result['calmar']:.2f}",
                    f"- years_above_20: {sum(item['annual_return'] >= 0.20 for item in result['annuals'].values())}/{len(result['annuals'])}",
                    f"- weakest_year_annualized: {pct(min(item['annual_return'] for item in result['annuals'].values()))}",
                ]
            )
            annual_text = ", ".join(f"{year}={pct(item['annual_return'])}" for year, item in result["annuals"].items())
            lines.append(f"- annuals: {annual_text}")
        lines.append("")
    (out_path / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return results
