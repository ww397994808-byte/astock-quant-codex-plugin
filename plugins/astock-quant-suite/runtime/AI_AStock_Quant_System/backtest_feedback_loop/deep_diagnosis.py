from __future__ import annotations

from pathlib import Path

from backtest_feedback_loop.failure_classifier import FailureClassifier
from backtest_feedback_loop.regime_analyzer import RegimeAnalyzer
from backtest_feedback_loop.research_expander import ResearchExpander


class DeepDiagnosis:
    def run(self, analyses: list[dict], latest_run_dir: str | Path, output_path: str | Path) -> dict:
        failures = FailureClassifier().classify(analyses)
        expanded_actions = ResearchExpander().expand(failures)
        regime = RegimeAnalyzer().analyze(Path(latest_run_dir) / "equity_curve.csv")
        result = {"failures": failures, "expanded_actions": expanded_actions, "regime": regime}
        lines = ["# Deep Diagnosis", "", "## Failures", *[f"- {f}" for f in failures], "", "## Expanded Actions", *[f"- {a}" for a in expanded_actions], "", "## Regime", f"- {regime}"]
        Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return result

