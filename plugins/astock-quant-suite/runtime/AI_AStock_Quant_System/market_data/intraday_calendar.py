from __future__ import annotations

from datetime import date

from market_data.trading_session import TradingSession


class IntradayCalendar:
    def expected_bar_count(self, timeframe: str) -> int:
        return {"1h": 4, "30m": 8, "10m": 24, "5m": 48, "1d": 1}[timeframe]

    def expected_sessions(self, day: date, timeframe: str):
        return TradingSession().generate_sessions(day, timeframe)

