from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from backtest.report import write_json
from core.data_loader import load_csv_data
from core.result import TaskResult
from core.run_manager import RunManager
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest
from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import load_corporate_actions
from paper_live.observation import PaperObservationChecker
from services.stage_check_service import StageCheckService
from strategy_compiler.compile_report import CompileReportWriter
from strategy_compiler.compiler_errors import StrategyCompileError
from strategy_compiler.dsl_to_strategy import DSLToStrategy


class RepairDSLService:
    def run(
        self,
        dsl_path: str,
        symbol: str | None = None,
        data: str = "__auto_fetch__",
        timeframe: str | None = None,
        adjust: str | None = None,
        paper_observation: bool = False,
        stage_check: bool = False,
        qmt_run_id: str | None = None,
        auto_repair: bool = False,
    ) -> TaskResult:
        dsl_file = Path(dsl_path)
        dsl = yaml.safe_load(dsl_file.read_text(encoding="utf-8")) or {}
        session_id = str(dsl.get("session_id") or "")
        case_id = str(dsl.get("case_id") or "")
        symbol = symbol or self._symbol_from_dsl(dsl)
        timeframe = timeframe or str(dsl.get("timeframe") or "1d")
        adjust = adjust or str(dsl.get("adjust") or "point_in_time_qfq")
        if not data or data == "__auto_fetch__":
            data = DataAcquisitionAgent().fetch(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))["path"]

        ctx = RunManager().create_run("repair_dsl_backtest")
        (ctx.output_dir / "repair_dsl_input.yaml").write_text(
            yaml.safe_dump(dsl, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

        try:
            compiled = DSLToStrategy().compile(dsl, symbol=symbol)
        except StrategyCompileError as exc:
            CompileReportWriter().write(ctx.output_dir, errors=[str(exc)])
            self._write_run_report(
                ctx.output_dir,
                status="INVALID",
                symbol=symbol,
                timeframe=timeframe,
                adjust=adjust,
                data=data,
                dsl_path=dsl_file,
                compile_error=str(exc),
            )
            return TaskResult(
                status="INVALID",
                message="修复 DSL 编译失败：INVALID",
                run_id=ctx.run_id,
                report_path=str(ctx.output_dir),
                audit_status="INVALID",
                warnings=[str(exc)],
            )

        CompileReportWriter().write(ctx.output_dir, compiled.compiled_strategy)
        self._write_backtest_plan(ctx.output_dir, compiled.compiled_strategy, symbol, timeframe, adjust)
        rows = self._load_adjusted_rows(data, symbol, timeframe, adjust)
        template = compiled.template_class(strategy=compiled.strategy, symbol=symbol, initial_cash=1000000)
        result = template.run(
            ctx,
            rows,
            source_paths=[
                Path("strategy_compiler/dsl_to_strategy.py"),
                Path("strategy_compiler/action_compiler.py"),
            ],
        )
        observation = None
        stage = None
        warnings: list[str] = []
        final_status = result.status
        if paper_observation:
            checker = PaperObservationChecker()
            observation = checker.check(result.output_dir, strategy_pattern=compiled.template_name, timeframe=timeframe)
            checker.write_report(result.output_dir, observation)
            if not observation.ok:
                final_status = "INVALID"
                warnings.extend(observation.failures)
        next_actions = self._build_next_actions(
            status=result.status,
            compiled_strategy=compiled.compiled_strategy,
            performance=result.performance,
            observation=observation.to_dict() if observation else None,
            dsl_path=dsl_file,
            symbol=symbol,
            timeframe=timeframe,
            adjust=adjust,
        )
        self._write_next_actions(ctx.output_dir, next_actions)
        if stage_check:
            stage = StageCheckService().run(run_id=result.run_id, qmt_run_id=qmt_run_id)
            warnings.extend(stage.warnings)
        auto_candidates: list[dict] = []
        if auto_repair and result.status == "VALID" and self._needs_auto_repair(result.performance, observation.to_dict() if observation else None):
            auto_candidates = self._run_auto_repair_candidates(
                parent_dir=ctx.output_dir,
                dsl=dsl,
                symbol=symbol,
                data=data,
                timeframe=timeframe,
                adjust=adjust,
                paper_observation=paper_observation,
                stage_check=stage_check,
                qmt_run_id=qmt_run_id,
            )
        write_json(ctx.output_dir / "repair_dsl_run.json", {
            "status": final_status,
            "session_id": session_id,
            "case_id": case_id,
            "backtest_status": result.status,
            "audit_status": result.audit_status,
            "symbol": symbol,
            "timeframe": timeframe,
            "adjust": adjust,
            "data": data,
            "dsl_path": str(dsl_file),
            "compiled_strategy": compiled.compiled_strategy,
            "performance": result.performance,
            "paper_observation": observation.to_dict() if observation else None,
            "stage_gate": stage.artifacts.get("stage_gate") if stage else None,
            "next_actions": next_actions,
            "auto_repair_candidates": auto_candidates,
        })
        if auto_candidates:
            self._write_auto_repair_report(ctx.output_dir, auto_candidates)
            self._write_promotion_package(ctx.output_dir, auto_candidates, session_id=session_id, case_id=case_id)
        self._write_run_report(
            ctx.output_dir,
            status=final_status,
            symbol=symbol,
            timeframe=timeframe,
            adjust=adjust,
            data=data,
            dsl_path=dsl_file,
            compiled_strategy=compiled.compiled_strategy,
            performance=result.performance,
            observation=observation.to_dict() if observation else None,
            stage_gate=stage.artifacts.get("stage_gate") if stage else None,
            next_actions=next_actions,
            auto_candidates=auto_candidates,
        )
        return TaskResult(
            status=final_status,
            message=f"修复 DSL 回测完成：{final_status}",
            run_id=result.run_id,
            report_path=str(result.output_dir),
            audit_status=result.audit_status,
            warnings=warnings,
            artifacts={
                "performance": result.performance,
                "compiled_strategy": compiled.compiled_strategy,
                "paper_observation": observation.to_dict() if observation else None,
                "stage_gate": stage.artifacts.get("stage_gate") if stage else None,
                "auto_repair_candidates": auto_candidates,
            },
        )

    def _symbol_from_dsl(self, dsl: dict[str, Any]) -> str:
        symbols = dsl.get("symbols") or []
        if not symbols:
            raise ValueError("DSL 中缺少 symbols，或请用 --symbol 指定标的。")
        return str(symbols[0])

    def _load_adjusted_rows(self, data_path: str, symbol: str, timeframe: str, adjust: str) -> list[dict]:
        rows = load_csv_data(data_path, symbol=symbol)
        action_file = self._corporate_action_file(symbol)
        actions = load_corporate_actions(action_file, symbol) if action_file else []
        rows = AdjustmentEngine().adjust(rows, actions, adjust)
        for row in rows:
            row["timeframe"] = timeframe or row.get("timeframe", "1d")
        return rows

    def _corporate_action_file(self, symbol: str) -> Path | None:
        candidates = [
            Path(f"data/sample/corporate_actions_{symbol.split('.')[0]}.csv"),
            Path(f"data/sample/corporate_actions_{symbol.replace('.', '_')}.csv"),
            Path(f"data/sample/corporate_actions_{symbol}.csv"),
        ]
        return next((path for path in candidates if path.exists()), None)

    def _write_backtest_plan(self, output_dir: Path, compiled_strategy: dict, symbol: str, timeframe: str, adjust: str) -> None:
        plan = {
            "status": "VALID",
            "strategy_pattern": compiled_strategy.get("pattern") or "timing",
            "template_name": compiled_strategy.get("template_name") or "timing",
            "symbol_scope": "single",
            "symbols": [symbol],
            "timeframe": timeframe,
            "adjust": adjust,
            "data_required": ["OHLCV"],
            "execution_model": {
                "signal_bar": "close_confirmed",
                "fill_bar": "next_bar_open",
                "t_plus_1": True,
                "price_basis": "next_bar_open",
            },
            "audit_required": ["future_leak", "trade_rule", "adjustment_leak"],
            "promotion_policy": {
                "qmt_allowed": compiled_strategy.get("pattern") in {"timing", "swing", "grid"},
                "max_stage_without_real_data": "PAPER_OBSERVED",
                "requires_paper_observation": True,
                "requires_qmt_readonly": True,
            },
            "blockers": [],
            "warnings": ["这是修复 DSL 分支自动生成的回测计划；仍需模拟盘观察和阶段门验证。"],
        }
        (output_dir / "backtest_plan.yaml").write_text(
            yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def _write_run_report(
        self,
        output_dir: Path,
        status: str,
        symbol: str,
        timeframe: str,
        adjust: str,
        data: str,
        dsl_path: Path,
        compiled_strategy: dict | None = None,
        performance: dict | None = None,
        compile_error: str | None = None,
        observation: dict | None = None,
        stage_gate: dict | None = None,
        next_actions: list[dict] | None = None,
        auto_candidates: list[dict] | None = None,
    ) -> None:
        lines = [
            "# Repair DSL Backtest Report",
            "",
            f"status: {status}",
            f"symbol: {symbol}",
            f"timeframe: {timeframe}",
            f"adjust: {adjust}",
            f"data: {data}",
            f"dsl_path: {dsl_path}",
            "",
            "## 边界",
            "- 这里跑的是修复 DSL 分支，不代表原 student-workflow 已经执行这些组件。",
            "- 交易信号只能使用当前 K 线及以前的 OHLCV；审计报告必须保持 VALID 才能继续。",
            "- 该结果仍需进入模拟盘观察和阶段门，不能直接作为 QMT 实盘许可。",
            "",
        ]
        if compile_error:
            lines.extend(["## 编译错误", f"- {compile_error}", ""])
        if compiled_strategy:
            lines.extend([
                "## 编译策略",
                f"- pattern: {compiled_strategy.get('pattern')}",
                f"- template: {compiled_strategy.get('template_name')}",
                f"- entry_rules: {', '.join(compiled_strategy.get('entry_rules', []))}",
                f"- exit_rules: {', '.join(compiled_strategy.get('exit_rules', []))}",
                f"- filters: {', '.join(compiled_strategy.get('filters', [])) or 'none'}",
                f"- sizing_rules: {', '.join(compiled_strategy.get('sizing_rules', []))}",
                "",
            ])
        if performance:
            lines.extend([
                "## 关键结果",
                f"- trade_count: {performance.get('trade_count')}",
                f"- total_return: {performance.get('total_return')}",
                f"- max_drawdown: {performance.get('max_drawdown')}",
                f"- final_equity: {performance.get('final_equity')}",
                "",
            ])
        if observation:
            lines.extend([
                "## 模拟盘观察",
                f"- status: {observation.get('status')}",
                f"- observed_days: {observation.get('observed_days')}",
                f"- trade_count: {observation.get('trade_count')}",
                f"- failures: {'；'.join(observation.get('failures') or []) or '无'}",
                "",
            ])
        if stage_gate:
            lines.extend([
                "## 阶段门",
                f"- stage: {stage_gate.get('stage')}",
                f"- reasons: {'；'.join(stage_gate.get('reasons') or []) or '无'}",
                "",
            ])
        if next_actions:
            lines.extend([
                "## 下一步建议",
            ])
            lines.extend([f"- {item.get('title')}：{item.get('detail')}" for item in next_actions])
            lines.append("")
        if auto_candidates:
            lines.extend([
                "## 自动修订候选",
            ])
            for item in auto_candidates:
                lines.append(
                    f"- #{item.get('rank')} {item.get('variant_id')}：status={item.get('status')} "
                    f"audit={item.get('audit_status')} trades={item.get('trade_count')} return={item.get('total_return')} "
                    f"dd={item.get('max_drawdown')}"
                )
                lines.append(f"  - reason: {item.get('reason')}")
                lines.append(f"  - report: {item.get('report_path')}")
            lines.append("")
        if performance:
            lines.extend([
                "## 下一步",
                "- 先阅读 audit_report.md、future_leak_report.md、readiness_report.md。",
                "- 若尚未生成 paper_observation_report.md，可重新运行本命令并加上 --paper-observation --stage-check。",
                "- 若审计 VALID 但成交不足，先按 repair_dsl_next_actions.md 调整 DSL，再重新回测。",
                "- 若已生成 repair_dsl_auto_repair.md，优先看排名靠前且审计 VALID、成交数达标的候选。",
            ])
        (output_dir / "repair_dsl_run_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _run_auto_repair_candidates(
        self,
        *,
        parent_dir: Path,
        dsl: dict[str, Any],
        symbol: str,
        data: str,
        timeframe: str,
        adjust: str,
        paper_observation: bool,
        stage_check: bool,
        qmt_run_id: str | None,
    ) -> list[dict]:
        candidates = self._auto_repair_candidate_dsls(dsl)
        results: list[dict] = []
        for candidate in candidates:
            variant_dir = parent_dir / "auto_repair_candidates" / candidate["variant_id"]
            variant_dir.mkdir(parents=True, exist_ok=True)
            dsl_path = variant_dir / "strategy_dsl.yaml"
            dsl_path.write_text(yaml.safe_dump(candidate["dsl"], allow_unicode=True, sort_keys=False), encoding="utf-8")
            result = self.run(
                dsl_path=str(dsl_path),
                symbol=symbol,
                data=data,
                timeframe=timeframe,
                adjust=adjust,
                paper_observation=paper_observation,
                stage_check=stage_check,
                qmt_run_id=qmt_run_id,
                auto_repair=False,
            )
            report_path = Path(result.report_path or "")
            self._copy_candidate_artifacts(report_path, variant_dir)
            performance = result.artifacts.get("performance") or {}
            observation = result.artifacts.get("paper_observation") or {}
            results.append({
                "variant_id": candidate["variant_id"],
                "reason": candidate["reason"],
                "dsl_path": str(dsl_path),
                "report_path": str(report_path),
                "next_command": (
                    f"python3 cli.py repair-dsl-backtest --dsl {dsl_path} --symbol {symbol} "
                    f"--timeframe {timeframe} --adjust {adjust} --paper-observation --stage-check --auto-repair"
                ),
                "qmt_next_command": "python3 cli.py qmt-check",
                "stage_check_after_qmt_command": f"python3 cli.py stage-check --run-id {result.run_id} --qmt-run-id <qmt_run_id>",
                "pretrade_package_command": f"python3 cli.py pretrade-package --promotion <REPAIR_DSL_PROMOTION.json> --qmt-run-id <qmt_run_id>",
                "status": result.status,
                "audit_status": result.audit_status,
                "trade_count": int(performance.get("trade_count") or 0),
                "total_return": float(performance.get("total_return") or 0.0),
                "max_drawdown": float(performance.get("max_drawdown") or 0.0),
                "paper_status": observation.get("status"),
                "paper_failures": observation.get("failures") or [],
            })
        return self._rank_auto_repair_candidates(results)

    def _auto_repair_candidate_dsls(self, dsl: dict[str, Any]) -> list[dict]:
        candidates: list[dict] = []
        entry_type = (dsl.get("entry") or {}).get("type")
        entry_params = (dsl.get("entry") or {}).get("params") or {}
        if entry_type == "MADeviationEntry":
            current = float(entry_params.get("deviation", 0.04))
            candidates.append(self._candidate_with_entry_param(dsl, "relax_ma_deviation_1", "deviation", max(0.01, round(current - 0.01, 4)), "均线偏离阈值下调一档，优先恢复信号。"))
            candidates.append(self._candidate_with_entry_param(dsl, "relax_ma_deviation_2", "deviation", max(0.01, round(current - 0.02, 4)), "均线偏离阈值下调两档，观察是否仍能控制交易质量。"))
            candidates.append(self._candidate_with_entry_param(dsl, "diagnose_ma_deviation_001", "deviation", 0.01, "诊断性候选：阈值降到 1%，确认信号是否只是过严。"))
            window_probe = self._candidate_with_entry_param(dsl, "diagnose_ma_window_10_dev_001", "deviation", 0.01, "诊断性候选：缩短均线窗口并降低偏离阈值，检查周期是否过慢。")
            window_probe["dsl"].setdefault("entry", {}).setdefault("params", {})["window"] = 10
            candidates.append(window_probe)
            candidates.append(self._candidate_with_entry_param(dsl, "diagnose_ma_deviation_0005", "deviation", 0.005, "诊断性候选：阈值降到 0.5%，只用于恢复信号和定位门槛，不直接作为实盘候选。"))
            candidates.extend(self._ma_sample_expansion_candidates(dsl, current))
        if entry_type == "BollLowerEntry":
            current = float(entry_params.get("num_std", 2.0))
            candidates.append(self._candidate_with_entry_param(dsl, "relax_boll_std_1", "num_std", max(1.0, round(current - 0.2, 4)), "布林触发阈值下调一档，增加低吸信号。"))
            candidates.append(self._candidate_with_entry_param(dsl, "relax_boll_std_2", "num_std", max(1.0, round(current - 0.4, 4)), "布林触发阈值下调两档，作为信号恢复对照。"))
        trend = self._candidate_with_filter_param(dsl, "relax_trend_window", "TrendFilter", "window", 10, "缩短趋势过滤窗口，检查过滤器是否过严。")
        if trend:
            candidates.append(trend)
        no_trend = self._candidate_without_filter(dsl, "remove_trend_filter_probe", "TrendFilter", "临时移除趋势过滤做对照，只用于诊断过滤器是否挡掉所有信号。")
        if no_trend:
            candidates.append(no_trend)
        return self._unique_candidates([item for item in candidates if item])

    def _needs_auto_repair(self, performance: dict, observation: dict | None) -> bool:
        trade_count = int(performance.get("trade_count") or 0)
        if trade_count == 0:
            return True
        if observation and observation.get("status") != "VALID":
            policy = observation.get("policy") or {}
            min_trades = int(policy.get("min_trades") or 0)
            failures = " ".join(observation.get("failures") or [])
            return bool(min_trades and trade_count < min_trades and "成交次数不足" in failures)
        return False

    def _ma_sample_expansion_candidates(self, dsl: dict[str, Any], current_deviation: float) -> list[dict]:
        candidates: list[dict] = []
        for value in [0.003, 0.001]:
            if current_deviation > value:
                candidates.append(self._candidate_with_entry_param(
                    dsl,
                    f"expand_ma_deviation_{str(value).replace('.', '')}",
                    "deviation",
                    value,
                    f"样本扩展候选：偏离阈值降到 {value:.3f}，目标是把成交数推近模拟盘最低样本。",
                ))
        for window, deviation in [(10, 0.005), (7, 0.003), (5, 0.003)]:
            candidate = self._candidate_with_entry_param(
                dsl,
                f"expand_ma_window_{window}_dev_{str(deviation).replace('.', '')}",
                "deviation",
                deviation,
                f"样本扩展候选：{window} 日均线配合 {deviation:.3f} 偏离阈值，检查更短周期是否有足够信号。",
            )
            candidate["dsl"].setdefault("entry", {}).setdefault("params", {})["window"] = window
            candidates.append(candidate)
        for take_profit in [0.05, 0.03]:
            candidate = self._candidate_with_exit_param(
                dsl,
                f"expand_take_profit_{str(take_profit).replace('.', '')}",
                "FixedTakeProfitExit",
                "take_profit",
                take_profit,
                f"样本扩展候选：止盈降到 {take_profit:.2%}，检查是否因退出太慢导致交易样本不足。",
            )
            if candidate:
                candidates.append(candidate)
        for bars in [20, 10, 5]:
            candidates.append(self._candidate_with_added_exit(
                dsl,
                f"expand_holding_days_exit_{bars}",
                "HoldingDaysExit",
                {"max_holding_bars": bars},
                f"样本扩展候选：加入 {bars} 根 K 线持仓周期退出，检查是否因退出太慢导致只有买入没有卖出。",
            ))
        for deviation, bars in [(0.003, 20), (0.003, 10), (0.001, 10)]:
            candidate = self._candidate_with_entry_param(
                dsl,
                f"expand_dev_{str(deviation).replace('.', '')}_hold_{bars}",
                "deviation",
                deviation,
                f"组合候选：降低偏离阈值到 {deviation:.3f} 并加入 {bars} 根 K 线退出，目标是同时恢复入场和退出样本。",
            )
            candidate["dsl"].setdefault("exit", []).append({"type": "HoldingDaysExit", "params": {"max_holding_bars": bars}})
            candidates.append(candidate)
        return candidates

    def _candidate_with_entry_param(self, dsl: dict[str, Any], variant_id: str, key: str, value: Any, reason: str) -> dict:
        candidate = json.loads(json.dumps(dsl, ensure_ascii=False))
        candidate.setdefault("entry", {}).setdefault("params", {})[key] = value
        return {"variant_id": variant_id, "reason": reason, "dsl": candidate}

    def _candidate_with_filter_param(self, dsl: dict[str, Any], variant_id: str, filter_type: str, key: str, value: Any, reason: str) -> dict | None:
        candidate = json.loads(json.dumps(dsl, ensure_ascii=False))
        changed = False
        for item in candidate.get("filters") or []:
            if item.get("type") == filter_type:
                item.setdefault("params", {})[key] = value
                changed = True
        if not changed:
            return None
        return {"variant_id": variant_id, "reason": reason, "dsl": candidate}

    def _candidate_without_filter(self, dsl: dict[str, Any], variant_id: str, filter_type: str, reason: str) -> dict | None:
        candidate = json.loads(json.dumps(dsl, ensure_ascii=False))
        filters = candidate.get("filters") or []
        kept = [item for item in filters if item.get("type") != filter_type]
        if len(kept) == len(filters):
            return None
        candidate["filters"] = kept
        return {"variant_id": variant_id, "reason": reason, "dsl": candidate}

    def _candidate_with_exit_param(self, dsl: dict[str, Any], variant_id: str, exit_type: str, key: str, value: Any, reason: str) -> dict | None:
        candidate = json.loads(json.dumps(dsl, ensure_ascii=False))
        changed = False
        for item in candidate.get("exit") or []:
            if item.get("type") == exit_type:
                item.setdefault("params", {})[key] = value
                changed = True
        if not changed:
            return None
        return {"variant_id": variant_id, "reason": reason, "dsl": candidate}

    def _candidate_with_added_exit(self, dsl: dict[str, Any], variant_id: str, exit_type: str, params: dict[str, Any], reason: str) -> dict:
        candidate = json.loads(json.dumps(dsl, ensure_ascii=False))
        exits = candidate.setdefault("exit", [])
        exits.append({"type": exit_type, "params": dict(params)})
        return {"variant_id": variant_id, "reason": reason, "dsl": candidate}

    def _unique_candidates(self, candidates: list[dict]) -> list[dict]:
        unique: list[dict] = []
        seen_ids: set[str] = set()
        seen_payloads: set[str] = set()
        for item in candidates:
            payload = json.dumps(item.get("dsl") or {}, ensure_ascii=False, sort_keys=True)
            if item["variant_id"] in seen_ids or payload in seen_payloads:
                continue
            seen_ids.add(item["variant_id"])
            seen_payloads.add(payload)
            unique.append(item)
        return unique

    def _rank_auto_repair_candidates(self, results: list[dict]) -> list[dict]:
        def score(item: dict) -> tuple:
            audit_ok = 1 if item.get("audit_status") == "VALID" else 0
            paper_ok = 1 if item.get("paper_status") == "VALID" else 0
            trades = int(item.get("trade_count") or 0)
            ret = float(item.get("total_return") or 0.0)
            drawdown = abs(float(item.get("max_drawdown") or 0.0))
            return (audit_ok, paper_ok, min(trades, 20), ret, -drawdown)

        ranked = sorted(results, key=score, reverse=True)
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
            item["score"] = score(item)
            item["is_recommended"] = index == 1 and item.get("audit_status") == "VALID" and int(item.get("trade_count") or 0) > 0
            item["recommendation"] = self._auto_repair_recommendation(item)
        return ranked

    def _auto_repair_recommendation(self, item: dict) -> str:
        if item.get("audit_status") != "VALID":
            return "审计未通过，不继续。"
        if int(item.get("trade_count") or 0) <= 0:
            return "仍然 0 成交，只作为排除项。"
        if item.get("paper_status") != "VALID":
            return "信号已恢复但模拟盘观察仍未通过，可继续做参数细化。"
        return "可作为下一轮研究分支，但仍需阶段门和 QMT 只读检查。"

    def _copy_candidate_artifacts(self, report_path: Path, variant_dir: Path) -> None:
        if not report_path.exists():
            return
        for name in [
            "repair_dsl_run_report.md",
            "repair_dsl_next_actions.md",
            "audit_report.md",
            "paper_observation_report.md",
            "stage_gate_report.md",
            "performance.json",
            "trades.csv",
        ]:
            src = report_path / name
            if src.exists():
                shutil.copyfile(src, variant_dir / name)

    def _write_auto_repair_report(self, output_dir: Path, candidates: list[dict]) -> None:
        (output_dir / "repair_dsl_auto_repair.json").write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# Repair DSL Auto Repair",
            "",
            "这些候选是系统按修复建议自动生成并复跑的研究分支，不是实盘许可。",
            "",
        ]
        for item in candidates:
            lines.extend([
                f"## #{item.get('rank')} {item.get('variant_id')}",
                f"- status: {item.get('status')}",
                f"- audit_status: {item.get('audit_status')}",
                f"- paper_status: {item.get('paper_status')}",
                f"- trade_count: {item.get('trade_count')}",
                f"- total_return: {item.get('total_return')}",
                f"- max_drawdown: {item.get('max_drawdown')}",
                f"- reason: {item.get('reason')}",
                f"- recommendation: {item.get('recommendation')}",
                f"- dsl_path: {item.get('dsl_path')}",
                f"- report_path: {item.get('report_path')}",
                f"- next_command: `{item.get('next_command')}`",
                f"- qmt_next_command: `{item.get('qmt_next_command')}`",
                f"- stage_check_after_qmt_command: `{item.get('stage_check_after_qmt_command')}`",
                f"- pretrade_package_command: `{item.get('pretrade_package_command')}`",
                "",
            ])
        output_dir.joinpath("repair_dsl_auto_repair.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_promotion_package(self, output_dir: Path, candidates: list[dict], session_id: str = "", case_id: str = "") -> None:
        selected = next((item for item in candidates if item.get("audit_status") == "VALID" and item.get("paper_status") == "VALID" and int(item.get("trade_count") or 0) >= 3), None)
        if not selected:
            return
        package_dir = output_dir / "promotion_candidate"
        package_dir.mkdir(parents=True, exist_ok=True)
        src_dir = output_dir / "auto_repair_candidates" / str(selected["variant_id"])
        selected_dsl = package_dir / "SELECTED_REPAIR_DSL.yaml"
        if (src_dir / "strategy_dsl.yaml").exists():
            shutil.copyfile(src_dir / "strategy_dsl.yaml", selected_dsl)
        for name in [
            "audit_report.md",
            "paper_observation_report.md",
            "stage_gate_report.md",
            "repair_dsl_run_report.md",
            "performance.json",
            "trades.csv",
        ]:
            src = src_dir / name
            if src.exists():
                shutil.copyfile(src, package_dir / name)
        promotion = {
            "selected_variant_id": selected.get("variant_id"),
            "status": "READY_FOR_QMT_READONLY",
            "session_id": session_id,
            "case_id": case_id,
            "why_selected": [
                "审计状态 VALID",
                f"模拟盘观察通过，成交次数 {selected.get('trade_count')} 笔",
                f"最大回撤 {selected.get('max_drawdown')}",
                "阶段门已推进到 PAPER_OBSERVED，但 QMT 只读未完成",
            ],
            "selected_dsl_path": str(selected_dsl),
            "source_report_path": selected.get("report_path"),
            "qmt_next_command": selected.get("qmt_next_command"),
            "stage_check_after_qmt_command": selected.get("stage_check_after_qmt_command"),
            "pretrade_package_command": f"python3 cli.py pretrade-package --promotion {output_dir / 'REPAIR_DSL_PROMOTION.json'} --qmt-run-id <qmt_run_id>",
            "pretrade_boundary": "QMT 只读和 pretrade-check 未通过前，不允许真实下单。",
            "candidate": selected,
        }
        (output_dir / "REPAIR_DSL_PROMOTION.json").write_text(json.dumps(promotion, ensure_ascii=False, indent=2), encoding="utf-8")
        (package_dir / "promotion_manifest.json").write_text(json.dumps(promotion, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [
            "# Repair DSL Promotion Candidate",
            "",
            f"status: {promotion['status']}",
            f"session_id: {promotion.get('session_id') or 'MISSING'}",
            f"case_id: {promotion.get('case_id') or 'MISSING'}",
            f"selected_variant_id: {promotion['selected_variant_id']}",
            "",
            "## 为什么选它",
        ]
        lines.extend([f"- {item}" for item in promotion["why_selected"]])
        lines.extend([
            "",
            "## 关键产物",
            f"- SELECTED_REPAIR_DSL.yaml: {selected_dsl}",
            f"- source_report_path: {promotion['source_report_path']}",
            "",
            "## 下一步命令",
            f"- QMT 只读检查：`{promotion['qmt_next_command']}`",
            f"- QMT 后阶段门：`{promotion['stage_check_after_qmt_command']}`",
            f"- 生成实盘前证据包：`{promotion['pretrade_package_command']}`",
            "",
            "## 禁止事项",
            f"- {promotion['pretrade_boundary']}",
            "- 该候选只能进入 QMT 只读检查；不能跳过 pretrade-check 或人工确认。",
        ])
        (output_dir / "REPAIR_DSL_PROMOTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (package_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _build_next_actions(
        self,
        *,
        status: str,
        compiled_strategy: dict,
        performance: dict,
        observation: dict | None,
        dsl_path: Path,
        symbol: str,
        timeframe: str,
        adjust: str,
    ) -> list[dict]:
        trade_count = int(performance.get("trade_count") or 0)
        actions: list[dict] = []
        rerun = (
            f"python3 cli.py repair-dsl-backtest --dsl {dsl_path} --symbol {symbol} "
            f"--timeframe {timeframe} --adjust {adjust} --paper-observation --stage-check"
        )
        if status != "VALID":
            actions.append({
                "type": "fix_audit_first",
                "title": "先修审计",
                "detail": "当前修复 DSL 审计未通过，先看 audit_report.md 和 future_leak_report.md，不要进入模拟盘。",
                "next_command": "",
            })
            return actions
        if trade_count == 0:
            actions.extend(self._zero_trade_actions(compiled_strategy))
        elif observation and observation.get("status") != "VALID":
            actions.append({
                "type": "extend_or_refine_paper",
                "title": "补足模拟盘观察",
                "detail": "审计通过但模拟盘观察未通过，优先补足观察期和最低成交次数，再考虑 QMT 只读检查。",
                "next_command": rerun,
            })
        else:
            actions.append({
                "type": "continue_paper_stage",
                "title": "进入模拟盘和阶段门",
                "detail": "审计通过且已有成交样本，下一步用同一 DSL 分支生成模拟盘观察和阶段门报告。",
                "next_command": rerun,
            })
        return actions

    def _zero_trade_actions(self, compiled_strategy: dict) -> list[dict]:
        entry_rules = set(compiled_strategy.get("entry_rules") or [])
        filters = set(compiled_strategy.get("filters") or [])
        actions = [{
            "type": "zero_trade_blocker",
            "title": "先解决 0 成交",
            "detail": "当前分支审计通过但没有任何成交，不能进入 QMT；先放宽入场条件或过滤器，再重新回测。",
            "next_command": "",
        }]
        if "MADeviationEntry" in entry_rules:
            actions.append({
                "type": "relax_entry",
                "title": "放宽均线偏离入场",
                "detail": "把 MADeviationEntry 的 deviation 下调一档，例如从 0.04 调到 0.03，并观察成交次数是否恢复。",
                "dsl_hint": "entry.params.deviation: 0.03",
            })
        if "BollLowerEntry" in entry_rules:
            actions.append({
                "type": "relax_entry",
                "title": "放宽布林低吸条件",
                "detail": "把 BollLowerEntry 的 num_std 下调一档，例如从 2.0 调到 1.8，避免信号过稀。",
                "dsl_hint": "entry.params.num_std: 1.8",
            })
        if "TrendFilter" in filters:
            actions.append({
                "type": "relax_filter",
                "title": "检查趋势过滤是否过严",
                "detail": "TrendFilter 可能把所有入场挡掉；先把 window 缩短一档，或临时移除过滤器做对照实验。",
                "dsl_hint": "filters.TrendFilter.params.window: 10",
            })
        if "CooldownFilter" in filters:
            actions.append({
                "type": "check_filter",
                "title": "保留冷却期但不要先调它",
                "detail": "0 成交通常不是冷却期造成的，优先调入场阈值和趋势过滤；冷却期等成交恢复后再优化。",
                "dsl_hint": "filters.CooldownFilter.params.cooldown_bars: 3",
            })
        return actions

    def _write_next_actions(self, output_dir: Path, actions: list[dict]) -> None:
        (output_dir / "repair_dsl_next_actions.json").write_text(
            json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = ["# Repair DSL Next Actions", ""]
        for item in actions:
            lines.extend([
                f"## {item.get('title')}",
                f"- type: {item.get('type')}",
                f"- detail: {item.get('detail')}",
            ])
            if item.get("dsl_hint"):
                lines.append(f"- dsl_hint: `{item.get('dsl_hint')}`")
            if item.get("next_command"):
                lines.append(f"- next_command: `{item.get('next_command')}`")
            lines.append("")
        (output_dir / "repair_dsl_next_actions.md").write_text("\n".join(lines), encoding="utf-8")
