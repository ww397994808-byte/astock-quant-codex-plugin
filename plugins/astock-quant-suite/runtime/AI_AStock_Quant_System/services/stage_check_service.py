from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.result import TaskResult
from core.run_manager import RunManager
from core.stage_gate import StageGateEvaluator


class StageCheckService:
    """Summarize the current research-to-live gate status from run artifacts."""

    def run(self, run_id: str = "latest", plan_run_id: str | None = None, qmt_run_id: str | None = None) -> TaskResult:
        manager = RunManager()
        run_dir = manager.resolve_run_dir(run_id)
        plan_dir = manager.resolve_run_dir(plan_run_id) if plan_run_id else run_dir
        qmt_dir = manager.resolve_run_dir(qmt_run_id) if qmt_run_id else self._latest_prefixed_run("qmt_readonly")

        backtest_plan = self._load_yaml(plan_dir / "backtest_plan.yaml")
        audit_status = self._read_audit_status(run_dir)
        readiness = self._read_readiness(run_dir)
        paper_observed = self._read_paper_observed(run_dir)
        qmt_readonly_ok = self._read_qmt_readonly_ok(qmt_dir)

        gate = StageGateEvaluator().evaluate(
            backtest_plan=backtest_plan,
            audit_status=audit_status,
            readiness=readiness,
            paper_observed=paper_observed,
            qmt_readonly_ok=qmt_readonly_ok,
            pretrade_ok=False,
        )
        report_path = run_dir / "stage_gate_report.md"
        self._write_report(
            report_path,
            run_dir=run_dir,
            plan_dir=plan_dir if (plan_dir / "backtest_plan.yaml").exists() else None,
            qmt_dir=qmt_dir,
            stage=gate.stage.value,
            reasons=gate.reasons,
            audit_status=audit_status,
            readiness=readiness,
            paper_observed=paper_observed,
            qmt_readonly_ok=qmt_readonly_ok,
        )
        return TaskResult(
            status="VALID" if gate.stage.value != "INVALID" else "INVALID",
            message=f"阶段检查完成：{gate.stage.value}",
            run_id=run_dir.name,
            report_path=str(report_path),
            audit_status=audit_status,
            warnings=gate.reasons,
            artifacts={
                "stage_gate": gate.to_dict(),
                "run_id": run_dir.name,
                "plan_run_id": plan_dir.name if (plan_dir / "backtest_plan.yaml").exists() else "",
                "qmt_run_id": qmt_dir.name if qmt_dir else "",
            },
        )

    def _latest_prefixed_run(self, prefix: str) -> Path | None:
        root = Path("reports")
        candidates = sorted([p for p in root.glob(f"{prefix}_*") if p.is_dir()], key=lambda p: p.name)
        return candidates[-1] if candidates else None

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _read_audit_status(self, run_dir: Path) -> str:
        path = run_dir / "audit_report.md"
        if not path.exists():
            return "INVALID"
        head = path.read_text(encoding="utf-8")[:300]
        return "INVALID" if "状态：INVALID" in head or "status: INVALID" in head else "VALID"

    def _read_readiness(self, run_dir: Path) -> str | None:
        path = run_dir / "readiness_report.md"
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("readiness:"):
                return line.split(":", 1)[1].strip()
        return None

    def _read_paper_observed(self, run_dir: Path) -> bool:
        path = run_dir / "paper_observation.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("status") == "VALID"

    def _read_qmt_readonly_ok(self, qmt_dir: Path | None) -> bool:
        if not qmt_dir:
            return False
        path = qmt_dir / "qmt_account_snapshot.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("ok"))

    def _write_report(
        self,
        path: Path,
        *,
        run_dir: Path,
        plan_dir: Path | None,
        qmt_dir: Path | None,
        stage: str,
        reasons: list[str],
        audit_status: str,
        readiness: str | None,
        paper_observed: bool,
        qmt_readonly_ok: bool,
    ) -> None:
        lines = [
            "# Stage Gate Report",
            "",
            f"stage: {stage}",
            f"run_id: {run_dir.name}",
            f"plan_run_id: {plan_dir.name if plan_dir else 'MISSING'}",
            f"qmt_run_id: {qmt_dir.name if qmt_dir else 'MISSING'}",
            "",
            "## Evidence",
            f"- audit_status: {audit_status}",
            f"- readiness: {readiness or 'MISSING'}",
            f"- paper_observed: {paper_observed}",
            f"- qmt_readonly_ok: {qmt_readonly_ok}",
            "",
            "## Blockers",
        ]
        lines.extend([f"- {item}" for item in reasons] or ["- 当前阶段未发现新的阻断项。"])
        lines.extend(
            [
                "",
                "说明：stage-check 只判断研究链路证据是否齐全；任何真实下单仍必须经过 pretrade-check 和人工确认。",
            ]
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
