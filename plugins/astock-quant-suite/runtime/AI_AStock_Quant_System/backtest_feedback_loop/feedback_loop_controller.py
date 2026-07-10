from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from backtest_feedback_loop.backtest_result_analyzer import BacktestResultAnalyzer
from backtest_feedback_loop.candidate_selector import CandidateSelector
from backtest_feedback_loop.deep_diagnosis import DeepDiagnosis
from backtest_feedback_loop.feedback_loop_report import FeedbackLoopReportWriter
from backtest_feedback_loop.loop_config import LoopConfig
from backtest_feedback_loop.loop_memory import LoopMemory
from backtest_feedback_loop.modification_actions import ModificationAction
from backtest_feedback_loop.optimization_director import OptimizationDirector
from backtest_feedback_loop.research_expander import ResearchExpander
from backtest_feedback_loop.stopping_rules import StoppingRules
from backtest_feedback_loop.strategy_modifier import StrategyModifier
from backtest_templates.grid_template import GridTemplate
from core.data_loader import load_csv_data
from core.result import TaskResult
from core.run_manager import RunManager
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest
from experiment_scheduler.batch_report import BatchReport
from experiment_scheduler.batch_scheduler import BatchScheduler
from intake.strategy_intake_agent import StrategyIntakeAgent
from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import load_corporate_actions
from research.research_loop import ResearchLoop
from strategy_compiler.action_compiler import ActionCompiler
from strategy_compiler.compile_report import CompileReportWriter
from strategy_compiler.compiler_errors import StrategyCompileError
from strategy_compiler.component_registry import ComponentRegistry
from strategy_compiler.dsl_to_strategy import DSLToStrategy
from strategies.strategy_registry import create_strategy


