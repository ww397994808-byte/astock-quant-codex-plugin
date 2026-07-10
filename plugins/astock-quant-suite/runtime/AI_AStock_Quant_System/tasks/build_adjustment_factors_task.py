from __future__ import annotations

from core.result import TaskResult
from market_data.adjustment_factor_store import AdjustmentFactorStore
from market_data.corporate_actions import load_corporate_actions
from tasks.base_task import BaseTask


class BuildAdjustmentFactorsTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        symbol = kwargs["symbol"]
        actions = load_corporate_actions(kwargs["corporate_actions"], symbol)
        path = AdjustmentFactorStore().save_factors(symbol, actions)
        return TaskResult("VALID", f"复权因子已生成：{path}", artifacts={"path": str(path)})
