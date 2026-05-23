import pandas as pd

from utils.bom_delta import analyse_bom_delta



def test_detects_added_removed_and_changed_materials():
    old_bom = pd.DataFrame({
        'material_id': ['M1', 'M2'],
        'qty': [1, 2],
        'price_eur_per_kg': [10, 5],
    })

    new_bom = pd.DataFrame({
        'material_id': ['M1', 'M3'],
        'qty': [3, 1],
        'price_eur_per_kg': [10, 20],
    })

    report = analyse_bom_delta(old_bom, new_bom)

    assert report.total_old_cost == 20
    assert report.total_new_cost == 50
    assert report.total_delta_cost == 30

    change_types = {f.change_type for f in report.findings}

    assert 'added' in change_types
    assert 'removed' in change_types
    assert 'increased' in change_types



def test_missing_columns_raise_error():
    old_bom = pd.DataFrame({'material_id': ['M1']})
    new_bom = pd.DataFrame({'material_id': ['M1']})

    try:
        analyse_bom_delta(old_bom, new_bom)
    except ValueError:
        pass
    else:
        raise AssertionError('Expected ValueError for invalid BOM schema')
