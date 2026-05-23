from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SessionDefaults:
    active_project: str = 'default'
    selected_currency: str = 'EUR'
    dark_mode: bool = False
    diagnostics_enabled: bool = False
    telemetry_enabled: bool = False


DEFAULTS = SessionDefaults()


class SessionStateStore:
    def __init__(self):
        self._state: dict[str, Any] = {}

    def initialize_defaults(self) -> None:
        for key, value in DEFAULTS.__dict__.items():
            self._state.setdefault(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)


class FeatureFlags:
    def __init__(self, state: SessionStateStore):
        self.state = state

    @property
    def diagnostics_enabled(self) -> bool:
        return bool(self.state.get('diagnostics_enabled', False))

    @property
    def telemetry_enabled(self) -> bool:
        return bool(self.state.get('telemetry_enabled', False))
