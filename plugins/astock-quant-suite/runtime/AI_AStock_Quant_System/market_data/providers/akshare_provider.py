from __future__ import annotations

from data_acquisition.data_request import DataRequest
from examples.sample_data_generator import generate_intraday_sample_data, generate_sample_data
from market_data.parquet_store import ParquetStore
from market_data.resampler import Resampler


class AkShareProvider:
    name = "akshare"

    def available(self) -> bool:
        return True

    def fetch(self, request: DataRequest) -> list[dict]:
        # Course edition: deterministic sample-backed acquisition. Keeps pipeline runnable offline.
        if request.timeframe == "1d":
            generate_sample_data(symbol=request.symbol, timeframe="1d")
            from core.data_loader import load_csv_data
            return load_csv_data("data/sample/601088.csv", request.symbol) if request.symbol == "601088.SH" else []
        if request.timeframe == "1w":
            generate_sample_data(symbol=request.symbol, timeframe="1d")
            from core.data_loader import load_csv_data
            daily = load_csv_data("data/sample/601088.csv", request.symbol) if request.symbol == "601088.SH" else []
            weekly = Resampler().resample(daily, "1w")
            ParquetStore().save_bars(request.symbol, "1w", weekly)
            return weekly
        generate_intraday_sample_data(symbol=request.symbol, timeframe=request.timeframe)
        return ParquetStore().load_bars(request.symbol, request.timeframe)
