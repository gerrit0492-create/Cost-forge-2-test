from CF3.engines.escalation_engine import apply_escalation

import pandas as pd



def test_escalation_calculation():
    df = pd.DataFrame({'total_cost': [1000]})

    result = apply_escalation(df, 0.10)

    assert result['escalated_cost'].iloc[0] == 1100
