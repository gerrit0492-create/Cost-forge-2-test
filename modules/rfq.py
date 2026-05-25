import streamlit as st


def render_rfq():
    st.title('RFQ Workflow')

    customer = st.text_input('Customer')
    project = st.text_input('Project')
    target_price = st.number_input('Target Price', value=10000.0)

    st.success('RFQ workflow initialized')
