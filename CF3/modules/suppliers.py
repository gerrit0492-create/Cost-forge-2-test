import pandas as pd
import streamlit as st

from CF3.engines.bom_engine import prepare_bom
from CF3.engines.costing_engine import calculate_cost
from CF3.engines.routing_engine import calculate_routing_cost
from CF3.services.supplier_service import supplier_summary


def render():
    st.title('Supplier Intelligence')
    st.caption('Supplier pricing and sourcing overview')

    uploaded = st.file_uploader('Upload BOM for supplier analysis', type=['csv', 'xlsx'])

    if uploaded:
        if uploaded.name.endswith('.csv'):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)

        bom = prepare_bom(raw)
        routing = calculate_routing_cost(bom)
        costed = calculate_cost(routing)

        summary = supplier_summary(costed)

        st.subheader('Supplier Spend Overview')
        st.dataframe(summary, use_container_width=True)

        if not summary.empty:
            largest = summary.iloc[0]

            st.metric(
                'Largest Supplier Exposure',
                largest['Supplier'],
                f"€{largest['Spend']:,.2f}"
            )
