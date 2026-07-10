from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.order import Signal


class StrategyBase(ABC):
    name = "base"

    def __init__(self, **params: Any) -> None:
        self.params = params
        self.validate_params()

    @abstractmethod
    def generate_signal(self, history_data: list[dict[str, Any]]) -> Signal:
        ...

    @abstractmethod
    def validate_params(self) -> None:
        ...

    @abstractmethod
    def describe(self) -> str:
        ...


def avg(values: list[float]) -> float:
    return sum(values) / len(values)


def stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = avg(values)
    return (sum((x - mean) ** 2 for x in values) / (len(values) - 1)) ** 0.5

