from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class VnpyLikeEvent:
    type: str
    data: Any = None


class VnpyEventAdapter:
    """Small vn.py-style event adapter without importing vn.py.

    This is intentionally synchronous and minimal. It gives this project a
    future compatibility seam for EVENT_ORDER/EVENT_TRADE/EVENT_POSITION while
    keeping the current Task/Service/Engine stack in charge.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[VnpyLikeEvent], None]]] = defaultdict(list)
        self._events: deque[VnpyLikeEvent] = deque()

    def register(self, event_type: str, handler: Callable[[VnpyLikeEvent], None]) -> None:
        self._handlers[event_type].append(handler)

    def unregister(self, event_type: str, handler: Callable[[VnpyLikeEvent], None]) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def put(self, event: VnpyLikeEvent) -> None:
        self._events.append(event)

    def drain(self) -> int:
        count = 0
        while self._events:
            event = self._events.popleft()
            for handler in list(self._handlers.get(event.type, [])):
                handler(event)
            count += 1
        return count

