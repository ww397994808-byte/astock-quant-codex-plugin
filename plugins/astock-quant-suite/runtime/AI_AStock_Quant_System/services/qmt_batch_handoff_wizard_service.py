from __future__ import annotations

import json
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager
from services.qmt_batch_daily_review_service import QMTBatchDailyReviewService
from services.qmt_batch_handoff_service import QMTBatchHandoffService
from services.qmt_batch_lifecycle_service import QMTBatchLifecycleService
from services.qmt_batch_sandbox_service import QMTBatchSandboxService


class QMTBatchHandoffWizardService:
    """Run the batch QMT handoff workflow with explicit stop gates."""

    def run(
        self,
        package: str,
        orders: str,
        default_timeframe: str = "1d",
        qmt_run_id: str | None = None,
        trade_date: str | None = None,
        config: str = "config/qmt_config.yaml",
        notes: str = "",
    ) -> TaskResult:
        steps: list[dict] = []
        warnings: list[str] = []

        handoff = QMTBatchHandoffService().run(package=package, orders=orders, default_timeframe=default_timeframe)
        steps.append(self._step("qmt-batch-handoff", handoff))
        warnings.extend(handoff.warnings)
        if handoff.status != "VALID":
            return self._finish("BLOCKED_AT_BATCH_HANDOFF", steps, warnings)

        sandbox = QMTBatchSandboxService().run(batch_handoff=handoff.report_path or "", config=config)
        steps.append(self._step("qmt-batch-sandbox", sandbox))
        warnings.extend(sandbox.warnings)
        if sandbox.status != "VALID":
            return self._finish("BLOCKED_AT_BATCH_SANDBOX", steps, warnings)

        lifecycle = QMTBatchLifecycleService().run(batch_sandbox=sandbox.report_path or "", qmt_run_id=qmt_run_id)
        steps.append(self._step("qmt-batch-lifecycle", lifecycle))
        warnings.extend(lifecycle.warnings)
        if lifecycle.status != "VALID":
            return self._finish("BLOCKED_AT_BATCH_LIFECYCLE", steps, warnings)

        review = QMTBatchDailyReviewService().run(batch_lifecycle=lifecycle.report_path or "", trade_date=trade_date, notes=notes)
        steps.append(self._step("qmt-batch-daily-review", review))
        warnings.extend(review.warnings)
        final_status = "BATCH_WIZARD_REVIEW_READY" if review.status == "VALID" else "BLOCKED_AT_BATCH_DAILY_REVIEW"
        return self._finish(final_status, steps, warnings)

    def _step(self, name: str, result: TaskResult) -> dict:
        return {
            "name": name,
            "status": result.status,
            "run_id": result.run_id,
            "report_path": result.report_path,
            "warnings": list(result.warnings),
            "artifacts_status": result.artifacts.get("status"),
        }

    def _finish(self, wizard_status: str, steps: list[dict], warnings: list[str]) -> TaskResult:
        ctx = RunManager().create_run("qmt_batch_handoff_wizard")
        payload = {
            "status": wizard_status,
            "steps": steps,
            "warnings": warnings,
            "hard_boundary": "qmt-batch-handoff-wizard 只串联批量证据流程；它不连接真实 QMT，不发送真实委托。",
        }
        (ctx.output_dir / "QMT_BATCH_HANDOFF_WIZARD.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        self._write_report(ctx.output_dir, payload)
        result_status = "VALID" if wizard_status == "BATCH_WIZARD_REVIEW_READY" else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"批量 QMT 交接向导完成：{wizard_status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _write_report(self, output_dir: Path, payload: dict) -> None:
        lines = [
            "# QMT Batch Handoff Wizard",
            "",
            f"status: {payload['status']}",
            "",
            "## 步骤",
        ]
        for step in payload["steps"]:
            lines.extend([
                f"### {step['name']}",
                f"- status: {step['status']}",
                f"- artifacts_status: {step.get('artifacts_status')}",
                f"- run_id: {step.get('run_id') or 'MISSING'}",
                f"- report_path: {step.get('report_path') or 'MISSING'}",
            ])
            if step.get("warnings"):
                lines.append("- warnings:")
                lines.extend([f"  - {item}" for item in step["warnings"]])
            lines.append("")
        lines.extend(["## 汇总警告"])
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 当前批量向导未发现新的警告。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 批量向导通过也只是证据流程完成，不是交易许可。",
        ])
        (output_dir / "QMT_BATCH_HANDOFF_WIZARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
