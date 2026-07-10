from __future__ import annotations

from copy import deepcopy

from strategy_compiler.component_registry import ComponentRegistry
from strategy_compiler.compiler_errors import StrategyCompileError


class ActionCompiler:
    def __init__(self, registry: ComponentRegistry | None = None) -> None:
        self.registry = registry or ComponentRegistry()

    def compile_action(self, dsl: dict, action: str) -> dict:
        new_dsl = deepcopy(dsl)
        new_dsl.setdefault("entry", {"type": "BollLowerEntry", "params": {}})
        new_dsl.setdefault("exit", [])
        new_dsl.setdefault("filters", [])
        new_dsl.setdefault("sizing", {"type": "FixedPercentSizing", "params": {"percent": 0.5}})
        new_dsl.setdefault("risk_controls", [])
        self._normalize_placeholders(new_dsl)

        if action == "add_stop_loss":
            self._append_exit(new_dsl, "FixedStopLossExit", {"stop_loss": 0.08})
            new_dsl["risk_controls"].append({"type": "FixedStopLoss", "params": {"stop_loss": 0.08}})
        elif action == "tighten_stop_loss":
            self._append_exit(new_dsl, "FixedStopLossExit", {"stop_loss": 0.05})
            new_dsl["risk_controls"].append({"type": "FixedStopLoss", "params": {"stop_loss": 0.05}})
        elif action in {"add_trailing_stop", "test_trailing_stop"}:
            self._append_exit(new_dsl, "TrailingStopExit", {"trail_percent": 0.05})
        elif action in {"add_holding_days", "test_holding_days_exit"}:
            self._append_exit(new_dsl, "HoldingDaysExit", {"max_holding_bars": 20})
        elif action == "add_cooldown":
            self._append_filter(new_dsl, "CooldownFilter", {"cooldown_bars": 3})
        elif action == "add_trend_filter":
            self._append_filter(new_dsl, "TrendFilter", {"window": 20})
        elif action == "add_volatility_filter":
            self._append_filter(new_dsl, "VolatilityFilter", {"max_range": 0.12})
        elif action == "reduce_position_size":
            self._set_sizing(new_dsl, "ReducedPositionSizing", {"percent": 0.2})
        elif action in {"widen_entry_condition", "reduce_threshold"}:
            current = new_dsl.get("entry") or {}
            params = dict(current.get("params", {}))
            if current.get("type") == "BollLowerEntry":
                params["num_std"] = 1.6
            elif current.get("type") == "DrawdownEntry":
                params["drawdown_threshold"] = 0.05
            else:
                current = {"type": "MADeviationEntry"}
                params = {"window": 20, "deviation": 0.04}
            self._set_entry(new_dsl, current.get("type", "MADeviationEntry"), params)
        elif action in {"replace_entry_rule", "test_drawdown_entry"}:
            self._set_entry(new_dsl, "DrawdownEntry", {"lookback": 20, "drawdown_threshold": 0.08})
        elif action == "add_alternative_entry":
            new_dsl.setdefault("alternative_entries", [])
            self._append_component(new_dsl["alternative_entries"], "MADeviationEntry", {"window": 20, "deviation": 0.06})
        elif action == "test_boll_entry":
            self._set_entry(new_dsl, "BollLowerEntry", {"window": 20, "num_std": 2.0})
        elif action == "test_ma_deviation_entry":
            self._set_entry(new_dsl, "MADeviationEntry", {"window": 20, "deviation": 0.06})
        elif action == "test_atr_oversold_entry":
            self._set_entry(new_dsl, "ATROversoldEntry", {"window": 14, "atr_multiple": 1.5})
        elif action in {"replace_exit_rule", "test_fixed_take_profit", "adjust_take_profit", "test_alternative_exit"}:
            new_dsl["exit"] = []
            self._append_exit(new_dsl, "FixedTakeProfitExit", {"take_profit": 0.08})
        elif action == "test_boll_middle_exit":
            self._append_exit(new_dsl, "BollMiddleExit", {"window": 20})
        else:
            raise StrategyCompileError(f"暂不支持优化动作：{action}")

        self.validate_components(new_dsl)
        new_dsl.setdefault("compiler", {})["last_action"] = action
        return new_dsl

    def compile_actions(self, dsl: dict, actions: list[str]) -> tuple[dict, list[dict]]:
        current = deepcopy(dsl)
        reports = []
        for action in actions:
            try:
                current = self.compile_action(current, action)
                reports.append({"action": action, "status": "VALID", "error": ""})
            except StrategyCompileError as exc:
                reports.append({"action": action, "status": "INVALID", "error": str(exc)})
        return current, reports

    def validate_components(self, dsl: dict) -> None:
        self._normalize_placeholders(dsl)
        names = []
        entry = dsl.get("entry") or {}
        if entry.get("type"):
            names.append(entry["type"])
        names.extend(item.get("type") for item in dsl.get("alternative_entries", []) if item.get("type"))
        names.extend(item.get("type") for item in dsl.get("exit", []) if item.get("type"))
        names.extend(item.get("type") for item in dsl.get("filters", []) if item.get("type"))
        sizing = dsl.get("sizing") or {}
        if sizing.get("type"):
            names.append(sizing["type"])
        for name in names:
            self.registry.require(name)

    def _set_entry(self, dsl: dict, name: str, params: dict) -> None:
        self.registry.require(name)
        dsl["entry"] = {"type": name, "params": params}

    def _append_exit(self, dsl: dict, name: str, params: dict) -> None:
        self._append_component(dsl.setdefault("exit", []), name, params)

    def _append_filter(self, dsl: dict, name: str, params: dict) -> None:
        self._append_component(dsl.setdefault("filters", []), name, params)

    def _set_sizing(self, dsl: dict, name: str, params: dict) -> None:
        self.registry.require(name)
        dsl["sizing"] = {"type": name, "params": params}

    def _append_component(self, items: list[dict], name: str, params: dict) -> None:
        self.registry.require(name)
        if not any(item.get("type") == name for item in items):
            items.append({"type": name, "params": params})

    def _normalize_placeholders(self, dsl: dict) -> None:
        if (dsl.get("entry") or {}).get("type") == "SignalEntry":
            dsl["entry"] = {"type": "DrawdownEntry", "params": {"lookback": 20, "drawdown_threshold": 0.08}}
        exits = []
        for item in dsl.get("exit", []):
            if item.get("type") == "ExitLogic":
                exits.append({"type": "BollMiddleExit", "params": {"window": 20}})
            else:
                exits.append(item)
        dsl["exit"] = exits
