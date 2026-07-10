from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_backtest_plan_precheck_service import StudentBacktestPlanPrecheckService
from services.student_doctor_service import StudentDoctorService
from services.student_future_leak_precheck_service import StudentFutureLeakPrecheckService
from services.student_idea_preflight_service import StudentIdeaPreflightService


class StudentCoursePathService:
    """Course-facing zero-to-research route planner for beginners."""

    def run(
        self,
        idea: str | None = None,
        timeframe: str | None = None,
        adjust: str = "point_in_time_qfq",
        strategy_pattern: str | None = None,
        code: str | None = None,
        file: str | None = None,
        session_id: str | None = None,
        case_id: str | None = None,
    ) -> TaskResult:
        idea = str(idea or "").strip()
        session_id = self._clean_label(session_id)
        case_id = self._clean_label(case_id)

        doctor = StudentDoctorService().run()
        idea_preflight = StudentIdeaPreflightService().run(
            idea=idea,
            timeframe=timeframe,
            adjust=adjust,
            session_id=session_id,
            case_id=case_id,
            auto_refine=True,
        )
        plan_precheck = StudentBacktestPlanPrecheckService().run(
            idea=idea,
            timeframe=timeframe,
            adjust=adjust,
            strategy_pattern=strategy_pattern,
            session_id=session_id,
            case_id=case_id,
        )
        leak_precheck = None
        if str(code or "").strip() or str(file or "").strip():
            leak_precheck = StudentFutureLeakPrecheckService().run(
                code=code,
                file=file,
                strategy_name=strategy_pattern,
                session_id=session_id,
            )

        payload = self._payload(
            idea=idea,
            session_id=session_id,
            case_id=case_id,
            doctor=doctor,
            idea_preflight=idea_preflight,
            plan_precheck=plan_precheck,
            leak_precheck=leak_precheck,
        )
        ctx = RunManager().create_run("student_course_path")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"COURSE_PATH_READY", "COURSE_PATH_NEEDS_CLARIFICATION"} else "INVALID"
        warnings = [item["message"] for item in payload.get("blockers", []) + payload.get("warnings", [])]
        return TaskResult(
            status=result_status,
            message=f"学员课程路线生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _payload(
        self,
        idea: str,
        session_id: str,
        case_id: str,
        doctor: TaskResult,
        idea_preflight: TaskResult,
        plan_precheck: TaskResult,
        leak_precheck: TaskResult | None,
    ) -> dict[str, Any]:
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        route_steps = [
            self._step("environment", "环境体检", doctor),
            self._step("idea_preflight", "想法预检", idea_preflight),
            self._step("backtest_plan", "回测计划预检", plan_precheck),
        ]
        if leak_precheck:
            route_steps.append(self._step("future_leak", "未来函数代码预检", leak_precheck))
        else:
            warnings.append(self._issue(
                "future_leak_not_run",
                "未检查策略代码",
                "本次没有提供 --file 或 --code，未来函数代码预检被跳过。",
                "如果学员已经写了策略代码，先运行 student-future-leak-precheck 或给 student-course-path 加 --file/--code。",
            ))

        if doctor.status != "VALID":
            blockers.append(self._issue(
                "environment_blocked",
                "环境未通过",
                str(doctor.artifacts.get("summary") or "student-doctor 未通过。"),
                "先处理 student-doctor 报告里的 blocker。",
            ))
        idea_status = str(idea_preflight.artifacts.get("status") or "")
        plan_status = str(plan_precheck.artifacts.get("status") or "")
        if idea_status not in {"READY_FOR_STUDENT_WORKFLOW", "NEEDS_CLARIFICATION"}:
            blockers.append(self._issue(
                "idea_blocked",
                "想法不能开跑",
                str(idea_preflight.artifacts.get("summary") or idea_status),
                "按 STUDENT_IDEA_PREFLIGHT.md 的澄清问题补充。",
            ))
        elif idea_status == "NEEDS_CLARIFICATION":
            warnings.append(self._issue(
                "idea_needs_clarification",
                "想法仍需补充",
                str(idea_preflight.artifacts.get("summary") or idea_status),
                "先回答澄清问题，或运行报告里的 intake-chat。",
            ))
        if plan_status not in {"BACKTEST_PLAN_READY", "NEEDS_CLARIFICATION"}:
            blockers.append(self._issue(
                "plan_blocked",
                "回测计划不成立",
                str(plan_precheck.artifacts.get("summary") or plan_status),
                "先修正策略范式、周期、数据要求或资产版本。",
            ))
        elif plan_status == "NEEDS_CLARIFICATION":
            warnings.append(self._issue(
                "plan_needs_clarification",
                "回测计划仍是草案",
                str(plan_precheck.artifacts.get("summary") or plan_status),
                "补齐想法后重新生成正式回测计划。",
            ))
        if leak_precheck and leak_precheck.artifacts.get("status") != "LEAK_CHECK_VALID":
            blockers.append(self._issue(
                "future_leak_blocked",
                "策略代码存在未来函数风险",
                str(leak_precheck.artifacts.get("summary") or leak_precheck.artifacts.get("status")),
                "先修复 STUDENT_FUTURE_LEAK_PRECHECK.md 中的 HIGH 风险。",
            ))

        next_command = self._select_next_command(idea_preflight, plan_precheck, leak_precheck, blockers, warnings)
        status = (
            "COURSE_PATH_BLOCKED" if blockers else
            "COURSE_PATH_NEEDS_CLARIFICATION" if warnings and not self._ready_for_workflow(idea_preflight, plan_precheck, leak_precheck) else
            "COURSE_PATH_READY"
        )
        payload = {
            "status": status,
            "summary": self._summary(status, blockers, warnings),
            "idea": idea,
            "session_id": session_id,
            "case_id": case_id,
            "safe_to_copy": status == "COURSE_PATH_READY" and bool(next_command) and "<" not in next_command and ">" not in next_command,
            "next_command": next_command,
            "hard_boundary": "student-course-path 只生成课程路线和前置检查报告；不会执行 student-workflow、不会连接 QMT、不会 pretrade、不会下单。",
            "sources": {
                "student_doctor": self._source(doctor),
                "student_idea_preflight": self._source(idea_preflight),
                "student_backtest_plan_precheck": self._source(plan_precheck),
                "student_future_leak_precheck": self._source(leak_precheck) if leak_precheck else {"found": False},
            },
            "route_steps": route_steps,
            "blockers": self._dedupe_issues(blockers),
            "warnings": self._dedupe_issues(warnings),
            "cards": self._cards(route_steps, status, next_command),
        }
        return payload

    def _ready_for_workflow(self, idea_preflight: TaskResult, plan_precheck: TaskResult, leak_precheck: TaskResult | None) -> bool:
        if idea_preflight.artifacts.get("status") != "READY_FOR_STUDENT_WORKFLOW":
            return False
        if plan_precheck.artifacts.get("status") != "BACKTEST_PLAN_READY":
            return False
        if leak_precheck and leak_precheck.artifacts.get("status") != "LEAK_CHECK_VALID":
            return False
        return True

    def _select_next_command(
        self,
        idea_preflight: TaskResult,
        plan_precheck: TaskResult,
        leak_precheck: TaskResult | None,
        blockers: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> str:
        if blockers:
            if leak_precheck and leak_precheck.artifacts.get("status") not in {"", "LEAK_CHECK_VALID"}:
                return str(leak_precheck.artifacts.get("next_command") or "")
            if plan_precheck.status != "VALID":
                return str(plan_precheck.artifacts.get("next_command") or "")
            return str(idea_preflight.artifacts.get("next_command") or "")
        if self._ready_for_workflow(idea_preflight, plan_precheck, leak_precheck):
            return str(idea_preflight.artifacts.get("next_command") or plan_precheck.artifacts.get("next_command") or "")
        if warnings:
            return str(idea_preflight.artifacts.get("alternative_command") or plan_precheck.artifacts.get("alternative_command") or "")
        return str(idea_preflight.artifacts.get("next_command") or "")

    def _step(self, step_id: str, title: str, result: TaskResult) -> dict[str, Any]:
        artifacts = result.artifacts or {}
        return {
            "id": step_id,
            "title": title,
            "status": artifacts.get("status") or result.status,
            "result_status": result.status,
            "summary": artifacts.get("summary") or result.message,
            "report_path": result.report_path,
            "next_command": artifacts.get("next_command", ""),
            "safe_to_copy": bool(artifacts.get("safe_to_copy", False)),
        }

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

    def _cards(self, route_steps: list[dict[str, Any]], status: str, next_command: str) -> list[dict[str, Any]]:
        cards = [
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "action": item["summary"],
                "command": item.get("next_command") or "",
                "safe_to_copy": bool(item.get("safe_to_copy")),
                "report_path": item["report_path"],
            }
            for item in route_steps
        ]
        cards.append({
            "id": "course_next_step",
            "title": "课程下一步",
            "status": "READY" if status == "COURSE_PATH_READY" else "BLOCK" if status == "COURSE_PATH_BLOCKED" else "WARN",
            "action": "可以复制下一条研究命令。" if status == "COURSE_PATH_READY" else "先处理阻断或补充信息。",
            "command": next_command,
            "safe_to_copy": status == "COURSE_PATH_READY" and bool(next_command),
            "report_path": "",
        })
        return cards

    def _summary(self, status: str, blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> str:
        if status == "COURSE_PATH_BLOCKED":
            return f"课程路线被阻断：{len(blockers)} 个阻断项。"
        if status == "COURSE_PATH_NEEDS_CLARIFICATION":
            return f"课程路线需要补充信息：{len(warnings)} 个提醒项。"
        return "课程路线已准备好，可以进入 student-workflow 研究链路。"

    def _issue(self, issue_id: str, title: str, message: str, fix: str) -> dict[str, str]:
        return {"id": issue_id, "title": title, "message": message, "fix": fix}

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _dedupe_issues(self, issues: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped = []
        seen = set()
        for issue in issues:
            key = (issue.get("id", ""), issue.get("message", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(issue)
        return deduped

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_COURSE_PATH.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_course_path_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Course Path",
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
            f"- command: `{payload['next_command'] or 'MISSING'}`",
            "",
            "## 路线步骤",
        ]
        for step in payload["route_steps"]:
            lines.extend([
                f"### {step['title']}",
                f"- status: {step['status']}",
                f"- result_status: {step['result_status']}",
                f"- summary: {step['summary']}",
                f"- report_path: {step['report_path']}",
                f"- next_command: `{step.get('next_command') or 'MISSING'}`",
                "",
            ])
        lines.extend(["## 阻断项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("blockers") or []] or ["- NONE"])
        lines.extend(["", "## 提醒项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("warnings") or []] or ["- NONE"])
        lines.extend(["", "## 卡片"])
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- command: `{card['command']}`",
                f"- safe_to_copy: {card['safe_to_copy']}",
                f"- report_path: {card.get('report_path') or 'MISSING'}",
                "",
            ])
        (output_dir / "STUDENT_COURSE_PATH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
