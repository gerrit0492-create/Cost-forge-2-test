from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.io import load_bom
from utils.nav import home_button
from utils.routing import compute_routing_cost, routing_summary
from utils.safe import guard

ROUTING_PATH = Path("data/routing.csv")

st.set_page_config(page_title="Routing Costs", layout="wide", page_icon="🛠️")


def main():
    home_button()
    st.title("🛠️ Routing Costs")
    st.caption(
        "Upload a routing file to compute setup + run-time per process centre. "
        "The file is saved and reloaded automatically on future visits."
    )
    st.markdown(
        "**Required columns:** `process_id`, `time_h_per_unit`, `setup_h`  \n"
        "_These map to `process_route` in the BOM._"
    )

    up = st.file_uploader("Upload routing.csv", type=["csv"])
    if up:
        try:
            routing = pd.read_csv(up)
            ROUTING_PATH.write_text(routing.to_csv(index=False), encoding="utf-8")
            st.success(f"Routing file saved to `{ROUTING_PATH}`.")
        except Exception as e:
            st.error(f"Could not read routing file: {e}")
            return
    elif ROUTING_PATH.exists():
        st.info(f"Using saved routing file: `{ROUTING_PATH}`")
        try:
            routing = pd.read_csv(ROUTING_PATH)
        except Exception as e:
            st.error(f"Could not read saved routing file: {e}")
            return
    else:
        st.info(
            "No routing file uploaded yet. "
            "Upload a CSV with columns: `process_id`, `time_h_per_unit`, `setup_h`."
        )
        return

    bom     = load_bom()
    df      = compute_routing_cost(bom, routing)
    summary = routing_summary(df)

    st.subheader("Routing detail")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Summary by process centre")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ Download routing detail CSV",
        data=df.to_csv(index=False),
        file_name="routing_detail.csv",
        mime="text/csv",
        use_container_width=True,
    )


guard(main)
