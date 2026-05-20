from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes, expired_quote_materials
from utils.style import inject_css, page_header


st.set_page_config(page_title="Quick Cost", layout="wide", page_icon="⚡")
inject_css()
home_button()
page_header(
    title="Quick Cost",
    icon="⚡",
    caption="Fast overview of the active BOM with best supplier prices applied.",
)

if st.button("🔄 Refresh", help="Clear cache and reload all data"):
    st.cache_data.clear()
    st.rerun()

# ── Load & compute ────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load() -> pd.DataFrame:
    mats   = load_materials()
    procs  = load_processes()
    bom    = load_bom()
    quotes = load_quotes()
    return compute_costs(apply_best_quotes(mats, quotes), procs, bom)


try:
    df = _load()
except Exception as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()

# ── Expired quote warning ─────────────────────────────────────────────────────
try:
    expired = expired_quote_materials(load_quotes())
    if expired:
        st.warning(f"⚠️ Expired quotes ignored for: {', '.join(expired)} — base catalogue prices used.")
except Exception:
    pass

# ── Subsystem filter ──────────────────────────────────────────────────────────
def _subsystem_prefix(line_id: str) -> str:
    upper = str(line_id).upper()
    for prefix in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
        if upper.startswith(prefix):
            return prefix
    return "?"


df["subsystem"] = df["line_id"].apply(_subsystem_prefix)
subsystem_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}

col_sub, col_search = st.columns([2, 3])
all_label = "All subsystems"
sub_options = [all_label] + [subsystem_names[p] for p in WATERJET_SUBSYSTEMS if p in df["subsystem"].values]
chosen_sub  = col_sub.selectbox("Subsystem", sub_options)
search_term = col_search.text_input("Search line ID / component", placeholder="e.g. I01 or impeller")

view = df.copy()
if chosen_sub != all_label:
    prefix = next(p for p, name in subsystem_names.items() if name == chosen_sub)
    view = view[view["subsystem"] == prefix]

if search_term:
    desc = view["part_name"] if "part_name" in view.columns else pd.Series("", index=view.index)
    mask = (
        view["line_id"].astype(str).str.contains(search_term, case=False, na=False) |
        desc.astype(str).str.contains(search_term, case=False, na=False)
    )
    view = view[mask]

st.caption(f"Showing {len(view)} of {len(df)} BOM lines")

# ── KPI row ───────────────────────────────────────────────────────────────────
total_mass = (
    (pd.to_numeric(view["qty"], errors="coerce").fillna(1) * view["mass_kg"].fillna(0)).sum()
)
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Material (purchase)", fmt(view['material_cost'].sum()))
k2.metric("Process",             fmt(view['process_cost'].sum()))
k3.metric("Overhead",            fmt(view['overhead'].sum()))
k4.metric("Your cost",           fmt(view['base_cost'].sum()))
k5.metric("Selling price",       fmt(view['total_cost'].sum()))
k6.metric("Dry weight",          f"{total_mass:,.0f} kg")

st.divider()

# ── Line table ────────────────────────────────────────────────────────────────
display_cols = {
    "line_id":       "Line ID",
    "part_name":     "Component",
    "material_id":   "Material",
    "qty":           "Qty",
    "mass_kg":       "Mass kg",
    "material_cost": "Purchase €",
    "process_route": "Process",
    "runtime_h":     "Runtime h",
    "machine_cost":  "Machine €",
    "labour_cost":   "Labour €",
    "process_cost":  "Process €",
    "overhead":      "Overhead €",
    "base_cost":     "Your cost €",
    "margin":        "Margin €",
    "total_cost":    "Sell price €",
}
table = view[[c for c in display_cols if c in view.columns]].copy()
table.rename(columns=display_cols, inplace=True)

for col in ["Purchase €", "Machine €", "Labour €", "Process €",
            "Overhead €", "Your cost €", "Margin €", "Sell price €"]:
    if col in table.columns:
        table[col] = table[col].map(lambda x: fmt(x, 2) if pd.notna(x) else "—")

st.dataframe(table, use_container_width=True, hide_index=True)

# ── Subsystem summary ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Subsystem summary")

agg = (
    df.groupby("subsystem").agg(
        material_cost=("material_cost", "sum"),
        process_cost=("process_cost", "sum"),
        overhead=("overhead", "sum"),
        base_cost=("base_cost", "sum"),
        margin=("margin", "sum"),
        total_cost=("total_cost", "sum"),
        dry_kg=pd.NamedAgg(
            column="mass_kg",
            aggfunc=lambda s: (
                pd.to_numeric(df.loc[s.index, "qty"], errors="coerce").fillna(1) * s.fillna(0)
            ).sum()
        ),
    )
    .reset_index()
)
agg["Subsystem"]   = agg["subsystem"].map(lambda p: subsystem_names.get(p, p))
agg["Purchase €"]  = agg["material_cost"].map(lambda x: fmt(x))
agg["Process €"]   = agg["process_cost"].map(lambda x: fmt(x))
agg["Overhead €"]  = agg["overhead"].map(lambda x: fmt(x))
agg["Your cost €"] = agg["base_cost"].map(lambda x: fmt(x))
agg["Margin €"]    = agg["margin"].map(lambda x: fmt(x))
agg["Sell price €"]= agg["total_cost"].map(lambda x: fmt(x))
agg["Mass kg"]     = agg["dry_kg"].map(lambda x: f"{x:,.0f}")

st.dataframe(
    agg[["Subsystem", "Purchase €", "Process €", "Overhead €",
         "Your cost €", "Margin €", "Sell price €", "Mass kg"]],
    use_container_width=True, hide_index=True,
)

# ── CSV download ──────────────────────────────────────────────────────────────
st.divider()
st.download_button(
    "⬇️ Download full cost CSV",
    data=view[[c for c in display_cols if c in view.columns]].to_csv(index=False),
    file_name="quick_cost.csv",
    mime="text/csv",
    use_container_width=True,
)
