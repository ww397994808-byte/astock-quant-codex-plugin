from __future__ import annotations

import csv
from pathlib import Path

from market_data.timeframe import normalize_timeframe


class ParquetStore:
    def __init__(self, base_dir: str | Path = "data/parquet") -> None:
        self.base_dir = Path(base_dir)

    def path_for(self, symbol: str, timeframe: str) -> Path:
        timeframe = normalize_timeframe(timeframe)
        return self.base_dir / timeframe / f"{symbol}.parquet"

    def save_bars(self, symbol: str, timeframe: str, rows: list[dict]) -> Path:
        path = self.path_for(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            path.write_text("", encoding="utf-8")
            return path
        fieldnames = list(rows[0].keys())
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                item = dict(row)
                if hasattr(item.get("datetime"), "strftime"):
                    item["datetime"] = item["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(item.get("date"), "strftime"):
                    item["date"] = item["date"].strftime("%Y-%m-%d")
                writer.writerow(item)
        return path

    def load_bars(self, symbol: str, timeframe: str) -> list[dict]:
        from core.data_loader import load_csv_data

        return load_csv_data(self.path_for(symbol, timeframe), symbol=symbol)

    def list_symbols(self, timeframe: str) -> list[str]:
        path = self.base_dir / normalize_timeframe(timeframe)
        return sorted(p.stem for p in path.glob("*.parquet")) if path.exists() else []

    def has_symbol(self, symbol: str, timeframe: str) -> bool:
        return self.path_for(symbol, timeframe).exists()

