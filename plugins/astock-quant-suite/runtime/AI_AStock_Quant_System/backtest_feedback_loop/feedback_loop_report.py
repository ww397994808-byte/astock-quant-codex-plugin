from __future__ import annotations

import csv
from pathlib import Path


class FeedbackLoopReportWriter:
    def write_final_report(
        self,
        output_dir: str | Path,
        idea: str,
        records: list[dict],
        candidates: list[dict],
        rejected: list[dict],
        deep_diagnosis_files: list[str],
    ) -> Path:
        output_dir = Path(output_dir)
        lines = [
            "# 回测反馈优化闭环报告",
            "",
            "## 1. 原始策略想法",
            idea,
            "",
            "## 2. 初始策略如何生成",
            "系统先通过 Strategy Intake Agent 把自然语言想法整理为 Strategy DSL，再调用 Research Agent 生成初始研究计划。随后每一轮都先执行真实回测，再根据回测结果决定下一步修改。",
            "",
            "## 3. 每轮诊断与修改",
        ]
        for record in records:
            analysis = record.get("analysis", {})
            actions = record.get("actions", [])
            lines += [
                f"### 第 {record.get('iteration')} 轮",
                f"- 回测状态：{record.get('status', '')}",
                f"- 审计状态：{record.get('audit_status', '')}",
                f"- Readiness：{record.get('readiness', '')}",
                f"- Calmar：{analysis.get('calmar', 0):.4f}",
                f"- 最大回撤：{analysis.get('max_drawdown', 0):.4f}",
                f"- 交易次数：{analysis.get('trade_count', 0)}",
                f"- 发现问题：{', '.join(analysis.get('issues', [])) or '未发现明显问题'}",
                f"- 修改动作：{', '.join(a.get('action', '') for a in actions) or '保持并继续验证'}",
                "",
            ]

        lines += [
            "## 4. Deep Diagnosis",
            "连续无明显改善时，系统没有停止，而是进入 Deep Diagnosis：复盘失败原因、扩大研究空间，并至少安排一轮扩展实验。",
        ]
        if deep_diagnosis_files:
            lines += [f"- {Path(path).name}" for path in deep_diagnosis_files]
        else:
            lines.append("- 本次未达到 Deep Diagnosis 触发条件。")

        lines += [
            "",
            "## 5. 最终候选策略",
        ]
        if candidates:
            for candidate in candidates[:5]:
                lines.append(
                    f"- {candidate.get('variant_id')}: score={candidate.get('candidate_score', candidate.get('score', 0)):.4f}, readiness={candidate.get('readiness', '')}, audit={candidate.get('audit_status', '')}"
                )
        else:
            lines.append("本轮没有形成可推荐候选。该方向暂不适合进入模拟盘，需要继续检查策略结构、数据质量或研究目标。")

        lines += [
            "",
            "## 6. 哪些改动有效",
            self._effective_changes(records),
            "",
            "## 7. 哪些改动无效",
            self._ineffective_changes(records),
            "",
            "## 8. 是否适合进入模拟盘",
            "只有审计 VALID、Readiness 至少达到 PAPER_READY、并且不是普通 qfq/hfq 高风险复权结果的候选，才适合进入模拟盘观察。",
            "",
            "## 9. 下一步建议",
            "优先保留低回撤、样本外不明显退化、交易次数足够且规则简单的候选。若仍无候选，应扩大标的或周期验证，而不是继续压榨同一参数空间。",
        ]
        path = output_dir / "final_feedback_loop_report.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_modification_plan(self, path: str | Path, actions: list[dict], modifications: list[dict]) -> None:
        lines = ["# 修改计划", ""]
        if not actions:
            lines.append("本轮未提出修改动作。")
        for action, modification in zip(actions, modifications):
            lines += [
                f"## {action.get('action')}",
                f"- 修改原因：{action.get('reason')}",
                f"- 指标依据：{action.get('metric_basis')}",
                f"- 预期改善：{action.get('expected_improvement')}",
                f"- 修改前：{modification.get('before')}",
                f"- 修改后：{modification.get('after')}",
                "",
            ]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_codex_prompt(self, output_dir: str | Path, idea: str, candidates: list[dict], rejected: list[dict]) -> Path:
        lines = [
            "# Codex 下一轮优化 Prompt",
            "",
            f"原始想法：{idea}",
            "",
            "请基于 V7 回测反馈闭环结果继续研究。不要绕过 A股交易规则、审计、Readiness、DataQuality、AdjustmentLeakChecker。",
            "",
            "优先处理：",
            "- 保留审计 VALID 的候选；",
            "- 避免只追求最高收益；",
            "- 若候选不足，先做 Deep Diagnosis，再扩大周期、标的或入出场逻辑。",
            "",
            f"当前候选数量：{len(candidates)}",
            f"被拒绝数量：{len(rejected)}",
        ]
        path = Path(output_dir) / "codex_next_optimization_prompt.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_candidate_files(self, output_dir: str | Path, candidates: list[dict], rejected: list[dict]) -> None:
        headers = [
            "variant_id",
            "candidate_score",
            "readiness",
            "audit_status",
            "calmar",
            "max_drawdown",
            "trade_count",
            "adjust",
        ]
        for filename, rows in [("final_candidates.csv", candidates), ("rejected_candidates.csv", rejected)]:
            with (Path(output_dir) / filename).open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for row in rows:
                    data = {key: row.get(key, "") for key in headers}
                    if not data.get("candidate_score"):
                        data["candidate_score"] = row.get("score", "")
                    writer.writerow(data)

    def _effective_changes(self, records: list[dict]) -> str:
        for prev, curr in zip(records, records[1:]):
            if curr.get("score", 0) > prev.get("score", 0):
                return f"第 {curr.get('iteration')} 轮综合评分较前一轮改善，相关修改可进入下一轮验证。"
        return "未观察到稳定改善，不能把单轮结果当成有效结论。"

    def _ineffective_changes(self, records: list[dict]) -> str:
        if len(records) < 2:
            return "样本轮次不足，暂不能判断。"
        return "连续未改善的修改已触发 Deep Diagnosis，不应继续在同一狭窄参数空间内反复尝试。"
