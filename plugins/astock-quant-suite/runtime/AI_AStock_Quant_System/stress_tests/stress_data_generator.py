from __future__ import annotations

from copy import deepcopy
from datetime import timedelta


class StressDataGenerator:
    SCENARIOS = ["limit_up", "limit_down", "paused_30d", "extreme_volatility", "zero_volume", "gap", "bull", "bear", "morning_gap_limit_up", "afternoon_crash", "full_day_pause", "missing_afternoon", "high_freq_volatility", "ten_min_limit_down_near"]

    def generate(self, rows: list[dict]) -> dict[str, list[dict]]:
        return {name: getattr(self, f"_{name}")(deepcopy(rows)) for name in self.SCENARIOS}

    def _limit_up(self, rows):
        for i in range(1, min(6, len(rows))):
            rows[i]["open"] = rows[i]["high"] = rows[i]["low"] = rows[i]["close"] = round(rows[i - 1]["close"] * 1.10, 2)
        return rows

    def _limit_down(self, rows):
        for i in range(1, min(6, len(rows))):
            rows[i]["open"] = rows[i]["high"] = rows[i]["low"] = rows[i]["close"] = round(rows[i - 1]["close"] * 0.90, 2)
        return rows

    def _paused_30d(self, rows):
        for row in rows[5:35]:
            row["paused"] = True
            row["volume"] = 0
        return rows

    def _extreme_volatility(self, rows):
        for i, row in enumerate(rows):
            factor = 1.12 if i % 2 == 0 else 0.88
            row["close"] = round(row["close"] * factor, 2)
            row["high"] = max(row["high"], row["close"])
            row["low"] = min(row["low"], row["close"])
        return rows

    def _zero_volume(self, rows):
        for row in rows[5:15]:
            row["volume"] = 0
        return rows

    def _gap(self, rows):
        if len(rows) > 10:
            rows[10]["open"] = rows[10]["high"] = rows[10]["close"] = round(rows[9]["close"] * 1.45, 2)
            rows[10]["low"] = round(rows[9]["close"] * 1.40, 2)
        return rows

    def _bull(self, rows):
        for i, row in enumerate(rows):
            row["close"] = round(rows[0]["close"] * (1 + i * 0.01), 2)
            row["open"] = row["close"]
            row["high"] = round(row["close"] * 1.01, 2)
            row["low"] = round(row["close"] * 0.99, 2)
        return rows

    def _bear(self, rows):
        for i, row in enumerate(rows):
            row["close"] = round(max(1, rows[0]["close"] * (1 - i * 0.008)), 2)
            row["open"] = row["close"]
            row["high"] = round(row["close"] * 1.01, 2)
            row["low"] = round(row["close"] * 0.99, 2)
        return rows

    def _morning_gap_limit_up(self, rows):
        if rows:
            rows[0]["open"] = rows[0]["high"] = rows[0]["low"] = rows[0]["close"] = round(rows[0]["close"] * 1.10, 2)
        return rows

    def _afternoon_crash(self, rows):
        for row in rows:
            dt = row.get("datetime")
            if hasattr(dt, "hour") and dt.hour >= 13:
                row["close"] = round(row["close"] * 0.9, 2)
                row["low"] = min(row["low"], row["close"])
        return rows

    def _full_day_pause(self, rows):
        first_day = rows[0]["datetime"].date() if rows and hasattr(rows[0].get("datetime"), "date") else None
        for row in rows:
            if first_day and row["datetime"].date() == first_day:
                row["paused"] = True
                row["volume"] = 0
        return rows

    def _missing_afternoon(self, rows):
        return [row for row in rows if not (hasattr(row.get("datetime"), "hour") and row["datetime"].hour >= 13)]

    def _high_freq_volatility(self, rows):
        for i, row in enumerate(rows):
            row["close"] = round(row["close"] * (1.03 if i % 2 else 0.97), 2)
            row["high"] = max(row["high"], row["close"])
            row["low"] = min(row["low"], row["close"])
        return rows

    def _ten_min_limit_down_near(self, rows):
        for i in range(1, min(12, len(rows))):
            rows[i]["close"] = round(rows[i - 1]["close"] * 0.901, 2)
            rows[i]["open"] = rows[i]["close"]
            rows[i]["low"] = rows[i]["close"]
            rows[i]["high"] = round(rows[i]["close"] * 1.001, 2)
        return rows
