from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from core.result import TaskResult
from core.run_manager import RunManager
from data_acquisition.symbol_resolver import SymbolResolver
from strategy_compiler.action_compiler import ActionCompiler
from services.audit_service import AuditService
from services.backtest_service import BacktestService
from services.data_acquisition_service import DataAcquisitionService
from services.intake_service import IntakeService
from services.paper_service import PaperService
from services.paper_policy_advice import advice_for_failed_metrics
from services.qmt_check_service import QMTCheckService
from services.stage_check_service import StageCheckService


class StudentWorkflowService:
    """Run the beginner research workflow without manual run-id copying."""

    def run(
        self,
        *,
        idea: str,
        symbol: str | None = None,
        strategy: str | None = None,
        strategy_params: dict | None = None,
        data: str = "__auto_fetch__",
        timeframe: str = "1d",
        adjust: str = "point_in_time_qfq",
        include_qmt: bool = False,
        auto_refine: bool = False,
        max_refinements: int = 1,
        session_id: str | None = None,
        case_id: str | None = None,
    ) -> TaskResult:
        ctx = RunManager().create_run("student_workflow")
        attempts: list[dict] = []
        current_idea = idea
        session_id = self._clean_label(session_id)
        case_id = self._clean_label(case_id)
        max_attempts = max(1, int(max_refinements) + 1 if auto_refine else 1)

        for attempt_index in range(max_attempts):
            manifest = self._run_once(
                idea=current_idea,
                symbol=symbol,
                strategy=strategy,
                strategy_params=strategy_params or {},
                data=data,
                timeframe=timeframe,
                adjust=adjust,
                include_qmt=include_qmt,
                attempt=attempt_index + 1,
                session_id=session_id,
                case_id=case_id,
            )
            attempts.append(manifest)
            if manifest["status"] == "VALID" or not auto_refine:
                break
            actions = self._build_next_actions(manifest)
            refined_idea = self._suggest_idea(manifest, actions)
            if not refined_idea or refined_idea == current_idea:
                break
            current_idea = refined_idea

        final_manifest = dict(attempts[-1])
        if auto_refine:
            final_manifest["auto_refine"] = {
                "enabled": True,
                "max_refinements": max_refinements,
                "attempt_count": len(attempts),
                "original_idea": idea,
                "final_idea": final_manifest["idea"],
            }
            final_manifest["attempts"] = attempts
        return self._finish(ctx.output_dir, final_manifest)

    def _run_once(
        self,
        *,
        idea: str,
        symbol: str | None,
        strategy: str | None,
        strategy_params: dict,
        data: str,
        timeframe: str,
        adjust: str,
        include_qmt: bool,
        attempt: int,
        session_id: str,
        case_id: str,
    ) -> dict:
        steps: list[dict] = []
        original_symbol = symbol or ""

        symbol_result = self._resolve_symbol(symbol, idea)
        steps.append(self._step("resolve-symbol", symbol_result))
        resolved_symbol = symbol_result.artifacts.get("symbol", "")
        asset_type = symbol_result.artifacts.get("asset_type", "")
        if symbol_result.status == "INVALID" or not resolved_symbol:
            return self._manifest(idea, original_symbol, "", strategy or "", strategy_params, timeframe, adjust, steps, "INVALID", attempt, session_id, case_id)

        intake_idea = self._idea_for_intake(idea, original_symbol, resolved_symbol)

        intake = IntakeService().run(idea=intake_idea)
        steps.append(self._step("intake", intake))
        if intake.status == "INVALID" or not intake.run_id:
            return self._manifest(idea, resolved_symbol, asset_type, strategy or "", strategy_params, timeframe, adjust, steps, "INVALID", attempt, session_id, case_id)

        plan = self._load_plan(intake.run_id)
        strategy_result = self._select_strategy(idea=idea, explicit_strategy=strategy, plan=plan)
        steps.append(self._step("select-strategy", strategy_result))
        selected_strategy = strategy_result.artifacts.get("strategy", "")
        if strategy_result.status == "INVALID" or not selected_strategy:
            return self._manifest(idea, resolved_symbol, asset_type, selected_strategy, strategy_params, timeframe, adjust, steps, "INVALID", attempt, session_id, case_id)

        data_result = DataAcquisitionService().fetch(resolved_symbol, timeframe=timeframe, adjust=adjust)
        steps.append(self._step("fetch-data", data_result))

        backtest = BacktestService().run(selected_strategy, resolved_symbol, data, params=strategy_params, timeframe=timeframe, adjust=adjust)
        steps.append(self._step("backtest", backtest))
        if not backtest.run_id:
            return self._manifest(idea, resolved_symbol, asset_type, selected_strategy, strategy_params, timeframe, adjust, steps, "INVALID", attempt, session_id, case_id)

        audit = AuditService().run(backtest.run_id)
        steps.append(self._step("audit", audit))

        paper = PaperService().run(selected_strategy, resolved_symbol, data, params=strategy_params, timeframe=timeframe, adjust=adjust, plan_run_id=intake.run_id)
        steps.append(self._step("paper", paper))
        if not paper.run_id:
            return self._manifest(idea, resolved_symbol, asset_type, selected_strategy, strategy_params, timeframe, adjust, steps, "INVALID", attempt, session_id, case_id)

        qmt_run_id = None
        if include_qmt:
            qmt = QMTCheckService().run()
            qmt_run_id = qmt.run_id
            steps.append(self._step("qmt-check", qmt))

        stage = StageCheckService().run(run_id=paper.run_id, plan_run_id=intake.run_id, qmt_run_id=qmt_run_id)
        steps.append(self._step("stage-check", stage))

        final_status = "VALID" if all(step["status"] == "VALID" for step in steps) else "INVALID"
        return self._manifest(idea, resolved_symbol, asset_type, selected_strategy, strategy_params, timeframe, adjust, steps, final_status, attempt, session_id, case_id)

    def _resolve_symbol(self, symbol: str | None, idea: str) -> TaskResult:
        text = symbol or idea
        try:
            resolved_symbol, asset_type = SymbolResolver().resolve(text)
        except ValueError as exc:
            return TaskResult(
                "INVALID",
                "标的解析失败",
                warnings=[str(exc), "请使用例如：中国神华、神华、红利ETF、601088.SH 这样的标的表达。"],
                artifacts={"symbol": "", "asset_type": "", "input": text},
            )
        return TaskResult(
            "VALID",
            f"标的已解析：{text} -> {resolved_symbol}",
            artifacts={"symbol": resolved_symbol, "asset_type": asset_type, "input": text},
        )

    def _idea_for_intake(self, idea: str, original_symbol: str, resolved_symbol: str) -> str:
        if resolved_symbol in idea or (original_symbol and original_symbol in idea):
            return idea
        return f"{idea}，标的 {original_symbol or resolved_symbol}"

    def _load_plan(self, intake_run_id: str) -> dict:
        path = RunManager().resolve_run_dir(intake_run_id) / "backtest_plan.yaml"
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _select_strategy(self, *, idea: str, explicit_strategy: str | None, plan: dict) -> TaskResult:
        if explicit_strategy:
            return TaskResult(
                "VALID",
                f"使用用户指定策略：{explicit_strategy}",
                artifacts={"strategy": explicit_strategy, "selection_mode": "explicit"},
            )
        pattern = str(plan.get("strategy_pattern") or "")
        text = idea.lower()
        selected = ""
        reason = ""
        if pattern == "grid" or any(word in idea for word in ["网格", "分层"]):
            selected = "grid"
            reason = "想法或回测计划属于网格/分层交易，自动选择网格策略。"
        elif any(word in idea for word in ["布林", "低吸", "回撤", "跌破", "中轨"]):
            selected = "boll_mean_reversion"
            reason = "想法包含布林/低吸/回撤特征，自动选择布林低吸策略。"
        elif any(word in idea for word in ["红利", "股息", "高股息", "分红"]):
            selected = "dividend_drawdown"
            reason = "想法包含红利/股息特征，自动选择红利回撤策略。"
        elif any(word in idea for word in ["均线", "金叉", "死叉", "趋势"]) or any(word in text for word in ["ma", "moving average"]):
            selected = "ma_cross"
            reason = "想法包含均线/趋势特征，自动选择均线交叉策略。"
        elif pattern in {"timing", "swing"}:
            selected = "boll_mean_reversion"
            reason = "当前为单标的择时/波段，未指定策略时使用布林低吸作为保守默认。"
        else:
            return TaskResult(
                "INVALID",
                "当前策略范式没有可自动选择的已实现策略",
                warnings=[f"{pattern or 'unknown'} 暂无默认可运行策略；请先实现策略代码，或显式指定已注册策略。"],
                artifacts={"strategy": "", "selection_mode": "auto", "strategy_pattern": pattern},
            )
        return TaskResult(
            "VALID",
            reason,
            artifacts={"strategy": selected, "selection_mode": "auto", "strategy_pattern": pattern},
        )

    def _step(self, name: str, result: TaskResult) -> dict:
        return {
            "step": name,
            "status": result.status,
            "audit_status": result.audit_status or "",
            "run_id": result.run_id or "",
            "report_path": result.report_path or "",
            "warnings": list(result.warnings),
            "artifacts": result.artifacts,
        }

    def _manifest(
        self,
        idea: str,
        symbol: str,
        asset_type: str,
        strategy: str,
        strategy_params: dict,
        timeframe: str,
        adjust: str,
        steps: list[dict],
        status: str,
        attempt: int,
        session_id: str,
        case_id: str,
    ) -> dict:
        return {
            "status": status,
            "session_id": session_id,
            "case_id": case_id,
            "attempt": attempt,
            "idea": idea,
            "symbol": symbol,
            "asset_type": asset_type,
            "strategy": strategy,
            "strategy_params": strategy_params,
            "timeframe": timeframe,
            "adjust": adjust,
            "steps": steps,
        }

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _finish(self, output_dir: Path, manifest: dict) -> TaskResult:
        (output_dir / "workflow_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        next_actions = self._build_next_actions(manifest)
        manifest["next_actions"] = next_actions
        if manifest.get("auto_refine", {}).get("enabled"):
            manifest["auto_refine"]["final_suggested_idea"] = self._suggest_idea(manifest, next_actions)
        diagnostics = self._build_diagnostics(manifest)
        manifest["diagnostics"] = diagnostics
        assumption_card = self._backtest_assumption_card(manifest)
        if assumption_card:
            manifest["backtest_assumption_card"] = assumption_card
        policy_action_plan = self._paper_policy_action_plan(manifest)
        if policy_action_plan:
            manifest["paper_policy_action_plan"] = policy_action_plan
        experiments = self._run_candidate_experiments(manifest, diagnostics) if manifest.get("auto_refine", {}).get("enabled") else []
        if experiments:
            manifest["candidate_experiments"] = experiments
            repair_branch = self._build_repair_dsl_branch(manifest, experiments)
            if repair_branch:
                manifest["repair_dsl_branch"] = repair_branch
        (output_dir / "workflow_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self._write_next_actions(output_dir, manifest, next_actions)
        self._write_acceptance_checklist(output_dir, manifest, next_actions)
        self._write_diagnostics(output_dir, manifest, diagnostics)
        if assumption_card:
            self._write_backtest_assumption_card(output_dir, assumption_card)
        if policy_action_plan:
            self._write_policy_action_plan(output_dir, policy_action_plan)
        if experiments:
            self._write_candidate_experiments(output_dir, manifest, experiments)
        if manifest.get("repair_dsl_branch"):
            self._write_repair_dsl_branch(output_dir, manifest["repair_dsl_branch"])
        self._write_summary(output_dir, manifest)
        warnings = self._workflow_warnings(manifest["steps"])
        status = manifest["status"]
        return TaskResult(
            status=status,
            message=f"学生工作流完成：{status}",
            run_id=output_dir.name,
            report_path=str(output_dir),
            audit_status=status,
            warnings=warnings,
            artifacts={"workflow": manifest},
        )

    def _build_next_actions(self, manifest: dict) -> list[dict]:
        actions: list[dict] = []
        warnings = self._workflow_warnings(manifest["steps"])
        warning_text = "\n".join(warnings)
        if "无法识别标的" in warning_text:
            actions.append({
                "type": "fix_symbol",
                "title": "补充可识别的标的名称或代码",
                "detail": "在想法里写清楚股票/ETF，例如：中国神华、红利ETF，或使用 601088.SH。",
            })
        if "非 A 股标的/市场" in warning_text or "数字货币版本需要单独工作流" in warning_text:
            actions.append({
                "type": "wrong_asset_version",
                "title": "切换到正确资产版本",
                "detail": "当前是 A 股/QMT 工作流，只支持 A 股、ETF 和指数。数字货币策略需要单独的数字货币版本，不能混用 A 股数据、T+1、涨跌停和 QMT 假设。",
            })
        if "什么情况下卖" in warning_text:
            actions.append({
                "type": "fix_exit",
                "title": "补充卖出规则",
                "detail": "写清楚涨回均线/中轨卖出、达到目标收益卖出、止损卖出或持有固定时间退出。",
            })
        if "每次买多少" in warning_text:
            actions.append({
                "type": "fix_sizing",
                "title": "补充仓位规则",
                "detail": "写清楚每次买入比例、最大仓位、是否分批加仓，例如：每次买 30%，最大仓位 60%。",
            })
        if "最大回撤" in warning_text or "止损" in warning_text:
            actions.append({
                "type": "fix_risk",
                "title": "补充风险控制",
                "detail": "写清楚最大可接受回撤、止损线、是否允许连续加仓。",
            })
        if "模拟成交次数不足" in warning_text:
            actions.append({
                "type": "extend_paper",
                "title": "模拟盘观察证据不足",
                "detail": "当前样本触发交易太少，不能进入 QMT。换更长数据、调整策略参数，或改成更明确的触发条件后重新跑 student-workflow。",
            })
        if "Readiness 尚未达到 PAPER_READY" in warning_text:
            actions.append({
                "type": "readiness",
                "title": "Readiness 未达到模拟盘放行标准",
                "detail": "先看 readiness_report.md 和 paper_observation_report.md，补齐交易次数、样本长度、风险约束后再推进。",
            })
        if not actions:
            actions.append({
                "type": "review_stage",
                "title": "查看阶段报告",
                "detail": "打开 stage_gate_report.md，确认是否可以进入下一阶段；不要跳过 QMT 只读和 pretrade 检查。",
            })
        return actions

    def _workflow_warnings(self, steps: list[dict]) -> list[str]:
        warnings: list[str] = []
        for step in steps:
            if step["status"] == "INVALID":
                warnings.append(f"{step['step']} 未通过")
            warnings.extend(step.get("warnings") or [])
        return warnings

    def _write_summary(self, output_dir: Path, manifest: dict) -> None:
        lines = [
            "# Student Workflow Summary",
            "",
            f"status: {manifest['status']}",
            f"session_id: {manifest.get('session_id') or 'MISSING'}",
            f"case_id: {manifest.get('case_id') or 'MISSING'}",
            f"attempt: {manifest.get('attempt', 1)}",
            f"idea: {manifest['idea']}",
            f"symbol: {manifest['symbol']}",
            f"asset_type: {manifest.get('asset_type', '')}",
            f"strategy: {manifest['strategy']}",
            f"strategy_params: {manifest.get('strategy_params', {})}",
            f"timeframe: {manifest['timeframe']}",
            f"adjust: {manifest['adjust']}",
        ]
        auto_refine = manifest.get("auto_refine") or {}
        if auto_refine.get("enabled"):
            lines.extend([
                "",
                "## Auto Refine",
                f"- original idea: {auto_refine.get('original_idea', '')}",
                f"- final idea: {auto_refine.get('final_idea', '')}",
                f"- attempt count: {auto_refine.get('attempt_count', 1)}",
                "",
                "## Attempts",
            ])
            for attempt in manifest.get("attempts") or []:
                lines.append(f"- attempt {attempt.get('attempt')}: {attempt.get('status')} / {attempt.get('idea')}")
            lines.append("")
            lines.append("## Final Steps")
        else:
            lines.extend([
                "",
                "## Steps",
            ])
        for step in manifest["steps"]:
            lines.append(f"- {step['step']}: {step['status']} {step['run_id']}")
            if step.get("report_path"):
                lines.append(f"  report: {step['report_path']}")
        lines.append("")
        lines.append("## Next Action")
        invalid = next((step for step in manifest["steps"] if step["status"] == "INVALID"), None)
        if invalid:
            lines.append(f"- 先处理 `{invalid['step']}` 的阻断原因，不要进入后续实盘步骤。")
            for warning in invalid.get("warnings") or []:
                lines.append(f"- {warning}")
        else:
            lines.append("- 当前工作流未发现阻断项；继续看 stage_gate_report.md 决定下一步。")
        lines.append("- 详细修改建议见：NEXT_ACTIONS.md")
        lines.append("- 统一验收清单见：STUDENT_ACCEPTANCE_CHECKLIST.md")
        lines.append("- 问题分流诊断见：STUDENT_DIAGNOSTICS.md")
        if manifest.get("candidate_experiments"):
            lines.append("- 候选实验队列见：STUDENT_EXPERIMENTS.md")
        if manifest.get("repair_dsl_branch"):
            lines.append("- 修复动作 DSL 分支见：STUDENT_REPAIR_DSL.md")
        if manifest.get("backtest_assumption_card"):
            lines.append("- 回测假设卡见：BACKTEST_ASSUMPTION_CARD.md")
        lines.extend(
            [
                "",
                "说明：这个工作流用于教学研究和模拟观察，不代表允许真实下单。",
            ]
        )
        (output_dir / "STUDENT_WORKFLOW_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_next_actions(self, output_dir: Path, manifest: dict, actions: list[dict]) -> None:
        rerun_idea = self._suggest_idea(manifest, actions)
        lines = [
            "# Next Actions",
            "",
            f"status: {manifest['status']}",
            f"session_id: {manifest.get('session_id') or 'MISSING'}",
            f"case_id: {manifest.get('case_id') or 'MISSING'}",
            f"attempt: {manifest.get('attempt', 1)}",
        ]
        auto_refine = manifest.get("auto_refine") or {}
        if auto_refine.get("enabled"):
            lines.extend([
                "",
                "## 自动补全记录",
                f"- 原始想法：{auto_refine.get('original_idea', '')}",
                f"- 当前想法：{auto_refine.get('final_idea', '')}",
                f"- 已运行轮数：{auto_refine.get('attempt_count', 1)}",
                "",
                "## 需要先补的东西",
            ])
        else:
            lines.extend([
                "",
                "## 需要先补的东西",
            ])
        for action in actions:
            lines.append(f"- {action['title']}：{action['detail']}")
        lines.extend([
            "",
            "## 优先分流建议",
        ])
        for item in manifest.get("diagnostics") or []:
            lines.append(f"- {item['title']}：{item['recommendation']}")
        if manifest.get("backtest_assumption_card"):
            card = manifest["backtest_assumption_card"]
            lines.extend([
                "",
                "## 回测假设卡",
                f"- strategy_pattern: {card.get('strategy_pattern')}",
                f"- timeframe: {card.get('timeframe')}",
                f"- execution: signal={card.get('execution_model', {}).get('signal_bar')} / fill={card.get('execution_model', {}).get('fill_bar')}",
                "- 详细文件：BACKTEST_ASSUMPTION_CARD.md",
            ])
        if manifest.get("paper_policy_action_plan"):
            plan = manifest["paper_policy_action_plan"]
            lines.extend([
                "",
                "## 模拟观察政策行动计划",
                f"- status: {plan.get('status')}",
                f"- failed_metrics: {', '.join(plan.get('failed_metrics') or []) or 'NONE'}",
                "- 详细文件：STUDENT_POLICY_ACTION_PLAN.md",
            ])
        action_types = {item.get("type") for item in actions}
        if "wrong_asset_version" in action_types:
            lines.extend([
                "",
                "## 下一版想法示例",
                "",
                "不要在本 A 股/QMT 项目里继续重跑数字货币策略。",
                "",
                "## 重新运行",
                "",
                "当前工作流不提供重跑命令。请切换到单独的数字货币版本，或把想法改为 A 股、ETF、指数标的后重新开始。",
                "",
                "说明：资产版本不匹配时，不要跳到 QMT、pretrade 或 A 股回测命令。",
            ])
            (output_dir / "NEXT_ACTIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
        lines.extend([
            "",
            "## 下一版想法示例",
            "",
            rerun_idea,
            "",
            "## 重新运行",
            "",
            "```bash",
            f"python3 cli.py student-workflow --idea \"{rerun_idea}\" --timeframe {manifest['timeframe']} --adjust {manifest['adjust']}{self._session_cli_args(manifest, prefix_space=True)}",
            "```",
            "",
            "说明：如果仍然 INVALID，继续根据本文件和各阶段报告修改，不要跳到实盘。",
        ])
        (output_dir / "NEXT_ACTIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _run_candidate_experiments(self, manifest: dict, diagnostics: list[dict]) -> list[dict]:
        diagnostic_types = {item["type"] for item in diagnostics}
        if "increase_signal_frequency" not in diagnostic_types:
            return []
        strategy = str(manifest.get("strategy") or "")
        symbol = str(manifest.get("symbol") or "")
        if not strategy or not symbol:
            return []
        variants = self._candidate_specs(strategy)
        if not variants:
            return [{
                "variant_id": "manual_review",
                "status": "SKIPPED",
                "strategy": strategy,
                "params": {},
                "reason": "当前策略暂未配置自动候选实验；请先人工调整触发条件或策略范式。",
            }]
        baseline = self._paper_observation_for_manifest(manifest)
        baseline_trades = int(baseline.get("trade_count") or 0)
        min_trades = int((baseline.get("policy") or {}).get("min_trades") or 0)
        rows: list[dict] = []
        for idx, spec in enumerate(variants[:5], start=1):
            candidate_strategy = str(spec["strategy"])
            params = dict(spec.get("params") or {})
            variant_id = str(spec.get("variant_id") or f"{candidate_strategy}_candidate_{idx}")
            try:
                result = BacktestService().run(
                    candidate_strategy,
                    symbol,
                    "__auto_fetch__",
                    params=params,
                    prefix=f"student_candidate_{idx}",
                    timeframe=str(manifest.get("timeframe") or "1d"),
                    adjust=str(manifest.get("adjust") or "point_in_time_qfq"),
                )
                performance = result.artifacts.get("performance") or {}
                trade_count = int(performance.get("trade_count") or 0)
                max_drawdown = float(performance.get("max_drawdown") or 0.0)
                loss_analysis = self._candidate_loss_analysis(Path(result.report_path or ""), performance)
                repair_actions = self._repair_actions_for_candidate(candidate_strategy, loss_analysis, performance)
                repair_actions = self._annotate_repair_action_support(repair_actions, candidate_strategy)
                rows.append({
                    "variant_id": variant_id,
                    "candidate_type": spec.get("candidate_type", "parameter_tune"),
                    "status": result.status,
                    "audit_status": result.audit_status or "",
                    "strategy": candidate_strategy,
                    "params": params,
                    "reason": spec.get("reason", ""),
                    "run_id": result.run_id or "",
                    "report_path": result.report_path or "",
                    "trade_count": trade_count,
                    "baseline_trade_count": baseline_trades,
                    "min_trades": min_trades,
                    "trade_count_delta": trade_count - baseline_trades,
                    "max_drawdown": max_drawdown,
                    "total_return": float(performance.get("total_return") or 0.0),
                    "loss_analysis": loss_analysis,
                    "repair_actions": repair_actions,
                    "recommendation": self._experiment_recommendation(trade_count, baseline_trades, min_trades, result.audit_status or "", max_drawdown),
                })
            except Exception as exc:
                rows.append({
                    "variant_id": variant_id,
                    "candidate_type": spec.get("candidate_type", "parameter_tune"),
                    "status": "INVALID",
                    "audit_status": "INVALID",
                    "strategy": candidate_strategy,
                    "params": params,
                    "reason": str(exc),
                    "recommendation": "候选实验运行失败，先检查策略参数是否合法。",
                })
        return self._rank_candidate_experiments(rows, manifest)

    def _rank_candidate_experiments(self, rows: list[dict], manifest: dict) -> list[dict]:
        ranked = sorted(rows, key=self._experiment_sort_key, reverse=True)
        for rank, row in enumerate(ranked, start=1):
            row["rank"] = rank
            row["score"] = round(self._experiment_score(row), 6)
            row["next_research_idea"] = self._candidate_next_idea(manifest, row)
            row["next_command"] = self._candidate_next_command(manifest, row)
            if rank == 1:
                row["is_recommended"] = True
                row["recommendation"] = self._top_experiment_recommendation(row)
            else:
                row["is_recommended"] = False
        return ranked

    def _experiment_sort_key(self, row: dict) -> tuple:
        return (
            1 if row.get("audit_status") == "VALID" else 0,
            1 if int(row.get("min_trades") or 0) and int(row.get("trade_count") or 0) >= int(row.get("min_trades") or 0) else 0,
            int(row.get("trade_count_delta") or 0),
            int(row.get("trade_count") or 0),
            -abs(float(row.get("max_drawdown") or 0.0)),
            float(row.get("total_return") or 0.0),
        )

    def _experiment_score(self, row: dict) -> float:
        if row.get("audit_status") != "VALID":
            return -100.0
        min_trades = int(row.get("min_trades") or 0)
        trade_count = int(row.get("trade_count") or 0)
        trade_score = trade_count / min_trades if min_trades else 0.0
        return trade_score + 0.1 * int(row.get("trade_count_delta") or 0) - abs(float(row.get("max_drawdown") or 0.0)) + float(row.get("total_return") or 0.0)

    def _candidate_next_command(self, manifest: dict, row: dict) -> str:
        params = json.dumps(row.get("params") or {}, ensure_ascii=False, separators=(",", ":"))
        idea = str(row.get("next_research_idea") or manifest.get("idea") or "")
        return (
            f"python3 cli.py student-workflow --idea \"{idea}\" "
            f"--symbol {manifest.get('symbol')} --strategy {row.get('strategy')} "
            f"--strategy-params '{params}' --timeframe {manifest.get('timeframe')} "
            f"--adjust {manifest.get('adjust')} --auto-refine{self._session_cli_args(manifest, prefix_space=True)}"
        )

    def _candidate_next_idea(self, manifest: dict, row: dict) -> str:
        idea = str(manifest.get("idea") or "").strip()
        repairs = row.get("repair_actions") or []
        additions = [item.get("idea_addition", "") for item in repairs if item.get("idea_addition")]
        additions = [item for item in additions if item and item not in idea]
        if not additions:
            return idea
        return idea.rstrip("。") + "，" + "，".join(additions)

    def _top_experiment_recommendation(self, row: dict) -> str:
        base = row.get("recommendation") or ""
        if row.get("audit_status") != "VALID":
            return "当前没有可推荐候选：排名第一的候选也没有通过审计。"
        if int(row.get("min_trades") or 0) and int(row.get("trade_count") or 0) >= int(row.get("min_trades") or 0):
            if float(row.get("total_return") or 0.0) < 0:
                summary = (row.get("loss_analysis") or {}).get("summary", "下一轮应先检查亏损来源和风险约束。")
                return f"仅推荐作为研究分支：审计通过且成交样本达到最低要求，但收益为负，不能作为实盘候选。{summary}"
            return "推荐作为下一轮研究候选：审计通过且成交样本达到最低要求。继续跑完整 student-workflow、模拟盘和阶段门，不要直接进 QMT。"
        if int(row.get("trade_count_delta") or 0) > 0:
            return "暂列第一但仍未达标：它增加了成交样本，可继续围绕这组参数微调；不要进入 QMT。"
        return base or "暂列第一但没有解决核心阻断项；优先考虑换触发条件或策略范式。"

    def _candidate_specs(self, strategy: str) -> list[dict]:
        if strategy == "boll_mean_reversion":
            return [
                {"variant_id": "boll_signal_1", "candidate_type": "parameter_tune", "strategy": "boll_mean_reversion", "params": {"window": 20, "num_std": 1.8, "stop_loss": 0.08}, "reason": "放宽布林触发阈值，检查是否增加低吸信号。"},
                {"variant_id": "boll_signal_2", "candidate_type": "parameter_tune", "strategy": "boll_mean_reversion", "params": {"window": 15, "num_std": 1.8, "stop_loss": 0.08}, "reason": "缩短观察窗口，提高布林信号敏感度。"},
                {"variant_id": "boll_signal_3", "candidate_type": "parameter_tune", "strategy": "boll_mean_reversion", "params": {"window": 10, "num_std": 1.6, "stop_loss": 0.08}, "reason": "更敏感的短窗口低吸候选。"},
                {"variant_id": "switch_ma_cross", "candidate_type": "strategy_switch", "strategy": "ma_cross", "params": {"short_window": 5, "long_window": 20}, "reason": "布林低吸触发太少时，切换为均线趋势范式观察是否有更多信号。"},
                {"variant_id": "switch_grid", "candidate_type": "strategy_switch", "strategy": "grid", "params": {"grid_step": 0.02, "levels": 3, "layer_percent": 0.1}, "reason": "低波动标的信号稀疏时，尝试单标的网格范式；模拟盘门槛会更高。"},
            ]
        if strategy == "ma_cross":
            return [
                {"variant_id": "ma_signal_1", "candidate_type": "parameter_tune", "strategy": "ma_cross", "params": {"short_window": 5, "long_window": 20}, "reason": "标准均线交叉候选。"},
                {"variant_id": "ma_signal_2", "candidate_type": "parameter_tune", "strategy": "ma_cross", "params": {"short_window": 3, "long_window": 15}, "reason": "缩短均线窗口，提高趋势信号频率。"},
                {"variant_id": "switch_boll", "candidate_type": "strategy_switch", "strategy": "boll_mean_reversion", "params": {"window": 20, "num_std": 1.8, "stop_loss": 0.08}, "reason": "趋势信号太少时，切换为低吸反弹范式。"},
                {"variant_id": "switch_grid", "candidate_type": "strategy_switch", "strategy": "grid", "params": {"grid_step": 0.02, "levels": 3, "layer_percent": 0.1}, "reason": "趋势信号太少时，尝试网格范式。"},
            ]
        if strategy == "dividend_drawdown":
            return [
                {"variant_id": "dividend_signal_1", "candidate_type": "parameter_tune", "strategy": "dividend_drawdown", "params": {"drawdown_threshold": 0.04}, "reason": "放宽红利回撤阈值。"},
                {"variant_id": "dividend_signal_2", "candidate_type": "parameter_tune", "strategy": "dividend_drawdown", "params": {"drawdown_threshold": 0.03}, "reason": "进一步提高红利回撤触发频率。"},
                {"variant_id": "switch_boll", "candidate_type": "strategy_switch", "strategy": "boll_mean_reversion", "params": {"window": 20, "num_std": 1.8, "stop_loss": 0.08}, "reason": "红利回撤信号太少时，切换为布林低吸范式。"},
                {"variant_id": "switch_grid", "candidate_type": "strategy_switch", "strategy": "grid", "params": {"grid_step": 0.02, "levels": 3, "layer_percent": 0.1}, "reason": "红利标的波动较低时，尝试网格范式。"},
            ]
        return []

    def _paper_observation_for_manifest(self, manifest: dict) -> dict:
        paper = next((step for step in manifest["steps"] if step["step"] == "paper"), None)
        if not paper or not paper.get("report_path"):
            return {}
        return self._load_json(Path(paper["report_path"]) / "paper_observation.json")

    def _backtest_assumption_card(self, manifest: dict) -> dict:
        intake = next((step for step in manifest["steps"] if step["step"] == "intake"), None)
        if not intake or not intake.get("run_id"):
            return {}
        plan = self._load_plan(str(intake["run_id"]))
        if not plan:
            return {}
        pattern = str(plan.get("strategy_pattern") or "unknown")
        timeframe = str(plan.get("timeframe") or manifest.get("timeframe") or "1d")
        card = {
            "status": "VALID" if plan.get("status") == "VALID" and not plan.get("blockers") else "BLOCKED",
            "strategy_pattern": pattern,
            "template_name": plan.get("template_name"),
            "symbol_scope": plan.get("symbol_scope", ""),
            "symbol": manifest.get("symbol", ""),
            "asset_type": manifest.get("asset_type", ""),
            "timeframe": timeframe,
            "adjust": plan.get("adjust") or manifest.get("adjust"),
            "data_required": plan.get("data_required") or [],
            "execution_model": plan.get("execution_model") or {},
            "audit_required": plan.get("audit_required") or [],
            "promotion_policy": plan.get("promotion_policy") or {},
            "blockers": plan.get("blockers") or [],
            "warnings": plan.get("warnings") or [],
            "learner_checks": self._assumption_learner_checks(pattern, timeframe, plan),
            "hard_boundary": "这张卡只说明本次回测采用的假设；任何假设不满足，都必须回到研究阶段，不能推进 QMT 或实盘。",
        }
        card["can_run_backtest"] = card["status"] == "VALID" and bool(card["template_name"])
        card["can_approach_qmt_readonly"] = bool((card["promotion_policy"] or {}).get("qmt_allowed")) and card["can_run_backtest"]
        return card

    def _assumption_learner_checks(self, pattern: str, timeframe: str, plan: dict) -> list[dict]:
        checks = [
            {
                "id": "signal_timing",
                "title": "信号与成交错开",
                "detail": "信号在当前 K 线收盘确认，默认下一根 K 线开盘成交；禁止同 K 线收盘价成交。",
                "required": True,
            },
            {
                "id": "astock_rules",
                "title": "A 股交易规则",
                "detail": "回测必须检查 T+1、涨跌停、最小交易单位、手续费、现金和持仓约束。",
                "required": True,
            },
            {
                "id": "point_in_time_adjust",
                "title": "复权和数据时点",
                "detail": "优先使用 point_in_time_qfq；普通 qfq/hfq 最多只能作为研究参考，不能推进实盘。",
                "required": True,
            },
        ]
        if timeframe in {"5m", "10m", "30m", "1h"}:
            checks.append({
                "id": "intraday_data",
                "title": "日内数据完整性",
                "detail": "日内策略必须处理午休、交易日历、缺失分钟/小时 K 线，并经过更长模拟观察。",
                "required": True,
            })
        if pattern == "grid":
            checks.append({
                "id": "grid_state",
                "title": "网格状态与资金占用",
                "detail": "网格必须跟踪分层持仓、可用资金、T+1 可卖数量和重复成交，不允许假设无限资金。",
                "required": True,
            })
        if pattern in {"rotation", "stock_selection", "portfolio_rebalance"}:
            checks.append({
                "id": "multi_symbol_point_in_time",
                "title": "多标的时点一致",
                "detail": "多标的策略必须有同步交易日历、可交易股票池和 point-in-time 排名/因子，不能用未来成分股。",
                "required": True,
            })
        if not (plan.get("promotion_policy") or {}).get("qmt_allowed"):
            checks.append({
                "id": "qmt_promotion_blocked",
                "title": "第一阶段不允许 QMT",
                "detail": "该策略范式当前只允许研究，不允许进入 QMT 只读或盘前流程。",
                "required": True,
            })
        return checks

    def _paper_policy_card_for_manifest(self, manifest: dict) -> dict:
        paper = next((step for step in manifest["steps"] if step["step"] == "paper"), None)
        if not paper or not paper.get("report_path"):
            return {}
        card_path = Path(paper["report_path"]) / "paper_observation_policy_card.json"
        card = self._load_json(card_path)
        if card:
            card["path"] = str(card_path)
        return card

    def _paper_policy_action_plan(self, manifest: dict) -> dict:
        card = self._paper_policy_card_for_manifest(manifest)
        if not card:
            return {}
        failed_metrics = [
            str(item.get("metric"))
            for item in card.get("requirements") or []
            if item.get("status") == "FAIL" and item.get("metric")
        ]
        hints = advice_for_failed_metrics(failed_metrics)
        actions = self._paper_policy_research_actions(manifest, failed_metrics)
        return {
            "status": "VALID" if not failed_metrics else "NEEDS_RESEARCH_REPAIR",
            "policy_card_path": card.get("path", ""),
            "failed_metrics": failed_metrics,
            "repair_hints": hints,
            "research_actions": actions,
            "next_commands": [item["command"] for item in actions if item.get("command")],
            "hard_boundary": "这些动作只创建下一轮研究分支；必须重新回测、未来函数审核、模拟观察和阶段门，不能直接进入 QMT 或实盘。",
        }

    def _paper_policy_research_actions(self, manifest: dict, failed_metrics: list[str]) -> list[dict]:
        if not failed_metrics:
            return [{
                "metric": "all_passed",
                "title": "模拟观察政策已通过",
                "detail": "下一步只允许进入 QMT 只读检查；仍不代表可以真实下单。",
                "command": f"python3 cli.py qmt-config-status{self._session_cli_args(manifest, prefix_space=True)}",
            }]
        actions: list[dict] = []
        if "observed_days" in failed_metrics:
            actions.append({
                "metric": "observed_days",
                "title": "补足观察窗口",
                "detail": "换更长历史数据或延长模拟观察期，再重新跑完整 student-workflow。",
                "command": self._policy_rerun_command(manifest, "补充更长历史数据，先满足模拟观察期要求"),
            })
        if "trade_count" in failed_metrics:
            actions.append({
                "metric": "trade_count",
                "title": "增加有效成交样本",
                "detail": "优先放宽触发阈值、缩短观察窗口，或切换到更匹配的策略范式；所有候选都要重新审计。",
                "command": self._policy_rerun_command(manifest, "调整触发条件和参数，目标是增加有效成交样本"),
            })
        if "completed_rounds" in failed_metrics:
            actions.append({
                "metric": "completed_rounds",
                "title": "补完整买卖闭环",
                "detail": "补充退出规则、止盈止损或持有天数退出，避免只有单边买入/卖出。",
                "command": self._policy_rerun_command(manifest, "补充明确退出规则，至少形成完整买卖回合"),
            })
        if "max_drawdown" in failed_metrics:
            actions.append({
                "metric": "max_drawdown",
                "title": "先降低回撤",
                "detail": "降低单次仓位、收紧止损或加入暂停交易规则，重新跑模拟观察。",
                "command": self._policy_rerun_command(manifest, "降低单次仓位并收紧止损，先控制最大回撤"),
            })
        if "rejected_order_rate" in failed_metrics:
            actions.append({
                "metric": "rejected_order_rate",
                "title": "修正无法成交的委托假设",
                "detail": "检查价格、数量、T+1、涨跌停、现金和仓位约束；被拒委托不能算交易证据。",
                "command": "python3 cli.py stage-check --run-id latest",
            })
        return actions

    def _policy_rerun_command(self, manifest: dict, addition: str) -> str:
        idea = str(manifest.get("idea") or "").strip().rstrip("。")
        if addition and addition not in idea:
            idea = f"{idea}，{addition}"
        strategy_args = ""
        if manifest.get("strategy"):
            strategy_args += f" --strategy {manifest.get('strategy')}"
        if manifest.get("strategy_params"):
            params = json.dumps(manifest.get("strategy_params") or {}, ensure_ascii=False, separators=(",", ":"))
            strategy_args += f" --strategy-params '{params}'"
        return (
            f"python3 cli.py student-workflow --idea \"{idea}\" --symbol {manifest.get('symbol')} "
            f"--timeframe {manifest.get('timeframe')} --adjust {manifest.get('adjust')}{strategy_args} "
            f"--auto-refine{self._session_cli_args(manifest, prefix_space=True)}"
        )

    def _experiment_recommendation(self, trade_count: int, baseline: int, min_trades: int, audit_status: str, max_drawdown: float) -> str:
        if audit_status != "VALID":
            return "不要采用：候选没有通过审计。"
        if min_trades and trade_count >= min_trades:
            return "可作为下一轮研究候选：成交样本达到最低要求，继续跑模拟盘和阶段门。"
        if trade_count > baseline:
            return "有改善但仍不足：信号变多了，继续围绕这个方向微调，不要进入 QMT。"
        if abs(max_drawdown) > 0.2:
            return "不优先：回撤压力偏大，先降低仓位或收紧风险规则。"
        return "改善不明显：没有解决成交样本不足，换触发条件或策略范式。"

    def _write_candidate_experiments(self, output_dir: Path, manifest: dict, experiments: list[dict]) -> None:
        lines = [
            "# Student Candidate Experiments",
            "",
            f"status: {manifest['status']}",
            f"strategy: {manifest.get('strategy', '')}",
            f"symbol: {manifest.get('symbol', '')}",
            "",
            "## 推荐结论",
        ]
        top = next((row for row in experiments if row.get("is_recommended")), experiments[0] if experiments else None)
        if top:
            lines.extend([
                f"- 推荐候选：{top.get('variant_id')}，score={top.get('score')}",
                f"- 推荐理由：{top.get('recommendation')}",
                "- 下一轮命令：",
                "```bash",
                str(top.get("next_command") or ""),
                "```",
            ])
        lines.extend([
            "",
            "## 候选实验",
        ])
        for row in experiments:
            lines.extend([
                f"- #{row.get('rank', '')} {row.get('variant_id')}: {row.get('status')} / audit={row.get('audit_status', '')} / score={row.get('score', '')}",
                f"  - type: {row.get('candidate_type', '')}",
                f"  - strategy: {row.get('strategy')}",
                f"  - params: {row.get('params')}",
                f"  - reason: {row.get('reason', '')}",
            ])
            if "trade_count" in row:
                lines.append(f"  - trades: {row.get('trade_count')}，baseline: {row.get('baseline_trade_count')}，minimum: {row.get('min_trades')}")
                lines.append(f"  - return: {row.get('total_return')}，max_drawdown: {row.get('max_drawdown')}")
            loss_analysis = row.get("loss_analysis") or {}
            if loss_analysis:
                lines.append(f"  - loss_analysis: {loss_analysis.get('summary')}")
                lines.append(f"  - completed_rounds: {loss_analysis.get('completed_rounds')}，losing_rounds: {loss_analysis.get('losing_rounds')}，fee_drag: {loss_analysis.get('fee_drag_pct_of_loss')}")
            repair_actions = row.get("repair_actions") or []
            if repair_actions:
                lines.append("  - repair_actions:")
                for action in repair_actions:
                    lines.append(f"    - {action.get('title')}：{action.get('detail')}")
                    lines.append(f"      - support: {action.get('implementation_status')}；{action.get('support_note')}")
                lines.append(f"  - next_research_idea: {row.get('next_research_idea')}")
            if row.get("report_path"):
                lines.append(f"  - report: {row.get('report_path')}")
            lines.append(f"  - 建议：{row.get('recommendation') or row.get('reason', '')}")
        lines.extend([
            "",
            "## 使用原则",
            "- 候选实验只解决研究方向，不代表可实盘。",
            "- 优先看审计是否 VALID，再看成交样本是否达到模拟盘最低要求。",
            "- 如果候选只是提高收益但没有增加有效样本，不应推进 QMT。",
            "- repair_actions 写进 idea 只代表下一轮研究假设；只有 `implemented_in_current_run=true` 的动作才表示已由当前回测代码直接执行。",
            "- `component_available_requires_compiled_strategy` 表示组件存在，但需要进入策略编译/实现分支后重新审计。",
        ])
        (output_dir / "STUDENT_EXPERIMENTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_policy_action_plan(self, output_dir: Path, plan: dict) -> None:
        (output_dir / "STUDENT_POLICY_ACTION_PLAN.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Policy Action Plan",
            "",
            f"status: {plan.get('status')}",
            f"policy_card_path: {plan.get('policy_card_path') or 'MISSING'}",
            "",
            "## 失败指标",
        ]
        lines.extend([f"- {item}" for item in plan.get("failed_metrics") or []] or ["- NONE"])
        lines.extend(["", "## 修复提示"])
        for hint in plan.get("repair_hints") or []:
            lines.append(f"- {hint.get('metric')}：{hint.get('advice')}")
        if not plan.get("repair_hints"):
            lines.append("- NONE")
        lines.extend(["", "## 下一轮研究动作"])
        for action in plan.get("research_actions") or []:
            lines.extend([
                f"### {action.get('title')}",
                f"- metric: {action.get('metric')}",
                f"- detail: {action.get('detail')}",
                f"- command: `{action.get('command')}`",
                "",
            ])
        lines.extend([
            "## 硬边界",
            f"- {plan.get('hard_boundary')}",
        ])
        (output_dir / "STUDENT_POLICY_ACTION_PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_backtest_assumption_card(self, output_dir: Path, card: dict) -> None:
        (output_dir / "BACKTEST_ASSUMPTION_CARD.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Backtest Assumption Card",
            "",
            f"status: {card.get('status')}",
            f"strategy_pattern: {card.get('strategy_pattern')}",
            f"template_name: {card.get('template_name')}",
            f"symbol_scope: {card.get('symbol_scope')}",
            f"symbol: {card.get('symbol')}",
            f"asset_type: {card.get('asset_type')}",
            f"timeframe: {card.get('timeframe')}",
            f"adjust: {card.get('adjust')}",
            f"can_run_backtest: {card.get('can_run_backtest')}",
            f"can_approach_qmt_readonly: {card.get('can_approach_qmt_readonly')}",
            "",
            "## Data Required",
        ]
        lines.extend([f"- {item}" for item in card.get("data_required") or []] or ["- MISSING"])
        lines.extend([
            "",
            "## Execution Model",
        ])
        for key, value in (card.get("execution_model") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.extend([
            "",
            "## Audit Required",
        ])
        lines.extend([f"- {item}" for item in card.get("audit_required") or []] or ["- MISSING"])
        lines.extend([
            "",
            "## Promotion Policy",
        ])
        for key, value in (card.get("promotion_policy") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.extend([
            "",
            "## Learner Checks",
        ])
        for item in card.get("learner_checks") or []:
            lines.extend([
                f"### {item.get('title')}",
                f"- id: {item.get('id')}",
                f"- required: {item.get('required')}",
                f"- detail: {item.get('detail')}",
            ])
        lines.extend(["", "## Blockers"])
        lines.extend([f"- {item}" for item in card.get("blockers") or []] or ["- NONE"])
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {item}" for item in card.get("warnings") or []] or ["- NONE"])
        lines.extend([
            "",
            "## Hard Boundary",
            f"- {card.get('hard_boundary')}",
        ])
        (output_dir / "BACKTEST_ASSUMPTION_CARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _build_repair_dsl_branch(self, manifest: dict, experiments: list[dict]) -> dict:
        top = next((row for row in experiments if row.get("is_recommended")), None)
        if not top:
            return {}
        compiler_actions = [item.get("compiler_action") for item in top.get("repair_actions") or [] if item.get("requires_strategy_compiler") and item.get("compiler_action")]
        compiler_actions = list(dict.fromkeys(compiler_actions))
        if not compiler_actions:
            return {}
        base_dsl = self._base_dsl_for_candidate(manifest, top)
        compiled_dsl, compile_reports = ActionCompiler().compile_actions(base_dsl, compiler_actions)
        compiled_dsl["session_id"] = manifest.get("session_id", "")
        compiled_dsl["case_id"] = manifest.get("case_id", "")
        return {
            "source_variant_id": top.get("variant_id"),
            "source_strategy": top.get("strategy"),
            "session_id": manifest.get("session_id", ""),
            "case_id": manifest.get("case_id", ""),
            "status": "VALID" if all(item["status"] == "VALID" for item in compile_reports) else "INVALID",
            "base_dsl": base_dsl,
            "compiler_actions": compiler_actions,
            "compile_reports": compile_reports,
            "compiled_dsl": compiled_dsl,
            "note": "这是结构化研究分支，不代表当前 student-workflow 直连策略已经执行这些组件；必须用编译策略分支重新回测、审计、模拟盘和阶段检查。",
        }

    def _base_dsl_for_candidate(self, manifest: dict, candidate: dict) -> dict:
        strategy = candidate.get("strategy")
        symbol = manifest.get("symbol")
        if strategy == "ma_cross":
            return {
                "pattern": "timing",
                "symbols": [symbol],
                "entry": {"type": "MADeviationEntry", "params": {"window": 20, "deviation": 0.04}},
                "exit": [{"type": "FixedTakeProfitExit", "params": {"take_profit": 0.08}}],
                "filters": [],
                "sizing": {"type": "FixedPercentSizing", "params": {"percent": 0.5}},
                "market": "A股",
                "timeframe": manifest.get("timeframe"),
                "adjust": manifest.get("adjust"),
            }
        return {
            "pattern": "swing",
            "symbols": [symbol],
            "entry": {"type": "BollLowerEntry", "params": {"window": 20, "num_std": 2.0}},
            "exit": [{"type": "BollMiddleExit", "params": {"window": 20}}],
            "filters": [],
            "sizing": {"type": "FixedPercentSizing", "params": {"percent": 0.5}},
            "market": "A股",
            "timeframe": manifest.get("timeframe"),
            "adjust": manifest.get("adjust"),
        }

    def _write_repair_dsl_branch(self, output_dir: Path, branch: dict) -> None:
        (output_dir / "STUDENT_REPAIR_DSL.json").write_text(json.dumps(branch, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "STUDENT_REPAIR_DSL.yaml").write_text(yaml.safe_dump(branch.get("compiled_dsl") or {}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        compiled_dsl = branch.get("compiled_dsl") or {}
        symbol = (compiled_dsl.get("symbols") or [""])[0]
        timeframe = compiled_dsl.get("timeframe") or "1d"
        adjust = compiled_dsl.get("adjust") or "point_in_time_qfq"
        run_command = (
            f"python3 cli.py repair-dsl-backtest --dsl {output_dir / 'STUDENT_REPAIR_DSL.yaml'} "
            f"--symbol {symbol} --timeframe {timeframe} --adjust {adjust} --paper-observation --stage-check --auto-repair"
        )
        lines = [
            "# Student Repair DSL Branch",
            "",
            f"status: {branch.get('status')}",
            f"session_id: {branch.get('session_id') or 'MISSING'}",
            f"case_id: {branch.get('case_id') or 'MISSING'}",
            f"source_variant_id: {branch.get('source_variant_id')}",
            f"source_strategy: {branch.get('source_strategy')}",
            "",
            "## 下一步命令",
            f"`{run_command}`",
            "",
            "## 编译动作",
        ]
        for report in branch.get("compile_reports") or []:
            lines.append(f"- {report.get('action')}: {report.get('status')} {report.get('error')}")
        lines.extend([
            "",
            "## 产物",
            "- STUDENT_REPAIR_DSL.yaml：编译后的策略 DSL",
            "- STUDENT_REPAIR_DSL.json：包含 base_dsl、compile_reports 和 compiled_dsl 的完整结构",
            "- repair-dsl-backtest 会重新生成 audit_report.md、future_leak_report.md、readiness_report.md、paper_observation_report.md、stage_gate_report.md 和 repair_dsl_run_report.md",
            "- repair_dsl_next_actions.md：如果 0 成交或模拟盘不过，会给出下一步 DSL 调整建议",
            "- repair_dsl_auto_repair.md：如果启用 --auto-repair，会自动生成小步修订候选并复跑排序",
            "",
            "## 边界",
            f"- {branch.get('note')}",
            "- 只有 repair-dsl-backtest 跑完且审计 VALID 后，这个 DSL 分支才算有第一层证据。",
        ])
        (output_dir / "STUDENT_REPAIR_DSL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _session_cli_args(self, manifest: dict, prefix_space: bool = False) -> str:
        parts = []
        if manifest.get("session_id"):
            parts.extend(["--session-id", str(manifest["session_id"])])
        if manifest.get("case_id"):
            parts.extend(["--case-id", str(manifest["case_id"])])
        text = " ".join(parts)
        if prefix_space and text:
            return " " + text
        return text

    def _candidate_loss_analysis(self, report_path: Path, performance: dict) -> dict:
        total_return = float(performance.get("total_return") or 0.0)
        if total_return >= 0:
            return {}
        trades = self._load_csv(report_path / "trades.csv")
        rounds = self._completed_trade_rounds(trades)
        pnl_values = [item["pnl"] for item in rounds]
        losing = [value for value in pnl_values if value < 0]
        winning = [value for value in pnl_values if value > 0]
        total_fee = float(performance.get("total_fee") or 0.0)
        initial_cash = float(performance.get("initial_cash") or 0.0)
        final_equity = float(performance.get("final_equity") or 0.0)
        total_pnl = final_equity - initial_cash if initial_cash else sum(pnl_values)
        fee_drag = round(total_fee / abs(total_pnl), 6) if total_pnl else 0.0
        causes: list[str] = []
        if rounds and len(losing) == len(rounds):
            causes.append("所有已完成买卖回合均亏损")
        if fee_drag >= 0.3:
            causes.append("交易成本占亏损比例偏高")
        if abs(float(performance.get("max_drawdown") or 0.0)) >= 0.05:
            causes.append("回撤压力明显")
        if not causes:
            causes.append("收益为负，需要复核入场与退出逻辑")
        summary = self._loss_summary(causes, rounds, losing, winning, fee_drag)
        return {
            "summary": summary,
            "primary_causes": causes,
            "completed_rounds": len(rounds),
            "losing_rounds": len(losing),
            "winning_rounds": len(winning),
            "round_win_rate": round(len(winning) / len(rounds), 6) if rounds else 0.0,
            "average_round_win": round(sum(winning) / len(winning), 6) if winning else 0.0,
            "average_round_loss": round(sum(losing) / len(losing), 6) if losing else 0.0,
            "total_round_pnl": round(sum(pnl_values), 6),
            "total_fee": round(total_fee, 6),
            "fee_drag_pct_of_loss": fee_drag,
        }

    def _repair_actions_for_candidate(self, strategy: str, loss_analysis: dict, performance: dict) -> list[dict]:
        if not loss_analysis:
            return []
        causes = set(loss_analysis.get("primary_causes") or [])
        actions: list[dict] = []
        if "所有已完成买卖回合均亏损" in causes:
            if strategy == "ma_cross":
                actions.extend([
                    {
                        "action": "add_trend_filter",
                        "title": "加入更高周期趋势过滤",
                        "detail": "只在更高周期趋势向上时允许均线金叉买入，减少震荡市反复打脸。",
                        "idea_addition": "只在更高周期趋势向上时交易",
                    },
                    {
                        "action": "add_confirmation",
                        "title": "加入二次确认",
                        "detail": "金叉后等待收盘价继续站上长均线再买，降低假突破。",
                        "idea_addition": "金叉后等待收盘价继续站上长均线再买入",
                    },
                    {
                        "action": "add_cooldown",
                        "title": "加入冷却期",
                        "detail": "连续止损或死叉后暂停数根 K 线，避免震荡区间频繁进出。",
                        "idea_addition": "每次卖出后至少等待3根K线再重新买入",
                    },
                ])
            else:
                actions.append({
                    "action": "review_entry_exit",
                    "title": "复核入场和退出逻辑",
                    "detail": "完整回合全部亏损，优先检查买入触发是否追高、卖出是否过晚或过早。",
                    "idea_addition": "复核入场方向并加入更明确的退出确认",
                })
        if "交易成本占亏损比例偏高" in causes:
            actions.append({
                "action": "reduce_turnover",
                "title": "降低换手",
                "detail": "费用占亏损比例偏高，优先提高触发阈值、增加冷却期或减少仓位切换。",
                "idea_addition": "减少频繁交易并提高触发阈值",
            })
        if "回撤压力明显" in causes or abs(float(performance.get("max_drawdown") or 0.0)) >= 0.045:
            actions.append({
                "action": "tighten_risk",
                "title": "收紧风险控制",
                "detail": "回撤压力接近或超过阈值，先降低单次仓位并加入固定止损。",
                "idea_addition": "单次仓位降低到20%，跌破买入价5%止损",
            })
        return actions

    def _annotate_repair_action_support(self, actions: list[dict], strategy: str) -> list[dict]:
        annotated: list[dict] = []
        for action in actions:
            item = dict(action)
            support = self._repair_action_support(item["action"], strategy)
            item.update(support)
            annotated.append(item)
        return annotated

    def _repair_action_support(self, action: str, strategy: str) -> dict:
        compiler_action = {
            "add_trend_filter": "add_trend_filter",
            "add_cooldown": "add_cooldown",
            "tighten_risk": "tighten_stop_loss",
            "reduce_turnover": "add_cooldown",
        }.get(action)
        direct_supported = action in self._direct_strategy_supported_actions(strategy)
        compiler_supported = False
        compiler_error = ""
        if compiler_action:
            try:
                ActionCompiler().compile_action({}, compiler_action)
                compiler_supported = True
            except Exception as exc:
                compiler_error = str(exc)
        if direct_supported:
            status = "implemented_in_current_strategy"
            note = "该动作已由当前策略参数或当前回测路径直接执行。"
        elif compiler_supported:
            status = "component_available_requires_compiled_strategy"
            note = "组件和编译动作存在，但当前直连策略回测不会自动执行；需要进入策略编译/实现分支后再验证。"
        else:
            status = "research_note_only"
            note = "当前代码尚无可直接执行的组件或编译动作；这只是下一轮研究描述。"
        return {
            "implementation_status": status,
            "implemented_in_current_run": direct_supported,
            "component_available": compiler_supported,
            "requires_strategy_compiler": compiler_supported and not direct_supported,
            "compiler_action": compiler_action or "",
            "compiler_error": compiler_error,
            "support_note": note,
        }

    def _direct_strategy_supported_actions(self, strategy: str) -> set[str]:
        if strategy == "boll_mean_reversion":
            return {"tighten_risk"}
        return set()

    def _completed_trade_rounds(self, trades: list[dict]) -> list[dict]:
        rounds: list[dict] = []
        open_buy: dict | None = None
        for trade in trades:
            action = str(trade.get("action") or "").upper()
            if action == "BUY":
                open_buy = trade
            elif action == "SELL" and open_buy:
                buy_amount = float(open_buy.get("amount") or 0.0)
                buy_fee = float(open_buy.get("total_fee") or 0.0)
                sell_amount = float(trade.get("amount") or 0.0)
                sell_fee = float(trade.get("total_fee") or 0.0)
                rounds.append({
                    "buy_time": open_buy.get("execute_time") or open_buy.get("execute_datetime"),
                    "sell_time": trade.get("execute_time") or trade.get("execute_datetime"),
                    "pnl": (sell_amount - sell_fee) - (buy_amount + buy_fee),
                })
                open_buy = None
        return rounds

    def _loss_summary(self, causes: list[str], rounds: list[dict], losing: list[float], winning: list[float], fee_drag: float) -> str:
        if rounds and len(losing) == len(rounds):
            return f"亏损主因是信号质量：{len(rounds)} 个完整买卖回合全部亏损，优先检查入场方向、退出条件和震荡行情下的反复打脸；费用占亏损约 {fee_drag:.1%}。"
        if fee_drag >= 0.3:
            return f"亏损中交易成本占比偏高，费用占亏损约 {fee_drag:.1%}；优先降低交易频率或提高单笔期望收益。"
        return "收益为负但亏损来源不集中；先复核每笔买卖回合、胜率、盈亏比和回撤，再决定是否继续研究。"

    def _load_csv(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _build_diagnostics(self, manifest: dict) -> list[dict]:
        diagnostics: list[dict] = []
        steps = {step["step"]: step for step in manifest["steps"]}
        resolve_step = steps.get("resolve-symbol") or {}
        resolve_warnings = " ".join(resolve_step.get("warnings") or [])
        if "非 A 股标的/市场" in resolve_warnings or "数字货币版本需要单独工作流" in resolve_warnings:
            return [{
                "type": "wrong_asset_version",
                "severity": "blocker",
                "title": "资产版本不匹配",
                "evidence": resolve_warnings,
                "recommendation": "当前是 A 股/QMT 版本。数字货币策略需要单独版本；不要继续运行 QMT、pretrade 或 A 股回测命令。",
            }]
        paper_step = steps.get("paper")
        if paper_step and paper_step.get("report_path"):
            observation = self._load_json(Path(paper_step["report_path"]) / "paper_observation.json")
            diagnostics.extend(self._paper_diagnostics(observation))
        qmt_step = steps.get("qmt-check")
        if qmt_step is None:
            diagnostics.append({
                "type": "qmt_not_run",
                "severity": "info",
                "title": "QMT 只读还没有运行",
                "evidence": "当前工作流没有包含 --include-qmt，或者模拟盘尚未满足推进条件。",
                "recommendation": "先让模拟盘观察通过，再运行 qmt-check 或 student-workflow --include-qmt。不要把 QMT 连接当作实盘许可。",
            })
        elif qmt_step.get("status") != "VALID":
            diagnostics.append({
                "type": "qmt_readonly_blocked",
                "severity": "blocker",
                "title": "QMT 只读检查未通过",
                "evidence": "账户、资金、持仓、委托或成交读取不完整。",
                "recommendation": "先修 QMT 只读配置，只允许读取；在只读通过前不要进入 pretrade-check。",
            })
        if not diagnostics:
            diagnostics.append({
                "type": "review_stage",
                "severity": "info",
                "title": "查看阶段门报告",
                "evidence": "当前未识别到可自动分流的问题。",
                "recommendation": "打开 stage_gate_report.md，按阶段门的 blocker 处理。",
            })
        return diagnostics

    def _paper_diagnostics(self, observation: dict) -> list[dict]:
        if not observation:
            return [{
                "type": "paper_missing_report",
                "severity": "blocker",
                "title": "模拟盘观察报告缺失",
                "evidence": "没有找到 paper_observation.json。",
                "recommendation": "重新运行 paper 或 student-workflow，确认模拟盘报告完整生成。",
            }]
        policy = observation.get("policy") or {}
        observed_days = int(observation.get("observed_days") or 0)
        min_days = int(policy.get("min_observed_days") or 0)
        trade_count = int(observation.get("trade_count") or 0)
        min_trades = int(policy.get("min_trades") or 0)
        completed_rounds = int(observation.get("completed_rounds") or 0)
        min_completed_rounds = int(policy.get("min_completed_rounds") or 0)
        max_drawdown = float(observation.get("max_drawdown") or 0.0)
        max_drawdown_limit = float(policy.get("max_drawdown_limit") or 0.0)
        rejected_orders = int(observation.get("rejected_orders") or 0)
        rejected_order_rate = float(observation.get("rejected_order_rate") or 0.0)
        max_rejected_order_rate = float(policy.get("max_rejected_order_rate") or 0.0)
        diagnostics: list[dict] = []
        if observed_days < min_days:
            diagnostics.append({
                "type": "extend_observation_window",
                "severity": "blocker",
                "title": "观察期不够",
                "evidence": f"已观察 {observed_days} 根/天，要求至少 {min_days}。",
                "recommendation": "优先使用更长历史数据或更早开始模拟观察；不要因为短样本盈利就推进 QMT。",
            })
        if trade_count < min_trades:
            if observed_days >= min_days:
                recommendation = "观察期已经够，主要问题是信号太少。优先调整触发条件、参数或策略范式，让策略在同类市场环境中产生足够样本。"
            else:
                recommendation = "观察期和成交次数都不够。先延长数据，再判断是否需要调整触发条件。"
            diagnostics.append({
                "type": "increase_signal_frequency",
                "severity": "blocker",
                "title": "模拟成交次数不够",
                "evidence": f"已成交 {trade_count} 笔，要求至少 {min_trades} 笔。",
                "recommendation": recommendation,
            })
        if min_completed_rounds and completed_rounds < min_completed_rounds:
            diagnostics.append({
                "type": "complete_trade_rounds",
                "severity": "blocker",
                "title": "完整买卖回合不够",
                "evidence": f"已完成 {completed_rounds} 轮买卖，要求至少 {min_completed_rounds} 轮。",
                "recommendation": "不要只看单边买入或单边卖出样本。先补足能从入场到退出闭环的模拟记录，再评估收益、回撤和手续费。",
            })
        if max_drawdown_limit and abs(max_drawdown) > max_drawdown_limit:
            diagnostics.append({
                "type": "reduce_drawdown",
                "severity": "blocker",
                "title": "模拟回撤超过限制",
                "evidence": f"最大回撤 {max_drawdown:.4f}，限制 {max_drawdown_limit:.4f}。",
                "recommendation": "先收紧止损、降低单次仓位或加入暂停交易规则；不要用加仓掩盖回撤。",
            })
        if max_rejected_order_rate and rejected_order_rate > max_rejected_order_rate:
            diagnostics.append({
                "type": "reduce_rejected_order_rate",
                "severity": "blocker",
                "title": "模拟委托拒单率过高",
                "evidence": f"拒单率 {rejected_order_rate:.4f}，限制 {max_rejected_order_rate:.4f}。",
                "recommendation": "先修正无法成交的价格、数量、T+1、涨跌停和现金仓位约束；不要把被拒委托当作有效交易证据。",
            })
        if rejected_orders:
            diagnostics.append({
                "type": "fix_rejected_orders",
                "severity": "warning",
                "title": "存在被交易规则拒绝的模拟委托",
                "evidence": f"被拒委托 {rejected_orders} 笔。",
                "recommendation": "检查涨跌停、T+1、最小交易单位、现金和仓位约束，修正成交假设。",
            })
        if observation.get("status") == "VALID":
            diagnostics.append({
                "type": "paper_ready_for_qmt_readonly",
                "severity": "next",
                "title": "模拟盘观察已通过",
                "evidence": f"观察 {observed_days}，成交 {trade_count}，完整买卖回合 {completed_rounds}，回撤 {max_drawdown:.4f}。",
                "recommendation": "下一步只做 QMT 只读检查；仍然不能真实下单。",
            })
        return diagnostics

    def _write_diagnostics(self, output_dir: Path, manifest: dict, diagnostics: list[dict]) -> None:
        lines = [
            "# Student Diagnostics",
            "",
            f"status: {manifest['status']}",
            f"idea: {manifest['idea']}",
            "",
            "## 问题分流",
        ]
        for item in diagnostics:
            lines.extend([
                f"- [{item['severity']}] {item['title']}",
                f"  - 证据：{item['evidence']}",
                f"  - 建议：{item['recommendation']}",
            ])
        lines.extend([
            "",
            "## 分流原则",
            "- 观察期不足：先补数据或延长模拟观察。",
            "- 观察期足够但成交不足：优先调整触发条件、参数或策略范式。",
            "- 回撤超限：先降仓位、加止损或暂停交易规则。",
            "- 委托被拒：先修交易规则假设，不要把无法成交的订单算进收益。",
            "- QMT 未只读通过：只修读取链路，不讨论真实下单。",
        ])
        (output_dir / "STUDENT_DIAGNOSTICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_acceptance_checklist(self, output_dir: Path, manifest: dict, actions: list[dict]) -> None:
        step_by_name = {step["step"]: step for step in manifest["steps"]}
        checks = [
            self._check_item("标的已识别", step_by_name.get("resolve-symbol")),
            self._check_item("已生成结构化策略计划", step_by_name.get("intake")),
            self._check_item("回测策略与策略范式已匹配", step_by_name.get("select-strategy")),
            self._check_item("数据已准备并记录周期/复权方式", step_by_name.get("fetch-data")),
            self._check_item("回测已完成", step_by_name.get("backtest")),
            self._check_item("未来函数和交易规则审计已通过", step_by_name.get("audit")),
            self._check_item("模拟盘观察已通过", step_by_name.get("paper")),
            self._check_item("阶段门报告已生成", step_by_name.get("stage-check")),
            self._check_item("QMT 只读检查已通过", step_by_name.get("qmt-check")),
        ]
        lines = [
            "# Student Acceptance Checklist",
            "",
            f"status: {manifest['status']}",
            f"idea: {manifest['idea']}",
            "",
            "## 当前验收状态",
        ]
        for check in checks:
            lines.append(f"- [{check['mark']}] {check['title']}：{check['status']}")
            if check["detail"]:
                lines.append(f"  - {check['detail']}")
        lines.extend([
            "",
            "## 不能跳过的硬门槛",
            "- 交易信号只能使用当前 K 线及以前已知数据；未来数据、负 shift、居中窗口、未来标签都不能通过。",
            "- 回测必须匹配策略类型；网格、轮动、选股、日内和单标的波段不能共用一套默认假设。",
            "- 模拟盘通过只代表可以做 QMT 只读检查，不代表允许真实下单。",
            "- QMT 只读通过后，还必须跑 pretrade-check，并且需要人工确认才可讨论实盘候选。",
            "",
            "## 下一步",
        ])
        for action in actions:
            lines.append(f"- {action['title']}：{action['detail']}")
        lines.extend([
            "",
            "## 问题分流",
        ])
        for item in manifest.get("diagnostics") or []:
            lines.append(f"- {item['title']}：{item['recommendation']}")
        (output_dir / "STUDENT_ACCEPTANCE_CHECKLIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _check_item(self, title: str, step: dict | None) -> dict:
        if step is None:
            return {"title": title, "mark": " ", "status": "未运行", "detail": "当前工作流还没有执行到这一项。"}
        if step["status"] == "VALID":
            detail = step.get("report_path") or step.get("run_id") or ""
            return {"title": title, "mark": "x", "status": "已通过", "detail": detail}
        warnings = "；".join(step.get("warnings") or [])
        return {"title": title, "mark": " ", "status": "未通过", "detail": warnings or "请查看对应阶段报告。"}

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _suggest_idea(self, manifest: dict, actions: list[dict]) -> str:
        idea = str(manifest.get("idea") or "").strip()
        additions: list[str] = []
        action_types = {item["type"] for item in actions}
        if "fix_exit" in action_types:
            additions.append("涨回布林中轨或20日均线时卖出")
        if "fix_sizing" in action_types:
            additions.append("每次买入30%，最大仓位60%")
        if "fix_risk" in action_types:
            additions.append("最大回撤控制在10%，跌破买入价8%止损")
        if "extend_paper" in action_types:
            additions.append("使用更长历史数据观察至少达到模拟盘最低成交次数")
        additions = [addition for addition in additions if addition not in idea]
        if additions:
            return idea.rstrip("。") + "，" + "，".join(additions)
        return idea or "请补充标的、策略方向、买入规则、卖出规则、仓位和风险控制"
