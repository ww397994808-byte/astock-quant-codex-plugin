from __future__ import annotations

from pathlib import Path

from data_acquisition.data_request import DataRequest
from data_acquisition.symbol_resolver import SymbolResolver
from market_data.parquet_store import ParquetStore


class CacheManager:
    def __init__(self, base_dir: str | Path = "data_lake") -> None:
        self.base_dir = Path(base_dir)

    def store_for(self, symbol: str) -> ParquetStore:
        asset_type = SymbolResolver().asset_type(symbol)
        return ParquetStore(self.base_dir / {"stock": "stocks", "etf": "etf", "index": "index"}.get(asset_type, "stocks"))

    def has(self, request: DataRequest) -> bool:
        return self.store_for(request.symbol).has_symbol(request.symbol, request.timeframe)

    def path(self, request: DataRequest) -> Path:
        return self.store_for(request.symbol).path_for(request.symbol, request.timeframe)

    def save(self, request: DataRequest, rows: list[dict]) -> Path:
        return self.store_for(request.symbol).save_bars(request.symbol, request.timeframe, rows)

    def load(self, request: DataRequest) -> list[dict]:
        return self.store_for(request.symbol).load_bars(request.symbol, request.timeframe)

