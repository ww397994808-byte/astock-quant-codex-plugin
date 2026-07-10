from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_doctor_service import StudentDoctorService
from services.student_idea_preflight_service import StudentIdeaPreflightService


class StudentFirstRunService:
    """Beginner first-run wizard: doctor -> idea preflight -> optional safe workflow execution."""

    def run(
        self,
        idea: str | None = None,
        timeframe: str | None = None,
        adjust: str = "point_in_time_qfq",
        session_id: str | None = None,
        case_id: str | None = None,
        execute: bool = False,
        timeout_seconds: int = 300,
    ) -> TaskResult:
        doctor = StudentDoctorService().run()
        preflight = StudentIdeaPreflightService().run(
            idea=idea,
            timeframe=timeframe,
            adjust=adjust,
            session_id=session_id,
            case_id=case_id,
            auto_refine=True,
        )
        decision = self._decision(doctor, preflight)
        payload: dict[str, Any] = {
            "status": "READY_TO_EXECUTE" if decision["allowed"] and not execute else "EXECUTED_VALID" if decision["allowed"] else "BLOCKED",
            "execute": bool(execute),
            "timeout_seconds": int(timeout_seconds),
            "doctor_status": doctor.artifacts.get("status", doctor.status),
            "doctor_report_path": doctor.report_path,
            "preflight_status": preflight.artifacts.get("status", preflight.status),
            "preflight_report_path": preflight.report_path,
            "idea": idea or "",
            "session_id": session_id or "",
            "case_id": case_id or "",
            "command": preflight.artifacts.get("next_command", ""),
            "allowed": decision["allowed"],
            "reason": decision["reason"],
            "returncode": None,
            "child_report_path": "",
            "child_stdout_path": "",
            "child_stderr_path": "",
            "hard_boundary": "student-first-run 只串联体检、想法预检和 student-workflow；不会连接 QMT、不会 pretrade、不会下单。",
            "cards": self._cards(doctor, preflight, decision),
        }

        ctx = RunManager().create_run("student_first_run")
        if decision["allowed"] and execute:
            completed = subprocess.run(
                self._argv_for(payload["command"]),
                cwd=Path.cwd(),
                text=True,
                capture_output=True,
                timeout=max(1, int(timeout_seconds)),
            )
            payload["returncode"] = completed.returncode
            payload["status"] = "EXECUTED_VALID" if completed.returncode == 0 else "EXECUTED_FAILED"
            stdout_path = ctx.output_dir / "student_workflow_stdout.txt"
            stderr_path = ctx.output_dir / "student_workflow_stderr.txt"
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")
            payload["child_stdout_path"] = str(stdout_path)
            payload["child_stderr_path"] = str(stderr_path)
            payload["child_report_path"] = self._extract_report_path(completed.stdout)
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"READY_TO_EXECUTE", "EXECUTED_VALID"} else "INVALID"
        warnings = [] if result_status == "VALID" else [payload["reason"]]
        return TaskResult(
            status=result_status,
            message=f"学员首跑向导完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _decision(self, doctor: TaskResult, preflight: TaskResult) -> dict[str, Any]:
        if doctor.status != "VALID":
            return {"allowed": False, "reason": "student-doctor 未通过，先处理环境或安全配置阻断。"}
        if preflight.artifacts.get("status") != "READY_FOR_STUDENT_WORKFLOW":
            return {"allowed": False, "reason": "策略想法预检未达到 READY_FOR_STUDENT_WORKFLOW。"}
        command = str(preflight.artifacts.get("next_command") or "")
        if not preflight.artifacts.get("safe_to_copy"):
            return {"allowed": False, "reason": "预检命令不可直接复制，仍需人工补充。"}
        if "<" in command or ">" in command:
            return {"allowed": False, "reason": "命令仍包含占位符。"}
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return {"allowed": False, "reason": f"命令解析失败：{exc}"}
        if len(argv) < 3 or argv[0] != "python3" or argv[1] != "cli.py" or argv[2] != "student-workflow":
            return {"allowed": False, "reason": "首跑向导只允许执行 student-workflow。"}
        unsafe_tokens = {"--include-qmt", "qmt-check", "pretrade", "handoff", "sandbox"}
        if any(token in command for token in unsafe_tokens):
            return {"allowed": False, "reason": "命令包含 QMT/pretrade/交接/沙盒相关内容，首跑向导拒绝执行。"}
        return {"allowed": True, "reason": "环境和想法预检通过；可安全启动 student-workflow 研究链路。"}

    def _argv_for(self, command: str) -> list[str]:
        argv = shlex.split(command)
        return [sys.executable if item == "python3" else item for item in argv]

    def _extract_report_path(self, stdout: str) -> str:
        for line in stdout.splitlines():
            if line.startswith("report_path: "):
                return line.split(": ", 1)[1].strip()
        return ""

    def _cards(self, doctor: TaskResult, preflight: TaskResult, decision: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "id": "doctor",
                "title": "环境体检",
                "status": doctor.artifacts.get("status", doctor.status),
                "action": doctor.artifacts.get("summary", ""),
                "report_path": doctor.report_path,
            },
            {
                "id": "idea_preflight",
                "title": "想法预检",
                "status": preflight.artifacts.get("status", preflight.status),
                "action": preflight.artifacts.get("summary", ""),
                "report_path": preflight.report_path,
            },
            {
                "id": "workflow_execution",
                "title": "研究启动",
                "status": "READY" if decision["allowed"] else "BLOCK",
                "action": decision["reason"],
                "report_path": "",
            },
        ]

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_FIRST_RUN.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_first_run_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student First Run",
            "",
            f"status: {payload['status']}",
            f"execute: {payload['execute']}",
            f"allowed: {payload['allowed']}",
            f"returncode: {payload['returncode']}",
            "",
            "## 当前结论",
            f"- {payload['reason']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 命令",
            f"- `{payload['command'] or 'MISSING'}`",
            "",
            "## 证据",
            f"- doctor_report_path: {payload['doctor_report_path']}",
            f"- preflight_report_path: {payload['preflight_report_path']}",
            f"- child_report_path: {payload['child_report_path'] or 'MISSING'}",
            "",
            "## 卡片",
        ]
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- report_path: {card.get('report_path') or 'MISSING'}",
                "",
            ])
        (output_dir / "STUDENT_FIRST_RUN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
