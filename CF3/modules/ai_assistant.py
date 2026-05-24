import streamlit as st


def render():
    st.title('AI Assistant')
    st.caption('AI powered estimating and BOM support')

    prompt = st.text_area('Ask the CF3 AI Assistant')

    if prompt:
        st.success('AI assistant workflow placeholder active')
