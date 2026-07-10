from __future__ import annotations

from pathlib import Path

from core.data_loader import load_csv_data
from market_data.data_provider_base import DataProviderBase


class CSVIntradayProvider(DataProviderBase):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_bars(self, symbol: str, timeframe: str = "1d", adjust: str = "raw") -> list[dict]:
        rows = load_csv_data(self.path, symbol=symbol)
        for row in rows:
            row["timeframe"] = timeframe
            row["adjust_type"] = adjust
        return rows

