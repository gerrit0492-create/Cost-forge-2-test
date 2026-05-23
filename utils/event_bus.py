from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, topic: str, payload: Any) -> None:
        for handler in self._subscribers.get(topic, []):
            handler(payload)
