from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.io import load_bom, load_materials, load_processes, load_quotes, df_to_excel_bytes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes

BASE_BORE_MM = 720  # reference design — scale ratio 1.000

# Standard waterjet sizes (nominal impeller bore diameter in mm)
STANDARD_SIZES = [410, 500, 550, 600, 650, 720, 800, 900, 1000, 1100, 1200, 1350, 1500, 1650, 1800, 2000, 2120]

st.set_page_config(page_title="Waterjet Size Scale", layout="wide", page_icon="📐")
home_button()
st.title("📐 Waterjet Size Scale")
st.caption(
    f"Scale the MWJ-{BASE_BORE_MM} BOM to any waterjet bore size (410 – 2120 mm). "
    f"MWJ-{BASE_BORE_MM} is the reference unit at scale ratio **1.000**. "
    "Exponent 3 = volume (castings), 2 = area (rings/plates), 1 = linear (seals/tubes), 0 = fixed (fasteners/testing)."
)

if st.button("🔄 Refresh", help="Clear cache and reload"):
    st.cache_data.clear()
    st.rerun()

# ── Load baseline ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load():
    mats  = apply_best_quotes(load_materials(), load_quotes())
    procs = load_processes()
    bom   = load_bom()
    df    = compute_costs(mats, procs, bom)
    return mats, procs, bom, df


try:
    mats, procs, bom, df_base = _load()
except Exception as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()

if df_base is None:
    st.stop()

# ── Target size selector ──────────────────────────────────────────────────────
st.subheader("Target waterjet size")

sz1, sz2, sz3 = st.columns([2, 2, 1])

target_bore = sz1.slider(
    "Bore diameter (mm)",
    min_value=410, max_value=2120,
    value=BASE_BORE_MM, step=10,
    help="Drag to any size between MWJ-410 and MWJ-2120.",
)

# Snap to nearest standard size button
snap_label = min(STANDARD_SIZES, key=lambda s: abs(s - target_bore))
if sz2.button(f"Snap to nearest standard: MWJ-{snap_label}"):
    target_bore = snap_label

ratio = target_bore / BASE_BORE_MM
sz3.metric("Scale ratio", f"{ratio:.3f}×")

# Standard sizes quick-select
st.caption("**Standard sizes:**  "
           + "  |  ".join(
               f"**MWJ-{s}**" if s == target_bore
               else (f"`MWJ-{s}`" if s == BASE_BORE_MM else f"MWJ-{s}")
               for s in STANDARD_SIZES
           ))

if target_bore == BASE_BORE_MM:
    st.info(f"Target equals reference MWJ-{BASE_BORE_MM} — scale ratio 1.000, no changes applied.")

st.divider()

# ── Apply bore scaling ────────────────────────────────────────────────────────
bom_scaled = bom.copy()

if "scale_exp" not in bom_scaled.columns:
    bom_scaled["scale_exp"] = 2.0

# Ensure numeric, fill missing with area default
bom_scaled["scale_exp"] = pd.to_numeric(bom_scaled["scale_exp"], errors="coerce").fillna(2.0)

bom_scaled["mass_kg"] = (
    bom_scaled["mass_kg"] * ratio ** bom_scaled["scale_exp"]
).round(3)

# Runtime scales at half the geometric exponent (feeds/speeds partially compensate)
bom_scaled["runtime_h"] = (
    bom_scaled["runtime_h"] * ratio ** (bom_scaled["scale_exp"] * 0.5)
).round(3)

df_scaled = compute_costs(mats, procs, bom_scaled)

# ── KPI comparison ────────────────────────────────────────────────────────────
base_mass = (
    pd.to_numeric(bom["qty"], errors="coerce").fillna(1) * bom["mass_kg"].fillna(0)
).sum()
scaled_mass = (
    pd.to_numeric(bom_scaled["qty"], errors="coerce").fillna(1) * bom_scaled["mass_kg"].fillna(0)
).sum()

base_sell  = df_base["total_cost"].sum()
scale_sell = df_scaled["total_cost"].sum()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric(f"Sell price MWJ-{BASE_BORE_MM}", fmt(base_sell))
k2.metric(f"Sell price MWJ-{target_bore}",  fmt(scale_sell),
          delta=fmt_delta(scale_sell - base_sell))
