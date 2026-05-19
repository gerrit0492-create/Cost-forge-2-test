from __future__ import annotations

import json
from pathlib import Path

_PATH = Path("data/project.json")


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load()
    existing.update(data)
    _PATH.write_text(json.dumps(existing))


def load_project_name() -> str:
    return _load().get("name", "")


def save_project_name(name: str) -> None:
    _save({"name": name})


def load_project_meta() -> dict:
    return _load()


def save_project_meta(**kwargs) -> None:
    _save(kwargs)
