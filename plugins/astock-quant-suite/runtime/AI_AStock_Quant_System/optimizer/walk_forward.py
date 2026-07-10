from __future__ import annotations


class WalkForwardAnalyzer:
    def analyze(self, optimization_result: dict) -> dict:
        results = optimization_result.get("results", [])
        midpoint = max(1, int(len(results) * 0.7))
        in_sample = results[:midpoint]
        out_sample = results[midpoint:]
        return {
            "in_sample_count": len(in_sample),
            "out_sample_count": len(out_sample),
            "has_out_sample": bool(out_sample),
            "out_sample_degradation": False if out_sample else True,
        }

