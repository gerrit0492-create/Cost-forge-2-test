import pandas as pd

from cf_core import (
    REQUIRED_BOM_COLUMNS,
    calculate_costs,
    default_assumptions,
    default_bom,
    excel_bytes,
    normalize_bom_dataframe,
    quote_text,
    scenario_matrix,
    subsystem_summary,
)


def test_default_bom_has_required_columns():
    bom = default_bom()
    assert list(bom.columns) == REQUIRED_BOM_COLUMNS
    assert len(bom) > 0


def test_cost_engine_calculates_positive_values():
    bom = default_bom()
    assumptions = default_assumptions()
    costed, summary = calculate_costs(bom, assumptions)

    assert summary["total_cost"] > 0
    assert summary["sales_price"] > summary["total_cost"]
    assert summary["cost_per_kg"] > 0
    assert summary["quote_coverage"] == summary["bom_lines"]
    assert "Total Cost €" in costed.columns
    assert "Quote vs Should Gap €" in costed.columns


def test_normalize_bom_aliases():
    raw = pd.DataFrame(
        {
            "description": ["Part A"],
            "aantal": [2],
            "gewicht": [10],
            "price/kg": [5],
            "quote": [120],
            "hours": [1.5],
        }
    )
    normalized = normalize_bom_dataframe(raw)
    assert list(normalized.columns) == REQUIRED_BOM_COLUMNS
    assert normalized.loc[0, "Part"] == "Part A"
    assert normalized.loc[0, "Qty"] == 2
    assert normalized.loc[0, "Weight kg"] == 10


def test_subsystem_scenario_and_exports():
    bom = default_bom()
    assumptions = default_assumptions()
    costed, summary = calculate_costs(bom, assumptions)

    subsystems = subsystem_summary(costed)
    scenarios = scenario_matrix(bom, assumptions)
    export = excel_bytes(costed, summary, assumptions)
    text = quote_text(summary, assumptions)

    assert len(subsystems) > 0
    assert len(scenarios) == 5
    assert len(export) > 1000
    assert "Cost Forge 2.0 Quote Summary" in text
