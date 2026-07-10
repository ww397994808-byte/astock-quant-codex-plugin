from __future__ import annotations


class StabilityChecker:
    def analyze(self, optimization_result: dict) -> dict:
        valid = [r for r in optimization_result.get("results", []) if r.get("status") == "VALID"]
        ranked = sorted(valid, key=lambda r: r.get("total_return", -999), reverse=True)
        return {
            "stable_rank": [
                {"params": r.get("params"), "total_return": r.get("total_return"), "max_drawdown": r.get("max_drawdown")}
                for r in ranked[:5]
            ],
            "overfit_risk": "MEDIUM" if len(valid) < 3 else "LOW",
        }

