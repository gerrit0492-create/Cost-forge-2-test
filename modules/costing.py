import streamlit as st


def render_costing():
    st.title('Costing')

    material = st.number_input('Material Cost', value=1000.0)
    routing = st.number_input('Routing Cost', value=500.0)
    overhead = st.number_input('Overhead %', value=15.0)

    total = (material + routing) * (1 + overhead / 100)

    st.metric('Total Cost', f'€ {total:,.2f}')
