import streamlit as st
import pandas as pd


def render_dashboard():
    st.title('Dashboard')

    c1, c2, c3 = st.columns(3)

    c1.metric('Projects', 12)
    c2.metric('RFQs', 7)
    c3.metric('Margin', '28%')

    data = pd.DataFrame({
        'Month': ['Jan', 'Feb', 'Mar', 'Apr'],
        'Revenue': [120000, 145000, 167000, 210000]
    })

    st.line_chart(data.set_index('Month'))
