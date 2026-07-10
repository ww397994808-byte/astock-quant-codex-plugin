from __future__ import annotations

import json

from core.result import TaskResult
from services.backtest_service import BacktestService
from tasks.base_task import BaseTask


class BacktestTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        params = json.loads(kwargs.get("strategy_params") or "{}")
        return BacktestService().run(kwargs["strategy"], kwargs["symbol"], kwargs.get("data", "__auto_fetch__"), params=params, timeframe=kwargs.get("timeframe", "1d"), adjust=kwargs.get("adjust", "raw"))
