from __future__ import annotations

import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_control_center_service import StudentControlCenterService


class StudentNextStepRunnerService:
    """Execute only the safe, concrete next command selected by the control center."""

    ALLOWED_COMMANDS = {
        "repair-dsl-backtest",
        "qmt-check",
        "qmt-readiness-dashboard",
        "stage-check",
        "student-backtest-plan-precheck",
        "student-contract-check",
        "student-control-center",
        "student-course-path",
        "student-future-leak-precheck",
        "student-idea-preflight",
        "student-product-audit",
        "student-research-contract",
        "student-workflow",
    }

    DENIED_PREFIXES = (
        "qmt-handoff",
        "qmt-handoff-wizard",
        "qmt-batch-handoff",
        "qmt-batch-handoff-wizard",
        "qmt-order-sandbox",
        "qmt-batch-sandbox",
        "pretrade-check",
        "pretrade-package",
        "pretrade-runbook-refresh",
    )

    def run(
        self,
        workflow: str | None = None,
        promotion: str | None = None,
        qmt_dashboard: str | None = None,
        dry_run: bool = False,
        timeout_seconds: int = 180,
        session_id: str | None = None,
    ) -> TaskResult:
        session_id = self._clean_label(session_id)
        control = StudentControlCenterService().run(
            workflow=workflow,
            promotion=promotion,
            qmt_dashboard=qmt_dashboard,
            session_id=session_id,
        )
        command = str(control.artifacts.get("next_command") or "")
        decision = self._validate_command(command, bool(control.artifacts.get("safe_to_copy")))
        ctx = RunManager().create_run("student_next_step")
        payload: dict[str, Any] = {
            "status": "DRY_RUN_READY" if dry_run and decision["allowed"] else "BLOCKED",
            "control_center_run_id": control.run_id,
            "control_center_report_path": control.report_path,
            "session_id": session_id,
            "command": command,
            "allowed": decision["allowed"],
            "reason": decision["reason"],
            "dry_run": dry_run,
            "timeout_seconds": int(timeout_seconds),
            "returncode": None,
            "child_report_path": "",
            "argv": self._argv_for(command) if decision["allowed"] else [],
            "hard_boundary": "student-run-next 只执行白名单内的安全研究/只读命令；不会执行 QMT 交接、沙盒、pretrade 或真实委托相关命令。",
        }
        if decision["allowed"] and not dry_run:
            completed = subprocess.run(
                self._argv_for(command),
                cwd=Path.cwd(),
                text=True,
                capture_output=True,
                timeout=max(1, int(timeout_seconds)),
            )
            payload["status"] = "EXECUTED_VALID" if completed.returncode == 0 else "EXECUTED_FAILED"
            payload["returncode"] = completed.returncode
            (ctx.output_dir / "child_stdout.txt").write_text(completed.stdout, encoding="utf-8")
            (ctx.output_dir / "child_stderr.txt").write_text(completed.stderr, encoding="utf-8")
            payload["child_report_path"] = self._extract_report_path(completed.stdout)

        self._write_outputs(ctx.output_dir, payload)
        self._append_ledger(ctx.run_id, ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"DRY_RUN_READY", "EXECUTED_VALID"} else "INVALID"
        warnings = [] if result_status == "VALID" else [payload["reason"]]
        return TaskResult(
            status=result_status,
            message=f"学员下一步执行器完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _validate_command(self, command: str, safe_to_copy: bool) -> dict[str, Any]:
        if not safe_to_copy:
            return {"allowed": False, "reason": "控制台标记 safe_to_copy=false，说明命令含占位符或需要人工决策。"}
        if "<" in command or ">" in command:
            return {"allowed": False, "reason": "命令仍包含占位符，不能自动执行。"}
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return {"allowed": False, "reason": f"命令解析失败：{exc}"}
        if len(argv) < 3 or argv[0] != "python3" or argv[1] != "cli.py":
            return {"allowed": False, "reason": "只允许执行 python3 cli.py 开头的项目命令。"}
        subcommand = argv[2]
        if subcommand in self.DENIED_PREFIXES:
            return {"allowed": False, "reason": f"{subcommand} 属于交接/盘前/交易相关命令，必须人工执行。"}
        if subcommand not in self.ALLOWED_COMMANDS:
            return {"allowed": False, "reason": f"{subcommand} 不在 student-run-next 安全白名单中。"}
        return {"allowed": True, "reason": "命令通过安全白名单检查。"}

    def _argv_for(self, command: str) -> list[str]:
        argv = shlex.split(command)
        return [sys.executable if item == "python3" else item for item in argv]

    def _extract_report_path(self, stdout: str) -> str:
        for line in stdout.splitlines():
            if line.startswith("report_path: "):
                return line.split(": ", 1)[1].strip()
        return ""

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_NEXT_STEP_RUN.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "execution_decision.json").write_text(
            json.dumps({
                "allowed": payload["allowed"],
                "reason": payload["reason"],
                "command": payload["command"],
                "argv": payload["argv"],
                "dry_run": payload["dry_run"],
                "timeout_seconds": payload["timeout_seconds"],
                "hard_boundary": payload["hard_boundary"],
            }, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        lines = [
            "# Student Next Step Run",
            "",
            f"status: {payload['status']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            f"allowed: {payload['allowed']}",
            f"dry_run: {payload['dry_run']}",
            f"timeout_seconds: {payload['timeout_seconds']}",
            f"returncode: {payload['returncode']}",
            "",
            "## Command",
            f"- `{payload['command']}`",
            "",
            "## Decision",
            f"- {payload['reason']}",
            "",
            "## Output",
            f"- child_report_path: {payload['child_report_path'] or 'MISSING'}",
            "",
            "## Hard Boundary",
            f"- {payload['hard_boundary']}",
        ]
        (output_dir / "STUDENT_NEXT_STEP_RUN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_ledger(self, run_id: str, output_dir: Path, payload: dict[str, Any]) -> None:
        ledger_path = Path("reports") / "student_session_ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run_id": run_id,
            "report_path": str(output_dir),
            "status": payload["status"],
            "allowed": payload["allowed"],
            "dry_run": payload["dry_run"],
            "command": payload["command"],
            "reason": payload["reason"],
            "child_report_path": payload["child_report_path"],
            "control_center_report_path": payload["control_center_report_path"],
            "session_id": payload.get("session_id", ""),
        }
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]
