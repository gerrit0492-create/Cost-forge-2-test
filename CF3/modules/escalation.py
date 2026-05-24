import pandas as pd
import streamlit as st

from CF3.engines.bom_engine import prepare_bom
from CF3.engines.costing_engine import calculate_cost
from CF3.engines.escalation_engine import apply_escalation
from CF3.engines.routing_engine import calculate_routing_cost


def render():
    st.title('Escalation Engine')
    st.caption('Commodity and inflation escalation modelling')

    escalation_rate = st.slider(
        'Escalation Rate (%)',
        min_value=0.0,
        max_value=25.0,
        value=5.0,
        step=0.5,
    ) / 100

    uploaded = st.file_uploader('Upload BOM for escalation analysis', type=['csv', 'xlsx'])

    if uploaded:
        if uploaded.name.endswith('.csv'):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)

        bom = prepare_bom(raw)
        routing = calculate_routing_cost(bom)
        costed = calculate_cost(routing)
        escalated = apply_escalation(costed, escalation_rate)

        c1, c2, c3 = st.columns(3)

        c1.metric('Base Cost', f"€{escalated['total_cost'].sum():,.2f}")
        c2.metric('Escalation Impact', f"€{escalated['escalation_delta'].sum():,.2f}")
        c3.metric('Escalated Cost', f"€{escalated['escalated_cost'].sum():,.2f}")

        st.dataframe(escalated, use_container_width=True)
