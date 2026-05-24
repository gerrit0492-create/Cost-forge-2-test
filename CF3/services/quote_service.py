from __future__ import annotations

import pandas as pd


def add_quote_pricing(df: pd.DataFrame, margin_pct: float = 0.20) -> pd.DataFrame:
    data = df.copy()
    if 'total_cost' not in data.columns:
        data['total_cost'] = 0
    data['margin_pct'] = margin_pct
    data['sell_price'] = data['total_cost'] * (1 + margin_pct)
    data['gross_margin'] = data['sell_price'] - data['total_cost']
    return data
