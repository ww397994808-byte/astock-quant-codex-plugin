from __future__ import annotations

import csv
from pathlib import Path


class CandidateSelector:
    def score(self, item: dict) -> float:
        if item.get("audit_status") == "INVALID":
            return -999
        readiness_score = {"LIVE_CANDIDATE": 1.0, "PAPER_READY": 0.8, "RESEARCH_ONLY": 0.4, "INVALID": -1}.get(item.get("readiness", "RESEARCH_ONLY"), 0.4)
        if item.get("adjust") in {"qfq", "hfq"}:
            readiness_score = min(readiness_score, 0.4)
        batch = item.get("batch_summary") or {}
        batch_stability = (
            float(batch.get("cross_timeframe_stability", 0.5))
            + float(batch.get("cross_symbol_stability", 0.5))
            + float(batch.get("regime_slice_stability", batch.get("regime_stability", 0.5)))
        ) / 3
        return (
            0.15 * readiness_score
            + 0.12 * float(item.get("out_sample_score", 0))
            + 0.12 * (1 - min(abs(float(item.get("max_drawdown", 0))), 0.5) / 0.5)
            + 0.14 * float(item.get("calmar", 0))
            + 0.10 * float(item.get("stability", 0.5))
            + 0.08 * min(float(item.get("trade_count", 0)) / 20, 1)
            + 0.08 * float(item.get("stress_result", 0.5))
            + 0.08 * float(item.get("data_quality_score", 1))
            + 0.05 * float(item.get("strategy_simplicity", 0.8))
            + 0.03 * float(item.get("regime_robustness", 0.5))
            + 0.05 * batch_stability
        )

    def select(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        accepted = []
        rejected = []
        for item in items:
            scored = dict(item)
            scored["candidate_score"] = round(self.score(scored), 6)
            if item.get("audit_status") == "INVALID" or item.get("user_gate_pass") is False:
                rejected.append(scored)
            else:
                accepted.append(scored)
        return sorted(accepted, key=lambda x: x["candidate_score"], reverse=True), rejected

    def write_csv(self, path: str | Path, rows: list[dict]) -> None:
        if not rows:
            Path(path).write_text("variant_id,candidate_score,audit_status\n", encoding="utf-8")
            return
        with Path(path).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