k3.metric("Material Δ",
          fmt_delta(df_scaled["material_cost"].sum() - df_base["material_cost"].sum()))
k4.metric("Process Δ",
          fmt_delta(df_scaled["process_cost"].sum() - df_base["process_cost"].sum()))
k5.metric(f"Dry weight MWJ-{BASE_BORE_MM}", f"{base_mass:,.0f} kg")
k6.metric(f"Dry weight MWJ-{target_bore}",  f"{scaled_mass:,.0f} kg",
          delta=f"{scaled_mass - base_mass:+,.0f} kg")

st.divider()

# ── Cost per kg ───────────────────────────────────────────────────────────────
if scaled_mass > 0 and base_mass > 0:
    cpk_base  = base_sell  / base_mass
    cpk_scale = scale_sell / scaled_mass
    ca1, ca2 = st.columns(2)
    ca1.metric(f"€/kg  MWJ-{BASE_BORE_MM}", f"{cpk_base:,.1f}")
    ca2.metric(f"€/kg  MWJ-{target_bore}",  f"{cpk_scale:,.1f}",
               delta=f"{cpk_scale - cpk_base:+,.1f}")
    st.divider()

# ── Scaling exponent guide ────────────────────────────────────────────────────
with st.expander("Scaling exponent guide", expanded=False):
    st.markdown("""
| Exponent | Scaling law | Typical parts |
|---|---|---|
| **3** | Volume (cubic) | Sand castings, large billet blanks |
| **2** | Area (quadratic) | Rings, flanges, housings, plates, weld structures |
| **1** | Linear | Seals, O-rings, tubes, thin-wall sleeves |
| **0** | Fixed | Standard fasteners, NDT, testing operations, coatings |
""")

# ── Per-line comparison table ─────────────────────────────────────────────────
st.subheader("Line-by-line comparison")

scale_exp_col = (
    bom["scale_exp"].values
    if "scale_exp" in bom.columns
    else pd.Series([2.0] * len(bom)).values
)

col_base_mass = f"Mass ref-{BASE_BORE_MM} (kg)"
col_tgt_mass  = f"Mass MWJ-{target_bore} (kg)"
col_base_cost = f"Cost ref-{BASE_BORE_MM}"
col_tgt_cost  = f"Cost MWJ-{target_bore}"

cmp = pd.DataFrame({
    "Line ID":      df_base["line_id"],
    "Component":    df_base["part_name"] if "part_name" in df_base.columns else "",
    "Scale exp":    scale_exp_col,
    col_base_mass:  bom["mass_kg"].round(2).values,
    col_tgt_mass:   bom_scaled["mass_kg"].round(2).values,
    col_base_cost:  df_base["total_cost"].round(2),
    col_tgt_cost:   df_scaled["total_cost"].round(2),
})
cmp["Cost Δ"] = (cmp[col_tgt_cost] - cmp[col_base_cost]).round(2)
cmp["Cost Δ%"] = (
    cmp["Cost Δ"] / cmp[col_base_cost].replace(0, float("nan")) * 100
).round(1)

cmp[col_base_cost] = cmp[col_base_cost].map(lambda x: fmt(x, 2))
cmp[col_tgt_cost]  = cmp[col_tgt_cost].map(lambda x: fmt(x, 2))
cmp["Cost Δ"]  = cmp["Cost Δ"].map(lambda x: fmt_delta(x, 2))
cmp["Cost Δ%"] = cmp["Cost Δ%"].map(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")

st.dataframe(cmp, use_container_width=True, hide_index=True)

st.divider()

# ── Download scaled BOM ───────────────────────────────────────────────────────
excel_scaled = df_to_excel_bytes(bom_scaled, "BOM")
st.download_button(
    f"⬇️ Download scaled BOM — MWJ-{target_bore} (Excel)",
    data=excel_scaled,
    file_name=f"bom_mwj{target_bore}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
    help="Scaled BOM with adjusted mass_kg and runtime_h — review before use.",
)
