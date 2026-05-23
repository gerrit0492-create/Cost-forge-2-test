from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True)
class CacheMetric:
    key: str
    elapsed_ms: float
    hit: bool


class SimpleCacheDiagnostics:
    def __init__(self):
        self._cache: dict[str, Any] = {}

    def get_or_compute(self, key: str, fn: Callable[[], Any]):
        start = perf_counter()

        if key in self._cache:
            elapsed = (perf_counter() - start) * 1000
            return self._cache[key], CacheMetric(key, elapsed, True)

        value = fn()
        self._cache[key] = value

        elapsed = (perf_counter() - start) * 1000
        return value, CacheMetric(key, elapsed, False)
