from __future__ import annotations


class ResearchExpander:
    MAP = {
        "参数空间太窄": ["expand_parameter_range", "random_search", "coarse_grid_restart"],
        "入场逻辑错误": ["replace_entry_rule", "add_alternative_entry", "test_drawdown_entry", "test_boll_entry", "test_ma_deviation_entry", "test_atr_oversold_entry"],
        "出场逻辑错误": ["replace_exit_rule", "test_fixed_take_profit", "test_trailing_stop", "test_boll_middle_exit", "test_holding_days_exit"],
        "周期不匹配": ["test_timeframe_10m", "test_timeframe_30m", "test_timeframe_1h", "test_timeframe_1d", "test_timeframe_1w"],
        "标的不适合": ["cross_symbol_validate", "test_similar_assets", "test_etf_proxy"],
        "市场状态不适合": ["regime_split_analysis", "bull_bear_sideways_split", "volatility_regime_split"],
        "过滤条件过强": ["remove_filter", "relax_filter", "test_no_filter_baseline"],
        "交易次数太少": ["relax_entry_condition", "reduce_threshold", "add_more_entry_variants"],
        "数据质量问题": ["request_data_fix", "switch_data_source", "downgrade_readiness"],
    }

    def expand(self, failures: list[str]) -> list[str]:
        actions = []
        for failure in failures:
            actions.extend(self.MAP.get(failure, ["expand_parameter_range"]))
        return list(dict.fromkeys(actions))

