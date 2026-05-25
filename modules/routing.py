import streamlit as st
import pandas as pd


def render_routing():
    st.title('Routing')

    routing = pd.DataFrame({
        'Operation': ['Laser', 'Bending', 'Welding', 'Assembly'],
        'Hours': [1.2, 0.6, 2.1, 1.5],
        'Rate': [85, 75, 95, 65]
    })

    routing['Cost'] = routing['Hours'] * routing['Rate']

    st.dataframe(routing, use_container_width=True)

    st.metric('Routing Total', f"€ {routing['Cost'].sum():,.2f}")
