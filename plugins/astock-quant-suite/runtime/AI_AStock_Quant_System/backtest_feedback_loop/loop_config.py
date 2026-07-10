from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoopConfig:
    max_iterations: int = 8
    max_total_experiments: int = 1000
    deep_diagnosis_after_no_improve_rounds: int = 2
    max_deep_diagnosis_rounds: int = 2
    allow_strategy_family_switch: bool = True
    allow_timeframe_switch: bool = True
    allow_symbol_expansion: bool = True
    min_improvement_threshold: float = 0.03
    primary_metric: str = "calmar"
    secondary_metrics: list[str] = field(default_factory=lambda: ["out_sample_score", "max_drawdown", "stability", "trade_count", "stress_result", "data_quality_score"])

