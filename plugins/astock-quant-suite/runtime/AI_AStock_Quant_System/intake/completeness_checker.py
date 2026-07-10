from __future__ import annotations

from intake.question_bank import QUESTION_BANK
from intake.strategy_requirement import StrategyRequirement


class CompletenessChecker:
    REQUIRED_FIELDS = ["symbols", "strategy_pattern", "timeframe", "entry_logic", "exit_logic", "risk_control", "objective"]

    def score(self, req: StrategyRequirement) -> StrategyRequirement:
        score = 0
        unanswered = []
        if req.symbols:
            score += 15
        else:
            unanswered.append(QUESTION_BANK["symbols"])
        if req.strategy_pattern:
            score += 15
        else:
            unanswered.append(QUESTION_BANK["strategy_pattern"])
        if req.timeframe:
            score += 10
        else:
            unanswered.append(QUESTION_BANK["timeframe"])
        if req.entry_logic:
            score += 15
        else:
            unanswered.append(QUESTION_BANK["entry_logic"])
        if req.exit_logic:
            score += 15
        else:
            unanswered.append(QUESTION_BANK["exit_logic"])
        if req.sizing_logic:
            score += 10
        else:
            unanswered.append(QUESTION_BANK["sizing_logic"])
        if req.risk_control:
            score += 10
        else:
            unanswered.append(QUESTION_BANK["risk_control"])
        if req.objective:
            score += 10
        else:
            unanswered.append(QUESTION_BANK["objective"])
        req.completeness_score = min(100, score)
        req.readiness_for_research = score >= 70
        req.unanswered_questions = unanswered
        return req

