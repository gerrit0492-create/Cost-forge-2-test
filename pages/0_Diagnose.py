import streamlit as st

from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.safe import guard


def main():
    home_button()
    st.title("🧬 Diagnose")
    for name, loader in [
        ("Materials", load_materials),
        ("Processes", load_processes),
        ("BOM", load_bom),
        ("Quotes", load_quotes),
    ]:
        st.subheader(name)
        try:
            st.dataframe(loader())
        except Exception as e:
            st.error(f"{name}: {e}")


guard(main)
