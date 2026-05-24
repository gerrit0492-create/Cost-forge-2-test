from __future__ import annotations

import pandas as pd
import streamlit as st

from CF3.engines.bom_engine import prepare_bom, validate_bom
from CF3.engines.costing_engine import calculate_cost

st.title('BOM Intelligence')
st.caption('Enterprise BOM validation and costing pipeline')

uploaded = st.file_uploader(
    'Upload BOM CSV or Excel',
    type=['csv', 'xlsx']
)

if uploaded:
    if uploaded.name.endswith('.csv'):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    errors = validate_bom(df)

    if errors:
        for error in errors:
            st.error(error)
    else:
        bom = prepare_bom(df)
        result = calculate_cost(bom)

        st.success('BOM validated successfully')

        c1, c2, c3 = st.columns(3)
        c1.metric('Lines', len(result))
        c2.metric('Total Material Cost', f"€{result['material_cost'].sum():,.2f}")
        c3.metric('Total Cost', f"€{result['total_cost'].sum():,.2f}")

        st.dataframe(result, use_container_width=True)
