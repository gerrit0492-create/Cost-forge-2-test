import streamlit as st


def render():
    st.title('Command Centre')
    st.caption('Enterprise operational overview')

    st.success('Command centre operational')

    c1, c2, c3 = st.columns(3)

    c1.metric('Projects', 14)
    c2.metric('RFQs Active', 6)
    c3.metric('Risk Alerts', 2)
