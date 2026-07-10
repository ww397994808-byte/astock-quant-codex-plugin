from __future__ import annotations

from backtest_feedback_loop.modification_actions import ACTION_GROUPS, ModificationAction


class OptimizationDirector:
    def propose(self, analysis: dict) -> list[ModificationAction]:
        actions = []
        for issue in analysis.get("issues", []):
            for action in ACTION_GROUPS.get(issue, [])[:3]:
                actions.append(ModificationAction(action, issue, analysis, self._expected(action)))
        if not actions:
            actions.append(ModificationAction("keep_and_validate", "current_candidate_ok", analysis, "继续验证稳定性"))
        return actions

    def _expected(self, action: str) -> str:
        if "stop_loss" in action or "drawdown" in action:
            return "降低最大回撤"
        if "entry" in action or "threshold" in action:
            return "改善交易次数和入场覆盖"
        if "exit" in action or "take_profit" in action or "trailing" in action:
            return "改善收益/盈亏比"
        if "filter" in action or "cooldown" in action:
            return "减少噪音交易"
        return "提升样本外稳定性"

