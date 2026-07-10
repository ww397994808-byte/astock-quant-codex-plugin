from __future__ import annotations

import csv
from pathlib import Path

from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import CorporateAction


class AdjustmentFactorStore:
    def __init__(self, base_dir: str | Path = "data/adjustment_factors") -> None:
        self.base_dir = Path(base_dir)

    def save_factors(self, symbol: str, actions: list[CorporateAction]) -> Path:
        path = self.base_dir / f"{symbol}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["symbol", "ex_date", "known_date", "factor", "action_type", "source"]
        engine = AdjustmentEngine()
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for action in actions:
                writer.writerow({
                    "symbol": symbol,
                    "ex_date": action.ex_date.strftime("%Y-%m-%d"),
                    "known_date": action.known_date.strftime("%Y-%m-%d"),
                    "factor": engine.calculate_factor(action.ex_date, actions, point_in_time=True),
                    "action_type": action.action_type,
                    "source": action.source,
                })
        return path

    def load_factors(self, symbol: str) -> list[dict]:
        path = self.base_dir / f"{symbol}.parquet"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

