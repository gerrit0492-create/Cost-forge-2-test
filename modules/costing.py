import streamlit as st

from engines.cost_engine import calculate_total_cost
from engines.margin_engine import calculate_margin


def render_costing():
    st.title('Manufacturing Costing')

    st.subheader('Direct Costs')

    material = st.number_input(
        'Material Cost',
        value=1000.0
    )

    routing = st.number_input(
        'Routing Cost',
        value=500.0
    )

    overhead = st.number_input(
        'Overhead %',
        value=15.0
    )

    sales_price = st.number_input(
        'Sales Price',
        value=2500.0
    )

    result = calculate_total_cost(
        material,
        routing,
        overhead
    )

    margin = calculate_margin(
        sales_price,
        result['total_cost']
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        'Total Cost',
        f"€ {result['total_cost']:,.2f}"
    )

    c2.metric(
        'Margin Value',
        f"€ {margin['margin_value']:,.2f}"
    )

    c3.metric(
        'Margin %',
        f"{margin['margin_percent']:.1f}%"
    )

    st.subheader('Cost Breakdown')

    st.json(result)
