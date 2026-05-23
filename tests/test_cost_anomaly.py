import pandas as pd

from utils.cost_anomaly import detect_cost_anomalies



def test_healthy_costing_scores_green():
    df = pd.DataFrame({
        'material_cost': [100, 120, 110, 115],
        'process_cost': [50, 55, 52, 54],
        'overhead': [20, 22, 21, 20],
        'margin': [40, 45, 42, 43],
        'total_cost': [150, 175, 162, 169],
    })

    report = detect_cost_anomalies(df)

    assert report.status == 'green'



def test_negative_costs_trigger_critical_findings():
    df = pd.DataFrame({
        'material_cost': [-100, 120],
        'process_cost': [50, -20],
        'overhead': [20, 22],
        'margin': [-10, 2],
        'total_cost': [-30, 1],
    })

    report = detect_cost_anomalies(df)

    assert report.status == 'red'
    assert len(report.anomalies) >= 3



def test_outlier_detection_finds_extreme_values():
    df = pd.DataFrame({
        'material_cost': [100, 100, 100, 1000],
        'process_cost': [50, 50, 50, 50],
        'overhead': [10, 10, 10, 10],
        'margin': [20, 20, 20, 20],
        'total_cost': [160, 160, 160, 5000],
    })

    report = detect_cost_anomalies(df)

    categories = {a.category for a in report.anomalies}

    assert 'cost_outlier' in categories
