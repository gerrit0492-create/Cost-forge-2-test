from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TimingResult:
    name: str
    elapsed_ms: float


@contextmanager
def timer(name: str) -> Iterator[list[TimingResult]]:
    start = time.perf_counter()
    bucket: list[TimingResult] = []
    try:
        yield bucket
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        bucket.append(TimingResult(name=name, elapsed_ms=elapsed_ms))


def measure_call(name: str, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, TimingResult(name=name, elapsed_ms=elapsed_ms)
