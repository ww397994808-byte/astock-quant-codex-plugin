from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.broker_base import BrokerBase
from qmt.qmt_broker import QMTBroker


@dataclass
class QMTReadonlySnapshot:
    connected: bool
    account: dict[str, Any]
    cash: float | None
    positions: list[dict[str, Any]]
    orders_today: list[dict[str, Any]]
    trades_today: list[dict[str, Any]]
    checks: dict[str, bool]
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.connected and all(self.checks.values()) and not self.failures)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ok"] = self.ok
        return data


class QMTReadonlyChecker:
    """QMT readonly gate: account data must be observable before pretrade."""

    def __init__(self, broker: BrokerBase | None = None) -> None:
        self.broker = broker or QMTBroker()

    def collect(self) -> QMTReadonlySnapshot:
        failures: list[str] = []
        connected = False
        account: dict[str, Any] = {}
        cash: float | None = None
        positions: list[dict[str, Any]] = []
        orders_today: list[dict[str, Any]] = []
        trades_today: list[dict[str, Any]] = []

        try:
            connected = bool(self.broker.connect())
        except Exception as exc:
            failures.append(f"QMT 连接异常：{exc}")

        try:
            account = dict(self.broker.get_account() or {})
        except Exception as exc:
            failures.append(f"账户读取失败：{exc}")

        try:
            cash = float(self.broker.get_cash())
        except Exception as exc:
            failures.append(f"资金读取失败：{exc}")

        try:
            positions = list(self.broker.get_positions() or [])
        except Exception as exc:
            failures.append(f"持仓读取失败：{exc}")

        try:
            orders_today = list(self.broker.get_orders() or [])
        except Exception as exc:
            failures.append(f"当日委托读取失败：{exc}")

        try:
            trades_today = list(self.broker.get_trades() or [])
        except Exception as exc:
            failures.append(f"当日成交读取失败：{exc}")

        checks = {
            "qmt_connected": connected,
            "account_available": bool(account) and connected,
            "cash_readable": cash is not None and cash >= 0,
            "positions_readable": isinstance(positions, list),
            "orders_readable": isinstance(orders_today, list),
            "trades_readable": isinstance(trades_today, list),
            "dry_run_default_safe": bool(account.get("dry_run", True)),
        }
        for key, ok in checks.items():
            if not ok:
                failures.append(self._message_for(key))

        return QMTReadonlySnapshot(
            connected=connected,
            account=account,
            cash=cash,
            positions=positions,
            orders_today=orders_today,
            trades_today=trades_today,
            checks=checks,
            failures=failures,
        )

    def write_report(self, output_dir: str | Path, snapshot: QMTReadonlySnapshot) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "qmt_account_snapshot.json").write_text(
            json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        lines = ["# QMT Readonly Report", "", f"status: {'VALID' if snapshot.ok else 'INVALID'}", ""]
        lines.append("## Checks")
        for key, ok in snapshot.checks.items():
            lines.append(f"- {key}: {'OK' if ok else 'FAIL'}")
        lines.append("")
        lines.append("## Failures")
        if snapshot.failures:
            lines.extend([f"- {item}" for item in snapshot.failures])
        else:
            lines.append("- 未发现只读阻断项。")
        lines.extend([
            "",
            "说明：QMT_READONLY_READY 只表示账户、资金、持仓、委托、成交可以读取；它不等于允许真实下单。",
        ])
        (out / "qmt_readonly_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _message_for(self, key: str) -> str:
        return {
            "qmt_connected": "QMT 未连接或 xtquant 不可用",
            "account_available": "账户信息不可读",
            "cash_readable": "资金不可读",
            "positions_readable": "持仓不可读",
            "orders_readable": "当日委托不可读",
            "trades_readable": "当日成交不可读",
            "dry_run_default_safe": "dry_run 未保持安全默认值 true",
        }.get(key, f"{key} 未通过")
