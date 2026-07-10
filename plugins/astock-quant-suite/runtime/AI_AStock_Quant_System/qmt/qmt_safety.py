from __future__ import annotations


class QMTSafetyGate:
    def allow_real_trade(self, config: dict, confirmation: str, audit_status: str, emergency_stop: bool) -> tuple[bool, str]:
        if emergency_stop:
            return False, "emergency_stop 已触发"
        if not config.get("enable_real_trade", False):
            return False, "enable_real_trade 未开启"
        if config.get("dry_run", True):
            return False, "dry_run=True，禁止真实下单"
        if confirmation != "CONFIRM_REAL_TRADE":
            return False, "缺少 CONFIRM_REAL_TRADE 二次确认"
        if audit_status != "VALID":
            return False, "策略审计未通过"
        return True, "允许真实下单"

