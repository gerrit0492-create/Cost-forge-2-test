import streamlit as st

from services.database_service import (
    initialize_database,
    save_project,
)


initialize_database()


def render_project_save():
    st.title('Project Save')

    customer = st.text_input('Customer')
    project_name = st.text_input('Project Name')
    sales_price = st.number_input('Sales Price', value=10000.0)
    total_cost = st.number_input('Total Cost', value=8000.0)
    margin_percent = st.number_input('Margin %', value=20.0)

    if st.button('Save Project'):
        save_project(
            customer,
            project_name,
            sales_price,
            total_cost,
            margin_percent,
        )

        st.success('Project saved successfully')
