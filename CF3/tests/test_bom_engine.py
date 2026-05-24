from CF3.engines.bom_engine import validate_bom

import pandas as pd



def test_validate_bom_required_columns():
    df = pd.DataFrame({'item': [1]})

    errors = validate_bom(df)

    assert len(errors) > 0
