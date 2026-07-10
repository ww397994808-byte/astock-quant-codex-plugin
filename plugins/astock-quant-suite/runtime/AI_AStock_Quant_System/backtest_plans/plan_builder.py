from __future__ import annotations

from intake.strategy_requirement import StrategyRequirement
from strategy_patterns import StrategyArchetypeClassifier
from backtest_plans.backtest_plan import BacktestPlan


class BacktestPlanBuilder:
    """Build the pre-run contract that binds strategy type, data, template, and gates."""

    _SINGLE_SYMBOL_PATTERNS = {"timing", "swing", "grid"}

    def build(self, req: StrategyRequirement) -> BacktestPlan:
        spec = StrategyArchetypeClassifier().classify_requirement(req)
        timeframe = req.timeframe or "1d"
        adjust = req.data_adjustment or "raw"
        blockers: list[str] = []
        warnings: list[str] = []

        if not req.symbols:
            blockers.append("缺少标的或股票池，不能生成可信回测计划。")
        if spec.template_name is None:
            blockers.append(spec.blocker_reason or "当前策略范式没有可用回测模板。")
        if timeframe not in spec.allowed_timeframes:
            blockers.append(f"{spec.archetype.value} 不支持 {timeframe} 周期；允许周期：{', '.join(spec.allowed_timeframes) or '无'}。")
        if adjust in {"qfq", "hfq"}:
            warnings.append(f"普通 {adjust} 存在未来复权泄漏风险，最多进入 RESEARCH_ONLY。")
        if timeframe in {"5m", "10m", "30m", "1h"} and spec.archetype.value in {"grid", "timing", "swing"}:
            warnings.append("日内周期受 A股 T+1、午休、涨跌停和数据完整性影响，实盘前必须先经过模拟盘观察。")
        if not spec.qmt_allowed:
            warnings.append(spec.blocker_reason or "该策略范式第一阶段不允许进入 QMT。")

        status = "INVALID" if blockers else "VALID"
        symbol_scope = "single" if spec.archetype.value in self._SINGLE_SYMBOL_PATTERNS else "multi"
        return BacktestPlan(
            strategy_pattern=spec.archetype.value,
            template_name=spec.template_name,
            symbol_scope=symbol_scope,
            timeframe=timeframe,
            adjust=adjust,
            data_required=list(spec.required_data),
            execution_model={
                "signal_bar": "close_confirmed",
                "fill_bar": "next_bar_open",
                "t_plus_1": True,
                "price_basis": "next_bar_open",
            },
            audit_required=list(spec.audit_required),
            promotion_policy={
                "qmt_allowed": spec.qmt_allowed,
                "max_stage_without_real_data": spec.max_stage_without_real_data,
                "requires_paper_observation": True,
                "requires_qmt_readonly": bool(spec.qmt_allowed),
            },
            status=status,
            blockers=blockers,
            warnings=warnings,
        )
