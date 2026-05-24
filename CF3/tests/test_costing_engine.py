from CF3.engines.costing_engine import calculate_cost

import pandas as pd



def test_total_cost_calculation():
    df = pd.DataFrame(
        {
            'material_cost': [100],
            'routing_cost': [50],
        }
    )

    result = calculate_cost(df)

    assert result['total_cost'].iloc[0] == 150
