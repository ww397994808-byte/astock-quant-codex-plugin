from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager
from services.paper_policy_advice import advice_for_failed_metrics


class StudentControlCenterService:
    """Read the latest learner evidence and produce one next-step dashboard."""

    def run(
        self,
        workflow: str | None = None,
        promotion: str | None = None,
        qmt_dashboard: str | None = None,
        session_id: str | None = None,
    ) -> TaskResult:
        session_id = self._clean_label(session_id)
        workflow_source = self._load_explicit_or_latest(workflow, "student_workflow", "workflow_manifest.json", session_id)
        evidence_session = session_id or self._clean_label((workflow_source.get("data") or {}).get("session_id"))
        scoped_to_explicit_workflow = bool(workflow and not evidence_session)
        promotion_source = self._load_scoped_optional_any(
            promotion,
            "REPAIR_DSL_PROMOTION.json",
            evidence_session,
            skip_latest=scoped_to_explicit_workflow,
        )
        qmt = self._load_scoped_optional(
            qmt_dashboard,
            "qmt_readiness_dashboard",
            "QMT_READINESS_DASHBOARD.json",
            evidence_session,
            skip_latest=scoped_to_explicit_workflow,
        )
        backtest_assumption_card = self._backtest_assumption_card_for_workflow(workflow_source)
        paper_policy_card = self._paper_policy_card_for_workflow(workflow_source)
        policy_action_plan = self._policy_action_plan_for_workflow(workflow_source)
        decision = self._decide(workflow_source, promotion_source, qmt, policy_action_plan)
        action_cards = self._action_cards(
            decision,
            workflow_source,
            promotion_source,
            qmt,
            backtest_assumption_card,
            paper_policy_card,
            policy_action_plan,
        )
        payload = {
            "status": decision["status"],
            "current_stage": decision["current_stage"],
            "summary": decision["summary"],
            "next_action": decision["next_action"],
            "next_command": decision["next_command"],
            "safe_to_copy": self._is_concrete_command(decision["next_command"]),
            "learner_boundary": "本控制台只做导航；不会回测、不会连接 QMT、不会下单。",
            "session_id": evidence_session,
            "sources": {
                "student_workflow": self._source_meta(workflow_source),
                "repair_dsl_promotion": self._source_meta(promotion_source),
                "qmt_readiness_dashboard": self._source_meta(qmt),
                "backtest_assumption_card": self._source_meta(backtest_assumption_card),
                "paper_observation_policy_card": self._source_meta(paper_policy_card),
                "student_policy_action_plan": self._source_meta(policy_action_plan),
            },
            "backtest_assumption_card": backtest_assumption_card.get("data") if backtest_assumption_card.get("found") else {},
            "paper_observation_policy_card": paper_policy_card.get("data") if paper_policy_card.get("found") else {},
            "student_policy_action_plan": policy_action_plan.get("data") if policy_action_plan.get("found") else {},
            "action_cards": action_cards,
        }
        ctx = RunManager().create_run("student_control_center")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"READY_FOR_RESEARCH_STEP", "READY_FOR_QMT_REVIEW"} else "INVALID"
        warnings = [] if result_status == "VALID" else [payload["summary"]]
        return TaskResult(
            status=result_status,
            message=f"学员控制台生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _load_explicit_or_latest(self, explicit: str | None, prefix: str, filename: str, session_id: str = "") -> dict[str, Any]:
        if explicit:
            return self._load_explicit(explicit, filename)
        return self._load_latest(prefix, filename, session_id)

    def _load_explicit_or_latest_any(self, explicit: str | None, filename: str, session_id: str = "") -> dict[str, Any]:
        if explicit:
            return self._load_explicit(explicit, filename)
        return self._load_latest_any(filename, session_id)

    def _load_scoped_optional(
        self,
        explicit: str | None,
        prefix: str,
        filename: str,
        session_id: str,
        *,
        skip_latest: bool,
    ) -> dict[str, Any]:
        if explicit:
            return self._load_explicit(explicit, filename)
        if skip_latest:
            return {"found": False, "path": "", "run_dir": "", "data": {}}
        return self._load_latest(prefix, filename, session_id)

    def _load_scoped_optional_any(
        self,
        explicit: str | None,
        filename: str,
        session_id: str,
        *,
        skip_latest: bool,
    ) -> dict[str, Any]:
        if explicit:
            return self._load_explicit(explicit, filename)
        if skip_latest:
            return {"found": False, "path": "", "run_dir": "", "data": {}}
        return self._load_latest_any(filename, session_id)

    def _load_explicit(self, explicit: str, filename: str) -> dict[str, Any]:
        path = Path(explicit)
        if path.is_dir():
            path = path / filename
        if not path.exists():
            return {"found": False, "path": str(path), "run_dir": str(path.parent), "data": {"status": "MISSING"}}
        return self._read_json(path)

    def _load_latest(self, prefix: str, filename: str, session_id: str = "") -> dict[str, Any]:
        candidates = sorted(Path("reports").glob(f"{prefix}_*/{filename}"))
        return self._latest_matching(candidates, session_id)

    def _load_latest_any(self, filename: str, session_id: str = "") -> dict[str, Any]:
        candidates = sorted(Path("reports").glob(f"*/{filename}"))
        return self._latest_matching(candidates, session_id)

    def _latest_matching(self, candidates: list[Path], session_id: str) -> dict[str, Any]:
        for path in reversed(candidates):
            source = self._read_json(path)
            if not session_id or self._matches_session(source["data"], session_id):
                return source
        return {"found": False, "path": "", "run_dir": "", "data": {}}

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            data = {"status": "UNREADABLE", "error": str(exc)}
        return {"found": True, "path": str(path), "run_dir": str(path.parent), "data": data}

    def _paper_policy_card_for_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        if not workflow.get("found"):
            return {"found": False, "path": "", "run_dir": "", "data": {}}
        for step in workflow.get("data", {}).get("steps") or []:
            if step.get("step") != "paper":
                continue
            report_path = str(step.get("report_path") or "").strip()
            if not report_path:
                continue
            card_path = Path(report_path) / "paper_observation_policy_card.json"
            if card_path.exists():
                return self._read_json(card_path)
            return {"found": False, "path": str(card_path), "run_dir": report_path, "data": {}}
        return {"found": False, "path": "", "run_dir": "", "data": {}}

    def _backtest_assumption_card_for_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        if not workflow.get("found"):
            return {"found": False, "path": "", "run_dir": "", "data": {}}
        card_path = Path(workflow.get("run_dir") or "") / "BACKTEST_ASSUMPTION_CARD.json"
        if card_path.exists():
            return self._read_json(card_path)
        embedded = (workflow.get("data") or {}).get("backtest_assumption_card") or {}
        if embedded:
            return {
                "found": True,
                "path": str(card_path),
                "run_dir": str(card_path.parent),
                "data": embedded,
            }
        return {"found": False, "path": str(card_path), "run_dir": str(card_path.parent), "data": {}}

    def _policy_action_plan_for_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        if not workflow.get("found"):
            return {"found": False, "path": "", "run_dir": "", "data": {}}
        plan_path = Path(workflow.get("run_dir") or "") / "STUDENT_POLICY_ACTION_PLAN.json"
        if plan_path.exists():
            return self._read_json(plan_path)
        return {"found": False, "path": str(plan_path), "run_dir": str(plan_path.parent), "data": {}}

    def _matches_session(self, data: dict[str, Any], session_id: str) -> bool:
        return str(data.get("session_id") or "") == session_id

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _decide(self, workflow: dict[str, Any], promotion: dict[str, Any], qmt: dict[str, Any], policy_action_plan: dict[str, Any]) -> dict[str, str]:
        if not workflow["found"]:
            return {
                "status": "NO_WORKFLOW",
                "current_stage": "START_RESEARCH",
                "summary": "还没有找到学生工作流报告，先从 student-workflow 开始。",
                "next_action": "输入策略想法，跑一条完整新手研究流程。",
                "next_command": 'python3 cli.py student-workflow --idea "<策略想法>" --timeframe 1d --adjust point_in_time_qfq --auto-refine',
            }

        workflow_data = workflow["data"]
        workflow_status = str(workflow_data.get("status") or "UNKNOWN")
        repair_path = Path(workflow["run_dir"]) / "STUDENT_REPAIR_DSL.yaml"
        if workflow_status != "VALID" and repair_path.exists():
            symbol = workflow_data.get("symbol") or "<代码>"
            timeframe = workflow_data.get("timeframe") or "1d"
            adjust = workflow_data.get("adjust") or "point_in_time_qfq"
            return {
                "status": "READY_FOR_RESEARCH_STEP",
                "current_stage": "REPAIR_DSL_READY",
                "summary": "最新学生工作流未通过，但已生成结构化修复 DSL 分支。",
                "next_action": "先运行修复 DSL 分支，重新回测、审计、模拟盘和阶段门。",
                "next_command": f"python3 cli.py repair-dsl-backtest --dsl {repair_path} --symbol {symbol} --timeframe {timeframe} --adjust {adjust} --paper-observation --stage-check --auto-repair",
            }

        if workflow_status != "VALID" and policy_action_plan.get("found"):
            plan_data = policy_action_plan.get("data") or {}
            next_commands = [str(item) for item in plan_data.get("next_commands") or [] if item]
            command = next_commands[0] if next_commands else ""
            if command:
                return {
                    "status": "READY_FOR_RESEARCH_STEP",
                    "current_stage": "POLICY_ACTION_PLAN_READY",
                    "summary": "最新学生工作流未通过，但已生成模拟观察政策行动计划。",
                    "next_action": "按政策行动计划创建下一轮研究分支，重新跑完整 student-workflow。",
                    "next_command": command,
                }

        if workflow_status != "VALID":
            return {
                "status": "WORKFLOW_BLOCKED",
                "current_stage": "RESEARCH_NEEDS_REPAIR",
                "summary": "最新学生工作流没有通过，且还没有可直接执行的修复 DSL。",
                "next_action": "先打开 NEXT_ACTIONS.md 和 STUDENT_DIAGNOSTICS.md，按诊断补充退出、仓位、风险或观察数据。",
                "next_command": f"打开报告目录：{workflow['run_dir']}",
            }

        if promotion["found"]:
            promotion_path = promotion["path"]
            return {
                "status": "READY_FOR_QMT_REVIEW",
                "current_stage": "PROMOTION_READY_FOR_QMT_READONLY",
                "summary": "已找到 repair promotion，可以进入 QMT 只读和盘前证据包阶段。",
                "next_action": "先做 QMT 只读，再用 promotion 生成盘前证据包。",
                "next_command": f"python3 cli.py pretrade-package --promotion {promotion_path} --qmt-run-id <qmt_run_id>",
            }

        if qmt["found"]:
            qmt_data = qmt["data"]
            return {
                "status": "QMT_DASHBOARD_AVAILABLE",
                "current_stage": str(qmt_data.get("current_stage") or qmt_data.get("status") or "QMT_REVIEW"),
                "summary": str(qmt_data.get("summary") or "已找到 QMT dashboard，请先按其行动单处理。"),
                "next_action": "打开 QMT_NEXT_ACTIONS.md，先处理最上游阻断。",
                "next_command": f"打开报告目录：{qmt['run_dir']}",
            }

        return {
            "status": "WORKFLOW_READY_BUT_NO_QMT",
            "current_stage": "RESEARCH_VALID_NEEDS_QMT_READONLY",
            "summary": "学生工作流已通过，但还没有 QMT 准备度证据。",
            "next_action": "先运行 qmt-check 和阶段门，再进入盘前包。",
            "next_command": "python3 cli.py qmt-check",
        }

    def _action_cards(
        self,
        decision: dict[str, str],
        workflow: dict[str, Any],
        promotion: dict[str, Any],
        qmt: dict[str, Any],
        backtest_assumption_card: dict[str, Any],
        paper_policy_card: dict[str, Any],
        policy_action_plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cards = [
            {
                "id": "primary_next_step",
                "title": "下一步",
                "status": "pending" if decision["status"].startswith("READY") else "blocked",
                "action": decision["next_action"],
                "command": decision["next_command"],
                "safe_to_copy": self._is_concrete_command(decision["next_command"]),
                "why": decision["summary"],
            }
        ]
        if backtest_assumption_card.get("found"):
            card_data = backtest_assumption_card.get("data") or {}
            execution_model = card_data.get("execution_model") or {}
            learner_checks = card_data.get("learner_checks") or []
            check_titles = [
                str(item.get("title") or item.get("id") or "")
                for item in learner_checks
                if item.get("status") in {"REQUIRED", "BLOCKED", "WARN"}
            ]
            strategy_pattern = card_data.get("strategy_pattern") or "UNKNOWN"
            timeframe = card_data.get("timeframe") or "UNKNOWN"
            signal_timing = execution_model.get("signal_timing") or execution_model.get("signal_bar") or "UNKNOWN"
            fill_timing = execution_model.get("fill_timing") or execution_model.get("fill_bar") or "UNKNOWN"
            cards.append({
                "id": "backtest_assumption",
                "title": "回测假设卡",
                "status": card_data.get("status", "UNKNOWN"),
                "action": f"先核对 {strategy_pattern}/{timeframe} 的数据周期、撮合假设、A股规则和推进边界。",
                "command": f"打开报告文件：{backtest_assumption_card['path']}",
                "safe_to_copy": False,
                "why": (
                    f"strategy_pattern={strategy_pattern}; timeframe={timeframe}; "
                    f"execution={signal_timing} -> {fill_timing}"
                ),
                "learner_checks": check_titles,
                "promotion_policy": card_data.get("promotion_policy") or {},
            })
        if paper_policy_card.get("found"):
            card_data = paper_policy_card.get("data") or {}
            failed = [
                item.get("metric")
                for item in card_data.get("requirements") or []
                if item.get("status") == "FAIL"
            ]
            cards.append({
                "id": "paper_observation_policy",
                "title": "模拟观察政策卡",
                "status": card_data.get("status", "UNKNOWN"),
                "action": card_data.get("learner_message") or "查看模拟观察政策卡，逐项处理失败项。",
                "command": f"打开报告文件：{paper_policy_card['path']}",
                "safe_to_copy": False,
                "why": "失败项：" + "、".join(failed) if failed else "所有模拟观察政策项均通过。",
                "repair_hints": advice_for_failed_metrics(failed),
            })
        if policy_action_plan.get("found"):
            plan = policy_action_plan.get("data") or {}
            cards.append({
                "id": "student_policy_action_plan",
                "title": "模拟观察行动计划",
                "status": plan.get("status", "UNKNOWN"),
                "action": "按行动计划重跑下一轮研究分支；仍需重新审计、模拟观察和阶段门。",
                "command": (plan.get("next_commands") or [""])[0],
                "safe_to_copy": self._is_concrete_command((plan.get("next_commands") or [""])[0]),
                "why": "失败项：" + "、".join(plan.get("failed_metrics") or []) if plan.get("failed_metrics") else "模拟观察政策无失败项。",
                "repair_hints": plan.get("repair_hints") or [],
            })
        if workflow["found"]:
            cards.append({
                "id": "open_student_workflow",
                "title": "学生工作流报告",
                "status": workflow["data"].get("status", "UNKNOWN"),
                "action": "查看 STUDENT_WORKFLOW_SUMMARY.md、NEXT_ACTIONS.md 和 STUDENT_DIAGNOSTICS.md。",
                "command": f"打开报告目录：{workflow['run_dir']}",
                "safe_to_copy": False,
                "why": f"workflow status={workflow['data'].get('status', 'UNKNOWN')}",
            })
        if qmt["found"]:
            cards.append({
                "id": "open_qmt_next_actions",
                "title": "QMT 行动单",
                "status": qmt["data"].get("status", "UNKNOWN"),
                "action": "查看 QMT_NEXT_ACTIONS.md，先处理最上游阻断。",
                "command": f"打开报告目录：{qmt['run_dir']}",
                "safe_to_copy": False,
                "why": str(qmt["data"].get("summary") or ""),
            })
        return cards

    def _source_meta(self, source: dict[str, Any]) -> dict[str, Any]:
        data = source.get("data") or {}
        return {
            "found": bool(source.get("found")),
            "path": source.get("path", ""),
            "run_dir": source.get("run_dir", ""),
            "status": data.get("status", "MISSING"),
            "session_id": data.get("session_id", ""),
        }

    def _is_concrete_command(self, command: str) -> bool:
        return command.startswith("python3 ") and "<" not in command and ">" not in command

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_CONTROL_CENTER.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_action_cards.json").write_text(
            json.dumps(payload["action_cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Control Center",
            "",
            f"status: {payload['status']}",
            f"current_stage: {payload['current_stage']}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['learner_boundary']}",
            "",
            "## 下一步",
            f"- action: {payload['next_action']}",
            f"- command: `{payload['next_command']}`",
            "",
            "## 行动卡",
        ]
        for card in payload["action_cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- command: `{card['command']}`",
                f"- safe_to_copy: {card['safe_to_copy']}",
                f"- why: {card['why']}",
                "",
            ])
        lines.extend(["## 证据来源"])
        for name, source in payload["sources"].items():
            lines.extend([
                f"### {name}",
                f"- found: {source['found']}",
                f"- status: {source['status']}",
                f"- session_id: {source.get('session_id') or 'MISSING'}",
                f"- path: {source['path'] or 'MISSING'}",
            ])
        (output_dir / "STUDENT_CONTROL_CENTER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
