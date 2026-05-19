from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes

BASE_BORE_MM = 720  # reference design bore diameter

st.set_page_config(page_title="Bore Scale", layout="wide", page_icon="📐")
home_button()
st.title("📐 Bore Scale")
st.caption(
    f"Scale the MWJ-{BASE_BORE_MM} BOM to a different bore diameter using per-line scaling exponents. "
    "Exponent 3 = volume (castings), 2 = area (rings/plates), 1 = linear (seals/tubes), 0 = fixed (fasteners/testing)."
)

if st.button("🔄 Refresh", help="Clear cache and reload"):
    st.cache_data.clear()
    st.rerun()

# ── Load baseline ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load():
    try:
        mats = apply_best_quotes(load_materials(), load_quotes())
        procs = load_processes()
        bom = load_bom()
        df = compute_costs(mats, procs, bom)
        return mats, procs, bom, df
    except Exception as exc:
        st.error(f"Could not load data: {exc}")
        return None, None, None, None


mats, procs, bom, df_base = _load()
if df_base is None:
    st.stop()

# ── Target bore selector ──────────────────────────────────────────────────────
st.subheader("Target bore diameter")
c1, c2 = st.columns([3, 1])
target_bore = c1.slider(
    "Target bore (mm)", min_value=400, max_value=1200, value=BASE_BORE_MM, step=10
)
c2.metric("Scale ratio", f"{target_bore / BASE_BORE_MM:.3f}×")

if target_bore == BASE_BORE_MM:
    st.info(f"Target bore equals reference bore ({BASE_BORE_MM} mm) — no scaling applied.")

st.divider()

# ── Apply bore scaling ────────────────────────────────────────────────────────
ratio = target_bore / BASE_BORE_MM
bom_scaled = bom.copy()

if "scale_exp" not in bom_scaled.columns:
    bom_scaled["scale_exp"] = 2.0  # default area scaling if column missing

bom_scaled["mass_kg"] = (
    bom_scaled["mass_kg"] * ratio ** bom_scaled["scale_exp"]
).round(3)

# Runtime also scales with volume/area (machining time ∝ mass roughly)
# Use half the scale_exp for time since feeds&speeds partially compensate
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
k1.metric(f"Sell price {BASE_BORE_MM} mm", fmt(base_sell))
k2.metric(f"Sell price {target_bore} mm",  fmt(scale_sell),
          delta=fmt_delta(scale_sell - base_sell))
k3.metric("Material Δ",
          fmt_delta(df_scaled["material_cost"].sum() - df_base["material_cost"].sum()))
k4.metric("Process Δ",
          fmt_delta(df_scaled["process_cost"].sum() - df_base["process_cost"].sum()))
k5.metric(f"Dry weight {BASE_BORE_MM} mm", f"{base_mass:,.0f} kg")
k6.metric(f"Dry weight {target_bore} mm",  f"{scaled_mass:,.0f} kg",
          delta=f"{scaled_mass - base_mass:+,.0f} kg")

st.divider()

# ── Cost per kg ───────────────────────────────────────────────────────────────
if scaled_mass > 0:
    cpk_base  = base_sell  / base_mass  if base_mass  else 0
    cpk_scale = scale_sell / scaled_mass
    ca1, ca2 = st.columns(2)
    ca1.metric("€/kg (baseline)", f"{cpk_base:,.1f}")
    ca2.metric("€/kg (scaled)",   f"{cpk_scale:,.1f}",
               delta=f"{cpk_scale - cpk_base:+,.1f}")
    st.divider()

# ── Scaling exponent legend ───────────────────────────────────────────────────
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

cmp = pd.DataFrame({
    "Line ID":        df_base["line_id"],
    "Component":      df_base["part_name"] if "part_name" in df_base.columns else "",
    "Scale exp":      bom["scale_exp"].values if "scale_exp" in bom.columns else 2.0,
    f"Mass {BASE_BORE_MM} mm (kg)": bom["mass_kg"].round(2).values,
    f"Mass {target_bore} mm (kg)":  bom_scaled["mass_kg"].round(2).values,
    f"Cost {BASE_BORE_MM} mm":      df_base["total_cost"].round(2),
    f"Cost {target_bore} mm":       df_scaled["total_cost"].round(2),
})
cmp["Cost Δ"] = (cmp[f"Cost {target_bore} mm"] - cmp[f"Cost {BASE_BORE_MM} mm"]).round(2)
cmp["Cost Δ%"] = (
    cmp["Cost Δ"] / cmp[f"Cost {BASE_BORE_MM} mm"].replace(0, float("nan")) * 100
).round(1)

for col in [f"Cost {BASE_BORE_MM} mm", f"Cost {target_bore} mm"]:
    cmp[col] = cmp[col].map(lambda x: fmt(x, 2))
cmp["Cost Δ"] = cmp["Cost Δ"].map(lambda x: fmt_delta(x, 2))
cmp["Cost Δ%"] = cmp["Cost Δ%"].map(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")

st.dataframe(cmp, use_container_width=True, hide_index=True)

st.divider()

# ── Download scaled BOM ───────────────────────────────────────────────────────
csv_scaled = bom_scaled.to_csv(index=False)
st.download_button(
    f"⬇️ Download scaled BOM CSV ({target_bore} mm)",
    data=csv_scaled,
    file_name=f"bom_scaled_{target_bore}mm.csv",
    mime="text/csv",
    use_container_width=True,
    help="Scaled BOM with adjusted mass_kg and runtime_h — review before use.",
)
