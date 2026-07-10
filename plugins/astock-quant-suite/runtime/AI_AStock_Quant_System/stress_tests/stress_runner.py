from __future__ import annotations

from pathlib import Path

from stress_tests.stress_data_generator import StressDataGenerator
from stress_tests.stress_report import write_stress_report


class StressRunner:
    def run(self, rows: list[dict], output_dir: str | Path) -> list[dict]:
        scenarios = StressDataGenerator().generate(rows)
        results = []
        for name, scenario_rows in scenarios.items():
            notes = []
            if any(r.get("paused") for r in scenario_rows):
                notes.append("包含停牌场景")
            if any(int(r.get("volume", 0)) == 0 for r in scenario_rows):
                notes.append("包含零成交量")
            results.append({"scenario": name, "status": "GENERATED", "notes": "; ".join(notes)})
        write_stress_report(Path(output_dir) / "stress_report.md", results)
        return results

