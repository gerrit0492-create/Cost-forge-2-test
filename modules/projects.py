import streamlit as st
import pandas as pd


def render_projects():
    st.title('Projects')

    projects = pd.DataFrame({
        'Project': ['DAF', 'ASML', 'Wartsila'],
        'Status': ['Open', 'Quoted', 'Production'],
        'Value': [250000, 125000, 430000]
    })

    st.dataframe(projects, use_container_width=True)
