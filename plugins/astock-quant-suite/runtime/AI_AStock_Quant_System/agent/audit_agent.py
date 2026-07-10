from __future__ import annotations


class AuditAgent:
    def guardrails(self) -> list[str]:
        return ["未来函数检查代码化", "交易规则检查代码化", "HIGH 风险必须 INVALID"]

