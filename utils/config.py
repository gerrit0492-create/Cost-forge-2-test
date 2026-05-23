from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    environment: str
    repo_root: Path
    data_dir: Path
    workbook_path: Path
    log_level: str
    use_google_sheets: bool


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def get_config() -> AppConfig:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / os.getenv('COST_FORGE_DATA_DIR', 'data')
    workbook_path = data_dir / os.getenv('COST_FORGE_WORKBOOK', 'cost_forge.xlsx')

    return AppConfig(
        app_name=os.getenv('COST_FORGE_APP_NAME', 'Cost Forge 2'),
        environment=os.getenv('COST_FORGE_ENV', 'local'),
        repo_root=repo_root,
        data_dir=data_dir,
        workbook_path=workbook_path,
        log_level=os.getenv('COST_FORGE_LOG_LEVEL', 'INFO').upper(),
        use_google_sheets=_bool_env('COST_FORGE_USE_GOOGLE_SHEETS', False),
    )
