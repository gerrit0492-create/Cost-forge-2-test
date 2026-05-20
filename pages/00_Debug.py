import platform
import sys

import streamlit as st

from utils.nav import home_button
from utils.safe import guard


def main():
    home_button()
    st.title("🪲 Debug")
    st.write("Python:", sys.version)
    st.write("Platform:", platform.platform())


guard(main)
