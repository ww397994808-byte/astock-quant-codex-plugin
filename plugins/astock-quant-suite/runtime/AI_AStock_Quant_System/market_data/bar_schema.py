from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time


@dataclass
class BarData:
    symbol: str
    datetime: datetime
    date: date
    time: time
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    is_st: bool = False
    board: str = "main"
    paused: bool = False
    source: str = "csv"
    adjust_type: str = "raw"
    adjust_factor: float = 1.0
    corporate_action_flag: bool = False

    def to_row(self) -> dict:
        row = asdict(self)
        row["datetime"] = self.datetime.strftime("%Y-%m-%d %H:%M:%S")
        row["date"] = self.date.strftime("%Y-%m-%d")
        row["time"] = self.time.strftime("%H:%M:%S")
        row["name"] = row.get("name", "")
        return row

