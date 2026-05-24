import streamlit as st
import pandas as pd


def render():
    st.title('Market Data')
    st.caption('Commodity and market intelligence overview')

    data = pd.DataFrame({
        'Commodity': ['Steel', 'Aluminium', 'Copper', 'Energy'],
        'Trend': ['Up', 'Stable', 'Up', 'Volatile'],
        'Risk': ['Medium', 'Low', 'High', 'High']
    })

    st.dataframe(data, use_container_width=True)
