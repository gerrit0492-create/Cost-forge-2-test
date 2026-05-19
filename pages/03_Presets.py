from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.nav import home_button
from utils.presets import PricingPreset, load_presets, save_presets
from utils.safe import guard


st.set_page_config(page_title="Presets", layout="wide", page_icon="⚙️")


def main():
    home_button()
    st.title("⚙️ Pricing Presets")
    st.caption(
        "Overhead % and margin % presets applied globally to all BOM lines. "
        "Overhead applies to process cost only (marine industry standard)."
    )

    presets = load_presets()
    names   = list(presets.keys())

    # ── Edit existing preset ──────────────────────────────────────────────────
    st.subheader("Edit preset")
    pick = st.selectbox("Preset", names, index=0 if names else None)
    if pick:
        p    = presets[pick]
        over = st.number_input("Overhead %", value=p.overhead_pct * 100, step=1.0,
                               help="Applied to process cost per line.") / 100.0
        marg = st.number_input("Margin %",   value=p.margin_pct * 100,   step=1.0,
                               help="Applied to base cost (material + process + overhead).") / 100.0
        if st.button("Save", type="primary"):
            presets[pick] = PricingPreset(pick, over, marg)
            save_presets(presets)
            st.success(f"Preset '{pick}' saved.")

    st.divider()

    # ── Add new preset ────────────────────────────────────────────────────────
    st.subheader("Add preset")
    nm     = st.text_input("Name")
    over_n = st.number_input("Overhead % (new)", value=20.0, step=1.0) / 100.0
    marg_n = st.number_input("Margin % (new)",   value=10.0, step=1.0) / 100.0
    if st.button("Add preset") and nm:
        presets[nm] = PricingPreset(nm, over_n, marg_n)
        save_presets(presets)
        st.success(f"Preset '{nm}' added.")

    st.divider()

    # ── Current presets table ─────────────────────────────────────────────────
    st.subheader("All presets")
    tbl = pd.DataFrame([
        {"Name": p.name, "Overhead %": f"{p.overhead_pct*100:.0f}%", "Margin %": f"{p.margin_pct*100:.0f}%"}
        for p in presets.values()
    ])
    st.dataframe(tbl, use_container_width=True, hide_index=True)


guard(main)
