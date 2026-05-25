import streamlit as st
import pandas as pd

from engines.bom_engine import (
    normalize_bom,
    calculate_bom_total,
)


def render_bom():
    st.title('BOM Import & Costing')

    st.markdown('### Step 1 — Upload BOM File')

    uploaded = st.file_uploader(
        'Upload BOM',
        type=['xlsx', 'csv'],
        key='bom_upload_main'
    )

    if uploaded:

        st.success('BOM file loaded successfully')

        st.markdown('### Step 2 — Read & Normalize BOM')

        if uploaded.name.endswith('.csv'):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)

        df = normalize_bom(df)

        st.dataframe(
            df,
            use_container_width=True,
            key='bom_dataframe_normalized'
        )

        st.markdown('### Step 3 — Material Cost Calculation')

        if 'Material Cost' in df.columns and 'Qty' in df.columns:

            df, total = calculate_bom_total(df)

            st.dataframe(
                df,
                use_container_width=True,
                key='bom_dataframe_calculated'
            )

            st.metric(
                'Total Material Cost',
                f'€ {total:,.2f}'
            )

            st.success('BOM costing completed')

        else:

            st.warning(
                'Columns Material Cost and Qty are required for costing.'
            )

        st.markdown('### Step 4 — Workflow Status')

        st.info(
            'BOM normalized → costing completed → ready for routing & manufacturing analysis.'
        )

    else:

        st.info(
            'Upload a BOM file to initialize the manufacturing costing workflow.'
        )
