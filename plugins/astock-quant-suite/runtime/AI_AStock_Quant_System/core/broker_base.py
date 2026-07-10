from __future__ import annotations

from abc import ABC, abstractmethod

from core.order import Order


class BrokerBase(ABC):
    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def get_account(self) -> dict: ...

    @abstractmethod
    def get_positions(self) -> list[dict]: ...

    @abstractmethod
    def get_cash(self) -> float: ...

    @abstractmethod
    def get_orders(self) -> list[dict]: ...

    @abstractmethod
    def get_trades(self) -> list[dict]: ...

    @abstractmethod
    def place_order(self, order: Order) -> dict: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    def sync_positions(self) -> None: ...

