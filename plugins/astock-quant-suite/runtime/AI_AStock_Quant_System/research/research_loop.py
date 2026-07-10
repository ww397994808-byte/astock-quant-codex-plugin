from __future__ import annotations

from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager
from research.experiment_runner import ExperimentRunner
from research.hypothesis_generator import HypothesisGenerator
from research.overfit_detector import OverfitDetector
from research.pattern_classifier import PatternClassifier
from research.research_plan import ResearchPlan
from research.research_report import ResearchReportWriter
from research.result_ranker import ResultRanker
from research.search_space_builder import SearchSpaceBuilder
from research.strategy_variant_generator import StrategyVariantGenerator


class ResearchLoop:
    def run(self, direction: str, symbol: str, data: str, timeframe: str = "1d", adjust: str = "raw", data_source: str = "local") -> TaskResult:
        ctx = RunManager().create_run("research")
        output_dir = ctx.output_dir
        classification = PatternClassifier().classify(direction)
        hypothesis = HypothesisGenerator().generate(direction, classification.pattern)
        search_space = SearchSpaceBuilder().build(classification.pattern, direction)
        blocker_notes = [classification.blocker_note] if classification.blocker else []
        plan = ResearchPlan(
            original_direction=direction,
            selected_pattern=classification.pattern,
            hypothesis=hypothesis,
            variables_to_test=list(search_space) or ["BLOCKER"],
            entry_logic_candidates=self._entry_candidates(classification.pattern),
            exit_logic_candidates=self._exit_candidates(classification.pattern),
            sizing_candidates=["target_percent", "cash_buffer", "layer_percent"],
            filter_candidates=["审计 VALID", "样本外不明显退化", "交易次数不能过少"],
            risk_candidates=["max_drawdown", "stop_loss", "drift_threshold", "switch_threshold"],
            search_space=search_space,
            constraints=["A股 T+1", "涨跌停", "停牌不可交易", "100股手数", "费用计入", "signal_time < execute_time"],
            evaluation_metrics=["calmar_score", "out_sample_score", "drawdown_score", "stability_score", "trade_count_score"],
            timeframe=timeframe,
            adjust=adjust,
            data_source=data_source,
            blocker_notes=blocker_notes,
        )
        writer = ResearchReportWriter()
        plan.write_markdown(output_dir / "research_plan.md")
        writer.write_hypothesis(output_dir / "hypothesis.md", hypothesis)
        writer.write_search_space(output_dir / "search_space.json", search_space)

        if classification.blocker:
            writer.write_variants(output_dir / "strategy_variants.csv", [])
            (output_dir / "experiment_results.csv").write_text("variant_id,audit_status\n", encoding="utf-8")
            (output_dir / "ranked_results.csv").write_text("variant_id,score,audit_status\n", encoding="utf-8")
            overfit_report = {}
            OverfitDetector().write_report(output_dir / "overfit_report.md", [], search_space)
            writer.write_stability_report(output_dir / "stability_report.md", [])
            writer.write_next_round(output_dir / "next_round_suggestions.md", [], overfit_report)
            writer.write_final_report(output_dir / "final_research_report.md", plan, [], overfit_report)
            return TaskResult("INVALID", "研究方向存在 BLOCKER，已生成说明报告", ctx.run_id, str(output_dir), "INVALID", warnings=blocker_notes)

        max_variants = 60 if classification.pattern == "grid" else 12
        variants = StrategyVariantGenerator().generate(classification.pattern, search_space, max_variants=max_variants)
        writer.write_variants(output_dir / "strategy_variants.csv", variants)
        results = ExperimentRunner().run(variants, symbol, data, output_dir, timeframe=timeframe, adjust=adjust)
        ranked = ResultRanker().rank(results)
        ResultRanker().write_csv(output_dir / "ranked_results.csv", ranked)
        overfit_report = OverfitDetector().write_report(output_dir / "overfit_report.md", results, search_space)
        writer.write_stability_report(output_dir / "stability_report.md", ranked)
        writer.write_next_round(output_dir / "next_round_suggestions.md", ranked, overfit_report)
        writer.write_final_report(output_dir / "final_research_report.md", plan, ranked, overfit_report)
        status = "VALID" if ranked else "INVALID"
        return TaskResult(status, f"Research Agent V2 完成：{status}", ctx.run_id, str(output_dir), status, artifacts={"ranked_count": len(ranked), "pattern": classification.pattern})

    def _entry_candidates(self, pattern: str) -> list[str]:
        return {
            "swing": ["布林下轨低吸", "N日回撤买入"],
            "timing": ["短均线上穿长均线", "趋势突破"],
            "grid": ["价格下穿网格层级"],
            "stock_selection": ["因子排名 top_n"],
            "rotation": ["强弱评分 top_k"],
            "portfolio": ["权重漂移超过阈值"],
        }.get(pattern, [])

    def _exit_candidates(self, pattern: str) -> list[str]:
        return {
            "swing": ["回到布林中轨", "止损", "时间退出"],
            "timing": ["短均线下穿长均线"],
            "grid": ["价格上穿网格层级"],
            "stock_selection": ["调仓日剔除"],
            "rotation": ["评分切换"],
            "portfolio": ["再平衡到目标权重"],
        }.get(pattern, [])
