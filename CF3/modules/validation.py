import pandas as pd
import streamlit as st

from CF3.engines.validation_engine import data_quality_report



def render():
    st.title('Validation Centre')
    st.caption('BOM and costing data quality checks')

    uploaded = st.file_uploader('Upload file for validation', type=['csv', 'xlsx'])

    if uploaded:
        if uploaded.name.endswith('.csv'):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)

        report = data_quality_report(df)

        st.dataframe(report, use_container_width=True)
