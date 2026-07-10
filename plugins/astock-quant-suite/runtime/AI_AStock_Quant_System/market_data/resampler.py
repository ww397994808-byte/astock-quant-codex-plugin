from __future__ import annotations

from datetime import datetime

from market_data.trading_session import TradingSession
from market_data.timeframe import normalize_timeframe


class Resampler:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def resample(self, rows: list[dict], target_timeframe: str) -> list[dict]:
        target_timeframe = normalize_timeframe(target_timeframe)
        self.warnings = []
        grouped: dict[tuple, list[dict]] = {}
        session = TradingSession()
        for row in sorted(rows, key=lambda r: r["datetime"]):
            dt = row["datetime"]
            if isinstance(dt, str):
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            bucket = self._bucket_start(dt, target_timeframe)
            if bucket is None:
                continue
            grouped.setdefault((row["symbol"], bucket), []).append(row)
        out = []
        for (_, bucket), items in sorted(grouped.items(), key=lambda kv: kv[0][1]):
            items = sorted(items, key=lambda r: r["datetime"])
            row = dict(items[0])
            if target_timeframe == "1w":
                row["datetime"] = items[-1]["datetime"]
                row["date"] = items[-1]["datetime"]
                trading_days = {i["datetime"].date() for i in items}
                if len(trading_days) < 5:
                    self.warnings.append(f"{bucket.date()} 所在自然周交易日不足5天：{len(trading_days)}")
            else:
                row["datetime"] = bucket
                row["date"] = bucket
            row["timeframe"] = target_timeframe
            row["open"] = float(items[0]["open"])
            row["high"] = max(float(i["high"]) for i in items)
            row["low"] = min(float(i["low"]) for i in items)
            row["close"] = float(items[-1]["close"])
            row["volume"] = sum(int(i["volume"]) for i in items)
            row["amount"] = sum(float(i["amount"]) for i in items)
            out.append(row)
        return out

    def _bucket_start(self, dt: datetime, target: str):
        if target == "1w":
            monday = dt.date()
            monday = monday.fromordinal(monday.toordinal() - monday.weekday())
            return datetime.combine(monday, datetime.min.time())
        if target == "1d":
            return datetime.combine(dt.date(), datetime.min.time())
        sessions = TradingSession().generate_sessions(dt.date(), target)
        for start, end in sessions:
            if start <= dt < end:
                return start
        return None
