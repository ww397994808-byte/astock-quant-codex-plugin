from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Signal:
    symbol: str
    signal_time: datetime
    action: str
    confidence: float
    reason: str
    target_position: int | None = None
    target_percent: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timeframe: str = "1d"


@dataclass
class Order:
    symbol: str
    action: str
    quantity: int
    signal_time: datetime
    execute_time: datetime
    price: float | None = None
    status: str = "PENDING"
    reason: str = ""
    timeframe: str = "1d"


@dataclass
class Trade:
    symbol: str
    action: str
    quantity: int
    price: float
    amount: float
    signal_time: datetime
    execute_time: datetime
    commission: float
    stamp_tax: float
    transfer_fee: float
    total_fee: float
    reason: str = ""
    timeframe: str = "1d"
