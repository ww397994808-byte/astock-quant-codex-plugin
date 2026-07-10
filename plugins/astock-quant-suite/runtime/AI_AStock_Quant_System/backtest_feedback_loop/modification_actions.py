from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModificationAction:
    action: str
    reason: str
    metric_basis: dict
    expected_improvement: str


ACTION_GROUPS = {
    "drawdown_too_large": ["add_stop_loss", "tighten_stop_loss", "add_trend_filter", "reduce_position_size", "add_max_drawdown_risk", "add_volatility_filter"],
    "too_few_trades": ["widen_entry_condition", "reduce_threshold", "add_alternative_entry", "lower_min_trade_constraint", "test_more_sensitive_indicator"],
    "too_many_trades": ["add_trend_filter", "add_holding_days", "increase_threshold", "add_cooldown", "reduce_intraday_noise"],
    "low_return": ["adjust_take_profit", "add_trailing_stop", "test_alternative_exit", "expand_parameter_range", "test_entry_exit_combinations"],
    "out_sample_degradation": ["simplify_strategy", "reduce_parameters", "reject_overfit_variant", "add_walk_forward_validation", "test_regime_split"],
    "high_win_low_pl": ["optimize_profit_loss_ratio", "avoid_small_win_big_loss", "add_profit_loss_constraint"],
    "concentrated_profit": ["downweight_candidate", "add_stability_validation", "block_live_candidate", "reduce_single_trade_dependency"],
}

