import streamlit as st


def render():
    st.title('Management Dashboard')
    st.caption('Executive KPI and financial overview')

    c1, c2, c3, c4 = st.columns(4)

    c1.metric('Revenue Exposure', '€1.2M')
    c2.metric('Cost Exposure', '€870K')
    c3.metric('Margin', '27.5%')
    c4.metric('Projects Active', 14)

    st.success('Executive management dashboard active')
