import streamlit as st


def render_reporting():
    st.title('Reporting')

    st.info('Reporting engine initialized')

    st.download_button(
        'Download Report',
        data='Cost Forge 2.0 Report',
        file_name='cf2_report.txt'
    )