class FeedbackLoopController:
    def run(
        self,
        idea: str,
        symbol: str,
        timeframe: str = "1d",
        adjust: str = "raw",
        max_iterations: int | None = None,
    ) -> TaskResult:
        config = LoopConfig(max_iterations=max_iterations or LoopConfig().max_iterations)
        ctx = RunManager().create_run("optimize_loop")
        output_dir = ctx.output_dir

        data_record = DataAcquisitionAgent().fetch(DataRequest(symbol=symbol, timeframe=timeframe, adjust=adjust))
        data_path = data_record["path"]

        intake_result = StrategyIntakeAgent().run(idea)
        if intake_result.report_path is None:
            return TaskResult("INVALID", "Intake 未生成报告，无法进入优化闭环", ctx.run_id, str(output_dir), "INVALID")
        intake_dir = Path(intake_result.report_path)
        dsl_path = intake_dir / "strategy_dsl.yaml"
        current_dsl = self._load_dsl(dsl_path)
        current_dsl["symbols"] = [symbol]
        current_dsl["timeframe"] = timeframe
        current_dsl["adjust"] = adjust
        (output_dir / "initial_strategy_dsl.yaml").write_text(
            yaml.safe_dump(current_dsl, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

        research_result = ResearchLoop().run(idea, symbol, data_path, timeframe=timeframe, adjust=adjust, data_source=data_record["source"])
        if research_result.report_path:
            self._copy_if_exists(Path(research_result.report_path) / "research_plan.md", output_dir / "initial_research_plan.md")

        memory = LoopMemory()
        writer = FeedbackLoopReportWriter()
        selector = CandidateSelector()
        stopping = StoppingRules()
        action_compiler = ActionCompiler()
        strategy_compiler = DSLToStrategy()
        compile_writer = CompileReportWriter()
        registry = ComponentRegistry()
        deep_files: list[str] = []
        deep_rounds = 0
        total_experiments = 0
        pending_action_reports: list[dict] = []

        for iteration in range(1, config.max_iterations + 1):
            should_stop, _ = stopping.should_stop(iteration - 1, total_experiments, deep_rounds, config)
            if should_stop:
                break

            iter_dir = output_dir / f"iteration_{iteration}"
            iter_dir.mkdir(parents=True, exist_ok=True)
            (iter_dir / "strategy_dsl.yaml").write_text(
                yaml.safe_dump(current_dsl, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            registry.write_component_list(iter_dir / "component_list.md")

            if current_dsl.get("pattern") == "grid":
                compiled_strategy = self._grid_compiled_strategy(current_dsl)
                compile_writer.write(iter_dir, compiled_strategy, action_reports=pending_action_reports)
                backtest = self._run_grid_backtest(current_dsl, symbol, data_path, timeframe, adjust)
                strategy_name = "grid_template"
            else:
                try:
                    compiled = strategy_compiler.compile(current_dsl, symbol=symbol)
                    compile_writer.write(iter_dir, compiled.compiled_strategy, action_reports=pending_action_reports)
                except StrategyCompileError as exc:
                    compile_writer.write(iter_dir, errors=[str(exc)], action_reports=pending_action_reports)
                    memory.add(self._compile_error_record(iteration, str(exc), current_dsl, adjust, data_record))
                    pending_action_reports = []
                    continue
                backtest = self._run_compiled_backtest(compiled, symbol, data_path, timeframe, adjust)
                strategy_name = compiled.strategy.name
            total_experiments += 1
            bt_dir = Path(backtest.report_path or "")
            self._copy_backtest_artifacts(bt_dir, iter_dir)

            analysis = BacktestResultAnalyzer().analyze(bt_dir)
            self._copy_if_exists(bt_dir / "analysis.md", iter_dir / "analysis.md")
            (iter_dir / "metrics.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

            actions = OptimizationDirector().propose(analysis)
            new_dsl, modifications = StrategyModifier().apply(current_dsl, actions)
            writer.write_modification_plan(
                iter_dir / "modification_plan.md",
                [action.__dict__ for action in actions],
                modifications,
            )

            record = self._record_from_iteration(
                iteration, backtest, analysis, actions, current_dsl, adjust, data_record, strategy_name
            )
            memory.add(record)

            current_dsl, pending_action_reports = action_compiler.compile_actions(current_dsl, [action.action for action in actions])
            if stopping.should_deep_diagnose(memory.no_improve_rounds(config.min_improvement_threshold), config):
                deep_rounds += 1
                deep_path = output_dir / f"deep_diagnosis_round_{deep_rounds}.md"
                diagnosis = DeepDiagnosis().run(memory.records, bt_dir, deep_path)
                deep_files.append(str(deep_path))
                expanded_actions = ResearchExpander().expand(diagnosis.get("failures", []))
                (output_dir / f"expanded_experiment_plan_round_{deep_rounds}.md").write_text(
                    "# Expanded Experiment Plan\n\n" + "\n".join(f"- {action}" for action in expanded_actions) + "\n",
                    encoding="utf-8",
                )
                batch_summary = BatchScheduler().run(
                    parent_iteration=iteration,
                    plan_actions=expanded_actions,
                    symbol=symbol,
                    timeframe=timeframe,
                    adjust=adjust,
                    dsl=current_dsl,
                    output_dir=iter_dir,
                    data_path=data_path,
                )
                memory.records[-1]["batch_summary"] = {key: value for key, value in batch_summary.items() if key != "jobs"}
                memory.records[-1]["batch_jobs"] = batch_summary.get("jobs", [])
                memory.records[-1]["batch_results_path"] = str(iter_dir / "batch_results.csv")
                current_dsl, pending_action_reports = action_compiler.compile_actions(current_dsl, expanded_actions[:3])
                memory.records[-1]["deep_diagnosis_triggered"] = True

        candidates, rejected = selector.select(memory.records)
        writer.write_candidate_files(output_dir, candidates, rejected)
        memory.save(output_dir / "loop_memory.json")
        writer.write_final_report(output_dir, idea, memory.records, candidates, rejected, deep_files)
        last_batch = next((record.get("batch_summary") for record in reversed(memory.records) if record.get("batch_summary")), None)
        if last_batch:
            BatchReport().append_to_final_report(output_dir / "final_feedback_loop_report.md", last_batch)
        writer.write_codex_prompt(output_dir, idea, candidates, rejected)
        self._write_completion_report(output_dir, memory.records, candidates, rejected, deep_files)

        return TaskResult(
            "VALID" if candidates else "INVALID",
            "V7 回测反馈优化闭环完成",
            ctx.run_id,
            str(output_dir),
            "VALID" if candidates else "INVALID",
            warnings=[] if candidates else ["没有形成可推荐候选，已输出失败诊断和下一轮建议"],
            artifacts={"iterations": len(memory.records), "candidates": len(candidates), "deep_diagnosis_rounds": deep_rounds},
        )

    def _load_dsl(self, path: Path) -> dict:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}

    def _strategy_for_dsl(self, dsl: dict) -> str:
        pattern = dsl.get("pattern", "swing")
        entry_type = (dsl.get("entry") or {}).get("type", "")
        if pattern == "timing" or "MA" in entry_type:
            return "ma_cross"
        if "Drawdown" in entry_type:
            return "dividend_drawdown"
        return "boll_mean_reversion"

    def _params_for_strategy(self, strategy: str, dsl: dict) -> dict:
        if strategy == "ma_cross":
            return {"short_window": 5, "long_window": 20}
        if strategy == "dividend_drawdown":
            return {"lookback": 20, "drawdown_threshold": 0.08, "rebound_threshold": 0.04, "stop_loss": 0.08}
        return {"window": 20, "num_std": 2.0, "stop_loss": 0.08}

    def _copy_backtest_artifacts(self, bt_dir: Path, iter_dir: Path) -> None:
        self._copy_if_exists(bt_dir / "README_本次研究.md", iter_dir / "backtest_report.md")
        if not (iter_dir / "backtest_report.md").exists():
            self._copy_if_exists(bt_dir / "audit_report.md", iter_dir / "backtest_report.md")
        for name in [
            "audit_report.md",
            "future_leak_report.md",
            "trade_rule_report.md",
            "readiness_report.md",
            "orders.csv",
            "trades.csv",
            "equity_curve.csv",
            "performance.json",
        ]:
            self._copy_if_exists(bt_dir / name, iter_dir / name)

    def _copy_if_exists(self, src: Path, dst: Path) -> None:
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)

    def _run_compiled_backtest(self, compiled, symbol: str, data_path: str, timeframe: str, adjust: str) -> TaskResult:
        ctx = RunManager().create_run("loop_backtest")
        rows = load_csv_data(data_path, symbol=symbol)
        candidates = [
            Path(f"data/sample/corporate_actions_{symbol.split('.')[0]}.csv"),
            Path(f"data/sample/corporate_actions_{symbol.replace('.', '_')}.csv"),
            Path(f"data/sample/corporate_actions_{symbol}.csv"),
        ]
        action_file = next((path for path in candidates if path.exists()), None)
        actions = load_corporate_actions(action_file, symbol) if action_file else []
        rows = AdjustmentEngine().adjust(rows, actions, adjust)
        for row in rows:
            row["timeframe"] = timeframe or row.get("timeframe", "1d")
        template = compiled.template_class(strategy=compiled.strategy, symbol=symbol, initial_cash=1000000)
        source_paths = [
            Path("strategy_compiler/dsl_to_strategy.py"),
            Path("strategy_compiler/action_compiler.py"),
        ]
        result = template.run(ctx, rows, source_paths=source_paths)
        return TaskResult(
            status=result.status,
            message=f"编译策略回测完成：{result.status}",
            run_id=result.run_id,
            report_path=str(result.output_dir),
            audit_status=result.audit_status,
            artifacts={"performance": result.performance},
        )

    def _grid_compiled_strategy(self, dsl: dict) -> dict:
        params = (dsl.get("entry") or {}).get("params", {})
        return {
            "strategy_name": "grid_template",
            "pattern": "grid",
            "template_name": "grid",
            "entry_rules": ["GridLayerEntry"],
            "exit_rules": ["GridLayerExit"],
            "filters": [],
            "sizing_rules": [dsl.get("sizing", {}).get("type", "LayeredSizing")],
            "risk_controls": [{"max_drawdown": dsl.get("objective", {}).get("max_drawdown")}],
            "params": self._first_params(params),
        }

    def _run_grid_backtest(self, dsl: dict, symbol: str, data_path: str, timeframe: str, adjust: str) -> TaskResult:
        ctx = RunManager().create_run("loop_backtest")
        rows = load_csv_data(data_path, symbol=symbol)
        candidates = [
            Path(f"data/sample/corporate_actions_{symbol.split('.')[0]}.csv"),
            Path(f"data/sample/corporate_actions_{symbol.replace('.', '_')}.csv"),
            Path(f"data/sample/corporate_actions_{symbol}.csv"),
        ]
        action_file = next((path for path in candidates if path.exists()), None)
        actions = load_corporate_actions(action_file, symbol) if action_file else []
        rows = AdjustmentEngine().adjust(rows, actions, adjust)
        for row in rows:
            row["timeframe"] = timeframe or row.get("timeframe", "1d")
        params = self._first_params((dsl.get("entry") or {}).get("params", {}))
        sizing_params = self._first_params((dsl.get("sizing") or {}).get("params", {}))
        template = GridTemplate(
            create_strategy("ma_cross"),
            symbol,
            initial_cash=1000000,
            grid_step=float(params.get("grid_step", 0.03)),
            levels=int(params.get("levels", 3)),
            layer_percent=float(params.get("layer_percent", sizing_params.get("percent", 0.1))),
            grid_base=str(params.get("grid_base", "fixed")),
            ma_window=int(params.get("ma_window", 5)),
            max_position_percent=float(params.get("max_position_percent", 0.95)),
        )
        result = template.run(ctx, rows, source_paths=[Path("backtest_templates/grid_template.py")])
        return TaskResult(
            status=result.status,
            message=f"网格策略回测完成：{result.status}",
            run_id=result.run_id,
            report_path=str(result.output_dir),
            audit_status=result.audit_status,
            artifacts={"performance": result.performance},
        )

    def _first_params(self, params: dict) -> dict:
        normalized = {}
        for key, value in params.items():
            normalized[key] = value[0] if isinstance(value, list) and value else value
        return normalized

    def _compile_error_record(self, iteration: int, error: str, dsl: dict, adjust: str, data_record: dict) -> dict:
        return {
            "iteration": iteration,
            "variant_id": f"iteration_{iteration}",
            "strategy_name": "compile_error",
            "status": "INVALID",
            "audit_status": "INVALID",
            "readiness": "INVALID",
            "compile_error": error,
            "analysis": {"issues": ["compile_error"], "trade_count": 0, "max_drawdown": 0, "calmar": 0},
            "actions": [],
            "score": -999,
            "out_sample_score": 0,
            "max_drawdown": 0,
            "calmar": 0,
            "stability": 0,
            "trade_count": 0,
            "stress_result": 0,
            "data_quality_score": data_record.get("data_quality_score", 60) / 100,
            "strategy_simplicity": 0,
            "regime_robustness": 0,
            "adjust": adjust,
            "qfq_risk": adjust in {"qfq", "hfq"},
            "dsl": dsl,
        }

    def _record_from_iteration(
        self,
        iteration: int,
        backtest: TaskResult,
        analysis: dict,
        actions: list[ModificationAction],
        dsl: dict,
        adjust: str,
        data_record: dict,
        strategy_name: str,
    ) -> dict:
        score = self._score(analysis, backtest)
        readiness = analysis.get("readiness") or ("PAPER_READY" if backtest.audit_status == "VALID" else "INVALID")
        if adjust in {"qfq", "hfq"} and readiness in {"PAPER_READY", "LIVE_CANDIDATE"}:
            readiness = "RESEARCH_ONLY"
        objective = dsl.get("objective", {})
        min_annual_return = objective.get("min_annual_return")
        max_allowed_drawdown = objective.get("max_drawdown")
        annual_return = float(analysis.get("annual_return", 0.0) or 0.0)
        max_drawdown = float(analysis.get("max_drawdown", 0.0) or 0.0)
        user_gate_pass = True
        if min_annual_return is not None and annual_return < float(min_annual_return):
            user_gate_pass = False
        if max_allowed_drawdown is not None and abs(max_drawdown) > float(max_allowed_drawdown):
            user_gate_pass = False
        if not user_gate_pass and readiness in {"PAPER_READY", "LIVE_CANDIDATE"}:
            readiness = "RESEARCH_ONLY"
        return {
            "iteration": iteration,
            "variant_id": f"iteration_{iteration}",
            "strategy_name": strategy_name,
            "status": backtest.status,
            "audit_status": backtest.audit_status,
            "readiness": readiness,
            "analysis": analysis,
            "actions": [action.__dict__ for action in actions],
            "score": score,
            "annual_return": annual_return,
            "min_annual_return": min_annual_return,
            "max_allowed_drawdown": max_allowed_drawdown,
            "user_gate_pass": user_gate_pass,
            "out_sample_score": self._bounded(analysis.get("out_sample_return", 0.0)),
            "max_drawdown": analysis.get("max_drawdown", 0.0),
            "calmar": analysis.get("calmar", 0.0),
            "stability": analysis.get("stability", 0.5),
            "trade_count": analysis.get("trade_count", 0),
            "stress_result": 1.0 if analysis.get("stress_result") == "VALID" else 0.6,
            "data_quality_score": data_record.get("data_quality_score", 60) / 100,
            "strategy_simplicity": max(0.3, 1.0 - len(dsl.get("filters", [])) * 0.1),
            "regime_robustness": 0.6,
            "adjust": adjust,
            "qfq_risk": adjust in {"qfq", "hfq"},
        }

    def _score(self, analysis: dict, backtest: TaskResult) -> float:
        if backtest.audit_status == "INVALID":
            return -999.0
        return (
            0.35 * self._bounded(analysis.get("calmar", 0.0) / 3)
            + 0.25 * self._bounded(analysis.get("out_sample_return", 0.0))
            + 0.2 * self._bounded(1 - abs(analysis.get("max_drawdown", 0.0)))
            + 0.1 * self._bounded(analysis.get("stability", 0.5))
            + 0.1 * self._bounded(analysis.get("trade_count", 0) / 20)
        )

    def _bounded(self, value: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    def _write_completion_report(self, output_dir: Path, records: list[dict], candidates: list[dict], rejected: list[dict], deep_files: list[str]) -> None:
        Path("V7_BACKTEST_FEEDBACK_LOOP_COMPLETION_REPORT.md").write_text(
            "\n".join(
                [
                    "# V7 Backtest Feedback Loop Completion Report",
                    "",
                    f"- 迭代轮数：{len(records)}",
                    f"- 候选数量：{len(candidates)}",
                    f"- 拒绝数量：{len(rejected)}",
                    f"- Deep Diagnosis 轮数：{len(deep_files)}",
                    f"- 输出目录：{output_dir}",
                    "",
                    "V7 已把一次性研究扩展为回测后反馈优化闭环：每轮先回测，再诊断，再修改，并在连续无改善时触发深度诊断和扩大研究。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
