import streamlit as st


def render():
    st.title('Contract & Cashflow')
    st.caption('Contract exposure and cashflow tracking')

    st.metric('Outstanding Cashflow', '€425K')
    st.metric('Contract Exposure', '€2.1M')

    st.info('Contract and cashflow module active')
