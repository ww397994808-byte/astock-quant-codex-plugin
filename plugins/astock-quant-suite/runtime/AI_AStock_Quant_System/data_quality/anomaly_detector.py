from __future__ import annotations


class AnomalyDetector:
    def suspicious_price_jumps(self, rows: list[dict], threshold: float = 0.30) -> list[dict]:
        jumps = []
        consecutive = 0
        for prev, curr in zip(rows, rows[1:]):
            prev_close = float(prev["close"])
            if prev_close <= 0:
                continue
            pct = float(curr["close"]) / prev_close - 1
            if abs(pct) > threshold:
                consecutive += 1
                jumps.append({
                    "date": curr["date"].strftime("%Y-%m-%d"),
                    "symbol": curr.get("symbol", ""),
                    "prev_close": prev_close,
                    "close": curr["close"],
                    "pct_change": round(pct, 6),
                    "consecutive_jump_count": consecutive,
                })
            else:
                consecutive = 0
        return jumps

