import pandas as pd

from utils.what_if import (
    WhatIfScenario,
    apply_scenario,
    compare_totals,
    rank_scenarios,
)



def test_material_price_factor_changes_prices():
    materials = pd.DataFrame({
        'price_eur_per_kg': [10],
    })

    processes = pd.DataFrame()

    scenario = WhatIfScenario(
        name='Steel +15%',
        material_price_factor=1.15,
    )

    mats, _ = apply_scenario(materials, processes, scenario)

    assert round(mats['price_eur_per_kg'].iloc[0], 2) == 11.5



def test_compare_totals_calculates_delta():
    result = compare_totals(
        scenario_name='Labor +10%',
        base_total=100,
        scenario_total=120,
    )

    assert result.delta_total == 20
    assert result.delta_pct == 20



def test_rank_scenarios_sorts_by_biggest_impact():
    results = [
        compare_totals('A', 100, 110),
        compare_totals('B', 100, 160),
        compare_totals('C', 100, 90),
    ]

    ranked = rank_scenarios(results)

    assert ranked[0].scenario_name == 'B'
