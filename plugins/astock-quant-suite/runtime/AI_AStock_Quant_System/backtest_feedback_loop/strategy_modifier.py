from __future__ import annotations

from copy import deepcopy

from backtest_feedback_loop.modification_actions import ModificationAction


class StrategyModifier:
    def apply(self, dsl: dict, actions: list[ModificationAction]) -> tuple[dict, list[dict]]:
        new_dsl = deepcopy(dsl)
        records = []
        before = deepcopy(dsl)
        for action in actions:
            self._apply_one(new_dsl, action.action)
            records.append({
                "before": before,
                "after": deepcopy(new_dsl),
                "action": action.action,
                "reason": action.reason,
                "metric_basis": action.metric_basis,
                "expected_improvement": action.expected_improvement,
            })
        return new_dsl, records

    def _apply_one(self, dsl: dict, action: str) -> None:
        constraints = dsl.setdefault("constraints", {})
        objective = dsl.setdefault("objective", {})
        if action in {"add_stop_loss", "tighten_stop_loss"}:
            exits = dsl.setdefault("exit", [])
            exits.append({"type": "FixedStopLossExit", "params": {"stop_loss": [0.05, 0.06, 0.08]}})
        elif action == "reduce_position_size":
            dsl.setdefault("sizing", {"type": "FixedPercentSizing", "params": {}})["params"] = {"percent": [0.05, 0.1, 0.15]}
        elif action in {"add_trend_filter", "add_volatility_filter"}:
            dsl.setdefault("filters", []).append({"type": action})
        elif action in {"widen_entry_condition", "reduce_threshold"}:
            dsl.setdefault("entry", {}).setdefault("params", {})["sensitivity"] = ["wider", "normal"]
        elif action == "test_alternative_exit":
            dsl.setdefault("exit", []).append({"type": "AlternativeExit"})
        elif action == "adjust_take_profit":
            dsl.setdefault("exit", []).append({"type": "TakeProfitExit", "params": {"take_profit": [0.04, 0.06, 0.08]}})
        elif action == "add_trailing_stop":
            dsl.setdefault("exit", []).append({"type": "TrailingStopExit", "params": {"trail_percent": [0.03, 0.05]}})
        elif action in {"add_holding_days", "add_cooldown"}:
            constraints["cooldown"] = "3 bars"
            constraints["cooldown_bars"] = 3
            constraints["min_holding_period"] = "3 bars"
            constraints["min_holding_bars"] = 3
        elif action == "simplify_strategy":
            dsl.pop("filters", None)
            constraints["max_experiments"] = min(int(constraints.get("max_experiments", 300)), 100)
        elif action == "expand_parameter_range":
            constraints["max_experiments"] = min(1000, int(constraints.get("max_experiments", 300)) + 100)
        objective.setdefault("primary", "calmar")
