import pandas as pd

from utils.data_quality_engine import analyse_data_quality



def test_healthy_data_scores_green():
    materials = pd.DataFrame({
        'material_id': ['M1'],
        'price_eur_per_kg': [5.0],
    })

    bom = pd.DataFrame({
        'line_id': ['L1'],
        'material_id': ['M1'],
        'process_route': ['P1'],
        'qty': [1],
    })

    processes = pd.DataFrame({
        'process_id': ['P1'],
    })

    quotes = pd.DataFrame({
        'material_id': ['M1'],
    })

    report = analyse_data_quality(materials, bom, processes, quotes)

    assert report.status == 'green'



def test_orphan_materials_trigger_findings():
    materials = pd.DataFrame({
        'material_id': ['M1'],
        'price_eur_per_kg': [0],
    })

    bom = pd.DataFrame({
        'line_id': ['L1', 'L1'],
        'material_id': ['M9', 'M9'],
        'process_route': ['PX', 'PX'],
        'qty': [-1, -1],
    })

    processes = pd.DataFrame({
        'process_id': ['P1'],
    })

    quotes = pd.DataFrame()

    report = analyse_data_quality(materials, bom, processes, quotes)

    assert report.status == 'red'
    assert report.score < 60
    assert len(report.findings) >= 4
