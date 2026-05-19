from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_name
from utils.quotes import apply_best_quotes, expired_quote_materials


st.set_page_config(page_title="Quote Sheet", layout="wide", page_icon="🧾")
home_button()
st.title("🧾 Quote Sheet")
st.caption("Internal cost + margin vs customer selling price — per subsystem and per line.")

if st.button("🔄 Refresh", help="Clear cache and reload all data"):
    st.cache_data.clear()
    st.rerun()

# ── Quote header ──────────────────────────────────────────────────────────────
st.subheader("Quote header")
h1, h2, h3, h4 = st.columns(4)
quote_number  = h1.text_input("Quote number", value="QT-2026-001")
quote_date    = h2.date_input("Date", value=datetime.date.today())
customer_name = h3.text_input("Customer", value="")
validity_days = h4.number_input("Valid (days)", min_value=1, max_value=365, value=60)
project_label = st.text_input("Project / description", value=load_project_name())

st.divider()

# ── Production run & classification ──────────────────────────────────────────
st.subheader("Production parameters")
p1, p2 = st.columns(2)

num_units = p1.number_input(
    "Production run (units)", min_value=1, max_value=20, value=1,
    help="Number of identical units in this order. Setup time is amortised across the run."
)

CERT_CLASSES = {
    "None (commercial / uncertified)": {"ndt_mult": 1.0, "test_mult": 1.0, "fee_eur": 0},
    "DNV / GL":                         {"ndt_mult": 1.5, "test_mult": 1.3, "fee_eur": 3_500},
    "Lloyd's Register (LRS)":           {"ndt_mult": 1.5, "test_mult": 1.3, "fee_eur": 3_500},
    "Bureau Veritas (BV)":              {"ndt_mult": 1.4, "test_mult": 1.25, "fee_eur": 3_000},
    "ABS":                              {"ndt_mult": 1.4, "test_mult": 1.25, "fee_eur": 3_000},
}
cert_class = p2.selectbox(
    "Classification society",
    list(CERT_CLASSES.keys()),
    help="Adds surcharge to NDT inspection and pressure test costs per class requirements.",
)
cert_cfg = CERT_CLASSES[cert_class]

st.divider()

# ── Load & compute ────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load(n_units: int) -> pd.DataFrame | None:
    try:
        mats = apply_best_quotes(load_materials(), load_quotes())
        return compute_costs(mats, load_processes(), load_bom(), num_units=n_units)
    except Exception as exc:
        st.error(f"Could not load cost data: {exc}")
        return None


df = _load(int(num_units))
if df is None:
    st.stop()

# Expired quote warning
try:
    expired = expired_quote_materials(load_quotes())
    if expired:
        st.warning(f"⚠️ Expired quotes ignored for: {', '.join(expired)}")
except Exception:
    pass

df["subsystem"] = df["line_id"].apply(
    lambda lid: next(
        (p for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True)
         if str(lid).upper().startswith(p)), "?"
    )
)
subsystem_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}

# ── Margin override ───────────────────────────────────────────────────────────
st.subheader("Margin settings")
use_override = st.toggle("Override BOM margin with a single global margin")
global_margin_pct: float | None = None
if use_override:
    global_margin_pct = st.slider(
        "Global margin %", min_value=0, max_value=50, value=18, step=1
    ) / 100.0
    st.info(f"All lines will use **{global_margin_pct*100:.0f}%** margin for this quote.")

work = df.copy()
if global_margin_pct is not None:
    work["margin_pct"] = global_margin_pct
    work["margin"]     = work["base_cost"] * global_margin_pct
    work["total_cost"] = work["base_cost"] + work["margin"]

# ── Certification surcharge ───────────────────────────────────────────────────
ndt_cost  = work.loc[work["process_route"] == "NDT_INSPECT",  "process_cost"].sum()
test_cost = work.loc[work["process_route"] == "PRESSURE_TEST", "process_cost"].sum()
cert_surcharge = (
    ndt_cost  * (cert_cfg["ndt_mult"]  - 1.0) +
    test_cost * (cert_cfg["test_mult"] - 1.0) +
    cert_cfg["fee_eur"]
)

st.divider()

# ── Top-level KPIs ────────────────────────────────────────────────────────────
qty_s       = pd.to_numeric(work["qty"], errors="coerce").fillna(1)
total_mass  = (qty_s * work["mass_kg"].fillna(0)).sum()
total_mat   = work["material_cost"].sum()
total_mach  = work["machine_cost"].sum()
total_lab   = work["labour_cost"].sum()
total_oh    = work["overhead"].sum()
total_base  = work["base_cost"].sum()
total_marg  = work["margin"].sum()
total_sell  = work["total_cost"].sum() + cert_surcharge

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Material (purchase)", fmt(total_mat))
k2.metric("Machine + Labour",    fmt(total_mach + total_lab))
k3.metric("Overhead",            fmt(total_oh))
k4.metric("Your cost",           fmt(total_base))
k5.metric("Selling price",       fmt(total_sell),
          delta=f"Margin {fmt(total_marg)} ({total_marg/total_base*100:.1f}%)" if total_base else None)
k6.metric("Dry weight",          f"{total_mass:,.0f} kg")

if cert_surcharge > 0:
    st.info(
        f"**{cert_class} certification surcharge: {fmt(cert_surcharge)}** added to selling price  \n"
        f"(NDT ×{cert_cfg['ndt_mult']}, pressure test ×{cert_cfg['test_mult']}, "
        f"cert. fee {fmt(cert_cfg['fee_eur'])})"
    )

if num_units > 1:
    st.info(f"Setup hours amortised across **{int(num_units)} units**. Costs shown are per-unit.")

st.divider()

