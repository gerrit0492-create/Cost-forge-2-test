from __future__ import annotations

import streamlit as st
import pandas as pd

from CF3.engines.bom_engine import prepare_bom
from CF3.engines.routing_engine import calculate_routing_cost
from CF3.engines.costing_engine import calculate_cost
from CF3.services.export_service import export_excel

st.title('CF3 Cost Engine')
st.caption('Enterprise manufacturing cost calculation')

uploaded = st.file_uploader('Upload BOM', type=['csv', 'xlsx'])

if uploaded:
    if uploaded.name.endswith('.csv'):
        raw = pd.read_csv(uploaded)
    else:
        raw = pd.read_excel(uploaded)

    bom = prepare_bom(raw)
    routing = calculate_routing_cost(bom)
    result = calculate_cost(routing)

    total_cost = result['total_cost'].sum()
    routing_cost = result['routing_cost'].sum()
    material_cost = result['material_cost'].sum()

    c1, c2, c3 = st.columns(3)

    c1.metric('Material Cost', f'€{material_cost:,.2f}')
    c2.metric('Routing Cost', f'€{routing_cost:,.2f}')
    c3.metric('Total Cost', f'€{total_cost:,.2f}')

    st.dataframe(result, use_container_width=True)

    excel_data = export_excel(result)

    st.download_button(
        label='Download Excel Cost Report',
        data=excel_data,
        file_name='cf3_cost_report.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
