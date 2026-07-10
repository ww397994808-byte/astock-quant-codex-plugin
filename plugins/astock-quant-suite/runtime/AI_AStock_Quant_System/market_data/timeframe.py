from __future__ import annotations

SUPPORTED_TIMEFRAMES = {"1w", "1d", "1h", "30m", "10m", "5m"}


def normalize_timeframe(value: str | None) -> str:
    value = (value or "1d").lower()
    aliases = {"60m": "1h", "1hour": "1h", "1小时": "1h", "10min": "10m", "10分钟": "10m", "30min": "30m", "5min": "5m", "周线": "1w", "weekly": "1w", "week": "1w"}
    value = aliases.get(value, value)
    if value not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"不支持的周期：{value}。支持：{', '.join(sorted(SUPPORTED_TIMEFRAMES))}")
    return value


def minutes_of(timeframe: str) -> int:
    timeframe = normalize_timeframe(timeframe)
    return {"5m": 5, "10m": 10, "30m": 30, "1h": 60, "1d": 240, "1w": 1200}[timeframe]
