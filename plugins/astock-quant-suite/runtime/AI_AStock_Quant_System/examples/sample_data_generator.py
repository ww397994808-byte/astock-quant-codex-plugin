from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from market_data.parquet_store import ParquetStore
from market_data.resampler import Resampler
from market_data.trading_session import TradingSession
from market_data.corporate_actions import write_sample_corporate_actions


def _write_rows(path: Path, rows: list[dict]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_sample_data(path: str | Path = "data/sample/601088.csv", symbol: str = "601088.SH", timeframe: str = "1d") -> Path:
    write_sample_corporate_actions(Path("data/sample") / f"corporate_actions_{symbol.split('.')[0]}.csv", symbol)
    if timeframe == "1w":
        daily_path = generate_sample_data(path=path, symbol=symbol, timeframe="1d")
        from core.data_loader import load_csv_data

        rows = load_csv_data(daily_path, symbol=symbol)
        weekly = Resampler().resample(rows, "1w")
        return ParquetStore().save_bars(symbol, "1w", weekly)
    if timeframe != "1d":
        return generate_intraday_sample_data(symbol=symbol, timeframe=timeframe)
    path = Path(path)
    start = datetime(2024, 1, 2)
    rows = []
    price = 30.0
    for i in range(140):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        drift = ((i % 23) - 11) * 0.015
        price = max(20.0, price + drift)
        open_price = round(price * (1 + ((i % 5) - 2) * 0.001), 2)
        close = round(price, 2)
        high = round(max(open_price, close) * 1.01, 2)
        low = round(min(open_price, close) * 0.99, 2)
        rows.append({
            "date": day.strftime("%Y-%m-%d"),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000000 + i * 1000,
            "amount": round(close * (1000000 + i * 1000), 2),
            "symbol": symbol,
            "name": "中国神华",
            "is_st": "false",
            "board": "main",
            "paused": "false",
        })
    return _write_rows(path, rows)


def generate_intraday_sample_data(symbol: str = "601088.SH", timeframe: str = "10m") -> Path:
    rows = []
    start = datetime(2024, 1, 2)
    price = 30.0
    session = TradingSession()
    for day_idx in range(30):
        day = start + timedelta(days=day_idx)
        if day.weekday() >= 5:
            continue
        for start_dt, end_dt in session.generate_sessions(day.date(), timeframe):
            drift = ((len(rows) % 17) - 8) * 0.01
            price = max(20.0, price + drift)
            open_price = round(price * 0.999, 2)
            close = round(price, 2)
            rows.append({
                "datetime": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "date": start_dt.strftime("%Y-%m-%d"),
                "time": start_dt.strftime("%H:%M:%S"),
                "timeframe": timeframe,
                "open": open_price,
                "high": round(max(open_price, close) * 1.002, 2),
                "low": round(min(open_price, close) * 0.998, 2),
                "close": close,
                "volume": 10000 + len(rows),
                "amount": round(close * (10000 + len(rows)), 2),
                "symbol": symbol,
                "name": "中国神华",
                "is_st": "false",
                "board": "main",
                "paused": "false",
                "source": "sample",
                "adjust_type": "raw",
                "adjust_factor": 1.0,
                "corporate_action_flag": "false",
            })
    return ParquetStore().save_bars(symbol, timeframe, rows)


if __name__ == "__main__":
    print(generate_sample_data())
