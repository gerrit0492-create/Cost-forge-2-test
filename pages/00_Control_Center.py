import streamlit as st

from config.navigation_registry import NAVIGATION_STRUCTURE

st.set_page_config(page_title='Cost Forge Control Center', layout='wide')

st.title('Cost Forge Control Center')
st.caption('Central application navigation')

for group, modules in NAVIGATION_STRUCTURE.items():
    st.subheader(group)

    cols = st.columns(2)

    for idx, module in enumerate(modules):
        with cols[idx % 2]:
            st.info(module)
