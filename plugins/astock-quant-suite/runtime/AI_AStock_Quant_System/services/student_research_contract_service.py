from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_course_path_service import StudentCoursePathService


class StudentResearchContractService:
    """Create an immutable pre-run research contract for learner and mentor review."""

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
        course_path = StudentCoursePathService().run(
            idea=idea,
            timeframe=timeframe,
            adjust=adjust,
            strategy_pattern=strategy_pattern,
            code=code,
            file=file,
            session_id=session_id,
            case_id=case_id,
        )
        payload = self._payload(course_path)
        ctx = RunManager().create_run("student_research_contract")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] == "CONTRACT_READY" else "INVALID"
        warnings = [item["message"] for item in payload.get("blockers", []) + payload.get("warnings", [])]
        return TaskResult(
            status=result_status,
            message=f"学员研究契约生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _payload(self, course_path: TaskResult) -> dict[str, Any]:
        artifacts = course_path.artifacts or {}
        sources = artifacts.get("sources") or {}
        idea_report = self._load_json_from_source(sources.get("student_idea_preflight"), "STUDENT_IDEA_PREFLIGHT.json")
        plan_report = self._load_json_from_source(sources.get("student_backtest_plan_precheck"), "STUDENT_BACKTEST_PLAN_PRECHECK.json")
        leak_report = self._load_json_from_source(sources.get("student_future_leak_precheck"), "STUDENT_FUTURE_LEAK_PRECHECK.json")

        plan = plan_report.get("backtest_plan") or idea_report.get("backtest_plan") or {}
        parsed = plan_report.get("parsed") or idea_report.get("parsed") or {}
        status = "CONTRACT_READY" if artifacts.get("status") == "COURSE_PATH_READY" else "CONTRACT_BLOCKED"
        blockers = list(artifacts.get("blockers") or [])
        warnings = list(artifacts.get("warnings") or [])
        if not leak_report:
            warnings.append(self._issue(
                "future_leak_not_attached",
                "未绑定策略代码预检",
                "本契约没有绑定 --file 或 --code 的未来函数检查结果。",
                "若学员已经有代码，应重新生成契约并传入 --file 或 --code。",
            ))
        elif leak_report.get("status") != "LEAK_CHECK_VALID":
            status = "CONTRACT_BLOCKED"
            message = str(leak_report.get("summary") or leak_report.get("status"))
            if not any(item.get("message") == message for item in blockers):
                blockers.append(self._issue(
                    "future_leak_contract_blocker",
                    "未来函数风险未清除",
                    message,
                    "先修复代码并重新生成研究契约。",
                ))

        contract_body = {
            "idea": artifacts.get("idea", ""),
            "session_id": artifacts.get("session_id", ""),
            "case_id": artifacts.get("case_id", ""),
            "asset_boundary": "A股/ETF/指数；数字货币、交易所合约、永续合约必须使用独立版本。",
            "resolved_symbol": parsed.get("resolved_symbol", ""),
            "asset_type": parsed.get("asset_type", ""),
            "strategy_pattern": plan.get("strategy_pattern", ""),
            "template_name": plan.get("template_name", ""),
            "timeframe": plan.get("timeframe", ""),
            "adjust": plan.get("adjust", ""),
            "data_required": plan.get("data_required") or [],
            "execution_model": plan.get("execution_model") or {},
            "audit_required": plan.get("audit_required") or [],
            "promotion_policy": plan.get("promotion_policy") or {},
            "signal_causality_rule": "交易信号只能使用当前 K 线及以前的 OHLCV/成交量；未来数据、负向 shift、居中窗口、forward merge、未来标签、当前 K 线收盘成交均为无效。",
            "required_gates": [
                "student-course-path READY",
                "student-workflow 完整生成 workflow_manifest",
                "future_leak_report VALID",
                "audit_report VALID",
                "paper_observation_policy_card 通过策略对应门槛",
                "stage-check 通过当前阶段",
                "QMT 只读前必须 qmt-config-status READY_FOR_QMT_READONLY",
                "真实交易前必须 pretrade-check 且人工确认",
            ],
        }
        contract_id = self._contract_id(contract_body)
        next_command = artifacts.get("next_command") if status == "CONTRACT_READY" else ""
        payload = {
            "status": status,
            "contract_id": contract_id,
            "summary": self._summary(status, blockers, warnings),
            "safe_to_copy": status == "CONTRACT_READY" and bool(next_command),
            "next_command": next_command or "先处理研究契约阻断项。",
            "hard_boundary": "student-research-contract 只固化研究前假设和门槛；不会执行 student-workflow、不会连接 QMT、不会 pretrade、不会下单。",
            "contract": contract_body,
            "sources": sources,
            "course_path_report_path": course_path.report_path,
            "blockers": self._dedupe_issues(blockers),
            "warnings": self._dedupe_issues(warnings),
            "cards": self._cards(status, contract_id, contract_body, next_command or ""),
        }
        return payload

    def _load_json_from_source(self, source: dict[str, Any] | None, filename: str) -> dict[str, Any]:
        if not source or not source.get("found") or not source.get("report_path"):
            return {}
        path = Path(str(source["report_path"])) / filename
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _contract_id(self, contract_body: dict[str, Any]) -> str:
        text = json.dumps(contract_body, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _cards(self, status: str, contract_id: str, contract: dict[str, Any], next_command: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "research_contract",
                "title": "研究契约",
                "status": "PASS" if status == "CONTRACT_READY" else "BLOCK",
                "action": "契约可作为本轮研究开跑依据。" if status == "CONTRACT_READY" else "契约存在阻断，不能开跑。",
                "why": f"contract_id={contract_id}",
                "command": next_command,
                "safe_to_copy": status == "CONTRACT_READY" and bool(next_command),
            },
            {
                "id": "contract_assumptions",
                "title": "固定假设",
                "status": "PASS" if status == "CONTRACT_READY" else "BLOCK",
                "action": f"{contract.get('strategy_pattern')}/{contract.get('timeframe')}/{contract.get('adjust')} 不应在同一轮研究中偷换。",
                "why": f"template={contract.get('template_name')}; symbol={contract.get('resolved_symbol') or 'MISSING'}",
                "command": next_command,
                "safe_to_copy": False,
            },
        ]

    def _summary(self, status: str, blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> str:
        if status == "CONTRACT_BLOCKED":
            return f"研究契约不可签署：{len(blockers)} 个阻断项。"
        return f"研究契约可签署；提醒项 {len(warnings)} 个，后续仍需完整 workflow、审计、模拟观察和阶段门。"

    def _issue(self, issue_id: str, title: str, message: str, fix: str) -> dict[str, str]:
        return {"id": issue_id, "title": title, "message": message, "fix": fix}

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
        (output_dir / "STUDENT_RESEARCH_CONTRACT.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_research_contract_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "research_contract.json").write_text(
            json.dumps(payload["contract"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Research Contract",
            "",
            f"status: {payload['status']}",
            f"contract_id: {payload['contract_id']}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
            f"- command: `{payload['next_command']}`",
            "",
            "## 固定研究假设",
        ]
        contract = payload["contract"]
        for key in ["idea", "resolved_symbol", "asset_type", "strategy_pattern", "template_name", "timeframe", "adjust"]:
            lines.append(f"- {key}: {contract.get(key, 'MISSING') or 'MISSING'}")
        lines.extend([
            f"- data_required: {', '.join(contract.get('data_required') or []) or 'MISSING'}",
            f"- audit_required: {', '.join(contract.get('audit_required') or []) or 'MISSING'}",
            "",
            "## 撮合与因果边界",
            f"- execution_model: {json.dumps(contract.get('execution_model') or {}, ensure_ascii=False)}",
            f"- signal_causality_rule: {contract.get('signal_causality_rule')}",
            "",
            "## 必须通过的门槛",
        ])
        lines.extend([f"- {item}" for item in contract.get("required_gates") or []])
        lines.extend(["", "## 阻断项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("blockers") or []] or ["- NONE"])
        lines.extend(["", "## 提醒项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("warnings") or []] or ["- NONE"])
        lines.extend(["", "## 证据来源"])
        for name, source in payload.get("sources", {}).items():
            lines.extend([
                f"### {name}",
                f"- found: {source.get('found', False)}",
                f"- status: {source.get('status', 'MISSING')}",
                f"- report_path: {source.get('report_path', 'MISSING')}",
            ])
        (output_dir / "STUDENT_RESEARCH_CONTRACT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
