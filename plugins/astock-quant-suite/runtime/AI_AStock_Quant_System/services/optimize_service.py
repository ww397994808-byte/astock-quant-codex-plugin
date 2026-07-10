from __future__ import annotations

from backtest.report import write_json
from core.result import TaskResult
from core.run_manager import RunManager
from optimizer.grid_search import GridSearchOptimizer
from optimizer.optimizer_report import write_optimizer_report
from optimizer.stability_check import StabilityChecker
from optimizer.walk_forward import WalkForwardAnalyzer


class OptimizeService:
    def run(self, strategy: str, symbol: str, data: str) -> TaskResult:
        ctx = RunManager().create_run("optimize")
        opt = GridSearchOptimizer().run(strategy, symbol, data, ctx.output_dir)
        wf = WalkForwardAnalyzer().analyze(opt)
        stability = StabilityChecker().analyze(opt)
        write_json(ctx.output_dir / "optimizer_results.json", opt)
        write_optimizer_report(ctx.output_dir / "optimizer_report.md", opt, wf, stability)
        return TaskResult("VALID", "参数优化完成", ctx.run_id, str(ctx.output_dir), "VALID", artifacts={"best": opt.get("best")})