# ── Per-subsystem summary ─────────────────────────────────────────────────────
st.subheader("Subsystem summary")

work["_line_mass"] = qty_s * work["mass_kg"].fillna(0)
agg = (
    work.groupby("subsystem")[
        ["material_cost", "machine_cost", "labour_cost",
         "overhead", "base_cost", "margin", "total_cost", "_line_mass"]
    ]
    .sum()
    .reset_index()
)
agg["Subsystem"]   = agg["subsystem"].map(lambda p: subsystem_names.get(p, p))
agg["Purchase €"]  = agg["material_cost"].map(lambda x: fmt(x))
agg["Machine €"]   = agg["machine_cost"].map(lambda x: fmt(x))
agg["Labour €"]    = agg["labour_cost"].map(lambda x: fmt(x))
agg["Overhead €"]  = agg["overhead"].map(lambda x: fmt(x))
agg["Your cost €"] = agg["base_cost"].map(lambda x: fmt(x))
agg["Margin €"]    = agg["margin"].map(lambda x: fmt(x))
agg["Margin %"]    = (agg["margin"] / agg["base_cost"] * 100).map(lambda x: f"{x:.1f}%")
agg["Sell price €"]= agg["total_cost"].map(lambda x: fmt(x))
agg["Mass (kg)"]   = agg["_line_mass"].map(lambda x: f"{x:,.0f}")
agg["Share %"]     = (agg["total_cost"] / work["total_cost"].sum() * 100).map(lambda x: f"{x:.1f}%")

st.dataframe(
    agg[["Subsystem", "Purchase €", "Machine €", "Labour €", "Overhead €",
         "Your cost €", "Margin €", "Margin %", "Sell price €", "Mass (kg)", "Share %"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── Full line detail ──────────────────────────────────────────────────────────
with st.expander("Full BOM line detail", expanded=False):
    line_cols = {
        "line_id":       "Line ID",
        "part_name":     "Component",
        "material_id":   "Material",
        "qty":           "Qty",
        "mass_kg":       "Mass kg",
        "yield_factor":  "Yield",
        "material_cost": "Purchase €",
        "process_route": "Process",
        "runtime_h":     "Run h",
        "setup_h":       "Setup h",
        "machine_cost":  "Machine €",
        "labour_cost":   "Labour €",
        "overhead":      "Overhead €",
        "base_cost":     "Your cost €",
        "margin":        "Margin €",
        "total_cost":    "Sell price €",
    }
    lt = work[[c for c in line_cols if c in work.columns]].copy()
    lt.rename(columns=line_cols, inplace=True)
    for col in ["Purchase €", "Machine €", "Labour €", "Overhead €",
                "Your cost €", "Margin €", "Sell price €"]:
        if col in lt.columns:
            lt[col] = lt[col].map(lambda x: fmt(x, 2))
    st.dataframe(lt, use_container_width=True, hide_index=True)

st.divider()

# ── Downloads ─────────────────────────────────────────────────────────────────
st.subheader("Downloads")

internal_cols = ["line_id", "part_name", "material_id", "qty", "mass_kg",
                 "yield_factor", "price_eur_per_kg", "material_cost",
                 "process_route", "runtime_h", "setup_h",
                 "machine_cost", "labour_cost", "overhead_pct", "overhead",
                 "base_cost", "margin_pct", "margin", "total_cost"]
internal_df = work[[c for c in internal_cols if c in work.columns]].copy()

customer_agg = (
    work.groupby("subsystem")[["total_cost"]]
    .sum()
    .reset_index()
)
customer_agg["Description"] = customer_agg["subsystem"].map(
    lambda p: WATERJET_SUBSYSTEMS.get(p, {}).get("name", p)
)
customer_agg["Selling price (EUR)"] = customer_agg["total_cost"].map(lambda x: round(x, 2))
customer_agg = customer_agg[["Description", "Selling price (EUR)"]].copy()

if cert_surcharge > 0:
    cert_row = pd.DataFrame([{
        "Description": f"Classification surcharge ({cert_class})",
        "Selling price (EUR)": round(cert_surcharge, 2),
    }])
    customer_agg = pd.concat([customer_agg, cert_row], ignore_index=True)

header_rows = pd.DataFrame([
    {"Description": "Quote number",        "Selling price (EUR)": quote_number},
    {"Description": "Date",                "Selling price (EUR)": str(quote_date)},
    {"Description": "Customer",            "Selling price (EUR)": customer_name},
    {"Description": "Project",             "Selling price (EUR)": project_label},
    {"Description": "Valid (days)",        "Selling price (EUR)": str(validity_days)},
    {"Description": "Classification",      "Selling price (EUR)": cert_class},
    {"Description": "Production run (units)", "Selling price (EUR)": str(int(num_units))},
    {"Description": "---",                 "Selling price (EUR)": "---"},
])
customer_sheet = pd.concat([header_rows, customer_agg], ignore_index=True)
total_row = pd.DataFrame([{"Description": "TOTAL", "Selling price (EUR)": round(total_sell, 2)}])
customer_sheet = pd.concat([customer_sheet, total_row], ignore_index=True)

dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        "⬇️ Internal cost detail (CSV)",
        data=internal_df.to_csv(index=False),
        file_name=f"{quote_number}_internal_cost.csv",
        mime="text/csv",
        use_container_width=True,
        help="Full cost breakdown — keep confidential.",
    )
with dl2:
    st.download_button(
        "⬇️ Customer quote sheet (CSV)",
        data=customer_sheet.to_csv(index=False),
        file_name=f"{quote_number}_quote.csv",
        mime="text/csv",
        use_container_width=True,
        help="Selling prices only — safe to share with customer.",
    )
