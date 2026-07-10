from __future__ import annotations


class StrategyAgent:
    """Natural-language strategy requests must become code changes plus tests, then run Task Layer."""

    def guardrails(self) -> list[str]:
        return ["策略只能输出 Signal", "不得直接下单", "必须通过回测和审计"]

