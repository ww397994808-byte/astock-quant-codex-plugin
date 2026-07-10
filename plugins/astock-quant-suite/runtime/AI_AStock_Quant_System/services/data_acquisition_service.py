from __future__ import annotations

from core.result import TaskResult
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest


class DataAcquisitionService:
    def fetch(self, symbol: str, timeframe: str = "1d", adjust: str = "raw") -> TaskResult:
        record = DataAcquisitionAgent().fetch(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))
        return TaskResult("VALID", f"数据已就绪：{record['path']}", report_path=record["path"], artifacts=record)

    def status(self, symbol: str, timeframe: str = "1d", adjust: str = "raw") -> TaskResult:
        record = DataAcquisitionAgent().status(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))
        status = "VALID" if record.get("exists") else "INVALID"
        return TaskResult(status, "数据状态检查完成", report_path=record.get("path"), warnings=[] if record.get("exists") else ["本地无缓存"], artifacts=record)

