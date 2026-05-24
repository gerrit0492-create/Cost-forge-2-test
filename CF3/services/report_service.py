from __future__ import annotations

from datetime import datetime

import pandas as pd



def generate_management_summary(df: pd.DataFrame) -> dict:
    total_cost = float(df.get('total_cost', pd.Series(dtype=float)).sum())
    material_cost = float(df.get('material_cost', pd.Series(dtype=float)).sum())
    routing_cost = float(df.get('routing_cost', pd.Series(dtype=float)).sum())

    return {
        'generated_at': datetime.now().isoformat(),
        'bom_lines': len(df),
        'total_cost': total_cost,
        'material_cost': material_cost,
        'routing_cost': routing_cost,
    }
