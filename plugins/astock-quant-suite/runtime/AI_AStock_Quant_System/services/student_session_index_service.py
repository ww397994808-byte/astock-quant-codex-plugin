from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.paper_policy_advice import advice_for_failed_metrics


class StudentSessionIndexService:
    """Build a read-only index of learner sessions and their latest evidence."""

    def run(self, limit: int = 50) -> TaskResult:
        workflows = self._load_workflows()
        ledger_entries = self._load_ledger(Path("reports/student_session_ledger.jsonl"))
        sessions = self._sessions(workflows, ledger_entries)
        rows = sorted(sessions.values(), key=lambda item: item.get("last_seen", ""), reverse=True)
        rows = rows[: max(1, int(limit))]
        payload = {
            "status": "NO_SESSIONS" if not rows else "SESSION_INDEX_READY",
            "session_count": len(rows),
            "sessions": rows,
            "next_commands": self._next_commands(rows),
            "hard_boundary": "student-session-index 只读取报告和账本；不会回测、不会连接 QMT、不会下单。",
        }
        ctx = RunManager().create_run("student_session_index")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if rows else "INVALID"
        warnings = [] if rows else ["还没有找到带 session_id 的学生工作流或执行账本。"]
        return TaskResult(
            status=result_status,
            message=f"学员 session 名册生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _load_workflows(self) -> list[dict[str, Any]]:
        rows = []
        for path in sorted(Path("reports").glob("student_workflow_*/workflow_manifest.json")):
            data = self._read_json(path)
            session_id = str(data.get("session_id") or "")
            if not session_id:
                continue
            rows.append({
                "path": str(path),
                "run_dir": str(path.parent),
                "run_id": path.parent.name,
                "data": data,
            })
        return rows

    def _load_ledger(self, ledger_path: Path) -> list[dict[str, Any]]:
        if not ledger_path.exists():
            return []
        entries = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("session_id"):
                entries.append(item)
        return entries

    def _sessions(self, workflows: list[dict[str, Any]], ledger_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        sessions: dict[str, dict[str, Any]] = {}
        for workflow in workflows:
            data = workflow["data"]
            session_id = str(data.get("session_id") or "")
            item = sessions.setdefault(session_id, self._empty_session(session_id))
            latest = item.get("latest_workflow") or {}
            if workflow["run_id"] > str(latest.get("run_id") or ""):
                item["latest_workflow"] = self._workflow_summary(workflow)
            item["workflow_count"] += 1
            item["case_ids"].add(str(data.get("case_id") or ""))
            item["symbols"].add(str(data.get("symbol") or ""))
            item["last_seen"] = max(str(item.get("last_seen") or ""), workflow["run_id"])

        for entry in ledger_entries:
            session_id = str(entry.get("session_id") or "")
            item = sessions.setdefault(session_id, self._empty_session(session_id))
            item["ledger_summary"]["allowed"] += 1 if entry.get("allowed") is True else 0
            item["ledger_summary"]["blocked"] += 1 if entry.get("allowed") is False else 0
            item["ledger_summary"]["dry_run"] += 1 if entry.get("dry_run") is True else 0
            item["ledger_summary"]["executed"] += 1 if entry.get("dry_run") is False and entry.get("allowed") is True else 0
            item["last_seen"] = max(str(item.get("last_seen") or ""), str(entry.get("timestamp") or ""))

        for item in sessions.values():
            item["case_ids"] = sorted(value for value in item["case_ids"] if value)
            item["symbols"] = sorted(value for value in item["symbols"] if value)
            item["risk_notes"] = self._risk_notes(item)
            item["next_command"] = self._next_command(item)
        return sessions

    def _empty_session(self, session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "last_seen": "",
            "workflow_count": 0,
            "case_ids": set(),
            "symbols": set(),
            "latest_workflow": {},
            "ledger_summary": {
                "allowed": 0,
                "blocked": 0,
                "dry_run": 0,
                "executed": 0,
            },
            "risk_notes": [],
            "next_command": "",
        }

    def _workflow_summary(self, workflow: dict[str, Any]) -> dict[str, Any]:
        data = workflow["data"]
        paper_policy = self._paper_policy_summary(data)
        backtest_assumption = self._backtest_assumption_summary(data, workflow["run_dir"])
        return {
            "run_id": workflow["run_id"],
            "report_path": workflow["run_dir"],
            "status": data.get("status", "UNKNOWN"),
            "case_id": data.get("case_id", ""),
            "symbol": data.get("symbol", ""),
            "strategy": data.get("strategy", ""),
            "timeframe": data.get("timeframe", ""),
            "adjust": data.get("adjust", ""),
            "current_stage": self._stage_for(data, workflow["run_dir"]),
            "backtest_assumption": backtest_assumption,
            "paper_policy": paper_policy,
        }

    def _stage_for(self, data: dict[str, Any], run_dir: str) -> str:
        if data.get("status") != "VALID" and Path(run_dir, "STUDENT_REPAIR_DSL.yaml").exists():
            return "REPAIR_DSL_READY"
        if data.get("status") != "VALID":
            return "WORKFLOW_BLOCKED"
        return "WORKFLOW_VALID"

    def _risk_notes(self, item: dict[str, Any]) -> list[str]:
        notes = []
        if item["ledger_summary"]["blocked"]:
            notes.append("存在被安全执行器拒绝的步骤。")
        latest = item.get("latest_workflow") or {}
        if latest.get("status") == "INVALID":
            notes.append("最新工作流未通过，不能推进 QMT。")
        paper_policy = latest.get("paper_policy") or {}
        if paper_policy.get("status") == "INVALID":
            failed = "、".join(paper_policy.get("failed_metrics") or [])
            notes.append(f"模拟观察政策卡未通过：{failed or '存在失败项'}。")
        backtest_assumption = latest.get("backtest_assumption") or {}
        if backtest_assumption.get("status") == "BLOCKED":
            notes.append("回测假设卡存在阻断项，先确认数据周期、撮合假设和A股规则。")
        if not latest:
            notes.append("只有执行账本，没有找到 session 对应工作流。")
        if not notes:
            notes.append("未发现新的 session 级风险；仍需遵守阶段门。")
        return notes

    def _next_command(self, item: dict[str, Any]) -> str:
        session_id = item["session_id"]
        latest = item.get("latest_workflow") or {}
        if not latest:
            return f'python3 cli.py student-workflow --idea "<策略想法>" --session-id {session_id} --timeframe 1d --adjust point_in_time_qfq --auto-refine'
        return f"python3 cli.py student-control-center --session-id {session_id}"

    def _next_commands(self, rows: list[dict[str, Any]]) -> list[str]:
        return [row["next_command"] for row in rows[:5]]

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"status": "UNREADABLE", "error": str(exc)}

    def _paper_policy_summary(self, workflow_data: dict[str, Any]) -> dict[str, Any]:
        for step in workflow_data.get("steps") or []:
            if step.get("step") != "paper":
                continue
            report_path = str(step.get("report_path") or "").strip()
            if not report_path:
                break
            card_path = Path(report_path) / "paper_observation_policy_card.json"
            if not card_path.exists():
                return {
                    "found": False,
                    "path": str(card_path),
                    "status": "MISSING",
                    "failed_metrics": [],
                    "repair_hints": [],
                    "can_continue_qmt_readonly": False,
                }
            data = self._read_json(card_path)
            failed = [
                str(item.get("metric"))
                for item in data.get("requirements") or []
                if item.get("status") == "FAIL" and item.get("metric")
            ]
            return {
                "found": True,
                "path": str(card_path),
                "status": data.get("status", "UNKNOWN"),
                "strategy_pattern": data.get("strategy_pattern", ""),
                "timeframe": data.get("timeframe", ""),
                "failed_metrics": failed,
                "repair_hints": advice_for_failed_metrics(failed),
                "can_continue_qmt_readonly": bool(data.get("can_continue_qmt_readonly")),
                "learner_message": data.get("learner_message", ""),
            }
        return {
            "found": False,
            "path": "",
            "status": "MISSING",
            "failed_metrics": [],
            "repair_hints": [],
            "can_continue_qmt_readonly": False,
        }

    def _backtest_assumption_summary(self, workflow_data: dict[str, Any], run_dir: str) -> dict[str, Any]:
        card_path = Path(run_dir) / "BACKTEST_ASSUMPTION_CARD.json"
        data = {}
        found = False
        if card_path.exists():
            data = self._read_json(card_path)
            found = True
        elif workflow_data.get("backtest_assumption_card"):
            data = workflow_data.get("backtest_assumption_card") or {}
            found = True
        if not found:
            return {
                "found": False,
                "path": str(card_path),
                "status": "MISSING",
                "strategy_pattern": "",
                "timeframe": "",
                "learner_checks": [],
            }
        checks = [
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
            }
            for item in data.get("learner_checks") or []
        ]
        return {
            "found": True,
            "path": str(card_path),
            "status": data.get("status", "UNKNOWN"),
            "strategy_pattern": data.get("strategy_pattern", ""),
            "template_name": data.get("template_name", ""),
            "symbol_scope": data.get("symbol_scope", ""),
            "timeframe": data.get("timeframe", ""),
            "execution_model": data.get("execution_model") or {},
            "data_required": data.get("data_required") or {},
            "promotion_policy": data.get("promotion_policy") or {},
            "learner_checks": checks,
        }

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_SESSION_INDEX.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_session_cards.json").write_text(
            json.dumps(payload["sessions"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Session Index",
            "",
            f"status: {payload['status']}",
            f"session_count: {payload['session_count']}",
            "",
            "## 下一步候选",
        ]
        lines.extend([f"- `{command}`" for command in payload["next_commands"]] or ["- 暂无。"])
        lines.extend(["", "## Sessions"])
        for item in payload["sessions"]:
            latest = item.get("latest_workflow") or {}
            lines.extend([
                f"### {item['session_id']}",
                f"- last_seen: {item.get('last_seen') or 'MISSING'}",
                f"- workflow_count: {item['workflow_count']}",
                f"- case_ids: {', '.join(item['case_ids']) or 'MISSING'}",
                f"- symbols: {', '.join(item['symbols']) or 'MISSING'}",
                f"- latest_workflow_status: {latest.get('status', 'MISSING')}",
                f"- current_stage: {latest.get('current_stage', 'MISSING')}",
                f"- latest_report_path: {latest.get('report_path', 'MISSING')}",
                f"- backtest_assumption_status: {(latest.get('backtest_assumption') or {}).get('status', 'MISSING')}",
                f"- backtest_assumption_pattern: {(latest.get('backtest_assumption') or {}).get('strategy_pattern', 'MISSING') or 'MISSING'}",
                f"- backtest_assumption_timeframe: {(latest.get('backtest_assumption') or {}).get('timeframe', 'MISSING') or 'MISSING'}",
                f"- backtest_assumption_path: {(latest.get('backtest_assumption') or {}).get('path', 'MISSING') or 'MISSING'}",
                "- backtest_assumption_checks:",
            ])
            assumption_checks = (latest.get("backtest_assumption") or {}).get("learner_checks") or []
            lines.extend([f"  - {check.get('id')}: {check.get('status')}" for check in assumption_checks] or ["  - NONE"])
            lines.extend([
                f"- paper_policy_status: {(latest.get('paper_policy') or {}).get('status', 'MISSING')}",
                f"- paper_policy_failed_metrics: {', '.join((latest.get('paper_policy') or {}).get('failed_metrics') or []) or 'NONE'}",
                f"- paper_policy_path: {(latest.get('paper_policy') or {}).get('path', 'MISSING') or 'MISSING'}",
                "- paper_policy_repair_hints:",
            ])
            hints = (latest.get("paper_policy") or {}).get("repair_hints") or []
            lines.extend([f"  - {hint.get('metric')}: {hint.get('advice')}" for hint in hints] or ["  - NONE"])
            lines.extend([
                f"- ledger_allowed: {item['ledger_summary']['allowed']}",
                f"- ledger_blocked: {item['ledger_summary']['blocked']}",
                f"- next_command: `{item['next_command']}`",
                "- risk_notes:",
            ])
            lines.extend([f"  - {note}" for note in item["risk_notes"]])
            lines.append("")
        lines.extend([
            "## Hard Boundary",
            f"- {payload['hard_boundary']}",
        ])
        (output_dir / "STUDENT_SESSION_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
