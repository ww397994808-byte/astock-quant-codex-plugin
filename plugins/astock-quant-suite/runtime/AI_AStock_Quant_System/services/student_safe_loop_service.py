from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_next_step_runner_service import StudentNextStepRunnerService
from services.student_session_report_service import StudentSessionReportService


class StudentSafeLoopService:
    """Preview or execute a bounded sequence of safe learner next steps."""

    def run(
        self,
        workflow: str | None = None,
        promotion: str | None = None,
        qmt_dashboard: str | None = None,
        max_steps: int = 3,
        execute: bool = False,
        timeout_seconds: int = 180,
        session_id: str | None = None,
    ) -> TaskResult:
        steps: list[dict[str, Any]] = []
        seen_commands: set[str] = set()
        stop_reason = ""
        max_steps = max(1, int(max_steps))
        for index in range(1, max_steps + 1):
            preview = StudentNextStepRunnerService().run(
                workflow=workflow,
                promotion=promotion,
                qmt_dashboard=qmt_dashboard,
                dry_run=True,
                timeout_seconds=timeout_seconds,
                session_id=session_id,
            )
            step = self._step_from_result(index, "preview", preview)
            steps.append(step)
            command = str(step.get("command") or "")
            if not execute:
                stop_reason = "默认预演模式，只展示第一步，不执行。"
                break
            if preview.status != "VALID" or not preview.artifacts.get("allowed"):
                stop_reason = str(preview.artifacts.get("reason") or "预演未通过。")
                break
            if command in seen_commands:
                step["status"] = "DUPLICATE_NEXT_COMMAND"
                step["reason"] = "下一步命令与本轮已执行命令重复，停止循环，避免重复跑同一研究分支。"
                stop_reason = step["reason"]
                break
            seen_commands.add(command)

            executed = StudentNextStepRunnerService().run(
                workflow=workflow,
                promotion=promotion,
                qmt_dashboard=qmt_dashboard,
                dry_run=False,
                timeout_seconds=timeout_seconds,
                session_id=session_id,
            )
            executed_step = self._step_from_result(index, "execute", executed)
            steps.append(executed_step)
            if executed.status != "VALID" or executed.artifacts.get("status") != "EXECUTED_VALID":
                stop_reason = str(executed.artifacts.get("reason") or "执行未通过。")
                break
            if not executed.artifacts.get("child_report_path"):
                stop_reason = "执行完成但没有发现 child_report_path，停止等待人工查看产物。"
                break

        if not stop_reason:
            stop_reason = "达到 max_steps 上限。"

        session = StudentSessionReportService().run(limit=20, session_id=session_id)
        payload = {
            "status": self._status_for(steps, execute),
            "session_id": session_id or "",
            "execute": execute,
            "max_steps": max_steps,
            "stop_reason": stop_reason,
            "steps": steps,
            "session_report_run_id": session.run_id,
            "session_report_path": session.report_path,
            "hard_boundary": "student-safe-loop 默认只预演；即使 --execute，也只能通过 student-run-next 的安全白名单推进。",
        }
        ctx = RunManager().create_run("student_safe_loop")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"DRY_RUN_READY", "LOOP_EXECUTED", "LOOP_STOPPED"} else "INVALID"
        warnings = [] if result_status == "VALID" else [steps[-1]["reason"] if steps else "没有可执行步骤。"]
        return TaskResult(
            status=result_status,
            message=f"学员安全循环完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _step_from_result(self, index: int, phase: str, result: TaskResult) -> dict[str, Any]:
        return {
                "index": index,
                "phase": phase,
                "status": result.artifacts.get("status"),
                "task_status": result.status,
                "run_id": result.run_id,
                "report_path": result.report_path,
                "allowed": result.artifacts.get("allowed"),
                "dry_run": result.artifacts.get("dry_run"),
                "command": result.artifacts.get("command"),
                "reason": result.artifacts.get("reason"),
                "child_report_path": result.artifacts.get("child_report_path"),
            }

    def _status_for(self, steps: list[dict[str, Any]], execute: bool) -> str:
        if not steps:
            return "NO_STEPS"
        if not execute:
            return "DRY_RUN_READY" if steps[-1].get("allowed") else "BLOCKED"
        if any(step.get("task_status") != "VALID" for step in steps):
            return "LOOP_BLOCKED"
        if any(step.get("status") == "DUPLICATE_NEXT_COMMAND" for step in steps):
            return "LOOP_STOPPED"
        return "LOOP_EXECUTED"

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_SAFE_LOOP.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Safe Loop",
            "",
            f"status: {payload['status']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            f"execute: {payload['execute']}",
            f"max_steps: {payload['max_steps']}",
            f"stop_reason: {payload['stop_reason']}",
            f"session_report_path: {payload['session_report_path'] or 'MISSING'}",
            "",
            "## Steps",
        ]
        for step in payload["steps"]:
            lines.extend([
                f"### Step {step['index']}",
                f"- phase: {step['phase']}",
                f"- status: {step['status']}",
                f"- allowed: {step['allowed']}",
                f"- dry_run: {step['dry_run']}",
                f"- command: `{step['command'] or ''}`",
                f"- reason: {step['reason'] or ''}",
                f"- report_path: {step['report_path'] or 'MISSING'}",
                f"- child_report_path: {step['child_report_path'] or 'MISSING'}",
                "",
            ])
        lines.extend([
            "## Hard Boundary",
            f"- {payload['hard_boundary']}",
            "- 不会自动执行 QMT 交接、pretrade、沙盒或真实委托相关命令。",
        ])
        (output_dir / "STUDENT_SAFE_LOOP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
