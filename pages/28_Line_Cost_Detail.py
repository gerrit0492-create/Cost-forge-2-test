from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes


st.set_page_config(page_title="Line Cost Detail", layout="wide", page_icon="🔍")
home_button()
st.title("🔍 Line Cost Detail")
st.caption("Full cost breakdown per BOM line — material purchase, machine time, labour, overhead, margin.")


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
        st.error(f"Could not load BOM data: {exc}")
        return None


def _subsystem_prefix(line_id: str) -> str:
    upper = str(line_id).upper()
    for prefix in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
        if upper.startswith(prefix):
            return prefix
    return "?"


def _error_check(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    zero_qty = df[pd.to_numeric(df["qty"], errors="coerce").fillna(0) == 0]["line_id"].tolist()
    if zero_qty:
        issues.append(f"Zero qty on lines: {', '.join(str(x) for x in zero_qty)}")

    no_price = df[df["price_eur_per_kg"].isna() | (df["price_eur_per_kg"] == 0)]
    if len(no_price):
        issues.append(f"Missing material price on {len(no_price)} line(s): "
                      + ", ".join(no_price["line_id"].astype(str).tolist()))

    zero_mass_non_test = df[
        (df["mass_kg"].fillna(0) == 0) &
        (~df["process_route"].isin(["FINAL_ASSEMBLY", "NDT_INSPECT", "PRESSURE_TEST", "DYN_BALANCE"]))
    ]
    if len(zero_mass_non_test):
        issues.append(f"Zero mass on non-test lines: "
                      + ", ".join(zero_mass_non_test["line_id"].astype(str).tolist()))

    high_oh = df[df["overhead_pct"] > 0.40]
    if len(high_oh):
        issues.append(f"Overhead > 40% on: {', '.join(high_oh['line_id'].astype(str).tolist())}")

    high_margin = df[df["margin_pct"] > 0.30]
    if len(high_margin):
        issues.append(f"Margin > 30% on: {', '.join(high_margin['line_id'].astype(str).tolist())}")

    return issues


df = _load()
if df is None:
    st.stop()

df["subsystem"] = df["line_id"].apply(_subsystem_prefix)

# ── Error checks ──────────────────────────────────────────────────────────────
issues = _error_check(df)
if issues:
    with st.expander(f"⚠️ {len(issues)} BOM issue(s) found", expanded=True):
        for issue in issues:
            st.warning(issue)
else:
    st.success("✅ No BOM errors detected.")

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
col_sub, col_search, col_sort = st.columns([2, 3, 2])

subsystem_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}
all_label = "All subsystems"
sub_options = [all_label] + [subsystem_names[p] for p in WATERJET_SUBSYSTEMS if p in df["subsystem"].values]
chosen_sub = col_sub.selectbox("Subsystem", sub_options)

search_term = col_search.text_input("Search line ID / description", placeholder="e.g. I01 or impeller")

sort_col = col_sort.selectbox("Sort by", ["line_id", "total_cost", "material_cost", "process_cost", "overhead"])

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

view = view.sort_values(sort_col, ascending=(sort_col == "line_id"))

st.caption(f"Showing {len(view)} of {len(df)} BOM lines")

# ── KPI summary of filtered view ─────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Material (purchase)", f"€ {view['material_cost'].sum():,.0f}")
k2.metric("Machine cost",        f"€ {view['machine_cost'].sum():,.0f}")
k3.metric("Labour cost",         f"€ {view['labour_cost'].sum():,.0f}")
k4.metric("Overhead",            f"€ {view['overhead'].sum():,.0f}")
k5.metric("Your cost",           f"€ {view['base_cost'].sum():,.0f}")
k6.metric("Sell price (incl. margin)", f"€ {view['total_cost'].sum():,.0f}")

st.divider()

# ── Per-line detail table ─────────────────────────────────────────────────────
display_cols = {
    "line_id":        "Line ID",
    "part_name":      "Component",
    "material_id":    "Material",
    "qty":            "Qty",
    "mass_kg":        "Mass (kg)",
    "price_eur_per_kg": "€/kg",
    "material_cost":  "Purchase €",
    "process_route":  "Process",
    "runtime_h":      "Runtime h",
    "machine_cost":   "Machine €",
    "labour_cost":    "Labour €",
    "process_cost":   "Process €",
    "overhead_pct":   "OH%",
    "overhead":       "Overhead €",
    "base_cost":      "Your cost €",
    "margin_pct":     "Margin%",
    "margin":         "Margin €",
    "total_cost":     "Sell price €",
}
table = view[[c for c in display_cols if c in view.columns]].copy()
table.rename(columns=display_cols, inplace=True)

for col in ["Purchase €", "Machine €", "Labour €", "Process €", "Overhead €",
            "Your cost €", "Margin €", "Sell price €"]:
    if col in table.columns:
        table[col] = table[col].map(lambda x: f"€ {x:,.2f}" if pd.notna(x) else "—")

for col in ["OH%", "Margin%"]:
    if col in table.columns:
        table[col] = table[col].map(lambda x: f"{x*100:.0f}%" if pd.notna(x) else "—")

st.dataframe(table, use_container_width=True, hide_index=True)

# ── Per-subsystem totals ──────────────────────────────────────────────────────
st.divider()
st.subheader("Subsystem totals")

agg = (
    df.groupby("subsystem")[["material_cost", "machine_cost", "labour_cost",
                              "overhead", "base_cost", "margin", "total_cost"]]
    .sum()
    .reset_index()
)
agg["name"] = agg["subsystem"].map(lambda p: subsystem_names.get(p, p))
agg["OH%"]  = (agg["overhead"] / agg["base_cost"] * 100).map(lambda x: f"{x:.1f}%")
agg["Margin%"] = (agg["margin"] / agg["base_cost"] * 100).map(lambda x: f"{x:.1f}%")
agg["Share%"]  = (agg["total_cost"] / df["total_cost"].sum() * 100).map(lambda x: f"{x:.1f}%")

agg_display = agg.rename(columns={
    "name": "Subsystem",
    "material_cost": "Purchase €",
    "machine_cost":  "Machine €",
    "labour_cost":   "Labour €",
    "overhead":      "Overhead €",
    "base_cost":     "Your cost €",
    "margin":        "Margin €",
    "total_cost":    "Sell price €",
})
for col in ["Purchase €", "Machine €", "Labour €", "Overhead €",
            "Your cost €", "Margin €", "Sell price €"]:
    agg_display[col] = agg_display[col].map(lambda x: f"€ {x:,.0f}")

st.dataframe(
    agg_display[["Subsystem", "Purchase €", "Machine €", "Labour €",
                 "Overhead €", "Your cost €", "OH%", "Margin €", "Margin%",
                 "Sell price €", "Share%"]],
    use_container_width=True,
    hide_index=True,
)

# ── Download ──────────────────────────────────────────────────────────────────
st.divider()
csv_detail = view[[c for c in display_cols if c in view.columns]].to_csv(index=False)
st.download_button(
    "⬇️ Download detail CSV",
    data=csv_detail,
    file_name="line_cost_detail.csv",
    mime="text/csv",
    use_container_width=True,
)
