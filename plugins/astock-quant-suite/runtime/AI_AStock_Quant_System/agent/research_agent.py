from __future__ import annotations


class ResearchAgent:
    def guardrails(self) -> list[str]:
        return ["研究必须写入 reports/run_id", "结果必须可复现", "不得只报告最优参数"]

