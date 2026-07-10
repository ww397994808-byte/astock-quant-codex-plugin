from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.order import Order, Trade
from core.portfolio import Portfolio


@dataclass
class VnpyLikeOrderData:
    symbol: str
    exchange: str
    orderid: str
    direction: str
    offset: str
    price: float
    volume: int
    traded: int
    status: str
    datetime: datetime


@dataclass
class VnpyLikeTradeData:
    symbol: str
    exchange: str
    tradeid: str
    orderid: str
    direction: str
    offset: str
    price: float
    volume: int
    datetime: datetime


@dataclass
class VnpyLikePositionData:
    symbol: str
    exchange: str
    direction: str
    volume: int
    yd_volume: int
    frozen: int = 0


class VnpyOrderMapper:
    def to_vnpy_order(self, order: Order, orderid: str = "") -> VnpyLikeOrderData:
        symbol, exchange = self.split_symbol(order.symbol)
        return VnpyLikeOrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid or f"local_{order.execute_time.strftime('%Y%m%d%H%M%S')}",
            direction="LONG" if order.action == "BUY" else "SHORT",
            offset="OPEN" if order.action == "BUY" else "CLOSE",
            price=float(order.price or 0),
            volume=order.quantity,
            traded=order.quantity if order.status == "FILLED" else 0,
            status=order.status,
            datetime=order.execute_time,
        )

    def to_vnpy_trade(self, trade: Trade, tradeid: str = "", orderid: str = "") -> VnpyLikeTradeData:
        symbol, exchange = self.split_symbol(trade.symbol)
        return VnpyLikeTradeData(
            symbol=symbol,
            exchange=exchange,
            tradeid=tradeid or f"trade_{trade.execute_time.strftime('%Y%m%d%H%M%S')}",
            orderid=orderid,
            direction="LONG" if trade.action == "BUY" else "SHORT",
            offset="OPEN" if trade.action == "BUY" else "CLOSE",
            price=trade.price,
            volume=trade.quantity,
            datetime=trade.execute_time,
        )

    def to_vnpy_position(self, portfolio: Portfolio, symbol: str) -> VnpyLikePositionData:
        code, exchange = self.split_symbol(symbol)
        total = portfolio.positions.total(symbol)
        available = portfolio.positions.available(symbol)
        return VnpyLikePositionData(symbol=code, exchange=exchange, direction="LONG", volume=total, yd_volume=available, frozen=max(0, total - available))

    def split_symbol(self, symbol: str) -> tuple[str, str]:
        if "." in symbol:
            code, exchange = symbol.split(".", 1)
            return code, exchange
        return symbol, ""

