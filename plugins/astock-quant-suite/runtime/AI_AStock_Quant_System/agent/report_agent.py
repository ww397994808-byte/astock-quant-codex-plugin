from __future__ import annotations


class ReportAgent:
    def guardrails(self) -> list[str]:
        return ["报告必须引用 artifacts", "不得编造回测结果", "审计失败必须显示 INVALID"]

