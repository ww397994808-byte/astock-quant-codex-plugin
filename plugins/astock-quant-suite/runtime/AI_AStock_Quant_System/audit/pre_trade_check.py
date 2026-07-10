from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time


@dataclass
class PreTradeCheckResult:
    ok: bool
    failures: list[str] = field(default_factory=list)


class PreTradeChecker:
    def check(self, config: dict, audit_status: str = "INVALID", confirmation: str = "") -> PreTradeCheckResult:
        failures: list[str] = []
        if not config.get("qmt_connected", False):
            failures.append("QMT 未连接")
        if not config.get("account_available", False):
            failures.append("账户不可用")
        if config.get("dry_run", True):
            failures.append("当前为 dry_run，禁止真实下单")
        if not config.get("enable_real_trade", False):
            failures.append("enable_real_trade 未开启")
        if confirmation != "CONFIRM_REAL_TRADE":
            failures.append("未输入 CONFIRM_REAL_TRADE 二次确认")
        if audit_status != "VALID":
            failures.append("策略审计状态不是 VALID")
        if config.get("emergency_stop", False):
            failures.append("触发 emergency_stop")
        now = datetime.now().time()
        if not (time(9, 30) <= now <= time(15, 0)):
            failures.append("当前不在交易时间")
        for key, message in [
            ("data_latest", "数据不是最新"),
            ("symbol_tradable", "标的不可交易或停牌"),
            ("not_limit_price", "标的处于涨跌停"),
            ("daily_loss_ok", "今日亏损超过限制"),
            ("single_position_ok", "单票仓位超过限制"),
            ("total_position_ok", "总仓位超过限制"),
            ("no_duplicate_order", "存在重复下单风险"),
            ("no_abnormal_order", "存在未处理异常订单"),
        ]:
            if not config.get(key, False):
                failures.append(message)
        return PreTradeCheckResult(ok=not failures, failures=failures)

