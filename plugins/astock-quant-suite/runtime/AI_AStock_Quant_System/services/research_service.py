from __future__ import annotations

from core.result import TaskResult
from pathlib import Path
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest
from research.research_loop import ResearchLoop


class ResearchService:
    def run(self, direction: str, symbol: str, data: str, timeframe: str = "1d", adjust: str = "raw") -> TaskResult:
        data_source = "local"
        if not Path(data).exists():
            record = DataAcquisitionAgent().fetch(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))
            data = record["path"]
            data_source = record["source"]
        return ResearchLoop().run(direction, symbol, data, timeframe=timeframe, adjust=adjust, data_source=data_source)
