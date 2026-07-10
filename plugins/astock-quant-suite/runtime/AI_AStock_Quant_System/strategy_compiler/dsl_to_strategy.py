from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backtest_templates.grid_template import GridTemplate
from backtest_templates.rotation_template import RotationTemplate
from backtest_templates.stock_selection_template import StockSelectionTemplate
from backtest_templates.swing_template import SwingTemplate
from backtest_templates.timing_template import TimingTemplate
from core.order import Signal
from strategy_compiler.component_factory import ComponentFactory
from strategy_compiler.component_registry import ComponentRegistry
from strategy_compiler.compiler_errors import StrategyCompileError
from strategies.base import StrategyBase


@dataclass
class CompiledStrategyResult:
    strategy: StrategyBase
    template_class: type
    template_name: str
    entry_rules: list[str]
    exit_rules: list[str]
    filters: list[str]
    sizing_rules: list[str]
    risk_controls: list[dict]
    compiled_strategy: dict


class ComponentStrategy(StrategyBase):
    name = "compiled_component_strategy"

    def __init__(self, symbol: str, pattern: str, entry_rules: list[Any], exit_rules: list[Any], filters: list[Any], sizing_rule: Any, risk_controls: list[dict], **params: Any) -> None:
        self.symbol = symbol
        self.pattern = pattern
        self.entry_rules = entry_rules
        self.exit_rules = exit_rules
        self.filters = filters
        self.sizing_rule = sizing_rule
        self.risk_controls = risk_controls
        self.state: dict[str, Any] = {"in_position": False, "holding_bars": 0, "bars_since_signal": 999}
        super().__init__(**params)

    def validate_params(self) -> None:
        return None

    def generate_signal(self, history_data: list[dict[str, Any]]) -> Signal:
        row = history_data[-1]
        self.state["bars_since_signal"] = int(self.state.get("bars_since_signal", 999)) + 1
        if self.state.get("in_position"):
            self.state["holding_bars"] = int(self.state.get("holding_bars", 0)) + 1
            self.state["peak_price"] = max(float(self.state.get("peak_price", row["close"])), float(row["close"]))
            for exit_rule in self.exit_rules:
                ok, reason, metadata = exit_rule.check(history_data, self.state)
                if ok:
                    self.state["in_position"] = False
                    self.state["holding_bars"] = 0
                    self.state["bars_since_signal"] = 0
                    return Signal(row["symbol"], row["date"], "SELL", 0.65, reason, target_percent=0.0, metadata=metadata)

        for filter_rule in self.filters:
            if hasattr(filter_rule, "allow"):
                try:
                    allowed, reason, metadata = filter_rule.allow(history_data, self.state)
                except TypeError:
                    allowed, reason, metadata = filter_rule.allow(history_data)
                if not allowed:
                    return Signal(row["symbol"], row["date"], "HOLD", 0.0, reason, metadata=metadata)

        for entry_rule in self.entry_rules:
            ok, reason, metadata = entry_rule.check(history_data)
            if ok and not self.state.get("in_position"):
                self.state["in_position"] = True
                self.state["entry_price"] = float(row["close"])
                self.state["peak_price"] = float(row["close"])
                self.state["holding_bars"] = 0
                self.state["bars_since_signal"] = 0
                percent = self.sizing_rule.target_percent(history_data, self.state)
                return Signal(row["symbol"], row["date"], "BUY", 0.65, reason, target_percent=percent, metadata=metadata)
        return Signal(row["symbol"], row["date"], "HOLD", 0.0, "组件策略无信号")

    def describe(self) -> str:
        return f"组件化策略 pattern={self.pattern}, entry={len(self.entry_rules)}, exit={len(self.exit_rules)}"


class DSLToStrategy:
    def __init__(self, registry: ComponentRegistry | None = None) -> None:
        self.registry = registry or ComponentRegistry()
        self.factory = ComponentFactory(self.registry)

    def compile(self, dsl: dict, symbol: str | None = None) -> CompiledStrategyResult:
        try:
            pattern = dsl.get("pattern", "swing")
            symbol = symbol or (dsl.get("symbols") or [""])[0]
            entry_items = [self._normalize_entry(dsl.get("entry") or {"type": "BollLowerEntry", "params": {}})] + [
                self._normalize_entry(item) for item in dsl.get("alternative_entries", [])
            ]
            exit_items = [self._normalize_exit(item) for item in list(dsl.get("exit", []))] or [{"type": "BollMiddleExit", "params": {}}]
            filter_items = list(dsl.get("filters", []))
            sizing = dsl.get("sizing") or {"type": "FixedPercentSizing", "params": {"percent": 0.5}}

            entry_rules = [self.factory.create(item["type"], self._first_params(item.get("params", {}))) for item in entry_items]
            exit_rules = [self.factory.create(item["type"], self._first_params(item.get("params", {}))) for item in exit_items]
            filters = [self.factory.create(item["type"], self._first_params(item.get("params", {}))) for item in filter_items]
            sizing_rule = self.factory.create(sizing["type"], self._first_params(sizing.get("params", {})))
        except KeyError as exc:
            raise StrategyCompileError(f"DSL 缺少组件字段：{exc}") from exc

        strategy = ComponentStrategy(
            symbol=symbol,
            pattern=pattern,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            filters=filters,
            sizing_rule=sizing_rule,
            risk_controls=list(dsl.get("risk_controls", [])),
        )
        template_map = {
            "swing": SwingTemplate,
            "timing": TimingTemplate,
            "grid": GridTemplate,
            "rotation": RotationTemplate,
            "stock_selection": StockSelectionTemplate,
        }
        template_class = template_map.get(pattern, TimingTemplate)
        template_name = {
            SwingTemplate: "swing",
            TimingTemplate: "timing",
            GridTemplate: "grid",
            RotationTemplate: "rotation",
            StockSelectionTemplate: "stock_selection",
        }.get(template_class, "timing")
        compiled = {
            "strategy_name": strategy.name,
            "pattern": pattern,
            "template_name": template_name,
            "entry_rules": [item["type"] for item in entry_items],
            "exit_rules": [item["type"] for item in exit_items],
            "filters": [item["type"] for item in filter_items],
            "sizing_rules": [sizing["type"]],
            "risk_controls": list(dsl.get("risk_controls", [])),
        }
        return CompiledStrategyResult(
            strategy=strategy,
            template_class=template_class,
            template_name=compiled["template_name"],
            entry_rules=compiled["entry_rules"],
            exit_rules=compiled["exit_rules"],
            filters=compiled["filters"],
            sizing_rules=compiled["sizing_rules"],
            risk_controls=compiled["risk_controls"],
            compiled_strategy=compiled,
        )

    def _first_params(self, params: dict) -> dict:
        normalized = {}
        for key, value in params.items():
            normalized[key] = value[0] if isinstance(value, list) and value else value
        return normalized

    def _normalize_entry(self, item: dict) -> dict:
        if item.get("type") == "SignalEntry":
            return {"type": "DrawdownEntry", "params": {"lookback": 20, "drawdown_threshold": 0.08}}
        return item

    def _normalize_exit(self, item: dict) -> dict:
        if item.get("type") == "ExitLogic":
            return {"type": "BollMiddleExit", "params": {"window": 20}}
        return item
