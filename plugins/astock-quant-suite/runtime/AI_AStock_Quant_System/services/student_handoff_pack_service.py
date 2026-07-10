from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_product_audit_service import StudentProductAuditService
from services.student_session_report_service import StudentSessionReportService
from services.student_start_service import StudentStartService


class StudentHandoffPackService:
    """Read-only learner handoff package for classes and coaching sessions."""

    def run(
        self,
        workflow: str | None = None,
        session_id: str | None = None,
        include_product_audit: bool = True,
        include_session_report: bool = True,
    ) -> TaskResult:
        session_id = self._clean_label(session_id)
        start = StudentStartService().run(
            workflow=workflow,
            session_id=session_id or None,
            include_session_index=True,
            preview_next=True,
        )
        session_report = (
            StudentSessionReportService().run(session_id=session_id or None)
            if include_session_report
            else None
        )
        product_audit = StudentProductAuditService().run(workflow=workflow) if include_product_audit else None
        payload = self._payload(start, session_report, product_audit, workflow, session_id)

        ctx = RunManager().create_run("student_handoff_pack")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"HANDOFF_READY", "HANDOFF_READY_WITH_WARNINGS"} else "INVALID"
        warnings = payload.get("warnings") or []
        return TaskResult(
            status=result_status,
            message=f"学员交付包生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _payload(
        self,
        start: TaskResult,
        session_report: TaskResult | None,
        product_audit: TaskResult | None,
        workflow: str | None,
        session_id: str,
    ) -> dict[str, Any]:
        warnings = []
        if start.status != "VALID":
            warnings.append(str(start.artifacts.get("summary") or "student-start 未达到可继续状态。"))
        if product_audit and product_audit.artifacts.get("status") == "BLOCKED_PRODUCT_DELIVERY":
            warnings.append("产品化体检存在阻断项，不适合交付给学员。")
        if session_report and session_report.status != "VALID":
            warnings.extend(session_report.warnings or ["没有可用 session 执行账本。"])

        status = "HANDOFF_BLOCKED" if product_audit and product_audit.artifacts.get("status") == "BLOCKED_PRODUCT_DELIVERY" else "HANDOFF_READY_WITH_WARNINGS" if warnings else "HANDOFF_READY"
        report_links = self._report_links(start, session_report, product_audit)
        cards = self._cards(start, session_report, product_audit)
        return {
            "status": status,
            "summary": self._summary(status, warnings),
            "session_id": session_id or start.artifacts.get("session_id", ""),
            "workflow": workflow or "",
            "next_action": start.artifacts.get("next_action", ""),
            "next_command": start.artifacts.get("next_command", ""),
            "safe_to_copy": bool(start.artifacts.get("safe_to_copy")),
            "warnings": warnings,
            "hard_boundary": "student-handoff-pack 只汇总报告；不会执行研究、不会连接 QMT、不会 pretrade、不会下单。",
            "sources": {
                "student_start": self._source(start),
                "student_session_report": self._source(session_report),
                "student_product_audit": self._source(product_audit),
            },
            "cards": cards,
            "report_links": report_links,
            "learner_checklist": self._learner_checklist(start, product_audit),
        }

    def _cards(self, start: TaskResult, session_report: TaskResult | None, product_audit: TaskResult | None) -> list[dict[str, Any]]:
        cards = [
            {
                "id": "current_stage",
                "title": "当前阶段",
                "status": start.artifacts.get("status", start.status),
                "action": start.artifacts.get("next_action", ""),
                "report_path": start.report_path,
            }
        ]
        if session_report:
            cards.append({
                "id": "session_review",
                "title": "执行复盘",
                "status": session_report.artifacts.get("status", session_report.status),
                "action": "查看最近 allowed/blocked/dry-run 记录。",
                "report_path": session_report.report_path,
            })
        if product_audit:
            cards.append({
                "id": "product_audit",
                "title": "交付体检",
                "status": product_audit.artifacts.get("status", product_audit.status),
                "action": product_audit.artifacts.get("summary", ""),
                "report_path": product_audit.report_path,
            })
        return cards

    def _report_links(self, start: TaskResult, session_report: TaskResult | None, product_audit: TaskResult | None) -> list[dict[str, str]]:
        links = []
        for label, result, filename in [
            ("学员启动包", start, "STUDENT_START.md"),
            ("Session 复盘", session_report, "STUDENT_SESSION_REPORT.md"),
            ("产品化体检", product_audit, "STUDENT_PRODUCT_AUDIT.md"),
        ]:
            if result and result.report_path:
                links.append({
                    "label": label,
                    "path": str(Path(result.report_path) / filename),
                })
        for name, source in (start.artifacts.get("sources") or {}).items():
            report_path = source.get("report_path")
            if report_path and report_path != "MISSING":
                links.append({
                    "label": name,
                    "path": report_path,
                })
        return links

    def _learner_checklist(self, start: TaskResult, product_audit: TaskResult | None) -> list[dict[str, Any]]:
        checklist = [
            {
                "item": "先看当前阶段和下一步命令",
                "status": "READY" if start.artifacts.get("next_command") else "MISSING",
                "detail": start.artifacts.get("next_action", ""),
            },
            {
                "item": "确认不会直接进入实盘",
                "status": "READY",
                "detail": "所有入口默认不会连接 QMT、不会 pretrade、不会下单。",
            },
            {
                "item": "记录本次 session id",
                "status": "READY" if start.artifacts.get("session_id") else "WARN",
                "detail": start.artifacts.get("session_id") or "建议下次带 --session-id。",
            },
        ]
        if product_audit:
            checklist.append({
                "item": "查看交付体检提醒",
                "status": product_audit.artifacts.get("status", "UNKNOWN"),
                "detail": product_audit.artifacts.get("summary", ""),
            })
        return checklist

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

    def _summary(self, status: str, warnings: list[str]) -> str:
        if status == "HANDOFF_BLOCKED":
            return "交付包已生成，但存在产品化阻断项，先处理后再发给学员。"
        if status == "HANDOFF_READY_WITH_WARNINGS":
            return f"交付包可用，但有 {len(warnings)} 个提醒需要老师说明。"
        return "交付包已准备好，可用于学员课后查看或助教复盘。"

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_HANDOFF_PACK.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_handoff_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Handoff Pack",
            "",
            f"status: {payload['status']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
            f"- action: {payload.get('next_action') or 'MISSING'}",
            f"- command: `{payload.get('next_command') or 'MISSING'}`",
            "",
            "## 学员清单",
        ]
        for item in payload["learner_checklist"]:
            lines.extend([
                f"### {item['item']}",
                f"- status: {item['status']}",
                f"- detail: {item['detail']}",
            ])
        lines.extend(["", "## 报告入口"])
        for link in payload["report_links"]:
            lines.append(f"- {link['label']}: `{link['path']}`")
        lines.extend(["", "## 卡片"])
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- report_path: {card.get('report_path') or 'MISSING'}",
                "",
            ])
        lines.extend(["## 提醒"])
        lines.extend([f"- {warning}" for warning in payload["warnings"]] or ["- NONE"])
        (output_dir / "STUDENT_HANDOFF_PACK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
