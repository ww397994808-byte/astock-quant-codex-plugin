from __future__ import annotations

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent, RebalancePlan
from core.portfolio import Portfolio


class PortfolioRebalanceTemplate(BaseBacktestTemplate):
    template_name = "portfolio_rebalance"

    def __init__(self, strategy, symbol: str, initial_cash: float = 1000000, target_weights: dict[str, float] | None = None, drift_threshold: float = 0.05, rebalance_frequency: int = 20, cash_buffer: float = 0.02) -> None:
        super().__init__(strategy, symbol, initial_cash)
        self.target_weights = target_weights or {}
        self.drift_threshold = drift_threshold
        self.rebalance_frequency = rebalance_frequency
        self.cash_buffer = cash_buffer

    def should_rebalance(self, index: int, current_weights: dict[str, float]) -> bool:
        if index % self.rebalance_frequency != 0:
            return False
        adjusted_targets = self.adjusted_target_weights()
        symbols = set(current_weights) | set(adjusted_targets)
        return any(abs(adjusted_targets.get(symbol, 0.0) - current_weights.get(symbol, 0.0)) >= self.drift_threshold for symbol in symbols)

    def adjusted_target_weights(self) -> dict[str, float]:
        scale = max(0.0, 1.0 - self.cash_buffer)
        raw_total = sum(max(0.0, weight) for weight in self.target_weights.values())
        if raw_total <= 0:
            return {}
        return {symbol: round(max(0.0, weight) / raw_total * scale, 8) for symbol, weight in self.target_weights.items()}

    def build_rebalance_plan(self, plan_time, target_weights: dict[str, float] | None = None) -> RebalancePlan:
        if target_weights is not None:
            self.target_weights = target_weights
        return RebalancePlan(plan_time, self.adjusted_target_weights(), "组合目标权重再平衡", {"drift_threshold": self.drift_threshold, "rebalance_frequency": self.rebalance_frequency, "cash_buffer": self.cash_buffer})

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        current_weight = 1.0 if portfolio.positions.total(self.symbol) > 0 else 0.0
        current_weights = {self.symbol: current_weight}
        if not self.should_rebalance(index, current_weights):
            return []
        plan = self.build_rebalance_plan(history_data[-1]["date"])
        if self.symbol in plan.target_weights:
            return plan.to_order_intents(current_weights=current_weights)
        return []
