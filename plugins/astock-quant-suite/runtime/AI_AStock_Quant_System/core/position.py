from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PositionLot:
    quantity: int
    buy_date: datetime
    available: bool = False


class PositionBook:
    def __init__(self) -> None:
        self.lots: dict[str, list[PositionLot]] = {}

    def total(self, symbol: str) -> int:
        return sum(lot.quantity for lot in self.lots.get(symbol, []))

    def available(self, symbol: str) -> int:
        return sum(lot.quantity for lot in self.lots.get(symbol, []) if lot.available)

    def buy(self, symbol: str, quantity: int, buy_date: datetime) -> None:
        self.lots.setdefault(symbol, []).append(PositionLot(quantity=quantity, buy_date=buy_date, available=False))

    def sell(self, symbol: str, quantity: int) -> None:
        if quantity > self.available(symbol):
            raise ValueError("卖出数量超过 T+1 可用持仓")
        remaining = quantity
        for lot in self.lots.get(symbol, []):
            if not lot.available or remaining <= 0:
                continue
            sold = min(lot.quantity, remaining)
            lot.quantity -= sold
            remaining -= sold
        self.lots[symbol] = [lot for lot in self.lots.get(symbol, []) if lot.quantity > 0]

    def release_after_close(self, current_date: datetime) -> None:
        for lots in self.lots.values():
            for lot in lots:
                if lot.buy_date.date() < current_date.date():
                    lot.available = True

    def snapshot(self, symbol: str) -> dict:
        return {"symbol": symbol, "total_position": self.total(symbol), "available_position": self.available(symbol)}

