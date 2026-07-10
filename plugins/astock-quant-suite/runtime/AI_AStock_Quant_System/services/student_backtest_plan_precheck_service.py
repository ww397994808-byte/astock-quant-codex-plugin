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
from strategy_patterns import StrategyArchetypeClassifier


class StudentBacktestPlanPrecheckService:
    """Beginner-facing precheck for strategy archetype, timeframe, and backtest assumptions."""

    def run(
        self,
        idea: str | None = None,
        timeframe: str | None = None,
        adjust: str = "point_in_time_qfq",
        strategy_pattern: str | None = None,
        session_id: str | None = None,
        case_id: str | None = None,
    ) -> TaskResult:
        idea = str(idea or "").strip()
        session_id = self._clean_label(session_id)
        case_id = self._clean_label(case_id)
        if not idea:
            payload = self._missing_idea_payload()
        else:
            payload = self._payload(idea, timeframe, adjust, strategy_pattern, session_id, case_id)

        ctx = RunManager().create_run("student_backtest_plan_precheck")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"BACKTEST_PLAN_READY", "NEEDS_CLARIFICATION"} else "INVALID"
        warnings = [item["message"] for item in payload.get("blockers", []) + payload.get("warnings", [])]
        return TaskResult(
            status=result_status,
            message=f"回测计划预检完成：{payload['status']}",
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
        strategy_pattern: str | None,
        session_id: str,
        case_id: str,
    ) -> dict[str, Any]:
        unsupported = SymbolResolver().detect_unsupported_asset(idea)
        fields = AnswerParser().parse(idea)
        if timeframe:
            fields["timeframes"] = [timeframe]
        if adjust:
            fields["adjust"] = adjust
        if strategy_pattern:
            fields["strategy_pattern"] = strategy_pattern

        questions = ClarificationPolicy().top_questions(QuestionTree().next_questions(fields))
        score, _, missing = ResearchReadinessChecker().score(fields, user_confirmed=False)
        req = RequirementBuilder().build(idea, fields, score, score >= 70, [q for qid, q in questions if qid != "confirm"])
        plan = BacktestPlanBuilder().build(req)
        spec = StrategyArchetypeClassifier().classify_requirement(req)
        resolved_symbol, asset_type, symbol_error = self._resolve_symbol(idea, req.symbols)

        blockers = []
        warnings = []
        if unsupported:
            blockers.append(self._issue(
                "wrong_asset_version",
                "资产版本不匹配",
                f"检测到 {unsupported}，当前回测计划只适用于 A 股/ETF/指数。",
                "数字货币版本需要单独 workflow，不能套用 A 股/QMT/T+1/涨跌停/复权假设。",
            ))
        if symbol_error and not unsupported:
            warnings.append(self._issue(
                "symbol_unresolved",
                "标的未识别",
                symbol_error,
                "回测计划可以先看范式，但正式 workflow 前必须补充明确 A 股/ETF/指数标的。",
            ))
        if score < 70:
            warnings.append(self._issue(
                "idea_incomplete",
                "策略信息不完整",
                f"完整度 {score}/100，缺少：{', '.join(missing) or '若干确认项'}。",
                "先补齐入场、出场、仓位、风险或目标，再把计划作为正式研究依据。",
            ))
        for item in plan.blockers:
            blockers.append(self._issue("backtest_plan_blocker", "回测计划阻断", item, "修改策略范式、周期、数据源或先补齐 point-in-time 数据。"))
        for item in plan.warnings:
            warnings.append(self._issue("backtest_plan_warning", "回测计划提醒", item, "保留该提醒；推进模拟盘/QMT 前必须通过完整审计和阶段门。"))
        blockers = self._dedupe_issues(blockers)
        warnings = self._dedupe_issues(warnings)

        status = (
            "WRONG_ASSET_VERSION" if unsupported else
            "BLOCKED_BACKTEST_PLAN" if blockers else
            "BACKTEST_PLAN_READY" if score >= 70 and plan.can_run_backtest else
            "NEEDS_CLARIFICATION"
        )
        workflow_command = self._workflow_command(idea, resolved_symbol, plan.timeframe, plan.adjust, session_id, case_id) if status == "BACKTEST_PLAN_READY" and resolved_symbol else ""
        intake_command = f"python3 cli.py intake-chat --idea {shlex.quote(idea)}"
        payload = {
            "status": status,
            "summary": self._summary(status, plan, score, blockers, warnings),
            "idea": idea,
            "session_id": session_id,
            "case_id": case_id,
            "safe_to_copy": bool(workflow_command),
            "next_command": workflow_command or intake_command,
            "alternative_command": intake_command,
            "hard_boundary": "student-backtest-plan-precheck 只检查回测计划和假设；不会回测、不会连接 QMT、不会下单，也不能替代完整 audit/stage-check。",
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
            },
            "archetype_spec": spec.to_dict(),
            "completeness_score": score,
            "missing_fields": missing,
            "clarifying_questions": [q for qid, q in questions if qid != "confirm"],
            "backtest_plan": plan.to_dict(),
            "assumption_checks": self._assumption_checks(plan),
            "blockers": blockers,
            "warnings": warnings,
            "cards": self._cards(status, plan, spec.to_dict(), blockers, warnings, workflow_command, intake_command),
        }
        return payload

    def _missing_idea_payload(self) -> dict[str, Any]:
        blocker = self._issue(
            "missing_idea",
            "缺少策略想法",
            "没有 --idea，无法判断策略范式、周期和回测模板。",
            "先输入一句策略想法，例如：中国神华周线布林下轨买，涨回中轨卖，偏稳健，每次买20%。",
        )
        return {
            "status": "MISSING_IDEA",
            "summary": "还没有策略想法，不能生成回测计划。",
            "idea": "",
            "session_id": "",
            "case_id": "",
            "safe_to_copy": False,
            "next_command": 'python3 cli.py student-backtest-plan-precheck --idea "<策略想法>"',
            "alternative_command": 'python3 cli.py intake-chat --idea "<策略想法>"',
            "hard_boundary": "student-backtest-plan-precheck 只检查回测计划和假设；不会回测、不会连接 QMT、不会下单。",
            "parsed": {},
            "archetype_spec": {},
            "completeness_score": 0,
            "missing_fields": ["idea"],
            "clarifying_questions": [blocker["fix"]],
            "backtest_plan": {},
            "assumption_checks": [],
            "blockers": [blocker],
            "warnings": [],
            "cards": [],
        }

    def _resolve_symbol(self, idea: str, symbols: list[str]) -> tuple[str, str, str]:
        resolver = SymbolResolver()
        last_error = ""
        for item in symbols + [idea]:
            try:
                symbol, asset_type = resolver.resolve(item)
                return symbol, asset_type, ""
            except ValueError as exc:
                last_error = str(exc)
        return "", "", last_error or "无法识别标的。"

    def _workflow_command(self, idea: str, symbol: str, timeframe: str, adjust: str, session_id: str, case_id: str) -> str:
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
            "--auto-refine",
        ]
        if session_id:
            parts.extend(["--session-id", session_id])
        if case_id:
            parts.extend(["--case-id", case_id])
        return " ".join(shlex.quote(item) for item in parts)

    def _assumption_checks(self, plan: Any) -> list[dict[str, Any]]:
        if not plan or not getattr(plan, "strategy_pattern", ""):
            return []
        checks = [
            {
                "id": "signal_execution_timing",
                "title": "信号和成交时点",
                "status": "REQUIRED",
                "detail": "信号在当前 K 线收盘确认，默认下一根 K 线开盘成交；禁止当前 K 线收盘价成交。",
            },
            {
                "id": "astock_trade_rules",
                "title": "A 股交易规则",
                "status": "REQUIRED",
                "detail": "必须检查 T+1、涨跌停、停牌、100 股、手续费、现金和持仓约束。",
            },
            {
                "id": "point_in_time_adjustment",
                "title": "复权时点",
                "status": "REQUIRED",
                "detail": "优先使用 point_in_time_qfq；普通 qfq/hfq 只能作为研究参考。",
            },
        ]
        if plan.timeframe in {"5m", "10m", "30m", "1h"}:
            checks.append({
                "id": "intraday_data_integrity",
                "title": "日内数据完整性",
                "status": "REQUIRED",
                "detail": "日内策略必须处理午休、缺失分钟/小时 K 线、交易日历和更长模拟观察。",
            })
        if plan.strategy_pattern == "grid":
            checks.append({
                "id": "grid_state_cash",
                "title": "网格状态和资金占用",
                "status": "REQUIRED",
                "detail": "必须跟踪每层持仓、可卖数量、可用现金和重复触发；不能假设无限资金。",
            })
        if plan.strategy_pattern in {"rotation", "stock_selection", "portfolio_rebalance"}:
            checks.append({
                "id": "multi_symbol_point_in_time",
                "title": "多标的时点一致",
                "status": "REQUIRED",
                "detail": "必须使用同步交易日历、可交易股票池和 point-in-time 排名/因子；不能使用未来成分股。",
            })
        if plan.strategy_pattern == "event_driven":
            checks.append({
                "id": "event_available_time",
                "title": "事件可获得时间",
                "status": "BLOCKING",
                "detail": "必须知道公告/事件在当时何时可见；没有该字段时不能回测为可信策略。",
            })
        return checks

    def _cards(
        self,
        status: str,
        plan: Any,
        spec: dict[str, Any],
        blockers: list[dict[str, str]],
        warnings: list[dict[str, str]],
        workflow_command: str,
        intake_command: str,
    ) -> list[dict[str, Any]]:
        command = workflow_command or intake_command
        return [
            {
                "id": "strategy_archetype",
                "title": "策略范式",
                "status": "PASS" if spec.get("template_name") else "BLOCK",
                "action": f"按 {spec.get('label') or plan.strategy_pattern} 使用模板 {spec.get('template_name')}。" if spec.get("template_name") else "先补充或改写策略范式。",
                "why": f"archetype={spec.get('archetype')}; qmt_allowed={spec.get('qmt_allowed')}",
                "command": command,
                "safe_to_copy": bool(workflow_command),
            },
            {
                "id": "timeframe_fit",
                "title": "数据周期匹配",
                "status": "PASS" if plan.timeframe in spec.get("allowed_timeframes", []) else "BLOCK",
                "action": f"使用 {plan.timeframe}；允许周期：{', '.join(spec.get('allowed_timeframes') or []) or '无'}。",
                "why": f"timeframe={plan.timeframe}; blockers={len(blockers)}",
                "command": command,
                "safe_to_copy": bool(workflow_command),
            },
            {
                "id": "execution_assumption",
                "title": "撮合假设",
                "status": "PASS" if not blockers else "BLOCK",
                "action": "信号收盘确认，下一根 K 线开盘成交，保留 A 股规则和复权审计。" if not blockers else "先处理阻断项，再谈回测。",
                "why": f"fill_bar={(plan.execution_model or {}).get('fill_bar', 'MISSING')}; warnings={len(warnings)}",
                "command": command,
                "safe_to_copy": bool(workflow_command),
            },
        ]

    def _summary(self, status: str, plan: Any, score: int, blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> str:
        if status == "WRONG_ASSET_VERSION":
            return "这是非 A 股/ETF/指数想法，不能套用本项目回测假设。"
        if status == "BLOCKED_BACKTEST_PLAN":
            return f"回测计划被阻断：pattern={plan.strategy_pattern}, timeframe={plan.timeframe}, blockers={len(blockers)}。"
        if status == "NEEDS_CLARIFICATION":
            return f"暂可生成草案，但想法完整度 {score}/100；补齐信息后再作为正式研究依据。"
        return f"回测计划可进入 student-workflow：pattern={plan.strategy_pattern}, timeframe={plan.timeframe}, warnings={len(warnings)}。"

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
        (output_dir / "STUDENT_BACKTEST_PLAN_PRECHECK.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_backtest_plan_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "backtest_plan_precheck.yaml").write_text(
            self._yaml_like(payload.get("backtest_plan") or {}), encoding="utf-8"
        )
        lines = [
            "# Student Backtest Plan Precheck",
            "",
            f"status: {payload['status']}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
            f"- command: `{payload['next_command']}`",
            f"- alternative: `{payload['alternative_command']}`",
            "",
            "## 回测计划",
        ]
        plan = payload.get("backtest_plan") or {}
        for key in ["status", "strategy_pattern", "template_name", "symbol_scope", "timeframe", "adjust"]:
            lines.append(f"- {key}: {plan.get(key, 'MISSING') or 'MISSING'}")
        lines.append(f"- data_required: {', '.join(plan.get('data_required') or []) or 'MISSING'}")
        lines.append(f"- audit_required: {', '.join(plan.get('audit_required') or []) or 'MISSING'}")
        execution_model = plan.get("execution_model") or {}
        lines.extend([
            "",
            "## 撮合假设",
            f"- signal_bar: {execution_model.get('signal_bar', 'MISSING')}",
            f"- fill_bar: {execution_model.get('fill_bar', 'MISSING')}",
            f"- price_basis: {execution_model.get('price_basis', 'MISSING')}",
            f"- t_plus_1: {execution_model.get('t_plus_1', 'MISSING')}",
            "",
            "## 假设检查",
        ])
        for item in payload.get("assumption_checks") or []:
            lines.append(f"- [{item['status']}] {item['title']}: {item['detail']}")
        if not payload.get("assumption_checks"):
            lines.append("- NONE")
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
        (output_dir / "STUDENT_BACKTEST_PLAN_PRECHECK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _yaml_like(self, payload: dict[str, Any]) -> str:
        try:
            import yaml

            return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        except Exception:
            return json.dumps(payload, ensure_ascii=False, indent=2)
