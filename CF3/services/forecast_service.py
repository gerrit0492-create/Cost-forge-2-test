from __future__ import annotations

import pandas as pd



def generate_forecast(df: pd.DataFrame, growth_rate: float = 0.05) -> pd.DataFrame:
    data = df.copy()

    if 'total_cost' not in data.columns:
        data['total_cost'] = 0

    forecast = []

    current = float(data['total_cost'].sum())

    for year in range(1, 6):
        current *= (1 + growth_rate)
        forecast.append(
            {
                'year': year,
                'forecast_cost': round(current, 2),
            }
        )

    return pd.DataFrame(forecast)
