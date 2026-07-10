from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataRequest:
    symbol: str
    timeframe: str = "1d"
    adjust: str = "raw"
    start_date: str | None = None
    end_date: str | None = None
    preferred_source: str | None = None

