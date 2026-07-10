from __future__ import annotations

import csv
from pathlib import Path


class ResultRanker:
    def rank(self, results: list[dict]) -> list[dict]:
        valid = [r for r in results if r.get("audit_status") == "VALID"]
        ranked = []
        for row in valid:
            item = dict(row)
            item["score"] = round(self.score(item), 6)
            ranked.append(item)
        return sorted(ranked, key=lambda r: r["score"], reverse=True)

    def score(self, row: dict) -> float:
        total_return = float(row.get("total_return", 0) or 0)
        max_drawdown = abs(float(row.get("max_drawdown", 0) or 0))
        out_return = float(row.get("out_sample_return", 0) or 0)
        trade_count = int(float(row.get("trade_count", 0) or 0))
        calmar_score = max(-1.0, min(1.0, total_return / max(max_drawdown, 0.03)))
        out_sample_score = max(-1.0, min(1.0, out_return / 0.10))
        drawdown_score = max(0.0, 1.0 - max_drawdown / 0.25)
        stability_score = max(0.0, 1.0 - abs(total_return - out_return) / 0.20)
        trade_count_score = max(0.0, min(1.0, trade_count / 10))
        return 0.35 * calmar_score + 0.25 * out_sample_score + 0.20 * drawdown_score + 0.10 * stability_score + 0.10 * trade_count_score

    def write_csv(self, path: str | Path, ranked: list[dict]) -> None:
        path = Path(path)
        if not ranked:
            path.write_text("variant_id,score,audit_status\n", encoding="utf-8")
            return
        fieldnames = list(ranked[0])
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ranked)

