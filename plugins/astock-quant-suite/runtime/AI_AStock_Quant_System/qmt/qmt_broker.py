from __future__ import annotations

import yaml
from pathlib import Path

from core.broker_base import BrokerBase
from core.order import Order
from qmt.qmt_safety import QMTSafetyGate


class QMTBroker(BrokerBase):
    def __init__(self, config_path: str | Path = "config/qmt_config.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {"dry_run": True, "enable_real_trade": False}
        self.connected = False
        self.xt_trader = None

    def connect(self) -> bool:
        try:
            from xtquant import xttrader  # type: ignore
        except Exception:
            self.connected = False
            return False
        self.xt_trader = xttrader
        self.connected = True
        return True

    def get_account(self) -> dict:
        return {"connected": self.connected, "dry_run": self.config.get("dry_run", True), "account_id": self.config.get("account_id", "")}

    def get_positions(self) -> list[dict]:
        return []

    def get_cash(self) -> float:
        return 0.0

    def get_orders(self) -> list[dict]:
        return []

    def get_trades(self) -> list[dict]:
        return []

    def place_order(self, order: Order, confirmation: str = "", audit_status: str = "INVALID") -> dict:
        allowed, reason = QMTSafetyGate().allow_real_trade(self.config, confirmation, audit_status, bool(self.config.get("emergency_stop", False)))
        if not allowed:
            return {"status": "DRY_RUN_BLOCKED", "message": reason, "order": order}
        return {"status": "NOT_IMPLEMENTED", "message": "真实 QMT 下单适配需在本机 MiniQMT 环境内完成"}

    def cancel_order(self, order_id: str) -> bool:
        return False

    def sync_positions(self) -> None:
        return None

