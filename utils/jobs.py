from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class JobStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


@dataclass
class JobRecord:
    job_id: str
    name: str
    status: JobStatus = JobStatus.PENDING
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    result: Any = None
    error: str = ''


def create_job(name: str) -> JobRecord:
    return JobRecord(job_id=str(uuid4()), name=name)


def run_job(job: JobRecord, fn: Callable[..., Any], *args, **kwargs) -> JobRecord:
    job.status = JobStatus.RUNNING
    job.started_at_utc = datetime.now(timezone.utc).isoformat()

    try:
        job.result = fn(*args, **kwargs)
        job.status = JobStatus.SUCCEEDED
    except Exception as exc:
        job.error = f'{type(exc).__name__}: {exc}'
        job.status = JobStatus.FAILED
    finally:
        job.finished_at_utc = datetime.now(timezone.utc).isoformat()

    return job


class InMemoryJobRegistry:
    def __init__(self):
        self._jobs: dict[str, JobRecord] = {}

    def add(self, job: JobRecord) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def all(self) -> list[JobRecord]:
        return list(self._jobs.values())
