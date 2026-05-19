from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes


st.set_page_config(page_title="Scenario Planner", layout="wide", page_icon="🧭")
home_button()
st.title("🧭 Scenario Planner")
st.caption("Simulate the impact of material price changes, labour rate shifts, and margin adjustments.")

# ── Load baseline ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _baseline():
    mats   = load_materials()
    procs  = load_processes()
    quotes = load_quotes()
    bom    = load_bom()
    mats_q = apply_best_quotes(mats, quotes)
    df     = compute_costs(mats_q, procs, bom)
    return mats_q, procs, bom, df


mats_base, procs_base, bom, df_base = _baseline()
total_base = df_base["total_cost"].sum()

# ── Sidebar: per-commodity material sliders ───────────────────────────────────
st.sidebar.header("Scenario controls")

commodities = (
    sorted(mats_base["commodity"].dropna().unique().tolist())
    if "commodity" in mats_base.columns else []
)

st.sidebar.subheader("Material price change % by commodity")
commodity_deltas: dict[str, float] = {}
for comm in commodities:
    delta = st.sidebar.slider(comm, min_value=-50, max_value=50, value=0, step=5, key=f"mat_{comm}")
    commodity_deltas[comm] = delta / 100.0

st.sidebar.divider()
st.sidebar.subheader("Process rates")
labour_delta  = st.sidebar.slider("Labour rate ±%",  -50, 50, 0, 5) / 100.0
machine_delta = st.sidebar.slider("Machine rate ±%", -50, 50, 0, 5) / 100.0
margin_delta  = st.sidebar.slider("Margin ±pp",      -20, 20, 0, 1) / 100.0

# ── Apply scenario ────────────────────────────────────────────────────────────
mats_s = mats_base.copy()
if "commodity" in mats_s.columns:
    for comm, delta in commodity_deltas.items():
        if delta != 0:
            mats_s.loc[mats_s["commodity"] == comm, "price_eur_per_kg"] *= (1 + delta)

procs_s = procs_base.copy()
procs_s["labor_rate_eur_h"]   *= (1 + labour_delta)
procs_s["machine_rate_eur_h"] *= (1 + machine_delta)
procs_s["margin_pct"]         += margin_delta

df_s = compute_costs(mats_s, procs_s, bom)
total_s    = df_s["total_cost"].sum()
delta_abs  = total_s - total_base
delta_pct  = delta_abs / total_base * 100 if total_base else 0

# ── KPI comparison ────────────────────────────────────────────────────────────
st.subheader("Cost impact")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Baseline selling price", f"€ {total_base:,.0f}")
k2.metric("Scenario selling price", f"€ {total_s:,.0f}",
          delta=f"€ {delta_abs:+,.0f} ({delta_pct:+.1f}%)")
k3.metric("Material Δ",
          f"€ {df_s['material_cost'].sum() - df_base['material_cost'].sum():+,.0f}")
k4.metric("Process Δ",
          f"€ {df_s['process_cost'].sum() - df_base['process_cost'].sum():+,.0f}")

st.divider()

# ── Commodity breakdown ───────────────────────────────────────────────────────
if "commodity" in df_base.columns and "commodity" in df_s.columns:
    st.subheader("Material cost by commodity — baseline vs scenario")
    grp_base = df_base.groupby("commodity")["material_cost"].sum()
    grp_s    = df_s.groupby("commodity")["material_cost"].sum()
    comm_df  = pd.DataFrame({"Baseline €": grp_base, "Scenario €": grp_s}).fillna(0)
    comm_df["Delta €"] = comm_df["Scenario €"] - comm_df["Baseline €"]
    comm_df["Delta %"] = (
        comm_df["Delta €"] / comm_df["Baseline €"].replace(0, float("nan")) * 100
    ).round(1)
    comm_df = comm_df.sort_values("Delta €", ascending=False)

    col_chart, col_tbl = st.columns([2, 1])
    with col_chart:
        st.bar_chart(comm_df[["Baseline €", "Scenario €"]])
    with col_tbl:
        st.dataframe(
            comm_df.style.format({
                "Baseline €": "€ {:,.0f}", "Scenario €": "€ {:,.0f}",
                "Delta €": "€ {:+,.0f}", "Delta %": "{:+.1f}%",
            }),
            use_container_width=True,
        )
    st.divider()

# ── Line-by-line comparison ───────────────────────────────────────────────────
st.subheader("Line-by-line comparison")

cmp = pd.DataFrame({
    "line_id":   df_base["line_id"],
    "Component": df_base["part_name"] if "part_name" in df_base.columns else "",
    "Baseline €": df_base["total_cost"].round(2),
    "Scenario €": df_s["total_cost"].round(2),
})
cmp["Delta €"] = (cmp["Scenario €"] - cmp["Baseline €"]).round(2)
cmp["Delta %"] = (cmp["Delta €"] / cmp["Baseline €"].replace(0, float("nan")) * 100).round(1)

st.dataframe(
    cmp.style.format({
        "Baseline €": "€ {:,.2f}", "Scenario €": "€ {:,.2f}",
        "Delta €": "€ {:+,.2f}", "Delta %": "{:+.1f}%",
    }),
    use_container_width=True, hide_index=True,
)
