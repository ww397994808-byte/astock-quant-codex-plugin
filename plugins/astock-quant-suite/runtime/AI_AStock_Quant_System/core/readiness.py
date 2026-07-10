from __future__ import annotations

from enum import Enum
from pathlib import Path


class StrategyReadiness(str, Enum):
    INVALID = "INVALID"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    PAPER_READY = "PAPER_READY"
    LIVE_CANDIDATE = "LIVE_CANDIDATE"


def classify_readiness(
    audit_status: str,
    future_leak_high: bool = False,
    trade_rule_violation: bool = False,
    out_sample_ok: bool = True,
    stability_ok: bool = True,
    trade_count: int = 0,
    backtest_days: int = 0,
    multi_period_verified: bool = False,
    multi_symbol_verified: bool = False,
    risk_ok: bool = True,
    adjust_type: str = "raw",
) -> StrategyReadiness:
    if audit_status != "VALID" or future_leak_high or trade_rule_violation:
        return StrategyReadiness.INVALID
    if adjust_type in {"qfq", "hfq"}:
        return StrategyReadiness.RESEARCH_ONLY
    if not out_sample_ok or not stability_ok or trade_count < 3:
        return StrategyReadiness.RESEARCH_ONLY
    if backtest_days >= 500 and multi_period_verified and multi_symbol_verified and risk_ok:
        return StrategyReadiness.LIVE_CANDIDATE
    return StrategyReadiness.PAPER_READY


def write_readiness_report(path: str | Path, readiness: StrategyReadiness, reasons: list[str]) -> None:
    lines = ["# Readiness Report", "", f"readiness: {readiness.value}", ""]
    lines.append("## Reasons")
    lines.extend([f"- {reason}" for reason in reasons] or ["- 未发现阻断项。"])
    lines.extend([
        "",
        "说明：LIVE_CANDIDATE 仍不等于允许实盘，下单前必须通过 QMT pre-trade check 和人工二次确认。",
    ])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
