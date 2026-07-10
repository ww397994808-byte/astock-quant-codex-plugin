from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from backtest_plans.plan_builder import BacktestPlanBuilder
from core.result import TaskResult
from core.run_manager import RunManager
from data_acquisition.symbol_resolver import SymbolResolver
from intake.adaptive.answer_parser import AnswerParser
from intake.adaptive.clarification_policy import ClarificationPolicy
from intake.adaptive.question_tree import QuestionTree
from intake.adaptive.requirement_builder import RequirementBuilder
from intake.adaptive.research_readiness_checker import ResearchReadinessChecker


class StudentIdeaPreflightService:
    """Read-only idea quality gate before running the full student workflow."""

    def run(
        self,
        idea: str | None = None,
        timeframe: str | None = None,
        adjust: str = "point_in_time_qfq",
        session_id: str | None = None,
        case_id: str | None = None,
        auto_refine: bool = True,
    ) -> TaskResult:
        idea = str(idea or "").strip()
        session_id = self._clean_label(session_id)
        case_id = self._clean_label(case_id)
        if not idea:
            payload = self._missing_idea_payload()
        else:
            payload = self._payload(idea, timeframe, adjust, session_id, case_id, bool(auto_refine))

        ctx = RunManager().create_run("student_idea_preflight")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"READY_FOR_STUDENT_WORKFLOW", "NEEDS_CLARIFICATION"} else "INVALID"
        warnings = [item["message"] for item in payload.get("blockers", []) + payload.get("warnings", [])]
        return TaskResult(
            status=result_status,
            message=f"策略想法预检完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _payload(
        self,
        idea: str,
        timeframe: str | None,
        adjust: str,
        session_id: str,
        case_id: str,
        auto_refine: bool,
    ) -> dict[str, Any]:
        unsupported = SymbolResolver().detect_unsupported_asset(idea)
        fields = AnswerParser().parse(idea)
        fields.setdefault("adjust", adjust or "point_in_time_qfq")
        if timeframe:
            fields["timeframes"] = [timeframe]
        if fields.get("risk_preference") == "conservative" or fields.get("constraints", {}).get("trade_count_penalty"):
            fields.setdefault("objective", {"primary": "calmar", "trade_frequency": "low"})

        questions = ClarificationPolicy().top_questions(QuestionTree().next_questions(fields))
        score, _, missing = ResearchReadinessChecker().score(fields, user_confirmed=False)
        req = RequirementBuilder().build(idea, fields, score, score >= 70, [q for qid, q in questions if qid != "confirm"])
        plan = BacktestPlanBuilder().build(req)
        resolved_symbol, asset_type, symbol_error = self._resolve_symbol(idea, req.symbols)

        blockers = []
        warnings = []
        if unsupported:
            blockers.append(self._issue(
                "wrong_asset_version",
                "资产版本不匹配",
                f"检测到 {unsupported}，当前命令只适用于 A 股/ETF/指数。",
                "数字货币版本需要单独 workflow，不能套用 A 股/QMT/T+1/涨跌停假设。",
            ))
        if symbol_error and not unsupported:
            blockers.append(self._issue(
                "symbol_unresolved",
                "标的未识别",
                symbol_error,
                "先补充明确股票/ETF/指数名称或代码，例如：中国神华、601088.SH、红利ETF。",
            ))
        if score < 70:
            warnings.append(self._issue(
                "idea_incomplete",
                "策略想法不完整",
                f"完整度 {score}/100，缺少：{', '.join(missing) or '若干确认项'}。",
                "先回答澄清问题，或运行 intake-chat 生成确认摘要。",
            ))
        if not unsupported and not (score < 70 and not req.strategy_pattern):
            for item in plan.blockers:
                issue = self._issue("backtest_plan_blocker", "回测计划阻断", item, "先修改策略范式、周期或数据要求。")
                if score < 70 and not self._is_hard_plan_blocker(item):
                    warnings.append(issue)
                else:
                    blockers.append(issue)
            for item in plan.warnings:
                warnings.append(self._issue("backtest_plan_warning", "回测计划提醒", item, "可以研究，但推进模拟盘/QMT 前必须保留该提醒。"))
        if fields.get("adjust_warning"):
            warnings.append(self._issue("adjustment_warning", "复权风险提醒", fields["adjust_warning"], "建议改用 point_in_time_qfq 或 raw。"))
        blockers = self._dedupe_issues(blockers)
        warnings = self._dedupe_issues(warnings)

        can_run = not blockers and score >= 70 and bool(resolved_symbol)
        status = (
            "WRONG_ASSET_VERSION" if unsupported else
            "BLOCKED_BACKTEST_PLAN" if blockers else
            "READY_FOR_STUDENT_WORKFLOW" if can_run else
            "NEEDS_CLARIFICATION"
        )
        workflow_command = self._workflow_command(idea, resolved_symbol, req.timeframe or timeframe or "1d", req.data_adjustment, session_id, case_id, auto_refine) if can_run else ""
        intake_command = f"python3 cli.py intake-chat --idea {shlex.quote(idea)}"
        payload = {
            "status": status,
            "summary": self._summary(status, score, blockers, warnings),
            "idea": idea,
            "session_id": session_id,
            "case_id": case_id,
            "can_run_student_workflow": can_run,
            "safe_to_copy": bool(workflow_command),
            "next_command": workflow_command or intake_command,
            "alternative_command": intake_command,
            "hard_boundary": "student-idea-preflight 只检查想法质量；不会回测、不会连接 QMT、不会下单。",
            "parsed": {
                "symbols": req.symbols,
                "resolved_symbol": resolved_symbol,
                "asset_type": asset_type,
                "strategy_pattern": req.strategy_pattern,
                "timeframe": req.timeframe,
                "adjust": req.data_adjustment,
                "entry_logic": req.entry_logic,
                "exit_logic": req.exit_logic,
                "sizing_logic": req.sizing_logic,
                "risk_control": req.risk_control,
                "objective": req.objective,
                "live_intent": fields.get("live_intent", ""),
            },
            "completeness_score": score,
            "missing_fields": missing,
            "clarifying_questions": [q for qid, q in questions if qid != "confirm"],
            "backtest_plan": {
                "status": plan.status,
                "strategy_pattern": plan.strategy_pattern,
                "template_name": plan.template_name,
                "symbol_scope": plan.symbol_scope,
                "timeframe": plan.timeframe,
                "adjust": plan.adjust,
                "data_required": plan.data_required,
                "execution_model": plan.execution_model,
                "audit_required": plan.audit_required,
                "promotion_policy": plan.promotion_policy,
                "blockers": plan.blockers,
                "warnings": plan.warnings,
            },
            "blockers": blockers,
            "warnings": warnings,
            "cards": self._cards(status, score, resolved_symbol, plan, blockers, warnings, workflow_command, intake_command),
        }
        return payload

    def _missing_idea_payload(self) -> dict[str, Any]:
        question = "先输入一句策略想法，例如：中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%，先研究。"
        return {
            "status": "MISSING_IDEA",
            "summary": "还没有策略想法，不能预检。",
            "idea": "",
            "session_id": "",
            "case_id": "",
            "can_run_student_workflow": False,
            "safe_to_copy": False,
            "next_command": 'python3 cli.py student-idea-preflight --idea "<策略想法>"',
            "alternative_command": 'python3 cli.py intake-chat --idea "<策略想法>"',
            "hard_boundary": "student-idea-preflight 只检查想法质量；不会回测、不会连接 QMT、不会下单。",
            "parsed": {},
            "completeness_score": 0,
            "missing_fields": ["idea"],
            "clarifying_questions": [question],
            "backtest_plan": {},
            "blockers": [self._issue("missing_idea", "缺少策略想法", "没有 --idea。", question)],
            "warnings": [],
            "cards": [],
        }

    def _resolve_symbol(self, idea: str, symbols: list[str]) -> tuple[str, str, str]:
        resolver = SymbolResolver()
        candidates = symbols + [idea]
        for item in candidates:
            try:
                symbol, asset_type = resolver.resolve(item)
                return symbol, asset_type, ""
            except ValueError as exc:
                last_error = str(exc)
        return "", "", last_error if "last_error" in locals() else "无法识别标的。"

    def _workflow_command(
        self,
        idea: str,
        symbol: str,
        timeframe: str,
        adjust: str,
        session_id: str,
        case_id: str,
        auto_refine: bool,
    ) -> str:
        parts = [
            "python3",
            "cli.py",
            "student-workflow",
            "--idea",
            idea,
            "--symbol",
            symbol,
            "--timeframe",
            timeframe or "1d",
            "--adjust",
            adjust or "point_in_time_qfq",
        ]
        if auto_refine:
            parts.append("--auto-refine")
        if session_id:
            parts.extend(["--session-id", session_id])
        if case_id:
            parts.extend(["--case-id", case_id])
        return " ".join(shlex.quote(item) for item in parts)

    def _cards(
        self,
        status: str,
        score: int,
        resolved_symbol: str,
        plan: Any,
        blockers: list[dict[str, str]],
        warnings: list[dict[str, str]],
        workflow_command: str,
        intake_command: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "idea_quality",
                "title": "想法完整度",
                "status": "PASS" if score >= 70 else "WARN",
                "action": "可以进入 student-workflow。" if workflow_command else "先补充澄清问题。",
                "why": f"completeness_score={score}",
                "command": workflow_command or intake_command,
                "safe_to_copy": bool(workflow_command),
            },
            {
                "id": "asset_boundary",
                "title": "资产版本",
                "status": "PASS" if resolved_symbol else "BLOCK" if status == "WRONG_ASSET_VERSION" else "WARN",
                "action": f"已识别 {resolved_symbol}。" if resolved_symbol else "补充 A 股/ETF/指数标的，不要混入数字货币版本。",
                "why": "A股版本只允许 A 股/ETF/指数。",
                "command": intake_command,
                "safe_to_copy": False,
            },
            {
                "id": "backtest_plan",
                "title": "回测计划",
                "status": "PASS" if plan.status == "VALID" else "BLOCK" if blockers else "WARN",
                "action": (
                    "按该范式、周期和撮合假设进入研究。"
                    if plan.status == "VALID"
                    else "先处理回测计划阻断。"
                    if blockers
                    else "先补充澄清问题，再生成可信回测计划。"
                ),
                "why": f"pattern={plan.strategy_pattern}; timeframe={plan.timeframe}; blockers={len(blockers)}; warnings={len(warnings)}",
                "command": workflow_command or intake_command,
                "safe_to_copy": bool(workflow_command),
            },
        ]

    def _issue(self, issue_id: str, title: str, message: str, fix: str) -> dict[str, str]:
        return {"id": issue_id, "title": title, "message": message, "fix": fix}

    def _summary(self, status: str, score: int, blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> str:
        if status == "WRONG_ASSET_VERSION":
            return "这是非 A 股/ETF/指数想法，数字货币版本需要单独 workflow，不能混用本项目。"
        if status == "BLOCKED_BACKTEST_PLAN":
            return f"想法已解析，但有 {len(blockers)} 个阻断项，不能直接开跑。"
        if status == "NEEDS_CLARIFICATION":
            return f"想法还需要补充，完整度 {score}/100。"
        return f"想法可以进入 student-workflow；仍需后续未来函数审计、模拟观察和阶段门。提醒项 {len(warnings)} 个。"

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _is_hard_plan_blocker(self, message: str) -> bool:
        return any(token in message for token in ["不支持", "没有可用回测模板", "事件", "配对", "禁止"])

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
        (output_dir / "STUDENT_IDEA_PREFLIGHT.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_idea_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Idea Preflight",
            "",
            f"status: {payload['status']}",
            f"can_run_student_workflow: {payload['can_run_student_workflow']}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            f"completeness_score: {payload['completeness_score']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
            f"- command: `{payload['next_command']}`",
            f"- alternative: `{payload['alternative_command']}`",
            "",
            "## 解析结果",
        ]
        parsed = payload.get("parsed") or {}
        for key in ["resolved_symbol", "asset_type", "strategy_pattern", "timeframe", "adjust", "entry_logic", "exit_logic", "sizing_logic", "live_intent"]:
            lines.append(f"- {key}: {parsed.get(key, 'MISSING') or 'MISSING'}")
        lines.extend(["", "## 回测计划"])
        plan = payload.get("backtest_plan") or {}
        for key in ["status", "strategy_pattern", "template_name", "symbol_scope", "timeframe", "adjust"]:
            lines.append(f"- {key}: {plan.get(key, 'MISSING') or 'MISSING'}")
        lines.append(f"- data_required: {', '.join(plan.get('data_required') or []) or 'MISSING'}")
        lines.append(f"- audit_required: {', '.join(plan.get('audit_required') or []) or 'MISSING'}")
        lines.extend(["", "## 澄清问题"])
        lines.extend([f"- {question}" for question in payload.get("clarifying_questions") or []] or ["- NONE"])
        lines.extend(["", "## 阻断项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("blockers") or []] or ["- NONE"])
        lines.extend(["", "## 提醒项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("warnings") or []] or ["- NONE"])
        lines.extend(["", "## 卡片"])
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- why: {card['why']}",
                f"- command: `{card['command']}`",
                f"- safe_to_copy: {card['safe_to_copy']}",
                "",
            ])
        (output_dir / "STUDENT_IDEA_PREFLIGHT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
