from __future__ import annotations

from pathlib import Path

from intake.strategy_requirement import StrategyRequirement


class IntakeReportWriter:
    def write(self, output_dir: str | Path, req: StrategyRequirement) -> None:
        output_dir = Path(output_dir)
        lines = [
            "# Strategy Intake Report",
            "",
            f"- 原始想法：{req.original_idea}",
            f"- 完整度评分：{req.completeness_score}",
            f"- 是否可进入研究：{req.readiness_for_research}",
            f"- 识别范式：{req.strategy_pattern}",
            f"- 策略原型：{req.archetype or req.strategy_pattern or '待补充'}",
            f"- 标的：{', '.join(req.symbols) if req.symbols else '待补充'}",
            f"- 周期：{req.timeframe or '待补充'}",
            f"- 复权：{req.data_adjustment}",
            "",
            "## 风险与目标",
            f"- risk_control: {req.risk_control}",
            f"- objective: {req.objective}",
        ]
        if req.qmt_safety_note:
            lines.extend(["", "## QMT 安全提醒", f"- {req.qmt_safety_note}"])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "intake_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (output_dir / "unanswered_questions.md").write_text(
            "# Unanswered Questions\n\n" + "\n".join(f"- {q}" for q in req.unanswered_questions[:5]) + "\n",
            encoding="utf-8",
        )
