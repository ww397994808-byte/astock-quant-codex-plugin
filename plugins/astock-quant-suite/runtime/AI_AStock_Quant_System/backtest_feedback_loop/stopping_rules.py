from __future__ import annotations

from backtest_feedback_loop.loop_config import LoopConfig


class StoppingRules:
    def should_stop(self, iteration: int, total_experiments: int, deep_rounds: int, config: LoopConfig, data_quality_ok: bool = True, user_stop: bool = False) -> tuple[bool, str]:
        if user_stop:
            return True, "用户明确要求停止"
        if iteration >= config.max_iterations:
            return True, "达到 max_iterations"
        if total_experiments >= config.max_total_experiments:
            return True, "达到 max_total_experiments"
        if not data_quality_ok:
            return True, "数据质量不足"
        if deep_rounds >= config.max_deep_diagnosis_rounds:
            return True, "Deep Diagnosis 达到上限且仍无候选"
        return False, ""

    def should_deep_diagnose(self, no_improve_rounds: int, config: LoopConfig) -> bool:
        return no_improve_rounds >= config.deep_diagnosis_after_no_improve_rounds

