"""Waterjet BOM completeness detection and smart guidance."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# All 14 waterjet subsystems with short descriptions
WATERJET_SUBSYSTEMS: dict[str, dict] = {
    "I":  {"name": "Impeller Assembly",   "critical": True,  "icon": "🌀",
           "desc": "5-axis NAB impeller, balance ring, wear rings, NDT"},
    "SB": {"name": "Stator Bowl",         "critical": True,  "icon": "🪣",
           "desc": "Cast NAB diffuser bowl, stator vanes, machined flow passages"},
    "H":  {"name": "Pump Housing",        "critical": True,  "icon": "🏠",
           "desc": "NAB_CAST main housing, precision bore, flanges, seals"},
    "S":  {"name": "Shaft Line",          "critical": True,  "icon": "⚙️",
           "desc": "17-4PH drive shaft, bearings, couplings, hard chrome"},
    "TB": {"name": "Thrust Block",        "critical": True,  "icon": "🔩",
           "desc": "Duplex SS thrust housing, bearing bores, thrust collar"},
    "D":  {"name": "Inlet Duct",          "critical": True,  "icon": "🌊",
           "desc": "316L welded duct, mounting flanges, grating"},
    "N":  {"name": "Jet Nozzle",          "critical": False, "icon": "💨",
           "desc": "Nozzle body, steering nozzle, wear insert"},
    "ST": {"name": "Steering System",     "critical": False, "icon": "🕹️",
           "desc": "Tiller plates, deflector, actuator brackets"},
    "R":  {"name": "Reverse System",      "critical": False, "icon": "🔄",
           "desc": "Thrust reverser bucket, hinge pins, actuator"},
    "F":  {"name": "Mounting Frame",      "critical": False, "icon": "🏗️",
           "desc": "S355J2 welded baseframe, alignment pads, powder coat"},
    "SE": {"name": "Sealing System",      "critical": False, "icon": "🔒",
           "desc": "Shaft seals, PEEK bushings, NBR O-rings"},
    "HY": {"name": "Hydraulic System",    "critical": False, "icon": "🛢️",
           "desc": "316L tube manifold, fittings, pressure-tested"},
    "HW": {"name": "Fasteners & Hardware","critical": False, "icon": "🔧",
           "desc": "A4-80 fastener kits, pins, retaining hardware"},
    "QA": {"name": "QA / Testing",        "critical": False, "icon": "✅",
           "desc": "Dynamic balance, hydrostatic test, NDT, final assembly"},
}

_LEARNING_PATH = Path("data/usage_stats.json")


def detect_subsystems(bom: pd.DataFrame) -> dict[str, int]:
    """Return {prefix: line_count} for all recognised subsystems."""
    counts: dict[str, int] = {}
    sorted_prefixes = sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True)
    for line_id in bom["line_id"].astype(str):
        upper = line_id.upper()
        for prefix in sorted_prefixes:
            if upper.startswith(prefix):
                counts[prefix] = counts.get(prefix, 0) + 1
                break
    return counts


def missing_subsystems(bom: pd.DataFrame) -> list[tuple[str, dict]]:
    """Return [(prefix, info)] for subsystems not present in BOM."""
    present = detect_subsystems(bom)
    return [(p, info) for p, info in WATERJET_SUBSYSTEMS.items() if p not in present]


def completeness_score(bom: pd.DataFrame) -> float:
    """0.0–1.0 fraction of defined subsystems present."""
    present = detect_subsystems(bom)
    return len([p for p in WATERJET_SUBSYSTEMS if p in present]) / len(WATERJET_SUBSYSTEMS)


def critical_missing(bom: pd.DataFrame) -> list[tuple[str, dict]]:
    """Return critical-only missing subsystems."""
    return [(p, info) for p, info in missing_subsystems(bom) if info["critical"]]


# ── Usage / learning tracking ────────────────────────────────────────────────

def _load_stats() -> dict:
    try:
        return json.loads(_LEARNING_PATH.read_text())
    except Exception:
        return {"loads": 0, "subsystem_counts": {}, "last_project": ""}


def record_bom_load(bom: pd.DataFrame, project_name: str = "") -> None:
    """Persist lightweight usage stats for self-learning hints."""
    stats = _load_stats()
    stats["loads"] = stats.get("loads", 0) + 1
    sc = stats.setdefault("subsystem_counts", {})
    for prefix in detect_subsystems(bom):
        sc[prefix] = sc.get(prefix, 0) + 1
    if project_name:
        stats["last_project"] = project_name
    try:
        _LEARNING_PATH.write_text(json.dumps(stats, indent=2))
    except Exception:
        pass


def suggested_name(fallback: str = "") -> str:
    """Return the last saved project name as a smart default."""
    stats = _load_stats()
    return stats.get("last_project", fallback)


def common_missing(bom: pd.DataFrame) -> list[tuple[str, dict]]:
    """Prioritise missing subsystems that were present in past loads."""
    stats = _load_stats()
    sc = stats.get("subsystem_counts", {})
    absent = missing_subsystems(bom)
    # Sort by historical frequency — most-used first
    return sorted(absent, key=lambda x: sc.get(x[0], 0), reverse=True)
