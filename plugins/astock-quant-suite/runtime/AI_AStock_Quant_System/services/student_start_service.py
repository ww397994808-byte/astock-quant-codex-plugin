from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_control_center_service import StudentControlCenterService
from services.student_doctor_service import StudentDoctorService
from services.student_next_step_runner_service import StudentNextStepRunnerService
from services.student_session_index_service import StudentSessionIndexService


class StudentStartService:
    """One read-only beginner entrypoint: environment, current stage, and safe preview."""

    def run(
        self,
        workflow: str | None = None,
        promotion: str | None = None,
        qmt_dashboard: str | None = None,
        session_id: str | None = None,
        include_session_index: bool = True,
        preview_next: bool = True,
    ) -> TaskResult:
        doctor = StudentDoctorService().run()
        control = StudentControlCenterService().run(
            workflow=workflow,
            promotion=promotion,
            qmt_dashboard=qmt_dashboard,
            session_id=session_id,
        )
        session_index = StudentSessionIndexService().run(limit=10) if include_session_index else None
        preview = None
        if preview_next and control.artifacts.get("safe_to_copy"):
            preview = StudentNextStepRunnerService().run(
                workflow=workflow,
                promotion=promotion,
                qmt_dashboard=qmt_dashboard,
                session_id=session_id,
                dry_run=True,
            )

        payload = self._payload(doctor, control, session_index, preview, session_id)
        ctx = RunManager().create_run("student_start")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"READY_TO_START", "READY_FOR_SAFE_NEXT"} else "INVALID"
        warnings = [] if result_status == "VALID" else [payload["summary"]]
        return TaskResult(
            status=result_status,
            message=f"学员启动包生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _payload(self, doctor: TaskResult, control: TaskResult, session_index: TaskResult | None, preview: TaskResult | None, session_id: str | None) -> dict[str, Any]:
        doctor_status = str(doctor.artifacts.get("status") or doctor.status)
        control_status = str(control.artifacts.get("status") or control.status)
        preview_allowed = bool(preview and preview.artifacts.get("allowed"))
        if doctor.status != "VALID":
            status = "BLOCKED_ENVIRONMENT"
            summary = "环境体检存在阻断项，先处理 student-doctor 的修复动作。"
        elif preview_allowed:
            status = "READY_FOR_SAFE_NEXT"
            summary = "环境可用，控制台已有可安全预演的下一步研究/只读命令。"
        elif control.artifacts.get("safe_to_copy"):
            status = "READY_TO_START"
            summary = "环境可用，控制台有可复制命令；本次未预演或预演未开启。"
        else:
            status = "NEEDS_MANUAL_INPUT"
            summary = "环境可用，但下一步仍需要人工补参数、选报告或处理阻断。"

        cards = self._cards(doctor, control, session_index, preview)
        return {
            "status": status,
            "summary": summary,
            "session_id": session_id or control.artifacts.get("session_id", ""),
            "doctor_status": doctor_status,
            "control_status": control_status,
            "current_stage": control.artifacts.get("current_stage", ""),
            "next_action": control.artifacts.get("next_action", ""),
            "next_command": control.artifacts.get("next_command", ""),
            "safe_to_copy": bool(control.artifacts.get("safe_to_copy")),
            "preview_status": preview.artifacts.get("status") if preview else "SKIPPED",
            "preview_allowed": preview_allowed,
            "hard_boundary": "student-start 只做体检、导航、名册读取和 dry-run 预演；不会真正执行研究重跑、不会连接 QMT、不会下单。",
            "sources": {
                "student_doctor": self._source(doctor),
                "student_control_center": self._source(control),
                "student_session_index": self._source(session_index) if session_index else {"found": False},
                "student_next_step_preview": self._source(preview) if preview else {"found": False},
            },
            "cards": cards,
        }

    def _cards(self, doctor: TaskResult, control: TaskResult, session_index: TaskResult | None, preview: TaskResult | None) -> list[dict[str, Any]]:
        cards = [
            {
                "id": "environment",
                "title": "环境体检",
                "status": doctor.artifacts.get("status", doctor.status),
                "action": doctor.artifacts.get("summary", ""),
                "command": "python3 cli.py student-doctor",
                "safe_to_copy": True,
                "report_path": doctor.report_path,
            },
            {
                "id": "control_center",
                "title": "当前阶段",
                "status": control.artifacts.get("status", control.status),
                "action": control.artifacts.get("next_action", ""),
                "command": control.artifacts.get("next_command", ""),
                "safe_to_copy": bool(control.artifacts.get("safe_to_copy")),
                "report_path": control.report_path,
            },
        ]
        if session_index:
            cards.append({
                "id": "session_index",
                "title": "学员名册",
                "status": session_index.artifacts.get("status", session_index.status),
                "action": f"已发现 {session_index.artifacts.get('session_count', 0)} 个 session。",
                "command": "python3 cli.py student-session-index",
                "safe_to_copy": True,
                "report_path": session_index.report_path,
            })
        assumption_cards = [
            card for card in control.artifacts.get("action_cards") or []
            if card.get("id") == "backtest_assumption"
        ]
        if assumption_cards:
            assumption = assumption_cards[0]
            cards.append({
                "id": "backtest_assumption",
                "title": assumption.get("title", "回测假设卡"),
                "status": assumption.get("status", "UNKNOWN"),
                "action": assumption.get("action", ""),
                "command": assumption.get("command", ""),
                "safe_to_copy": False,
                "report_path": control.report_path,
                "why": assumption.get("why", ""),
                "learner_checks": assumption.get("learner_checks") or [],
            })
        if preview:
            cards.append({
                "id": "safe_preview",
                "title": "安全下一步预演",
                "status": preview.artifacts.get("status", preview.status),
                "action": preview.artifacts.get("reason", ""),
                "command": preview.artifacts.get("command", ""),
                "safe_to_copy": False,
                "report_path": preview.report_path,
            })
        return cards

    def _source(self, result: TaskResult | None) -> dict[str, Any]:
        if not result:
            return {"found": False}
        return {
            "found": True,
            "status": result.status,
            "audit_status": result.audit_status,
            "run_id": result.run_id,
            "report_path": result.report_path,
        }

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_START.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (output_dir / "student_start_cards.json").write_text(json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        lines = [
            "# Student Start",
            "",
            f"status: {payload['status']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            f"current_stage: {payload.get('current_stage') or 'MISSING'}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            f"preview_status: {payload['preview_status']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
            f"- action: {payload['next_action'] or 'MISSING'}",
            f"- command: `{payload['next_command'] or 'MISSING'}`",
            "",
            "## 卡片",
        ]
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- command: `{card['command']}`",
                f"- safe_to_copy: {card['safe_to_copy']}",
                f"- report_path: {card.get('report_path') or 'MISSING'}",
                f"- why: {card.get('why') or 'MISSING'}",
                "",
            ])
        lines.extend(["## 证据来源"])
        for name, source in payload["sources"].items():
            lines.extend([
                f"### {name}",
                f"- found: {source.get('found', False)}",
                f"- status: {source.get('status', 'MISSING')}",
                f"- report_path: {source.get('report_path', 'MISSING')}",
            ])
        (output_dir / "STUDENT_START.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
