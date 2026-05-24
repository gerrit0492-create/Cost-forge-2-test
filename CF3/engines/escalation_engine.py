from __future__ import annotations

import pandas as pd


DEFAULT_ESCALATION = {
    'steel': 0.06,
    'electronics': 0.08,
    'labour': 0.04,
    'energy': 0.10,
}



def apply_escalation(df: pd.DataFrame, escalation_rate: float = 0.05) -> pd.DataFrame:
    data = df.copy()

    if 'total_cost' not in data.columns:
        data['total_cost'] = 0

    data['escalation_rate'] = escalation_rate
    data['escalated_cost'] = data['total_cost'] * (1 + escalation_rate)
    data['escalation_delta'] = data['escalated_cost'] - data['total_cost']

    return data
