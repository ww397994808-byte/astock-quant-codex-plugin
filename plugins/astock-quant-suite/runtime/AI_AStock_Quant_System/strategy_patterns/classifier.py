from __future__ import annotations

from intake.strategy_requirement import StrategyRequirement
from strategy_patterns.archetype import StrategyArchetype, StrategyArchetypeSpec, get_archetype_spec


class StrategyArchetypeClassifier:
    """Deterministic strategy archetype classifier for planning and gates."""

    _ALIASES = {
        "timing": StrategyArchetype.TIMING,
        "trend": StrategyArchetype.TIMING,
        "swing": StrategyArchetype.SWING,
        "grid": StrategyArchetype.GRID,
        "rotation": StrategyArchetype.ROTATION,
        "stock_selection": StrategyArchetype.STOCK_SELECTION,
        "selection": StrategyArchetype.STOCK_SELECTION,
        "portfolio": StrategyArchetype.PORTFOLIO_REBALANCE,
        "portfolio_rebalance": StrategyArchetype.PORTFOLIO_REBALANCE,
        "event": StrategyArchetype.EVENT_DRIVEN,
        "event_driven": StrategyArchetype.EVENT_DRIVEN,
        "pair": StrategyArchetype.PAIR_TRADING,
        "pair_trading": StrategyArchetype.PAIR_TRADING,
        "arbitrage": StrategyArchetype.PAIR_TRADING,
    }

    def classify_requirement(self, req: StrategyRequirement) -> StrategyArchetypeSpec:
        return self.classify(req.strategy_pattern, req.original_idea)

    def classify(self, pattern: str | None, idea: str = "") -> StrategyArchetypeSpec:
        raw = (pattern or "").strip().lower()
        if raw in self._ALIASES:
            return get_archetype_spec(self._ALIASES[raw])

        text = (idea or "").lower()
        if any(k in text for k in ("网格", "grid", "分层")):
            return get_archetype_spec(StrategyArchetype.GRID)
        if any(k in text for k in ("轮动", "rotation", "切换", "强弱")):
            return get_archetype_spec(StrategyArchetype.ROTATION)
        if any(k in text for k in ("选股", "因子", "高股息", "低波动", "topn", "top n")):
            return get_archetype_spec(StrategyArchetype.STOCK_SELECTION)
        if any(k in text for k in ("事件", "业绩预告", "分红", "公告", "event")):
            return get_archetype_spec(StrategyArchetype.EVENT_DRIVEN)
        if any(k in text for k in ("配对", "套利", "ah", "a/h", "价差", "pair")):
            return get_archetype_spec(StrategyArchetype.PAIR_TRADING)
        if any(k in text for k in ("组合", "再平衡", "权重", "rebalance")):
            return get_archetype_spec(StrategyArchetype.PORTFOLIO_REBALANCE)
        if any(k in text for k in ("均线", "趋势", "突破", "macd", "择时")):
            return get_archetype_spec(StrategyArchetype.TIMING)
        if any(k in text for k in ("跌多了", "回撤", "波段", "低吸", "布林")):
            return get_archetype_spec(StrategyArchetype.SWING)
        return get_archetype_spec(StrategyArchetype.UNSUPPORTED)
