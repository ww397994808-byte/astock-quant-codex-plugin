from __future__ import annotations

from datetime import datetime, time, timedelta

from market_data.timeframe import minutes_of, normalize_timeframe


MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


class TradingSession:
    def is_trading_time(self, dt: datetime) -> bool:
        t = dt.time()
        return (MORNING_START <= t < MORNING_END) or (AFTERNOON_START <= t < AFTERNOON_END)

    def check_midday_break(self, start: datetime, end: datetime) -> bool:
        return start.time() < MORNING_END and end.time() > AFTERNOON_START

    def generate_sessions(self, day, timeframe: str) -> list[tuple[datetime, datetime]]:
        timeframe = normalize_timeframe(timeframe)
        if timeframe == "1d":
            return [(datetime.combine(day, MORNING_START), datetime.combine(day, AFTERNOON_END))]
        step = timedelta(minutes=minutes_of(timeframe))
        sessions = []
        for start_t, end_t in [(MORNING_START, MORNING_END), (AFTERNOON_START, AFTERNOON_END)]:
            cursor = datetime.combine(day, start_t)
            end = datetime.combine(day, end_t)
            while cursor + step <= end:
                sessions.append((cursor, cursor + step))
                cursor += step
        return sessions

    def validate_bar(self, bar: dict) -> tuple[bool, str]:
        dt = bar.get("datetime")
        timeframe = normalize_timeframe(bar.get("timeframe", "1d"))
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        if timeframe == "1d":
            return True, ""
        end = dt + timedelta(minutes=minutes_of(timeframe))
        valid = (dt, end) in self.generate_sessions(dt.date(), timeframe)
        if not valid:
            return False, "bar 不在合法 A股交易时段或跨午休"
        return True, ""

