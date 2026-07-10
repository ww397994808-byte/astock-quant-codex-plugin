from __future__ import annotations

import csv
import json
from pathlib import Path


class BacktestResultAnalyzer:
    def analyze(self, run_dir: str | Path, in_sample_return: float = 0.0, out_sample_return: float = 0.0) -> dict:
        run_dir = Path(run_dir)
        performance = self._load_json(run_dir / "performance.json")
        metrics = self._extract_metrics(run_dir / "metrics_report.md")
        trades = self._read_csv(run_dir / "trades.csv")
        audit_status = self._status_from_text(run_dir / "audit_report.md")
        readiness = self._readiness(run_dir / "readiness_report.md")
        trade_count = int(performance.get("trade_count", 0) or 0)
        total_return = float(performance.get("total_return", 0) or 0)
        max_drawdown = float(performance.get("max_drawdown", 0) or 0)
        calmar = metrics.get("risk", {}).get("Calmar", 0) if isinstance(metrics, dict) else 0
        fee_ratio = float(performance.get("total_fee", 0) or 0) / max(abs(total_return) * float(performance.get("initial_cash", 1) or 1), 1)
        concentration = self._profit_concentration(trades)
        issues = []
        if abs(max_drawdown) > 0.15:
            issues.append("drawdown_too_large")
        if trade_count < 3:
            issues.append("too_few_trades")
        if trade_count > 80:
            issues.append("too_many_trades")
        if total_return < 0.02:
            issues.append("low_return")
        if in_sample_return > 0 and out_sample_return < in_sample_return * 0.3:
            issues.append("out_sample_degradation")
        if concentration > 0.6:
            issues.append("concentrated_profit")
        analysis = {
            "total_return": total_return,
            "annual_return": performance.get("annual_return", 0),
            "max_drawdown": max_drawdown,
            "calmar": calmar,
            "sortino": metrics.get("risk", {}).get("Sortino", 0) if isinstance(metrics, dict) else 0,
            "win_rate": metrics.get("trade", {}).get("win_rate", 0) if isinstance(metrics, dict) else 0,
            "profit_loss_ratio": performance.get("profit_loss_ratio", 0),
            "trade_count": trade_count,
            "max_consecutive_loss": self._max_consecutive_loss(trades),
            "recovery_time": metrics.get("risk", {}).get("Recovery Time", 0) if isinstance(metrics, dict) else 0,
            "fee_to_return_ratio": fee_ratio,
            "in_sample_return": in_sample_return,
            "out_sample_return": out_sample_return,
            "stability": self._stability_score(metrics),
            "stress_result": self._status_from_text(run_dir / "stress_report.md", valid_word="GENERATED"),
            "data_quality": self._status_from_text(run_dir / "data_quality_report.md"),
            "audit_status": audit_status,
            "readiness": readiness,
            "profit_concentration": concentration,
            "parameter_at_boundary": False,
            "overfit_signals": ["out_sample_degradation"] if "out_sample_degradation" in issues else [],
            "issues": issues,
        }
        self.write_analysis(run_dir / "analysis.md", analysis)
        return analysis

    def write_analysis(self, path: str | Path, analysis: dict) -> None:
        lines = ["# Backtest Analysis", ""]
        lines.extend([f"- {k}: {v}" for k, v in analysis.items() if k != "issues"])
        issue_lines = [f"- {i}" for i in analysis["issues"]] or ["- no_major_issue"]
        lines.extend(["", "## Issues", *issue_lines])
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _extract_metrics(self, path: Path) -> dict:
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
        if "```json" in text:
            payload = text.split("```json", 1)[1].split("```", 1)[0]
            return json.loads(payload)
        return {}

    def _read_csv(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _status_from_text(self, path: Path, valid_word: str = "VALID") -> str:
        if not path.exists():
            return "UNKNOWN"
        text = path.read_text(encoding="utf-8")
        if "INVALID" in text[:300]:
            return "INVALID"
        if valid_word in text:
            return "VALID"
        return "UNKNOWN"

    def _readiness(self, path: Path) -> str:
        if not path.exists():
            return "UNKNOWN"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("readiness:"):
                return line.split(":", 1)[1].strip()
        return "UNKNOWN"

    def _profit_concentration(self, trades: list[dict]) -> float:
        amounts = [abs(float(t.get("amount", 0) or 0)) for t in trades]
        return max(amounts) / sum(amounts) if amounts and sum(amounts) else 0.0

    def _stability_score(self, metrics: dict) -> float:
        stability = metrics.get("stability", {}) if isinstance(metrics, dict) else {}
        if not isinstance(stability, dict):
            return 0.5
        yearly = stability.get("yearly_return_distribution", {})
        if isinstance(yearly, dict) and yearly:
            positives = sum(1 for value in yearly.values() if float(value or 0) >= 0)
            return positives / len(yearly)
        return 0.5

    def _max_consecutive_loss(self, trades: list[dict]) -> int:
        max_loss = 0
        current = 0
        for trade in trades:
            if trade.get("action") == "SELL" and float(trade.get("amount", 0) or 0) <= float(trade.get("total_fee", 0) or 0):
                current += 1
                max_loss = max(max_loss, current)
            elif trade.get("action") == "SELL":
                current = 0
        return max_loss
