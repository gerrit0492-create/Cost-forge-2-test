from __future__ import annotations

import pandas as pd


def data_quality_report(df: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, object]] = []
    data = df.copy()

    checks.append({
        'check': 'Rows available',
        'status': 'OK' if len(data) > 0 else 'ERROR',
        'details': len(data),
    })

    if 'qty' in data.columns:
        invalid_qty = pd.to_numeric(data['qty'], errors='coerce').fillna(0) <= 0
        checks.append({
            'check': 'Quantity > 0',
            'status': 'OK' if not invalid_qty.any() else 'ERROR',
            'details': int(invalid_qty.sum()),
        })

    if 'item' in data.columns:
        duplicates = data['item'].duplicated().sum()
        checks.append({
            'check': 'Duplicate item IDs',
            'status': 'OK' if duplicates == 0 else 'WARNING',
            'details': int(duplicates),
        })

    if 'unit_price' in data.columns:
        missing_price = pd.to_numeric(data['unit_price'], errors='coerce').fillna(0) <= 0
        checks.append({
            'check': 'Missing or zero unit prices',
            'status': 'OK' if not missing_price.any() else 'WARNING',
            'details': int(missing_price.sum()),
        })

    if 'material_id' in data.columns:
        missing_material = data['material_id'].astype(str).str.strip().eq('').sum()
        checks.append({
            'check': 'Missing material IDs',
            'status': 'OK' if missing_material == 0 else 'WARNING',
            'details': int(missing_material),
        })

    return pd.DataFrame(checks)
