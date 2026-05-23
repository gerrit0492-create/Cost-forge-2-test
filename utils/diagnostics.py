from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path


CRITICAL_FILES = [
    'home.py',
    'requirements.txt',
    'data/cost_forge.xlsx',
]

CRITICAL_MODULES = [
    'streamlit',
    'pandas',
    'openpyxl',
    'reportlab',
    'docx',
]

CRITICAL_PAGES = [
    'pages/45_Command_Centre.py',
    'pages/47_Carbon_Energy.py',
    'pages/48_Stakeholder_Package.py',
    'pages/51_QMS_Prices.py',
]


def file_status() -> list[dict[str, object]]:
    rows = []
    for item in CRITICAL_FILES + CRITICAL_PAGES:
        path = Path(item)
        rows.append({
            'path': item,
            'exists': path.exists(),
            'size_bytes': path.stat().st_size if path.exists() else 0,
        })
    return rows


def module_status() -> list[dict[str, object]]:
    rows = []
    for module in CRITICAL_MODULES:
        try:
            imported = importlib.import_module(module)
            version = getattr(imported, '__version__', 'unknown')
            rows.append({'module': module, 'ok': True, 'version': str(version), 'error': ''})
        except Exception as exc:
            rows.append({'module': module, 'ok': False, 'version': '', 'error': f'{type(exc).__name__}: {exc}'})
    return rows


def environment_status() -> dict[str, str]:
    return {
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'cwd': str(Path.cwd()),
    }


def health_summary() -> dict[str, object]:
    files = file_status()
    modules = module_status()
    return {
        'files_ok': all(row['exists'] for row in files),
        'modules_ok': all(row['ok'] for row in modules),
        'file_count': len(files),
        'module_count': len(modules),
        'environment': environment_status(),
    }
