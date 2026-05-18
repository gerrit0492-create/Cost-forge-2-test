from __future__ import annotations

import json
from pathlib import Path

_PATH = Path("data/project.json")


def load_project_name() -> str:
    try:
        return json.loads(_PATH.read_text())["name"]
    except Exception:
        return ""


def save_project_name(name: str) -> None:
    _PATH.write_text(json.dumps({"name": name}))
