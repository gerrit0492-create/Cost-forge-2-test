from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PluginDefinition:
    name: str
    version: str
    handler: Callable


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, PluginDefinition] = {}

    def register(self, plugin: PluginDefinition) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> PluginDefinition | None:
        return self._plugins.get(name)

    def all(self) -> list[PluginDefinition]:
        return list(self._plugins.values())
