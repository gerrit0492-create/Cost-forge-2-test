import streamlit as st
import pandas as pd

from services.pdf_quote_service import PDFQuoteService
from services.excel_export_service import ExcelExportService


def render_quote_generator():

    st.title('Quote Generator')

    customer = st.text_input('Customer')
    project = st.text_input('Project')

    total_cost = st.number_input(
        'Total Cost',
        value=10000.0
    )

    margin_percent = st.number_input(
        'Margin %',
        value=25.0
    )

    sales_price = (
        total_cost *
        (1 + margin_percent / 100)
    )

    st.metric(
        'Sales Price',
        f"€ {sales_price:,.2f}"
    )

    quote_df = pd.DataFrame({
        'Field': [
            'Customer',
            'Project',
            'Total Cost',
            'Margin %',
            'Sales Price'
        ],
        'Value': [
            customer,
            project,
            total_cost,
            margin_percent,
            sales_price
        ]
    })

    st.dataframe(
        quote_df,
        use_container_width=True
    )

    if st.button('Generate Excel Quote'):

        path = 'exports/quote.xlsx'

        ExcelExportService.export_dataframe(
            quote_df,
            path
        )

        st.success(f'Excel quote generated: {path}')

    if st.button('Generate PDF Quote'):

        path = 'exports/quote.pdf'

        PDFQuoteService.generate_quote(
            path,
            customer,
            project,
            total_cost,
            margin_percent,
            sales_price,
        )

        st.success(f'PDF quote generated: {path}')
