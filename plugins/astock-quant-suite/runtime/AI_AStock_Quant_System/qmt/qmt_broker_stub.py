from __future__ import annotations

from core.broker_base import BrokerBase
from core.order import Order


class QMTBrokerStub(BrokerBase):
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.orders: list[dict] = []

    def connect(self) -> bool:
        return False

    def get_account(self) -> dict:
        return {"connected": False, "dry_run": self.dry_run}

    def get_positions(self) -> list[dict]:
        return []

    def get_cash(self) -> float:
        return 0.0

    def get_orders(self) -> list[dict]:
        return self.orders

    def get_trades(self) -> list[dict]:
        return []

    def place_order(self, order: Order) -> dict:
        self.orders.append({"order": order, "dry_run": self.dry_run, "status": "DRY_RUN"})
        return {"status": "DRY_RUN", "message": "QMT stub 不会真实下单"}

    def cancel_order(self, order_id: str) -> bool:
        return False

    def sync_positions(self) -> None:
        return None

