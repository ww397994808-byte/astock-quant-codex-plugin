from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager


class StudentSessionReportService:
    """Summarize the append-only student session ledger for teaching review."""

    def run(self, ledger: str = "reports/student_session_ledger.jsonl", limit: int = 20, session_id: str | None = None) -> TaskResult:
        session_id = self._clean_label(session_id)
        ledger_path = Path(ledger)
        entries = self._read_ledger(ledger_path)
        if session_id:
            entries = [entry for entry in entries if str(entry.get("session_id") or "") == session_id]
        recent = entries[-max(1, int(limit)):]
        summary = self._summary(entries)
        payload = {
            "status": "NO_LEDGER" if not entries else "SESSION_REVIEW_READY",
            "session_id": session_id,
            "ledger_path": str(ledger_path),
            "total_entries": len(entries),
            "summary": summary,
            "recent_entries": recent,
            "risk_notes": self._risk_notes(summary, recent),
            "hard_boundary": "student-session-report 只汇总执行记录；它不执行命令，不连接 QMT，不产生交易许可。",
        }
        ctx = RunManager().create_run("student_session_report")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if entries else "INVALID"
        warnings = [] if entries else [f"找不到或没有可读取的学员执行账本：{ledger_path}"]
        return TaskResult(
            status=result_status,
            message=f"学员 session 汇总生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _read_ledger(self, ledger_path: Path) -> list[dict[str, Any]]:
        if not ledger_path.exists():
            return []
        entries = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({
                    "timestamp": "",
                    "status": "UNREADABLE",
                    "allowed": False,
                    "dry_run": False,
                    "command": "",
                    "reason": "ledger 行 JSON 解析失败。",
                })
        return entries

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _summary(self, entries: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "allowed": sum(1 for item in entries if item.get("allowed") is True),
            "blocked": sum(1 for item in entries if item.get("allowed") is False),
            "dry_run": sum(1 for item in entries if item.get("dry_run") is True),
            "executed": sum(1 for item in entries if item.get("dry_run") is False and item.get("allowed") is True),
            "failed": sum(1 for item in entries if str(item.get("status")) in {"EXECUTED_FAILED", "UNREADABLE"}),
        }

    def _risk_notes(self, summary: dict[str, int], recent: list[dict[str, Any]]) -> list[str]:
        notes = []
        if summary["blocked"]:
            notes.append("存在被安全执行器拒绝的步骤；老师应复盘拒绝原因，避免学员绕过。")
        if summary["failed"]:
            notes.append("存在执行失败或不可读账本记录；需要查看对应 run 目录的 stdout/stderr。")
        if any("pretrade" in str(item.get("command", "")) for item in recent):
            notes.append("最近记录出现 pretrade 字样；确认其是否被拒绝，不能自动推进实盘。")
        if not notes and recent:
            notes.append("最近 session 没有发现新的执行风险；仍需继续遵守阶段门。")
        return notes

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_SESSION_REPORT.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Session Report",
            "",
            f"status: {payload['status']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            f"ledger_path: {payload['ledger_path']}",
            f"total_entries: {payload['total_entries']}",
            "",
            "## 汇总",
        ]
        for key, value in payload["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## 风险提示"])
        lines.extend([f"- {item}" for item in payload["risk_notes"]] or ["- 暂无风险提示。"])
        lines.extend(["", "## 最近步骤"])
        for item in payload["recent_entries"]:
            lines.extend([
                f"### {item.get('timestamp') or 'UNKNOWN'}",
                f"- status: {item.get('status')}",
                f"- allowed: {item.get('allowed')}",
                f"- dry_run: {item.get('dry_run')}",
                f"- command: `{item.get('command') or ''}`",
                f"- reason: {item.get('reason') or ''}",
                f"- report_path: {item.get('report_path') or 'MISSING'}",
                f"- child_report_path: {item.get('child_report_path') or 'MISSING'}",
                "",
            ])
        lines.extend([
            "## 硬边界",
            f"- {payload['hard_boundary']}",
        ])
        (output_dir / "STUDENT_SESSION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
