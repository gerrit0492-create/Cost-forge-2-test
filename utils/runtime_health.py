from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from utils.diagnostics import health_summary
from utils.performance import TimingResult, measure_call


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    timestamp_utc: str
    health: dict[str, Any]
    timing: TimingResult


def capture_runtime_health() -> RuntimeHealthSnapshot:
    health, timing = measure_call('health_summary', health_summary)
    return RuntimeHealthSnapshot(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        health=health,
        timing=timing,
    )


def runtime_health_as_dict(snapshot: RuntimeHealthSnapshot) -> dict[str, Any]:
    return {
        'timestamp_utc': snapshot.timestamp_utc,
        'health': snapshot.health,
        'timing': {
            'name': snapshot.timing.name,
            'elapsed_ms': snapshot.timing.elapsed_ms,
        },
    }
