from __future__ import annotations

from abc import ABC, abstractmethod

from core.result import TaskResult


class BaseTask(ABC):
    @abstractmethod
    def run(self, **kwargs) -> TaskResult:
        ...

