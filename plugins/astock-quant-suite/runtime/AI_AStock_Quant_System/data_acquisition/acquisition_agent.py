from __future__ import annotations

from pathlib import Path

from data_acquisition.acquisition_report import write_acquisition_report
from data_acquisition.cache_manager import CacheManager
from data_acquisition.data_request import DataRequest
from data_acquisition.provider_router import ProviderRouter
from data_quality.data_quality_checker import DataQualityChecker


class DataAcquisitionAgent:
    def fetch(self, request: DataRequest) -> dict:
        cache = CacheManager()
        if cache.has(request):
            rows = cache.load(request)
            source = "local"
            downloaded = False
        else:
            source, rows = ProviderRouter().fetch(request)
            cache.save(request, rows)
            downloaded = True
        quality = DataQualityChecker().check(rows)
        record = {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "adjust": request.adjust,
            "source": source,
            "downloaded": downloaded,
            "path": str(cache.path(request)),
            "latest_datetime": rows[-1]["datetime"].strftime("%Y-%m-%d %H:%M:%S") if rows else "",
            "data_quality_status": quality["status"],
            "data_quality_score": 100 if quality["status"] == "VALID" else 60,
        }
        write_acquisition_report("DATA_ACQUISITION_REPORT.md", record)
        return record

    def status(self, request: DataRequest) -> dict:
        cache = CacheManager()
        if not cache.has(request):
            return {"symbol": request.symbol, "timeframe": request.timeframe, "exists": False}
        rows = cache.load(request)
        quality = DataQualityChecker().check(rows)
        return {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "adjust": request.adjust,
            "exists": True,
            "source": "local",
            "path": str(cache.path(request)),
            "latest_datetime": rows[-1]["datetime"].strftime("%Y-%m-%d %H:%M:%S") if rows else "",
            "data_quality_status": quality["status"],
            "data_quality_score": 100 if quality["status"] == "VALID" else 60,
        }

