import pandas as pd

from utils.data_integrity import (
    duplicate_values,
    missing_columns,
    negative_numeric_values,
    normalize_percentage_series,
    percentage_outliers,
    validate_dataframe,
)



def test_missing_columns_detects_absent_fields():
    df = pd.DataFrame(columns=['a'])
    result = missing_columns(df, ['a', 'b'])
    assert result == ['b']



def test_duplicate_values_detects_duplicates():
    df = pd.DataFrame({'material_id': ['M1', 'M1', 'M2']})
    result = duplicate_values(df, 'material_id')
    assert len(result) == 2



def test_negative_numeric_values_detects_negative_numbers():
    df = pd.DataFrame({'price': [10, -5, 3]})
    result = negative_numeric_values(df, ['price'])
    assert result['price'] == 1



def test_percentage_outliers_detect_values_above_one():
    df = pd.DataFrame({'margin_pct': [0.2, 15, 0.1]})
    result = percentage_outliers(df, ['margin_pct'])
    assert result['margin_pct'] == 1



def test_normalize_percentage_series_converts_15_to_0_15():
    series = pd.Series([15, 0.2])
    result = normalize_percentage_series(series)
    assert round(result.iloc[0], 2) == 0.15
    assert round(result.iloc[1], 2) == 0.20



def test_validate_dataframe_reports_issues():
    df = pd.DataFrame({
        'material_id': ['M1', 'M1'],
        'price': [-5, 10],
        'margin_pct': [15, 0.2],
    })

    issues = validate_dataframe(
        df=df,
        name='materials',
        required_columns=['material_id', 'price', 'missing_column'],
        duplicate_key='material_id',
        non_negative_columns=['price'],
        percentage_columns=['margin_pct'],
    )

    assert len(issues) >= 4
