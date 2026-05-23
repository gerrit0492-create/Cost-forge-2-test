from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BomDeltaFinding:
    change_type: str
    material_id: str
    old_qty: float
    new_qty: float
    delta_qty: float
    old_cost: float
    new_cost: float
    delta_cost: float


@dataclass(frozen=True)
class BomDeltaReport:
    total_old_cost: float
    total_new_cost: float
    total_delta_cost: float
    findings: list[BomDeltaFinding]


REQUIRED_COLUMNS = [
    'material_id',
    'qty',
    'price_eur_per_kg',
]


def _validate(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f'Missing required columns: {missing}')


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()

    prepared['qty'] = pd.to_numeric(prepared['qty'], errors='coerce').fillna(0)
    prepared['price_eur_per_kg'] = pd.to_numeric(
        prepared['price_eur_per_kg'],
        errors='coerce',
    ).fillna(0)

    prepared['total_cost'] = prepared['qty'] * prepared['price_eur_per_kg']

    grouped = prepared.groupby('material_id', as_index=False).agg(
        qty=('qty', 'sum'),
        total_cost=('total_cost', 'sum'),
    )

    return grouped


def analyse_bom_delta(
    old_bom: pd.DataFrame,
    new_bom: pd.DataFrame,
) -> BomDeltaReport:
    _validate(old_bom)
    _validate(new_bom)

    old_df = _prepare(old_bom)
    new_df = _prepare(new_bom)

    merged = old_df.merge(
        new_df,
        on='material_id',
        how='outer',
        suffixes=('_old', '_new'),
    ).fillna(0)

    findings: list[BomDeltaFinding] = []

    for _, row in merged.iterrows():
        old_qty = float(row['qty_old'])
        new_qty = float(row['qty_new'])

        old_cost = float(row['total_cost_old'])
        new_cost = float(row['total_cost_new'])

        delta_qty = new_qty - old_qty
        delta_cost = new_cost - old_cost

        if old_qty == 0 and new_qty > 0:
            change_type = 'added'
        elif new_qty == 0 and old_qty > 0:
            change_type = 'removed'
        elif delta_cost > 0:
            change_type = 'increased'
        elif delta_cost < 0:
            change_type = 'decreased'
        else:
            continue

        findings.append(BomDeltaFinding(
            change_type=change_type,
            material_id=str(row['material_id']),
            old_qty=old_qty,
            new_qty=new_qty,
            delta_qty=delta_qty,
            old_cost=old_cost,
            new_cost=new_cost,
            delta_cost=delta_cost,
        ))

    total_old = float(old_df['total_cost'].sum())
    total_new = float(new_df['total_cost'].sum())

    return BomDeltaReport(
        total_old_cost=total_old,
        total_new_cost=total_new,
        total_delta_cost=total_new - total_old,
        findings=sorted(findings, key=lambda x: abs(x.delta_cost), reverse=True),
    )
