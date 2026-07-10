from __future__ import annotations

from core.result import TaskResult
from core.run_manager import RunManager
from backtest_plans.plan_builder import BacktestPlanBuilder
from intake.adaptive.adaptive_intake_report import AdaptiveIntakeReportWriter
from intake.adaptive.answer_parser import AnswerParser
from intake.adaptive.clarification_policy import ClarificationPolicy
from intake.adaptive.conversation_memory import ConversationMemory
from intake.adaptive.interview_state import InterviewState
from intake.adaptive.question_tree import QuestionTree
from intake.adaptive.requirement_builder import RequirementBuilder
from intake.adaptive.research_readiness_checker import ResearchReadinessChecker
from intake.dsl_builder import DSLBuilder
from intake.prompt_builder import PromptBuilder


class AdaptiveInterviewAgent:
    def run(self, idea: str | None = None, confirm: bool = False) -> TaskResult:
        ctx = RunManager().create_run("adaptive_intake")
        idea = idea or ""
        fields = AnswerParser().parse(idea)
        fields.setdefault("adjust", "point_in_time_qfq")
        if fields.get("risk_preference") == "conservative":
            fields.setdefault("objective", {"primary": "calmar", "trade_frequency": "low"})
        if fields.get("constraints", {}).get("trade_count_penalty"):
            fields.setdefault("objective", {"primary": "calmar", "trade_frequency": "low"})

        all_questions = QuestionTree().next_questions(fields)
        top_questions = ClarificationPolicy().top_questions(all_questions)
        score, research_ready, missing = ResearchReadinessChecker().score(fields, user_confirmed=confirm)
        assumptions = self._assumptions(fields, missing)
        state = InterviewState(
            original_idea=idea,
            current_question_id=top_questions[0][0] if top_questions else "confirm",
            unanswered_questions=[q for _, q in top_questions],
            inferred_fields=fields,
            assumptions=assumptions,
            completeness_score=score,
            research_ready=research_ready,
            user_confirmed=confirm,
        )
        req = RequirementBuilder().build(idea, fields, score, research_ready, state.unanswered_questions)
        req.write_json(ctx.output_dir / "strategy_requirement.json")
        plan = BacktestPlanBuilder().build(req)
        plan.write_yaml(ctx.output_dir / "backtest_plan.yaml")
        state.write_json(ctx.output_dir / "interview_state.json")
        DSLBuilder().write_yaml(ctx.output_dir / "strategy_dsl.yaml", req)
        PromptBuilder().write(ctx.output_dir / "codex_research_prompt.md", req)
        ConversationMemory().write(ctx.output_dir / "conversation_log.md", idea, top_questions, fields)
        AdaptiveIntakeReportWriter().write(ctx.output_dir, state, req, top_questions)
        message = "Adaptive Intake 已生成确认摘要；用户确认前不会进入 Research Agent"
        if research_ready:
            message = "Adaptive Intake 已确认，可进入 Research Agent"
        return TaskResult(
            "VALID" if score >= 40 else "INVALID",
            message,
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status="VALID" if research_ready else "PENDING",
            warnings=state.unanswered_questions[:5],
            artifacts={
                "completeness_score": score,
                "research_ready": research_ready,
                "user_confirmed": confirm,
                "backtest_plan_status": plan.status,
                "backtest_plan_blockers": plan.blockers,
            },
        )

    def _assumptions(self, fields: dict, missing: list[str]) -> list[str]:
        assumptions = []
        if "adjust" not in fields:
            assumptions.append("默认使用 point_in_time_qfq，避免普通 qfq 未来函数风险。")
        for key in missing:
            assumptions.append(f"{key} 尚未确认，不能直接进入 Research Agent。")
        if fields.get("strategy_pattern") in {"pair_trading", "event_driven"}:
            assumptions.append(fields.get("blocker", "该策略范式当前为 BLOCKER。"))
        return assumptions
