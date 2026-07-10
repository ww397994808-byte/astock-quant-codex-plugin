from __future__ import annotations

import json
from pathlib import Path

from core.data_loader import load_csv_data
from core.result import TaskResult
from core.run_manager import RunManager
from data_acquisition.acquisition_agent import DataAcquisitionAgent
from data_acquisition.data_request import DataRequest
from experiment_scheduler.batch_budget_manager import BatchBudgetManager
from experiment_scheduler.batch_result_aggregator import BatchResultAggregator
from experiment_scheduler.cross_symbol_runner import CrossSymbolRunner
from experiment_scheduler.cross_timeframe_runner import CrossTimeframeRunner
from experiment_scheduler.experiment_job import ExperimentJob
from experiment_scheduler.random_search_runner import RandomSearchRunner
from experiment_scheduler.regime_split_runner import RegimeSplitRunner
from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import load_corporate_actions
from strategy_compiler.action_compiler import ActionCompiler
from strategy_compiler.compile_report import CompileReportWriter
from strategy_compiler.compiler_errors import StrategyCompileError
from strategy_compiler.dsl_to_strategy import DSLToStrategy


class BatchScheduler:
    def __init__(self, budget: BatchBudgetManager | None = None) -> None:
        self.budget = budget or BatchBudgetManager()
        self.action_compiler = ActionCompiler()
        self.strategy_compiler = DSLToStrategy()
        self.aggregator = BatchResultAggregator()

    def build_jobs(self, parent_iteration: int, plan_actions: list[str], symbol: str, timeframe: str, adjust: str, dsl: dict, data_path: str = "") -> list[ExperimentJob]:
        jobs: list[ExperimentJob] = []
        if any(action in plan_actions for action in ["random_search", "expand_parameter_range", "coarse_grid_restart"]):
            jobs.extend(RandomSearchRunner().create_jobs(parent_iteration, symbol, timeframe, adjust, dsl, max_samples=3))
        if any(action.startswith("test_timeframe") or action == "cross_timeframe_validation" for action in plan_actions):
            jobs.extend(CrossTimeframeRunner().create_jobs(parent_iteration, symbol, adjust, dsl))
        if any(action in plan_actions for action in ["cross_symbol_validate", "test_similar_assets", "test_etf_proxy", "cross_symbol_validation"]):
            jobs.extend(CrossSymbolRunner().create_jobs(parent_iteration, symbol, timeframe, adjust, dsl))
        if any(action in plan_actions for action in ["regime_split_analysis", "bull_bear_sideways_split", "volatility_regime_split", "regime_split_experiments"]):
            jobs.extend(RegimeSplitRunner().create_jobs(parent_iteration, symbol, timeframe, adjust, dsl, data_path=data_path))
        if any(action in plan_actions for action in ["test_entry_exit_combinations", "component_combination_experiments"]):
            jobs.extend(self._component_jobs(parent_iteration, symbol, timeframe, adjust, dsl))
        return self.budget.trim_round(jobs)

    def run(self, parent_iteration: int, plan_actions: list[str], symbol: str, timeframe: str, adjust: str, dsl: dict, output_dir: str | Path, data_path: str = "") -> dict:
        output_dir = Path(output_dir)
        jobs = self.build_jobs(parent_iteration, plan_actions, symbol, timeframe, adjust, dsl, data_path=data_path)
        regime_slice_jobs = []
        if any(action in plan_actions for action in ["regime_split_analysis", "bull_bear_sideways_split", "volatility_regime_split", "regime_split_experiments"]):
            from experiment_scheduler.regime_slice_runner import RegimeSliceRunner

            regime_slice_jobs = RegimeSliceRunner().run(parent_iteration, symbol, timeframe, adjust, dsl, data_path, output_dir / "regime_slice")
        for job in jobs:
            self._run_job(job, output_dir)
        all_jobs = jobs + regime_slice_jobs
        summary = self.aggregator.write(output_dir, all_jobs)
        if regime_slice_jobs:
            summary["regime_slice_stability"] = self.aggregator.summary(regime_slice_jobs).get("regime_stability", 0.5)
            summary["regime_slice_results_path"] = str(output_dir / "regime_slice" / "regime_slice_results.csv")
        summary["jobs"] = [job.to_dict() for job in all_jobs]
        return summary

    def _run_job(self, job: ExperimentJob, output_dir: Path) -> None:
        job_dir = output_dir / "batch_jobs" / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        try:
            data_path = job.data_path
            if not data_path:
                record = DataAcquisitionAgent().fetch(DataRequest(symbol=job.symbol, timeframe=job.timeframe, adjust=job.adjust))
                data_path = record["path"]
                job.data_path = data_path
            self.action_compiler.validate_components(job.strategy_dsl)
            compiled = self.strategy_compiler.compile(job.strategy_dsl, symbol=job.symbol)
            CompileReportWriter().write(job_dir, compiled.compiled_strategy)
            result = self._run_compiled_backtest(compiled, job.symbol, data_path, job.timeframe, job.adjust)
            job.status = "DONE"
            job.result_path = result.report_path or ""
            job.audit_status = result.audit_status or ""
            job.readiness = self._readiness(Path(job.result_path) / "readiness_report.md")
            job.score = self._score(result)
            self._copy_job_summary(job_dir, job, result)
        except (StrategyCompileError, Exception) as exc:
            job.status = "FAILED"
            job.audit_status = "INVALID"
            job.readiness = "INVALID"
            job.failure_reason = str(exc)
            (job_dir / "compile_report.md").write_text(f"# Compile Error\n\n{exc}\n", encoding="utf-8")
        (job_dir / "job.json").write_text(json.dumps(job.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _component_jobs(self, parent_iteration: int, symbol: str, timeframe: str, adjust: str, dsl: dict) -> list[ExperimentJob]:
        jobs = []
        for idx, action in enumerate(["test_boll_entry", "test_ma_deviation_entry", "test_atr_oversold_entry"], start=1):
            job_dsl = self.action_compiler.compile_action(dsl, action)
            jobs.append(ExperimentJob(f"component_{parent_iteration}_{idx}", parent_iteration, "component_combination", symbol, timeframe, adjust, job_dsl, parameters={"action": action}))
        return jobs

    def _score(self, result: TaskResult) -> float:
        perf = result.artifacts.get("performance", {}) if result.artifacts else {}
        if result.audit_status == "INVALID":
            return -999
        total_return = float(perf.get("total_return", 0) or 0)
        mdd = abs(float(perf.get("max_drawdown", 0) or 0))
        trades = min(float(perf.get("trade_count", 0) or 0) / 20, 1)
        return round(max(0.0, min(1.0, 0.4 * total_return + 0.4 * (1 - min(mdd, 0.5) / 0.5) + 0.2 * trades)), 6)

    def _run_compiled_backtest(self, compiled, symbol: str, data_path: str, timeframe: str, adjust: str) -> TaskResult:
        ctx = RunManager().create_run("batch_backtest")
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
        result = template.run(ctx, rows, source_paths=[Path("strategy_compiler/dsl_to_strategy.py"), Path("strategy_compiler/action_compiler.py")])
        return TaskResult(result.status, f"批量实验回测完成：{result.status}", result.run_id, str(result.output_dir), result.audit_status, artifacts={"performance": result.performance})

    def _readiness(self, path: Path) -> str:
        if not path.exists():
            return "UNKNOWN"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("readiness:"):
                return line.split(":", 1)[1].strip()
        return "UNKNOWN"

    def _copy_job_summary(self, job_dir: Path, job: ExperimentJob, result: TaskResult) -> None:
        (job_dir / "result_summary.md").write_text(
            f"# Job Result\n\nstatus: {job.status}\naudit_status: {job.audit_status}\nreadiness: {job.readiness}\nscore: {job.score}\nresult_path: {result.report_path}\n",
            encoding="utf-8",
        )
