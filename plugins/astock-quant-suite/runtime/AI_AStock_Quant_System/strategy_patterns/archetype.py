from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class StrategyArchetype(str, Enum):
    TIMING = "timing"
    SWING = "swing"
    GRID = "grid"
    ROTATION = "rotation"
    STOCK_SELECTION = "stock_selection"
    PORTFOLIO_REBALANCE = "portfolio_rebalance"
    EVENT_DRIVEN = "event_driven"
    PAIR_TRADING = "pair_trading"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class StrategyArchetypeSpec:
    archetype: StrategyArchetype
    label: str
    template_name: str | None
    allowed_timeframes: tuple[str, ...]
    required_data: tuple[str, ...]
    audit_required: tuple[str, ...]
    qmt_allowed: bool
    max_stage_without_real_data: str
    blocker_reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["archetype"] = self.archetype.value
        return data


ARCHETYPE_SPECS: dict[StrategyArchetype, StrategyArchetypeSpec] = {
    StrategyArchetype.TIMING: StrategyArchetypeSpec(
        archetype=StrategyArchetype.TIMING,
        label="单标的择时",
        template_name="timing",
        allowed_timeframes=("1d", "1w", "1h", "30m", "10m", "5m"),
        required_data=("OHLCV", "trading_calendar", "market_rules"),
        audit_required=("signal_causality", "trade_rule", "adjustment_leak", "data_quality"),
        qmt_allowed=True,
        max_stage_without_real_data="RESEARCH_ONLY",
    ),
    StrategyArchetype.SWING: StrategyArchetypeSpec(
        archetype=StrategyArchetype.SWING,
        label="单标的波段",
        template_name="swing",
        allowed_timeframes=("1d", "1w", "1h", "30m"),
        required_data=("OHLCV", "trading_calendar", "market_rules"),
        audit_required=("signal_causality", "trade_rule", "adjustment_leak", "data_quality"),
        qmt_allowed=True,
        max_stage_without_real_data="RESEARCH_ONLY",
    ),
    StrategyArchetype.GRID: StrategyArchetypeSpec(
        archetype=StrategyArchetype.GRID,
        label="网格/分层交易",
        template_name="grid",
        allowed_timeframes=("1d", "1h", "30m", "10m", "5m"),
        required_data=("OHLCV", "trading_calendar", "market_rules", "fee_model"),
        audit_required=("signal_causality", "trade_rule", "adjustment_leak", "data_quality", "grid_assumption"),
        qmt_allowed=True,
        max_stage_without_real_data="RESEARCH_ONLY",
    ),
    StrategyArchetype.ROTATION: StrategyArchetypeSpec(
        archetype=StrategyArchetype.ROTATION,
        label="多标的轮动",
        template_name="rotation",
        allowed_timeframes=("1d", "1w"),
        required_data=("multi_symbol_ohlcv", "trading_calendar", "market_rules", "score_table"),
        audit_required=("signal_causality", "trade_rule", "adjustment_leak", "data_quality", "survivorship_bias"),
        qmt_allowed=True,
        max_stage_without_real_data="RESEARCH_ONLY",
    ),
    StrategyArchetype.STOCK_SELECTION: StrategyArchetypeSpec(
        archetype=StrategyArchetype.STOCK_SELECTION,
        label="因子选股",
        template_name="stock_selection",
        allowed_timeframes=("1d", "1w"),
        required_data=("multi_symbol_ohlcv", "point_in_time_factors", "trading_calendar", "market_rules"),
        audit_required=("signal_causality", "trade_rule", "adjustment_leak", "data_quality", "factor_publish_time"),
        qmt_allowed=False,
        max_stage_without_real_data="RESEARCH_ONLY",
        blocker_reason="第一阶段因子选股必须先解决 point-in-time 因子发布时间和股票池幸存者偏差，默认不进入 QMT。",
    ),
    StrategyArchetype.PORTFOLIO_REBALANCE: StrategyArchetypeSpec(
        archetype=StrategyArchetype.PORTFOLIO_REBALANCE,
        label="组合再平衡",
        template_name="portfolio_rebalance",
        allowed_timeframes=("1d", "1w"),
        required_data=("multi_symbol_ohlcv", "target_weights", "trading_calendar", "market_rules"),
        audit_required=("signal_causality", "trade_rule", "adjustment_leak", "data_quality"),
        qmt_allowed=False,
        max_stage_without_real_data="RESEARCH_ONLY",
        blocker_reason="组合再平衡需要更完整的多标的账户净值与交易同步，第一阶段只做研究。",
    ),
    StrategyArchetype.EVENT_DRIVEN: StrategyArchetypeSpec(
        archetype=StrategyArchetype.EVENT_DRIVEN,
        label="事件驱动",
        template_name=None,
        allowed_timeframes=("1d",),
        required_data=("OHLCV", "event_time_available_at", "trading_calendar"),
        audit_required=("signal_causality", "event_publish_time", "trade_rule", "data_quality"),
        qmt_allowed=False,
        max_stage_without_real_data="RESEARCH_ONLY",
        blocker_reason="事件驱动必须有事件发布时间和可获得时间；没有 point-in-time 事件数据时禁止进入模拟盘或 QMT。",
    ),
    StrategyArchetype.PAIR_TRADING: StrategyArchetypeSpec(
        archetype=StrategyArchetype.PAIR_TRADING,
        label="配对/套利",
        template_name=None,
        allowed_timeframes=("1d", "1w"),
        required_data=("multi_symbol_ohlcv", "borrowability", "trading_calendar", "market_rules"),
        audit_required=("signal_causality", "trade_rule", "shorting_constraints", "data_quality"),
        qmt_allowed=False,
        max_stage_without_real_data="RESEARCH_ONLY",
        blocker_reason="A股配对/套利常涉及融券、港股通、汇率或交易时段差，第一阶段标记为研究阻断。",
    ),
    StrategyArchetype.UNSUPPORTED: StrategyArchetypeSpec(
        archetype=StrategyArchetype.UNSUPPORTED,
        label="暂不支持",
        template_name=None,
        allowed_timeframes=(),
        required_data=(),
        audit_required=("manual_review",),
        qmt_allowed=False,
        max_stage_without_real_data="INVALID",
        blocker_reason="策略范式不明确或当前系统没有可信模板，禁止伪装成已验证策略。",
    ),
}


def get_archetype_spec(archetype: StrategyArchetype | str | None) -> StrategyArchetypeSpec:
    try:
        if isinstance(archetype, StrategyArchetype):
            key = archetype
        else:
            key = StrategyArchetype(str(archetype or StrategyArchetype.UNSUPPORTED.value))
    except ValueError:
        key = StrategyArchetype.UNSUPPORTED
    return ARCHETYPE_SPECS[key]
