from __future__ import annotations

from core.result import TaskResult
from core.run_manager import RunManager
from backtest_plans.plan_builder import BacktestPlanBuilder
from intake.completeness_checker import CompletenessChecker
from intake.dsl_builder import DSLBuilder
from intake.intent_parser import IntentParser
from intake.intake_report import IntakeReportWriter
from intake.prompt_builder import PromptBuilder


class StrategyIntakeAgent:
    def run(self, idea: str) -> TaskResult:
        ctx = RunManager().create_run("intake")
        req = IntentParser().parse(idea)
        req = CompletenessChecker().score(req)
        req.write_json(ctx.output_dir / "strategy_requirement.json")
        IntakeReportWriter().write(ctx.output_dir, req)
        plan = BacktestPlanBuilder().build(req)
        plan.write_yaml(ctx.output_dir / "backtest_plan.yaml")
        if req.completeness_score >= 70:
            DSLBuilder().write_yaml(ctx.output_dir / "strategy_dsl.yaml", req)
            PromptBuilder().write(ctx.output_dir / "codex_research_prompt.md", req)
        else:
            (ctx.output_dir / "strategy_dsl.yaml").write_text("# incomplete\n", encoding="utf-8")
            (ctx.output_dir / "codex_research_prompt.md").write_text("# incomplete\n当前策略想法还不够完整，请先回答 unanswered_questions.md。\n", encoding="utf-8")
        message = "当前策略想法还不够完整，建议先回答以下问题" if req.completeness_score < 70 else "策略需求已结构化，可进入 Research Agent"
        return TaskResult(
            status="VALID" if req.completeness_score >= 70 else "INVALID",
            message=message,
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            warnings=req.unanswered_questions[:5],
            artifacts={
                "completeness_score": req.completeness_score,
                "readiness_for_research": req.readiness_for_research,
                "backtest_plan_status": plan.status,
                "backtest_plan_blockers": plan.blockers,
            },
        )
