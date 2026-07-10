from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketData:
    symbol: str
    rows: list[dict]
    daily: dict[str, dict]
    dates: list[str]
    date_idx: dict[str, int]
    atr_factors: dict[str, float]


def load_market(symbol: str, path: str, start_date: str, end_date: str) -> MarketData:
    rows = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for raw in csv.DictReader(f):
            raw_dt = raw.get("time") or raw.get("datetime") or raw.get("date")
            if not raw_dt:
                raise ValueError(f"{path} 缺少 time/datetime/date 列。")
            if len(raw_dt) <= 10:
                raw_dt = f"{raw_dt} 15:00:00"
            dt = datetime.fromisoformat(raw_dt).replace(tzinfo=None)
            date = dt.date().isoformat()
            if date < start_date or date > end_date:
                continue
            rows.append(
                {
                    "dt": dt,
                    "date": date,
                    "time": dt.time(),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                }
            )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["date"]].append(row)
    daily = {}
    for date, items in grouped.items():
        daily[date] = {
            "date": date,
            "open": items[0]["open"],
            "high": max(x["high"] for x in items),
            "low": min(x["low"] for x in items),
            "close": items[-1]["close"],
        }
    dates = sorted(daily)
    return MarketData(symbol, rows, daily, dates, {d: i for i, d in enumerate(dates)}, precompute_atr(daily, dates))


def precompute_atr(daily: dict[str, dict], dates: list[str]) -> dict[str, float]:
    out = {}
    trs = []
    prev_close = None
    for date in dates:
        row = daily[date]
        if prev_close is None:
            tr = row["high"] - row["low"]
        else:
            tr = max(row["high"] - row["low"], abs(row["high"] - prev_close), abs(row["low"] - prev_close))
        trs.append(tr)
        prev_close = row["close"]
    for i, date in enumerate(dates):
        recent = trs[max(0, i - 129) : i + 1]
        if len(recent) < 107:
            out[date] = 1.0
            continue
        atr7 = sum(recent[-7:]) / 7
        atr7_series = [sum(recent[j - 6 : j + 1]) / 7 for j in range(6, len(recent))]
        base = atr7_series[-101:-1]
        med = sorted(base)[len(base) // 2] if base else 0
        out[date] = round(min(1.5, max(0.8, atr7 / med)), 4) if med > 0 else 1.0
    return out


def ma_at(market: MarketData, row_index: int, period: int) -> float | None:
    row = market.rows[row_index]
    date_index = market.date_idx[row["date"]]
    previous_dates = market.dates[max(0, date_index - (period - 1)) : date_index]
    closes = [market.daily[d]["close"] for d in previous_dates] + [row["close"]]
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def completed_ma_before(market: MarketData, date: str, period: int, offset: int = 0) -> float | None:
    date_index = market.date_idx[date] - offset
    if date_index <= 0:
        return None
    dates = market.dates[max(0, date_index - period) : date_index]
    if len(dates) < period:
        return None
    return sum(market.daily[d]["close"] for d in dates) / period


def month_last_dates(dates: list[str]) -> list[str]:
    by_month = {}
    for date in dates:
        by_month[date[:7]] = date
    return [by_month[m] for m in sorted(by_month)]
