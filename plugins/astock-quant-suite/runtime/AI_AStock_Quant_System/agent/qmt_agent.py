from __future__ import annotations


class QMTAgent:
    def guardrails(self) -> list[str]:
        return ["默认 dry_run", "不得保存真实账号密码", "真实下单必须二次确认和 pre-trade check"]

