from __future__ import annotations

import shutil
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager
from examples.sample_data_generator import generate_sample_data
from services.backtest_service import BacktestService
from services.explain_report_service import ExplainReportService
from services.intake_service import IntakeService
from services.optimize_loop_service import OptimizeLoopService
from services.research_service import ResearchService


class CourseDemoService:
    def run(self) -> TaskResult:
        idea = "中国神华周线布林低吸波段，控制回撤，不要太频繁交易"
        symbol = "601088.SH"
        timeframe = "1w"
        adjust = "point_in_time_qfq"
        ctx = RunManager().create_run("course_demo")
        output_dir = ctx.output_dir

        data_path = generate_sample_data(symbol=symbol, timeframe="1d")
        weekly_path = generate_sample_data(symbol=symbol, timeframe=timeframe)
        steps: list[dict] = [
            {"step": "generate-sample-data", "status": "VALID", "path": str(data_path), "weekly_path": str(weekly_path)},
        ]

        intake = IntakeService().run(idea=idea)
        steps.append(self._step("intake", intake))
        self._copy_report(intake.report_path, output_dir / "01_intake")

        research = ResearchService().run(direction=idea, symbol=symbol, data=str(weekly_path), timeframe=timeframe, adjust=adjust)
        steps.append(self._step("research", research))
        self._copy_report(research.report_path, output_dir / "02_research")

        backtest = BacktestService().run("boll_mean_reversion", symbol, str(weekly_path), timeframe=timeframe, adjust=adjust)
        steps.append(self._step("backtest", backtest))
        self._copy_report(backtest.report_path, output_dir / "03_backtest")

        loop = OptimizeLoopService().run(idea=idea, symbol=symbol, timeframe=timeframe, adjust=adjust, max_iterations=3)
        steps.append(self._step("optimize-loop", loop))
        self._copy_report(loop.report_path, output_dir / "04_optimize_loop")

        explain = ExplainReportService().run(backtest.run_id or "latest")
        steps.append(self._step("explain-report", explain))
        if explain.report_path:
            (output_dir / "05_explain_report.md").write_text(Path(explain.report_path).read_text(encoding="utf-8"), encoding="utf-8")

        self._write_summary(output_dir, idea, symbol, timeframe, adjust, steps)
        return TaskResult(
            "VALID",
            "课程演示已完成：Intake -> Research -> Backtest -> Optimize-loop -> Explain-report",
            run_id=ctx.run_id,
            report_path=str(output_dir),
            audit_status=backtest.audit_status,
            artifacts={"steps": steps},
        )

    def _step(self, name: str, result: TaskResult) -> dict:
        return {
            "step": name,
            "status": result.status,
            "run_id": result.run_id or "",
            "report_path": result.report_path or "",
            "audit_status": result.audit_status or "",
        }

    def _copy_report(self, src: str | None, dst: Path) -> None:
        if not src:
            return
        src_path = Path(src)
        if not src_path.exists():
            return
        if src_path.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src_path, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_path, dst)

    def _write_summary(self, output_dir: Path, idea: str, symbol: str, timeframe: str, adjust: str, steps: list[dict]) -> None:
        lines = [
            "# Course Demo Summary",
            "",
            f"- idea: {idea}",
            f"- symbol: {symbol}",
            f"- timeframe: {timeframe}",
            f"- adjust: {adjust}",
            "",
            "## Steps",
        ]
        for item in steps:
            lines.append(f"- {item['step']}: {item['status']} {item.get('report_path', '')}")
        lines += [
            "",
            "## Student Notes",
            "这个 demo 的目的不是证明策略赚钱，而是让学生第一天跑通完整研究链路，并看到审计、Readiness 和解释报告如何工作。",
        ]
        (output_dir / "COURSE_DEMO_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
