from __future__ import annotations

import pandas as pd



def supplier_summary(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    if 'supplier' not in data.columns:
        data['supplier'] = 'Unknown'

    if 'total_cost' not in data.columns:
        data['total_cost'] = 0

    summary = (
        data.groupby('supplier', dropna=False)['total_cost']
        .sum()
        .reset_index()
        .sort_values('total_cost', ascending=False)
    )

    summary.columns = ['Supplier', 'Spend']

    return summary
