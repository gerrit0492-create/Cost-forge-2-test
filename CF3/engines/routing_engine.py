from __future__ import annotations

import pandas as pd


def calculate_routing_cost(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    required = [
        'setup_hours',
        'run_hours',
        'machine_rate',
        'labour_rate',
        'qty',
    ]

    for column in required:
        if column not in data.columns:
            data[column] = 0

    data['setup_cost'] = data['setup_hours'] * data['machine_rate']
    data['runtime_cost'] = data['run_hours'] * data['machine_rate'] * data['qty']
    data['labour_cost'] = data['run_hours'] * data['labour_rate'] * data['qty']

    data['routing_cost'] = (
        data['setup_cost']
        + data['runtime_cost']
        + data['labour_cost']
    )

    return data
