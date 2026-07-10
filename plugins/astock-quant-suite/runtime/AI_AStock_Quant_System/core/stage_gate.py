from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResearchStage(str, Enum):
    INVALID = "INVALID"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    BACKTEST_VALID = "BACKTEST_VALID"
    PAPER_READY = "PAPER_READY"
    PAPER_OBSERVED = "PAPER_OBSERVED"
    QMT_READONLY_READY = "QMT_READONLY_READY"
    PRETRADE_VALID = "PRETRADE_VALID"
    LIVE_CANDIDATE = "LIVE_CANDIDATE"


@dataclass
class StageGateResult:
    stage: ResearchStage
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"stage": self.stage.value, "reasons": self.reasons}


class StageGateEvaluator:
    """Promote a strategy only when each hard gate has evidence."""

    def evaluate(
        self,
        *,
        backtest_plan: dict[str, Any] | None = None,
        audit_status: str = "INVALID",
        readiness: str | None = None,
        paper_observed: bool = False,
        qmt_readonly_ok: bool = False,
        pretrade_ok: bool = False,
    ) -> StageGateResult:
        reasons: list[str] = []
        plan = backtest_plan or {}
        if plan.get("status") == "INVALID" or plan.get("blockers"):
            return StageGateResult(ResearchStage.INVALID, list(plan.get("blockers") or ["回测计划未通过。"]))
        if audit_status != "VALID":
            return StageGateResult(ResearchStage.INVALID, [f"审计状态不是 VALID：{audit_status}"])
        if not plan:
            return StageGateResult(ResearchStage.RESEARCH_ONLY, ["缺少 backtest_plan，最多停留在研究阶段。"])
        if not plan.get("promotion_policy", {}).get("qmt_allowed", False):
            return StageGateResult(ResearchStage.RESEARCH_ONLY, ["当前策略范式不允许进入 QMT。"])

        stage = ResearchStage.BACKTEST_VALID
        if readiness in {"PAPER_READY", "LIVE_CANDIDATE"}:
            stage = ResearchStage.PAPER_READY
        else:
            reasons.append("Readiness 尚未达到 PAPER_READY。")
            return StageGateResult(stage, reasons)

        if not paper_observed:
            return StageGateResult(stage, ["尚未完成连续模拟盘观察。"])
        stage = ResearchStage.PAPER_OBSERVED

        if not qmt_readonly_ok:
            return StageGateResult(stage, ["QMT 只读检查未通过。"])
        stage = ResearchStage.QMT_READONLY_READY

        if not pretrade_ok:
            return StageGateResult(stage, ["实盘前检查未通过。"])
        return StageGateResult(ResearchStage.PRETRADE_VALID, ["仍需人工确认 CONFIRM_REAL_TRADE 后才可进入 LIVE_CANDIDATE。"])
