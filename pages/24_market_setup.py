# pages/23_Market_Setup.py
from pathlib import Path

import pandas as pd
import streamlit as st
from utils.nav import home_button

URL_FILE = Path("data/market_factors_url.txt")
LOCAL_CSV = Path("data/market_factors.csv")


def save_url(url: str) -> None:
    URL_FILE.parent.mkdir(parents=True, exist_ok=True)
    URL_FILE.write_text(url.strip(), encoding="utf-8")


def try_read(url: str):
    try:
        df = pd.read_csv(url, comment="#")
        return df
    except Exception as e:
        return f"Kon CSV-URL niet lezen: {e}"


def try_read_local():
    try:
        if LOCAL_CSV.exists():
            return pd.read_csv(LOCAL_CSV, comment="#")
        return "Lokaal CSV niet gevonden (optional)."
    except Exception as e:
        return f"Kon lokaal CSV niet lezen: {e}"


home_button()
st.title("🧩 Market Setup (iPhone-proof)")
st.caption(
    "Plak je Google Sheet CSV-link hier, of upload handmatig een CSV. De wekelijkse update gebruikt eerst de URL, anders de lokale CSV."
)

with st.expander(
    "1) Plak je CSV-URL (Google Sheet → Bestand → Delen → 'Iedereen met link', export=csv)", True
):
    url = st.text_input(
        "CSV-URL", value=(URL_FILE.read_text(encoding="utf-8").strip() if URL_FILE.exists() else "")
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Opslaan URL"):
            if url.strip():
                save_url(url)
                st.success("URL opgeslagen in data/market_factors_url.txt")
            else:
                st.warning("Lege URL niet opgeslagen.")
    with c2:
        if st.button("🔍 Test URL"):
            res = try_read(url.strip())
            if isinstance(res, pd.DataFrame):
                st.success(f"URL OK — {len(res)} rijen")
                st.dataframe(res.head(), use_container_width=True)
            else:
                st.error(res)

with st.expander("2) Of upload handmatig een CSV (fallback)", False):
    up = st.file_uploader("Upload market_factors.csv", type=["csv"])
    if up is not None:
        df = pd.read_csv(up)
        LOCAL_CSV.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(LOCAL_CSV, index=False)
        st.success(f"Opgeslagen naar {LOCAL_CSV}")
        st.dataframe(df.head(), use_container_width=True)

with st.expander("3) Huidige bronnen (controle)", False):
    if URL_FILE.exists():
        st.info(f"URL-bron: {URL_FILE.read_text(encoding='utf-8').strip()}")
    else:
        st.warning("Nog geen URL-bron ingesteld.")
    res_local = try_read_local()
    if isinstance(res_local, pd.DataFrame):
        st.write(f"Lokaal CSV rijen: {len(res_local)}")
        st.dataframe(res_local.head(), use_container_width=True)
    else:
        st.write(res_local)

st.caption("Klaar. De workflow ‘Weekly Market Update’ gebruikt deze bronnen automatisch.")
