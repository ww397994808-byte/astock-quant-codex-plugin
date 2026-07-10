from __future__ import annotations

from core.position import PositionBook


class Portfolio:
    def __init__(self, initial_cash: float) -> None:
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.positions = PositionBook()

    def market_value(self, symbol: str, price: float) -> float:
        return self.positions.total(symbol) * price

    def equity(self, symbol: str, price: float) -> float:
        return round(self.cash + self.market_value(symbol, price), 6)

    def ensure_non_negative(self) -> None:
        if self.cash < -1e-6:
            raise ValueError("现金为负，违反风控")
        for symbol in self.positions.lots:
            if self.positions.total(symbol) < 0:
                raise ValueError("持仓为负，违反风控")

