import pandas as pd


def calculate_cost(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if 'material_cost' not in df.columns:
        df['material_cost'] = 0

    if 'routing_cost' not in df.columns:
        df['routing_cost'] = 0

    df['total_cost'] = df['material_cost'] + df['routing_cost']

    return df
