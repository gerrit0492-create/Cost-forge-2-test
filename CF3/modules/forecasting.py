import pandas as pd
import streamlit as st

from CF3.engines.bom_engine import prepare_bom
from CF3.engines.costing_engine import calculate_cost
from CF3.engines.routing_engine import calculate_routing_cost
from CF3.services.forecast_service import generate_forecast



def render():
    st.title('Forecasting')
    st.caption('Long-term manufacturing cost forecasting')

    uploaded = st.file_uploader('Upload BOM for forecast analysis', type=['csv', 'xlsx'])

    if uploaded:
        if uploaded.name.endswith('.csv'):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)

        bom = prepare_bom(raw)
        routing = calculate_routing_cost(bom)
        result = calculate_cost(routing)

        forecast = generate_forecast(result)

        st.line_chart(forecast.set_index('year'))
        st.dataframe(forecast, use_container_width=True)
