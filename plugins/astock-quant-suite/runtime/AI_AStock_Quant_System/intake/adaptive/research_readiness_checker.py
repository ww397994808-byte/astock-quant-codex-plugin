from __future__ import annotations


class ResearchReadinessChecker:
    REQUIRED = ["symbols", "strategy_pattern", "timeframes", "entry_logic", "exit_logic", "risk_control", "objective"]

    def score(self, fields: dict, user_confirmed: bool = False) -> tuple[int, bool, list[str]]:
        score = 0
        missing = []
        weights = {
            "symbols": 15,
            "strategy_pattern": 15,
            "timeframes": 10,
            "entry_logic": 15,
            "exit_logic": 15,
            "sizing_logic": 10,
            "risk_control": 10,
            "objective": 10,
        }
        for key, weight in weights.items():
            if fields.get(key):
                score += weight
            else:
                missing.append(key)
        score = min(100, score)
        return score, bool(user_confirmed and score >= 70), missing
