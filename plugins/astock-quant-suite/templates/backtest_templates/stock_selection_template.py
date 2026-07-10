from __future__ import annotations

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent, RebalancePlan
from core.portfolio import Portfolio


class StockSelectionTemplate(BaseBacktestTemplate):
    template_name = "stock_selection"

    def __init__(self, strategy, symbol: str, initial_cash: float = 1000000, universe: list[str] | None = None, factor_table: dict | None = None, top_n: int = 5, rebalance_frequency: int = 20) -> None:
        super().__init__(strategy, symbol, initial_cash)
        self.universe = universe or []
        self.factor_table = factor_table or {}
        self.top_n = top_n
        self.rebalance_frequency = rebalance_frequency
        self.ranking_history: list[dict] = []
        self.last_plan: RebalancePlan | None = None

    def rank_universe(self, plan_time) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        dated_scores = self.factor_table.get(plan_time, self.factor_table.get(str(plan_time), self.factor_table))
        for symbol in self.universe:
            if symbol in dated_scores:
                scores[symbol] = float(dated_scores[symbol])
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        self.ranking_history.append({"time": plan_time, "ranking": ranked})
        return ranked

    def should_rebalance(self, index: int) -> bool:
        return index % self.rebalance_frequency == 0

    def build_rebalance_plan(self, plan_time, factor_scores: dict[str, float] | None = None, top_n: int | None = None) -> RebalancePlan:
        if factor_scores is not None:
            self.factor_table = factor_scores
            if not self.universe:
                self.universe = list(factor_scores)
        ranked = self.rank_universe(plan_time)[: (top_n or self.top_n)]
        weight = 1.0 / len(ranked) if ranked else 0.0
        plan = RebalancePlan(plan_time, {symbol: weight for symbol, _ in ranked}, "因子选股 top_n 调仓", {"ranking": ranked, "top_n": top_n or self.top_n, "rebalance_frequency": self.rebalance_frequency})
        self.last_plan = plan
        return plan

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        if not self.should_rebalance(index):
            return []
        plan = self.build_rebalance_plan(history_data[-1]["date"])
        if self.symbol in plan.target_weights:
            return plan.to_order_intents(current_weights={self.symbol: 1.0 if portfolio.positions.total(self.symbol) > 0 else 0.0})
        return []
