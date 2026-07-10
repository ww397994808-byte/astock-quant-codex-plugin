from __future__ import annotations

from backtest.engine import BacktestEngine
from core.result import TaskResult
from core.run_manager import RunManager
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest


class BacktestService:
    def run(self, strategy: str, symbol: str, data: str, params: dict | None = None, prefix: str = "backtest", timeframe: str = "1d", adjust: str = "raw") -> TaskResult:
        if not data or data == "__auto_fetch__":
            data = DataAcquisitionAgent().fetch(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))["path"]
        ctx = RunManager().create_run(prefix)
        result = BacktestEngine().run(ctx, strategy, symbol, data, params, timeframe=timeframe, adjust=adjust)
        return TaskResult(
            status=result.status,
            message=f"回测完成：{result.status}",
            run_id=result.run_id,
            report_path=str(result.output_dir),
            audit_status=result.audit_status,
            artifacts={"performance": result.performance},
        )
