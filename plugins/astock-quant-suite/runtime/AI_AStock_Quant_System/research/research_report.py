from __future__ import annotations

import csv
import json
from pathlib import Path

from research.research_plan import ResearchPlan
from research.strategy_variant_generator import StrategyVariant


class ResearchReportWriter:
    def write_hypothesis(self, path: str | Path, hypothesis: str) -> None:
        Path(path).write_text(f"# Hypothesis\n\n{hypothesis}\n", encoding="utf-8")

    def write_variants(self, path: str | Path, variants: list[StrategyVariant]) -> None:
        fieldnames = ["variant_id", "pattern", "template_name", "strategy_name", "components", "params", "description", "expected_behavior"]
        with Path(path).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for variant in variants:
                row = variant.to_dict()
                row["components"] = json.dumps(row["components"], ensure_ascii=False)
                row["params"] = json.dumps(row["params"], ensure_ascii=False)
                writer.writerow({key: row.get(key, "") for key in fieldnames})

    def write_search_space(self, path: str | Path, search_space: dict) -> None:
        Path(path).write_text(json.dumps(search_space, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_stability_report(self, path: str | Path, ranked_results: list[dict]) -> None:
        lines = ["# Stability Report", ""]
        if not ranked_results:
            lines.append("没有审计 VALID 的候选，无法做稳定性排名。")
        else:
            for row in ranked_results[:5]:
                lines.append(f"- {row['variant_id']}: score={row['score']}, out_sample_return={row.get('out_sample_return')}, max_drawdown={row.get('max_drawdown')}")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_next_round(self, path: str | Path, ranked_results: list[dict], overfit_report: dict[str, list[str]]) -> None:
        lines = ["# Next Round Suggestions", ""]
        if not ranked_results:
            lines.append("- 当前没有可推荐候选。下一轮应缩小策略方向或放宽过严参数。")
        else:
            best = ranked_results[0]
            lines.append(f"- 保留候选：{best['variant_id']}，围绕其附近参数做更细搜索。")
            lines.append("- 优先减少最大回撤，而不是追逐最高收益。")
            lines.append("- 对边界参数向内收缩，验证是否仍稳定。")
        risky = [vid for vid, flags in overfit_report.items() if flags]
        if risky:
            lines.append(f"- 对这些候选降权或剔除：{', '.join(risky[:5])}")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_final_report(self, path: str | Path, plan: ResearchPlan, ranked_results: list[dict], overfit_report: dict[str, list[str]]) -> None:
        lines = [
            "# Final Research Report",
            "",
            f"研究方向：{plan.original_direction}",
            f"识别范式：{plan.selected_pattern}",
            f"研究周期：{plan.timeframe}",
            f"复权方式：{plan.adjust}",
            f"数据来源：{plan.data_source}",
            f"研究假设：{plan.hypothesis}",
            "",
            "## 结论",
        ]
        if plan.blocker_notes:
            lines.extend([f"- BLOCKER：{note}" for note in plan.blocker_notes])
        elif ranked_results:
            best = ranked_results[0]
            lines.extend([
                f"- 当前首选候选：{best['variant_id']}",
                f"- 综合评分：{best['score']}",
                f"- 样本外收益：{best.get('out_sample_return')}",
                f"- 最大回撤：{best.get('max_drawdown')}",
                f"- 交易次数：{best.get('trade_count')}",
                "- 说明：排序不是按总收益，而是按 Calmar、样本外、回撤、稳定性和交易次数综合评分。",
            ])
        else:
            lines.append("- 没有审计 VALID 的推荐候选。")
        lines.extend(["", "## 过拟合提示"])
        for variant_id, flags in overfit_report.items():
            if flags:
                lines.append(f"- {variant_id}: {'；'.join(flags)}")
        if not any(overfit_report.values()):
            lines.append("- 未发现明显过拟合信号。")
        lines.extend(["", "风险提示：研究报告用于教学和研究，不构成投资建议；进入模拟盘或实盘前仍需审计和 pre-trade check。"])
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
