from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EventRecord:
    timestamp_utc: str
    event_type: str
    source: str
    message: str
    metadata: dict[str, Any]


def create_event(
    event_type: str,
    source: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> EventRecord:
    return EventRecord(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        event_type=event_type,
        source=source,
        message=message,
        metadata=metadata or {},
    )


def event_to_dict(event: EventRecord) -> dict[str, Any]:
    return asdict(event)


def event_to_log_line(event: EventRecord) -> str:
    return (
        f'{event.timestamp_utc} | {event.event_type} | '
        f'{event.source} | {event.message} | {event.metadata}'
    )
