import streamlit as st
import pandas as pd

from engines.bom_engine import (
    normalize_bom,
    calculate_bom_total,
)


def render_bom():
    st.title('BOM Import & Costing')

    uploaded = st.file_uploader(
        'Upload BOM',
        type=['xlsx', 'csv']
    )

    if uploaded:

        if uploaded.name.endswith('.csv'):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)

        df = normalize_bom(df)

        st.subheader('BOM Data')

        st.dataframe(
            df,
            use_container_width=True
        )

        if 'Material Cost' in df.columns and 'Qty' in df.columns:

            df, total = calculate_bom_total(df)

            st.subheader('Calculated BOM')

            st.dataframe(
                df,
                use_container_width=True
            )

            st.metric(
                'Total Material Cost',
                f'€ {total:,.2f}'
            )

        st.success('BOM workflow initialized')
