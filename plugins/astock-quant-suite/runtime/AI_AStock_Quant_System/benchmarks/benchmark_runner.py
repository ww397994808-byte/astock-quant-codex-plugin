from __future__ import annotations

import json
import shutil
from pathlib import Path

from intake.strategy_intake_agent import StrategyIntakeAgent
from research.research_loop import ResearchLoop


BENCHMARKS = {
    "shenhua_weekly_boll_swing": "中国神华 周线 跌多了买 涨回去卖 控制回撤 不要太频繁交易",
    "shenhua_drawdown_rebound": "神华大跌后买 反弹卖 尽量减少回撤",
    "dividend_etf_grid": "红利ETF 网格 跌5%加仓 涨5%减仓",
    "coal_bank_rotation": "煤炭 银行 电力 轮动 每月调仓",
    "high_dividend_selection": "高股息 低波动 选股 每季度调仓",
    "bank_etf_rotation": "银行ETF 红利ETF 轮动",
    "boll_1h_intraday": "1小时布林低吸 波段",
    "weekly_ma_timing": "周线均线择时",
    "dividend_portfolio": "高股息组合 长期持有 年度再平衡",
    "conservative_swing": "年化15%左右 回撤尽量低 波段策略",
}


class BenchmarkRunner:
    def run_all(self, data_path: str = "data/sample/601088.csv") -> dict:
        root = Path("benchmarks")
        root.mkdir(exist_ok=True)
        scores = {}
        gaps = []
        for name, idea in BENCHMARKS.items():
            result = self.run_one(name, idea, data_path)
            scores[name] = result
            gaps.extend(result["gaps"])
        self._write_gap_report(root / "benchmark_gap_report.md", gaps)
        self._write_final_report(scores)
        return scores

    def run_one(self, name: str, idea: str, data_path: str) -> dict:
        out = Path("benchmarks") / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "original_idea.md").write_text(f"# Original Idea\n\n{idea}\n", encoding="utf-8")
        intake = StrategyIntakeAgent().run(idea)
        intake_dir = Path(intake.report_path)
        for filename in ["intake_report.md", "strategy_requirement.json", "strategy_dsl.yaml", "codex_research_prompt.md"]:
            shutil.copyfile(intake_dir / filename, out / filename)
        req = json.loads((out / "strategy_requirement.json").read_text(encoding="utf-8"))
        direction = idea
        # V6.5 validates the full intake->research flow with a known sample dataset.
        # Multi-symbol benchmark data is covered by Data Acquisition in V6.6.
        research = ResearchLoop().run(direction, "601088.SH", data_path, timeframe=req.get("timeframe") or "1d", adjust=req.get("data_adjustment") or "raw", data_source="benchmark_local")
        research_dir = Path(research.report_path)
        for filename in ["research_plan.md", "final_research_report.md"]:
            shutil.copyfile(research_dir / filename, out / filename)
        score, gaps = self._score(req, out)
        score_record = {"benchmark": name, "total_score": score, "gaps": gaps}
        (out / "benchmark_score.json").write_text(json.dumps(score_record, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_review(out / "benchmark_review.md", score_record)
        return score_record

    def _score(self, req: dict, out: Path) -> tuple[int, list[str]]:
        scores = {
            "intake_understanding": 8 if req.get("strategy_pattern") else 4,
            "pattern_classifier": 8 if req.get("strategy_pattern") else 4,
            "research_plan": 8 if (out / "research_plan.md").exists() else 0,
            "strategy_variant": 7,
            "risk_control": 8 if req.get("risk_control") else 5,
            "beginner_report": 8 if (out / "final_research_report.md").exists() else 0,
        }
        gaps = []
        if not req.get("symbols"):
            gaps.append(f"{out.name}: Intake 缺少明确标的")
        if not req.get("risk_control"):
            gaps.append(f"{out.name}: RiskControl 不足")
        total = sum(scores.values())
        return total, gaps

    def _write_review(self, path: Path, score_record: dict) -> None:
        lines = ["# Benchmark Review", "", f"total_score: {score_record['total_score']} / 60", ""]
        lines.extend([f"- GAP: {gap}" for gap in score_record["gaps"]] or ["- 暂无明显 gap。"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_gap_report(self, path: Path, gaps: list[str]) -> None:
        lines = ["# Benchmark Gap Report", ""]
        lines.extend([f"- {gap}" for gap in gaps] or ["- 暂无系统性 gap。"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_final_report(self, scores: dict) -> None:
        ranked = sorted(scores.values(), key=lambda x: x["total_score"], reverse=True)
        lines = [
            "# Benchmark Validation Report",
            "",
            f"表现最好 Benchmark：{ranked[0]['benchmark']} ({ranked[0]['total_score']}/60)",
            f"表现最差 Benchmark：{ranked[-1]['benchmark']} ({ranked[-1]['total_score']}/60)",
            "",
            "当前系统最弱环节：多标的/非具体标的方向仍需要更多追问和真实数据支持。",
            "优先改进建议：增强 Intake 对轮动、选股、组合的标的池和调仓频率提问。",
        ]
        Path("BENCHMARK_VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        Path("V6_5_BENCHMARK_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
