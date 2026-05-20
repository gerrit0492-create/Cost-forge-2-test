from pathlib import Path

import pandas as pd
import streamlit as st
from utils.nav import home_button

H = Path("data/history")
home_button()
st.title("🚨 Anomalie Overzicht")

if not H.exists():
    st.info("Nog geen history map.")
else:
    files = sorted(H.glob("anomalies_*.csv"))
    if not files:
        st.success("Geen anomaly-logs gevonden.")
    else:
        pick = st.selectbox("Kies log", [p.name for p in files], index=len(files) - 1)
        df = pd.read_csv(H / pick)
        st.write(f"Regels: {len(df)} | Bestand: {pick}")
        st.dataframe(df, use_container_width=True)
