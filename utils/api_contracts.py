from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    ok: bool
    data: Any = None
    error: str = ''


def success(data: Any = None) -> ApiResponse:
    return ApiResponse(ok=True, data=data)


def failure(error: str) -> ApiResponse:
    return ApiResponse(ok=False, error=error)


def as_dict(response: ApiResponse) -> dict[str, Any]:
    return {'ok': response.ok, 'data': response.data, 'error': response.error}
