from __future__ import annotations

from data_quality.data_quality_checker import DataQualityChecker


class MarketDataValidator:
    def validate(self, rows: list[dict], output_dir=None) -> dict:
        return DataQualityChecker().check(rows, output_dir)

