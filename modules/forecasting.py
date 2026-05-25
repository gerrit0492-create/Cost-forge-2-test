import streamlit as st
import pandas as pd


def render_forecasting():
    st.title('Forecasting')

    forecast = pd.DataFrame({
        'Month': ['May', 'Jun', 'Jul', 'Aug'],
        'Forecast Revenue': [220000, 240000, 255000, 280000]
    })

    st.dataframe(forecast, use_container_width=True)

    st.bar_chart(
        forecast.set_index('Month')
    )
