import pandas as pd

from utils.io import _ensure_material_schema



def test_missing_commodity_gets_general_fallback():
    df = pd.DataFrame({
        'material_id': ['M1'],
        'description': ['Legacy material'],
        'price_eur_per_kg': [10.0],
    })

    result = _ensure_material_schema(df)

    assert 'commodity' in result.columns
    assert result['commodity'].iloc[0] == 'General'



def test_commodity_alias_is_normalized():
    df = pd.DataFrame({
        'material_id': ['M1'],
        'Commodity': ['Steel'],
        'price_eur_per_kg': [10.0],
    })

    result = _ensure_material_schema(df)

    assert 'commodity' in result.columns
    assert result['commodity'].iloc[0] == 'Steel'



def test_price_alias_is_normalized():
    df = pd.DataFrame({
        'material_id': ['M1'],
        'commodity': ['Steel'],
        'price_eur_kg': [12.5],
    })

    result = _ensure_material_schema(df)

    assert 'price_eur_per_kg' in result.columns
    assert float(result['price_eur_per_kg'].iloc[0]) == 12.5



def test_empty_commodity_values_are_filled():
    df = pd.DataFrame({
        'material_id': ['M1', 'M2'],
        'commodity': ['', None],
        'price_eur_per_kg': [10.0, 20.0],
    })

    result = _ensure_material_schema(df)

    assert result['commodity'].tolist() == ['General', 'General']
