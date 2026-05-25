import streamlit as st
import pandas as pd

from engines.process_engine import (
    PROCESS_RATES,
    calculate_process_cost,
)


def render_routing():
    st.title('Routing Intelligence')

    process = st.selectbox(
        'Manufacturing Process',
        list(PROCESS_RATES.keys())
    )

    hours = st.number_input(
        'Process Hours',
        value=1.0,
        step=0.1
    )

    result = calculate_process_cost(
        process,
        hours
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        'Hourly Rate',
        f"€ {result['rate']:,.2f}"
    )

    c2.metric(
        'Hours',
        f"{result['hours']:.2f}"
    )

    c3.metric(
        'Total Process Cost',
        f"€ {result['total_cost']:,.2f}"
    )

    st.subheader('Available Manufacturing Rates')

    rates = pd.DataFrame({
        'Process': list(PROCESS_RATES.keys()),
        'Rate': list(PROCESS_RATES.values())
    })

    st.dataframe(
        rates,
        use_container_width=True
    )
