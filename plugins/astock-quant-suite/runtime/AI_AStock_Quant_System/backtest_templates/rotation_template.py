from __future__ import annotations

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent, RebalancePlan
from core.portfolio import Portfolio


class RotationTemplate(BaseBacktestTemplate):
    template_name = "rotation"

    def __init__(self, strategy, symbol: str, initial_cash: float = 1000000, asset_pool: list[str] | None = None, score_rules: dict | None = None, top_k: int = 1, switch_threshold: float = 0.0, rebalance_frequency: int = 20) -> None:
        super().__init__(strategy, symbol, initial_cash)
        self.asset_pool = asset_pool or []
        self.score_rules = score_rules or {}
        self.top_k = top_k
        self.switch_threshold = switch_threshold
        self.rebalance_frequency = rebalance_frequency
        self.current_selection: list[str] = []

    def should_rebalance(self, index: int) -> bool:
        return index % self.rebalance_frequency == 0

    def score_assets(self, plan_time) -> dict[str, float]:
        dated_scores = self.score_rules.get(plan_time, self.score_rules.get(str(plan_time), self.score_rules))
        return {symbol: float(dated_scores[symbol]) for symbol in self.asset_pool if symbol in dated_scores}

    def should_switch(self, selected: list[tuple[str, float]], scores: dict[str, float]) -> bool:
        if not self.current_selection:
            return True
        current_best = max((scores.get(symbol, float("-inf")) for symbol in self.current_selection), default=float("-inf"))
        new_best = selected[0][1] if selected else float("-inf")
        return new_best - current_best >= self.switch_threshold

    def build_rebalance_plan(self, plan_time, scores: dict[str, float] | None = None, top_k: int | None = None) -> RebalancePlan:
        if scores is not None:
            self.score_rules = scores
            if not self.asset_pool:
                self.asset_pool = list(scores)
        scores = self.score_assets(plan_time)
        selected = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: (top_k or self.top_k)]
        if not self.should_switch(selected, scores):
            return RebalancePlan(plan_time, {symbol: 1.0 / len(self.current_selection) for symbol in self.current_selection}, "轮动评分差未达到切换阈值", {"scores": scores, "switch_threshold": self.switch_threshold})
        self.current_selection = [symbol for symbol, _ in selected]
        weight = 1.0 / len(selected) if selected else 0.0
        return RebalancePlan(plan_time, {symbol: weight for symbol, _ in selected}, "强弱评分轮动", {"scores": scores, "top_k": top_k or self.top_k, "switch_threshold": self.switch_threshold, "rebalance_frequency": self.rebalance_frequency})

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        if not self.should_rebalance(index):
            return []
        plan = self.build_rebalance_plan(history_data[-1]["date"])
        if self.symbol in plan.target_weights:
            return plan.to_order_intents(current_weights={self.symbol: 1.0 if portfolio.positions.total(self.symbol) > 0 else 0.0})
        return []
