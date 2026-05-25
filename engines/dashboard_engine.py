import pandas as pd


def build_kpi_dataframe():
    return pd.DataFrame({
        'KPI': ['Projects', 'RFQs', 'Margin'],
        'Value': [12, 7, '28%']
    })
