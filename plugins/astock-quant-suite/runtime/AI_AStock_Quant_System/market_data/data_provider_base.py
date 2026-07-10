from __future__ import annotations

from abc import ABC, abstractmethod


class DataProviderBase(ABC):
    @abstractmethod
    def load_bars(self, symbol: str, timeframe: str = "1d", adjust: str = "raw") -> list[dict]:
        ...

