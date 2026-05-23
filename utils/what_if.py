from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WhatIfScenario:
    name: str
    material_price_factor: float = 1.0
    machine_rate_factor: float = 1.0
    labor_rate_factor: float = 1.0
    overhead_factor: float = 1.0
    margin_factor: float = 1.0


@dataclass(frozen=True)
class WhatIfResult:
    scenario_name: str
    base_total: float
    scenario_total: float
    delta_total: float
    delta_pct: float


def apply_scenario(
    materials: pd.DataFrame,
    processes: pd.DataFrame,
    scenario: WhatIfScenario,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mats = materials.copy()
    procs = processes.copy()

    if 'price_eur_per_kg' in mats.columns:
        mats['price_eur_per_kg'] = pd.to_numeric(
            mats['price_eur_per_kg'],
            errors='coerce',
        ).fillna(0) * scenario.material_price_factor

    if 'machine_rate_eur_h' in procs.columns:
        procs['machine_rate_eur_h'] = pd.to_numeric(
            procs['machine_rate_eur_h'],
            errors='coerce',
        ).fillna(0) * scenario.machine_rate_factor

    if 'labor_rate_eur_h' in procs.columns:
        procs['labor_rate_eur_h'] = pd.to_numeric(
            procs['labor_rate_eur_h'],
            errors='coerce',
        ).fillna(0) * scenario.labor_rate_factor

    if 'overhead_pct' in procs.columns:
        procs['overhead_pct'] = pd.to_numeric(
            procs['overhead_pct'],
            errors='coerce',
        ).fillna(0) * scenario.overhead_factor

    if 'margin_pct' in procs.columns:
        procs['margin_pct'] = pd.to_numeric(
            procs['margin_pct'],
            errors='coerce',
        ).fillna(0) * scenario.margin_factor

    return mats, procs


def compare_totals(
    scenario_name: str,
    base_total: float,
    scenario_total: float,
) -> WhatIfResult:
    delta = scenario_total - base_total
    delta_pct = delta / base_total * 100 if base_total else 0.0

    return WhatIfResult(
        scenario_name=scenario_name,
        base_total=float(base_total),
        scenario_total=float(scenario_total),
        delta_total=float(delta),
        delta_pct=float(delta_pct),
    )


def rank_scenarios(results: list[WhatIfResult]) -> list[WhatIfResult]:
    return sorted(results, key=lambda result: abs(result.delta_total), reverse=True)
