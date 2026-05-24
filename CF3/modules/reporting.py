import pandas as pd
import streamlit as st

from CF3.engines.bom_engine import prepare_bom
from CF3.engines.costing_engine import calculate_cost
from CF3.engines.routing_engine import calculate_routing_cost
from CF3.services.report_service import generate_management_summary



def render():
    st.title('Management Reporting')
    st.caption('Executive cost and project reporting')

    uploaded = st.file_uploader('Upload BOM for reporting', type=['csv', 'xlsx'])

    if uploaded:
        if uploaded.name.endswith('.csv'):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)

        bom = prepare_bom(raw)
        routing = calculate_routing_cost(bom)
        result = calculate_cost(routing)

        summary = generate_management_summary(result)

        c1, c2, c3 = st.columns(3)

        c1.metric('BOM Lines', summary['bom_lines'])
        c2.metric('Material Cost', f"€{summary['material_cost']:,.2f}")
        c3.metric('Total Cost', f"€{summary['total_cost']:,.2f}")

        st.dataframe(result, use_container_width=True)
