import pandas as pd
import streamlit as st



def render():

    st.title('Executive Dashboard')
    st.caption('Enterprise management intelligence')

    c1, c2, c3, c4 = st.columns(4)

    c1.metric('Revenue', '€4.2M')
    c2.metric('Margin', '28%')
    c3.metric('Projects', 18)
    c4.metric('Risk Alerts', 3)

    data = pd.DataFrame(
        {
            'Month': ['Jan', 'Feb', 'Mar', 'Apr'],
            'Revenue': [120000, 180000, 160000, 240000],
        }
    )

    st.line_chart(data.set_index('Month'))
