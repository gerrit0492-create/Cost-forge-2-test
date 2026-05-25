import pandas as pd


def normalize_bom(df):
    df.columns = [c.strip() for c in df.columns]

    if 'Qty' in df.columns:
        df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)

    return df


def calculate_bom_total(df, material_column='Material Cost', qty_column='Qty'):
    if material_column in df.columns and qty_column in df.columns:
        df['Total Material'] = (
            df[material_column] * df[qty_column]
        )

        return df, df['Total Material'].sum()

    return df, 0
