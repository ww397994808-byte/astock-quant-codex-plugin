from __future__ import annotations

from intake.strategy_requirement import StrategyRequirement


class RequirementBuilder:
    def build(self, idea: str, fields: dict, score: int, research_ready: bool, unanswered: list[str]) -> StrategyRequirement:
        timeframes = fields.get("timeframes") or []
        req = StrategyRequirement(original_idea=idea)
        req.symbols = fields.get("symbols", [])
        req.asset_type = "ETF" if any("ETF" in idea.upper() for _ in [0]) else "stock"
        req.timeframe = timeframes[0] if timeframes else None
        req.strategy_pattern = fields.get("strategy_pattern")
        entry = fields.get("entry_logic")
        req.entry_logic = "多路线研究：布林下轨 / N日回撤 / 均线偏离 / ATR超跌" if fields.get("multi_route_research") and entry == "NEEDS_ENTRY_CLARIFICATION" else entry
        req.exit_logic = fields.get("exit_logic")
        req.sizing_logic = fields.get("sizing_logic")
        req.risk_control = fields.get("risk_control", {})
        req.data_adjustment = fields.get("adjust", "point_in_time_qfq")
        req.objective = fields.get("objective", {"primary": "calmar"} if fields.get("risk_preference") else {})
        req.constraints = fields.get("constraints", {})
        if len(timeframes) > 1:
            req.constraints["timeframes_to_test"] = timeframes
        if fields.get("sizing_percent"):
            req.constraints["sizing_percent"] = fields["sizing_percent"]
        req.unanswered_questions = unanswered
        req.completeness_score = score
        req.readiness_for_research = research_ready
        req.qmt_safety_note = fields.get("qmt_safety_note", "")
        return req
