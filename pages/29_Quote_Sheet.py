from __future__ import annotations

import datetime
import io

import pandas as pd
import streamlit as st

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_name
from utils.quotes import apply_best_quotes


st.set_page_config(page_title="Quote Sheet", layout="wide", page_icon="🧾")
home_button()
st.title("🧾 Quote Sheet")
st.caption("Internal cost + margin vs customer selling price — per subsystem and per line.")


@st.cache_data(ttl=30)
def _load() -> pd.DataFrame | None:
    try:
        mats = apply_best_quotes(load_materials(), load_quotes())
        df = compute_costs(mats, load_processes(), load_bom())
        qty = pd.to_numeric(df["qty"], errors="coerce").fillna(1)
        df["machine_cost"] = qty * df["runtime_h"] * df["machine_rate_eur_h"]
        df["labour_cost"]  = qty * df["runtime_h"] * df["labor_rate_eur_h"]
        return df
    except Exception as exc:
        st.error(f"Could not load cost data: {exc}")
        return None


def _subsystem_prefix(line_id: str) -> str:
    upper = str(line_id).upper()
    for prefix in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
        if upper.startswith(prefix):
            return prefix
    return "?"


df = _load()
if df is None:
    st.stop()

df["subsystem"] = df["line_id"].apply(_subsystem_prefix)
subsystem_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}

# ── Quote header ──────────────────────────────────────────────────────────────
st.subheader("Quote header")
h1, h2, h3, h4 = st.columns(4)
quote_number  = h1.text_input("Quote number", value="QT-2026-001")
quote_date    = h2.date_input("Date", value=datetime.date.today())
customer_name = h3.text_input("Customer", value="")
validity_days = h4.number_input("Valid (days)", min_value=1, max_value=180, value=30)
project_label = st.text_input("Project / description", value=load_project_name())

st.divider()

# ── Margin override ───────────────────────────────────────────────────────────
st.subheader("Margin settings")
use_override = st.toggle("Override BOM margin with a single global margin")
global_margin_pct: float | None = None
if use_override:
    global_margin_pct = st.slider(
        "Global margin %", min_value=0, max_value=50, value=18, step=1
    ) / 100.0
    st.info(f"All lines will use **{global_margin_pct*100:.0f}%** margin for this quote.")

# Build working copy with optional margin override
work = df.copy()
if global_margin_pct is not None:
    work["margin_pct"]  = global_margin_pct
    work["margin"]      = work["base_cost"] * global_margin_pct
    work["total_cost"]  = work["base_cost"] + work["margin"]

st.divider()

# ── Top-level KPIs ────────────────────────────────────────────────────────────
total_mat   = work["material_cost"].sum()
total_mach  = work["machine_cost"].sum()
total_lab   = work["labour_cost"].sum()
total_oh    = work["overhead"].sum()
total_base  = work["base_cost"].sum()
total_marg  = work["margin"].sum()
total_sell  = work["total_cost"].sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Material (purchase)", f"€ {total_mat:,.0f}")
k2.metric("Machine + Labour",    f"€ {total_mach + total_lab:,.0f}")
k3.metric("Overhead",            f"€ {total_oh:,.0f}")
k4.metric("Your cost",           f"€ {total_base:,.0f}", help="Material + process + overhead")
k5.metric("Selling price",       f"€ {total_sell:,.0f}",
          delta=f"Margin € {total_marg:,.0f} ({total_marg/total_base*100:.1f}%)")

st.divider()

# ── Per-subsystem summary ─────────────────────────────────────────────────────
st.subheader("Subsystem summary")

agg = (
    work.groupby("subsystem")[
        ["material_cost", "machine_cost", "labour_cost",
         "overhead", "base_cost", "margin", "total_cost"]
    ]
    .sum()
    .reset_index()
)
agg["Subsystem"]   = agg["subsystem"].map(lambda p: subsystem_names.get(p, p))
agg["Purchase €"]  = agg["material_cost"].map(lambda x: f"€ {x:,.0f}")
agg["Machine €"]   = agg["machine_cost"].map(lambda x: f"€ {x:,.0f}")
agg["Labour €"]    = agg["labour_cost"].map(lambda x: f"€ {x:,.0f}")
agg["Overhead €"]  = agg["overhead"].map(lambda x: f"€ {x:,.0f}")
agg["Your cost €"] = agg["base_cost"].map(lambda x: f"€ {x:,.0f}")
agg["Margin €"]    = agg["margin"].map(lambda x: f"€ {x:,.0f}")
agg["Margin %"]    = (agg["margin"] / agg["base_cost"] * 100).map(lambda x: f"{x:.1f}%")
agg["Sell price €"]= agg["total_cost"].map(lambda x: f"€ {x:,.0f}")
agg["Share %"]     = (agg["total_cost"] / total_sell * 100).map(lambda x: f"{x:.1f}%")

st.dataframe(
    agg[["Subsystem", "Purchase €", "Machine €", "Labour €", "Overhead €",
         "Your cost €", "Margin €", "Margin %", "Sell price €", "Share %"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── Full line detail ──────────────────────────────────────────────────────────
with st.expander("Full BOM line detail", expanded=False):
    line_cols = {
        "line_id":          "Line ID",
        "material_id":      "Material",
        "qty":              "Qty",
        "mass_kg":          "Mass kg",
        "material_cost":    "Purchase €",
        "process_route":    "Process",
        "runtime_h":        "h",
        "machine_cost":     "Machine €",
        "labour_cost":      "Labour €",
        "overhead":         "Overhead €",
        "base_cost":        "Your cost €",
        "margin":           "Margin €",
        "total_cost":       "Sell price €",
    }
    lt = work[[c for c in line_cols if c in work.columns]].copy()
    lt.rename(columns=line_cols, inplace=True)
    for col in ["Purchase €", "Machine €", "Labour €", "Overhead €",
                "Your cost €", "Margin €", "Sell price €"]:
        if col in lt.columns:
            lt[col] = lt[col].map(lambda x: f"€ {x:,.2f}")
    st.dataframe(lt, use_container_width=True, hide_index=True)

st.divider()

# ── Downloads ─────────────────────────────────────────────────────────────────
st.subheader("Downloads")

# Internal CSV — full detail
internal_cols = ["line_id", "material_id", "qty", "mass_kg", "price_eur_per_kg",
                 "material_cost", "process_route", "runtime_h",
                 "machine_cost", "labour_cost", "overhead_pct", "overhead",
                 "base_cost", "margin_pct", "margin", "total_cost"]
internal_df = work[[c for c in internal_cols if c in work.columns]].copy()

# Customer CSV — subsystem totals, selling price only (no cost detail)
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

# Header rows for customer sheet
header_rows = pd.DataFrame([
    {"Description": "Quote number",  "Selling price (EUR)": quote_number},
    {"Description": "Date",          "Selling price (EUR)": str(quote_date)},
    {"Description": "Customer",      "Selling price (EUR)": customer_name},
    {"Description": "Project",       "Selling price (EUR)": project_label},
    {"Description": "Valid (days)",  "Selling price (EUR)": str(validity_days)},
    {"Description": "---",           "Selling price (EUR)": "---"},
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
