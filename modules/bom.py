import streamlit as st
import pandas as pd


def render_bom():
    st.title('BOM Import')

    uploaded = st.file_uploader('Upload BOM', type=['xlsx', 'csv'])

    if uploaded:
        if uploaded.name.endswith('.csv'):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)

        st.dataframe(df, use_container_width=True)
        st.success('BOM loaded successfully')
