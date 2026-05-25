import streamlit as st

from engines.should_cost_engine import ShouldCostEngine


def render_should_costing():

    st.title('Should Cost Intelligence')

    material_cost = st.number_input(
        'Material Cost',
        value=5000.0
    )

    labor_cost = st.number_input(
        'Labor Cost',
        value=2500.0
    )

    machine_cost = st.number_input(
        'Machine Cost',
        value=3200.0
    )

    overhead = st.number_input(
        'Overhead %',
        value=18.0
    )

    result = (
        ShouldCostEngine
        .calculate_should_cost(
            material_cost,
            labor_cost,
            machine_cost,
            overhead,
        )
    )

    c1, c2 = st.columns(2)

    c1.metric(
        'Overhead',
        f"€ {result['overhead']:,.2f}"
    )

    c2.metric(
        'Should Cost',
        f"€ {result['should_cost']:,.2f}"
    )

    st.json(result)
