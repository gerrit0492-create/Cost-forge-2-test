from __future__ import annotations

import streamlit as st

from utils.project import load_project_name


def home_button() -> None:
    from utils.currency import currency_selector
    currency_selector()
    col_home, col_project = st.columns([1, 6])
    col_home.markdown("[🏠 ← Home](/)")
    name = load_project_name()
    if name:
        col_project.markdown(f"**Assembly:** {name}")
    st.divider()
