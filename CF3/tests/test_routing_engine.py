from CF3.engines.routing_engine import calculate_routing_cost

import pandas as pd



def test_routing_cost_calculation():
    df = pd.DataFrame(
        {
            'setup_hours': [1],
            'run_hours': [2],
            'machine_rate': [100],
            'labour_rate': [50],
            'qty': [2],
        }
    )

    result = calculate_routing_cost(df)

    assert result['routing_cost'].iloc[0] > 0
