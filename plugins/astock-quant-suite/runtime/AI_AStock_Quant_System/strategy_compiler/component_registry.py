from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ComponentSpec:
    component_name: str
    component_type: str
    supported_patterns: list[str]
    required_params: list[str]
    default_params: dict
    parameter_ranges: dict
    description: str
    import_path: str
    class_name: str

    def to_dict(self) -> dict:
        return asdict(self)


class ComponentRegistry:
    def __init__(self) -> None:
        self._components = {spec.component_name: spec for spec in self._build()}

    def get(self, name: str) -> ComponentSpec | None:
        return self._components.get(name)

    def require(self, name: str) -> ComponentSpec:
        spec = self.get(name)
        if spec is None:
            from strategy_compiler.compiler_errors import StrategyCompileError

            raise StrategyCompileError(f"不存在策略组件：{name}")
        return spec

    def list_components(self) -> list[ComponentSpec]:
        return list(self._components.values())

    def write_component_list(self, path) -> None:
        lines = ["# Component List", ""]
        for spec in self.list_components():
            lines += [
                f"## {spec.component_name}",
                f"- type: {spec.component_type}",
                f"- supported_patterns: {', '.join(spec.supported_patterns)}",
                f"- required_params: {', '.join(spec.required_params) or 'none'}",
                f"- default_params: {spec.default_params}",
                f"- parameter_ranges: {spec.parameter_ranges}",
                f"- description: {spec.description}",
                "",
            ]
        from pathlib import Path

        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def _build(self) -> list[ComponentSpec]:
        return [
            ComponentSpec("BollLowerEntry", "entry", ["swing", "timing"], [], {"window": 20, "num_std": 2.0}, {"window": [10, 30], "num_std": [1.5, 2.5]}, "布林下轨低吸入场", "strategies.components.entry_rules.boll_lower_entry", "BollLowerEntry"),
            ComponentSpec("DrawdownEntry", "entry", ["swing"], [], {"lookback": 20, "drawdown_threshold": 0.08}, {"drawdown_threshold": [0.05, 0.15]}, "近期高点回撤入场", "strategies.components.entry_rules.drawdown_entry", "DrawdownEntry"),
            ComponentSpec("MADeviationEntry", "entry", ["swing", "timing"], [], {"window": 20, "deviation": 0.06}, {"deviation": [0.03, 0.1]}, "价格相对均线负偏离入场", "strategies.components.entry_rules.ma_deviation_entry", "MADeviationEntry"),
            ComponentSpec("ATROversoldEntry", "entry", ["swing"], [], {"window": 14, "atr_multiple": 1.5}, {"atr_multiple": [1.0, 2.5]}, "ATR 超跌入场", "strategies.components.entry_rules.atr_oversold_entry", "ATROversoldEntry"),
            ComponentSpec("BollMiddleExit", "exit", ["swing", "timing"], [], {"window": 20}, {"window": [10, 30]}, "回到布林中轨退出", "strategies.components.exit_rules.boll_middle_exit", "BollMiddleExit"),
            ComponentSpec("FixedStopLossExit", "exit", ["swing", "timing"], [], {"stop_loss": 0.08}, {"stop_loss": [0.04, 0.12]}, "固定止损退出", "strategies.components.exit_rules.fixed_stop_loss_exit", "FixedStopLossExit"),
            ComponentSpec("FixedTakeProfitExit", "exit", ["swing", "timing"], [], {"take_profit": 0.08}, {"take_profit": [0.03, 0.12]}, "固定止盈退出", "strategies.components.exit_rules.fixed_take_profit_exit", "FixedTakeProfitExit"),
            ComponentSpec("TrailingStopExit", "exit", ["swing", "timing"], [], {"trail_percent": 0.05}, {"trail_percent": [0.03, 0.1]}, "移动止盈退出", "strategies.components.exit_rules.trailing_stop_exit", "TrailingStopExit"),
            ComponentSpec("HoldingDaysExit", "exit", ["swing", "timing"], [], {"max_holding_bars": 20}, {"max_holding_bars": [5, 40]}, "持仓周期退出", "strategies.components.exit_rules.holding_days_exit", "HoldingDaysExit"),
            ComponentSpec("TrendFilter", "filter", ["swing", "timing"], [], {"window": 20}, {"window": [10, 60]}, "趋势过滤", "strategies.components.filters.trend_filter", "TrendFilter"),
            ComponentSpec("VolatilityFilter", "filter", ["swing", "timing"], [], {"max_range": 0.12}, {"max_range": [0.05, 0.2]}, "波动过滤", "strategies.components.filters.volatility_filter", "VolatilityFilter"),
            ComponentSpec("CooldownFilter", "filter", ["swing", "timing"], [], {"cooldown_bars": 3}, {"cooldown_bars": [2, 10]}, "信号冷却过滤", "strategies.components.filters.cooldown_filter", "CooldownFilter"),
            ComponentSpec("VolumeFilter", "filter", ["swing", "timing"], [], {"min_volume": 1.0}, {"min_volume": [1, 1000000]}, "成交量过滤", "strategies.components.filters.volume_filter", "VolumeFilter"),
            ComponentSpec("FixedPercentSizing", "sizing", ["swing", "timing"], [], {"percent": 0.5}, {"percent": [0.1, 0.8]}, "固定比例仓位", "strategies.components.sizing_rules.fixed_percent_sizing", "FixedPercentSizing"),
            ComponentSpec("ReducedPositionSizing", "sizing", ["swing", "timing"], [], {"percent": 0.2}, {"percent": [0.05, 0.3]}, "降低仓位", "strategies.components.sizing_rules.reduced_position_sizing", "ReducedPositionSizing"),
            ComponentSpec("VolatilityAdjustedSizing", "sizing", ["swing", "timing"], [], {"base_percent": 0.3, "max_range": 0.1}, {"base_percent": [0.1, 0.5]}, "波动率调整仓位", "strategies.components.sizing_rules.volatility_adjusted_sizing", "VolatilityAdjustedSizing"),
        ]
