import streamlit as st

from engines.supplier_engine import (
    SUPPLIER_DATA,
    calculate_supplier_material_cost,
)


def render_suppliers():
    st.title('Supplier Costing')

    supplier = st.selectbox(
        'Supplier',
        list(SUPPLIER_DATA.keys())
    )

    material_kg = st.number_input(
        'Material Weight (kg)',
        value=100.0
    )

    result = calculate_supplier_material_cost(
        material_kg,
        SUPPLIER_DATA[supplier]
    )

    st.metric(
        'Material Cost',
        f"€ {result['total_material_cost']:,.2f}"
    )
