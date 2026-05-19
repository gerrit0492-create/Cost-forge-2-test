from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.currency import fmt, fmt_delta
from utils.io import load_bom, load_materials, load_processes, load_quotes, save_sheet, df_to_excel_bytes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes

st.set_page_config(page_title="Pre / Post", layout="wide", page_icon="📊")
home_button()
st.title("📊 Pre / Post — Budget vs Actuals")
st.caption("Compare estimated (budget) costs against recorded actuals, line by line and per subsystem.")

if st.button("🔄 Refresh", help="Clear cache and reload"):
    st.cache_data.clear()
    st.rerun()

STATUS_COLOURS = {
    "complete":     "🟢",
    "in_progress":  "🟡",
    "not_started":  "⚪",
    "cancelled":    "🔴",
}

# ── Load budget ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load_budget() -> pd.DataFrame:
    mats = apply_best_quotes(load_materials(), load_quotes())
    return compute_costs(mats, load_processes(), load_bom())


df_budget = _load_budget()

# ── Load / upload actuals ─────────────────────────────────────────────────────
st.subheader("Actuals data")
col_src, col_up = st.columns([3, 2])

with col_src:
    src = st.radio(
        "Actuals source",
        ["Use saved actuals (cost_forge.xlsx)", "Upload actuals CSV"],
        horizontal=True,
        label_visibility="collapsed",
    )

uploaded = None
if src == "Upload actuals CSV":
    with col_up:
        uploaded = st.file_uploader("Upload actuals CSV", type="csv", label_visibility="collapsed")

@st.cache_data(ttl=30)
def _load_saved_actuals() -> pd.DataFrame:
    from utils.io import load_actuals
    return load_actuals()


if uploaded:
    raw = pd.read_csv(uploaded)
    for c in ["actual_material_cost", "actual_process_cost", "actual_total_cost"]:
        if c in raw.columns:
            raw[c] = pd.to_numeric(raw[c], errors="coerce")
    df_actuals_raw = raw
else:
    df_actuals_raw = _load_saved_actuals()

# ── Editable actuals table ────────────────────────────────────────────────────
st.subheader("Enter / edit actuals")
st.caption("Fill in what was actually spent per line. Leave blank if not yet incurred.")

# Build editable frame: merge budget line names with actuals
edit_base = df_budget[["line_id", "part_name", "material_cost", "process_cost", "total_cost"]].copy()
edit_base.rename(columns={
    "material_cost": "budget_material",
    "process_cost":  "budget_process",
    "total_cost":    "budget_total",
}, inplace=True)

if not df_actuals_raw.empty and "line_id" in df_actuals_raw.columns:
    edit_base = edit_base.merge(
        df_actuals_raw[["line_id",
                        "actual_material_cost",
                        "actual_process_cost",
                        "actual_total_cost",
                        "notes",
                        "status"]],
        on="line_id", how="left",
    )
else:
    edit_base["actual_material_cost"] = None
    edit_base["actual_process_cost"]  = None
    edit_base["actual_total_cost"]    = None
    edit_base["notes"]                = ""
    edit_base["status"]               = "not_started"

edit_base["status"] = edit_base["status"].fillna("not_started")
edit_base["notes"]  = edit_base["notes"].fillna("")

edited = st.data_editor(
    edit_base,
    column_config={
        "line_id":               st.column_config.TextColumn("Line", disabled=True, width="small"),
        "part_name":             st.column_config.TextColumn("Component", disabled=True, width="large"),
        "budget_material":       st.column_config.NumberColumn("Budget mat €", disabled=True, format="%.0f"),
        "budget_process":        st.column_config.NumberColumn("Budget proc €", disabled=True, format="%.0f"),
        "budget_total":          st.column_config.NumberColumn("Budget total €", disabled=True, format="%.0f"),
        "actual_material_cost":  st.column_config.NumberColumn("Actual mat €",  format="%.0f"),
        "actual_process_cost":   st.column_config.NumberColumn("Actual proc €", format="%.0f"),
        "actual_total_cost":     st.column_config.NumberColumn("Actual total €", format="%.0f"),
        "notes":                 st.column_config.TextColumn("Notes"),
        "status":                st.column_config.SelectboxColumn(
            "Status",
            options=list(STATUS_COLOURS.keys()),
            width="small",
        ),
    },
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="actuals_editor",
)

# Save button
if st.button("💾 Save actuals to workbook"):
    save_cols = ["line_id", "actual_material_cost", "actual_process_cost",
                 "actual_total_cost", "notes", "status"]
    save_sheet(edited[save_cols], "actuals")
    st.success("Actuals saved to cost_forge.xlsx.")
    st.cache_data.clear()

st.divider()

# ── Merge budget + actuals for analysis ───────────────────────────────────────
df = edited.copy()

# Where actual_total_cost is blank, fall back to mat+proc if both entered
mask_total_blank = df["actual_total_cost"].isna()
mask_parts_filled = df["actual_material_cost"].notna() & df["actual_process_cost"].notna()
df.loc[mask_total_blank & mask_parts_filled, "actual_total_cost"] = (
    df["actual_material_cost"] + df["actual_process_cost"]
)

# Lines with any actual data entered
has_actuals = df["actual_total_cost"].notna()
n_total   = len(df)
n_actual  = has_actuals.sum()
n_complete = (df["status"] == "complete").sum()

budget_total  = df["budget_total"].sum()
actual_total  = df.loc[has_actuals, "actual_total_cost"].sum()
variance_abs  = actual_total - df.loc[has_actuals, "budget_total"].sum()
# Full-scope variance (actuals so far vs same-scope budget)
budget_scope  = df.loc[has_actuals, "budget_total"].sum()

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.subheader("Summary")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Budget (full scope)", fmt(budget_total))
k2.metric("Budget (actuals scope)", fmt(budget_scope))
k3.metric("Actuals to date", fmt(actual_total))
k4.metric(
    "Variance (actuals scope)",
    fmt_delta(variance_abs),
    delta=f"{variance_abs / budget_scope * 100:+.1f}%" if budget_scope else None,
    delta_color="inverse",
)
k5.metric("Lines with actuals", f"{n_actual} / {n_total}")
k6.metric("Lines complete", f"{n_complete} / {n_total}")

if n_actual == 0:
    st.info("No actuals entered yet. Fill in the table above to see the comparison.")
    st.stop()

st.divider()

# ── Per-subsystem comparison ──────────────────────────────────────────────────
st.subheader("Subsystem comparison")

def _prefix(lid: str) -> str:
    u = str(lid).upper()
    for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
        if u.startswith(p):
            return p
    return "?"

df["subsystem"] = df["line_id"].apply(_prefix)
subsystem_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}

grp = (
    df.groupby("subsystem")
    .agg(
        budget=("budget_total", "sum"),
        actual=("actual_total_cost", lambda s: s.dropna().sum()),
        n_lines=("line_id", "count"),
        n_actual=("actual_total_cost", lambda s: s.notna().sum()),
    )
    .reset_index()
)
grp["Subsystem"]   = grp["subsystem"].map(lambda p: subsystem_names.get(p, p))
grp["Budget €"]    = grp["budget"].map(lambda x: fmt(x))
grp["Actual €"]    = grp.apply(
    lambda r: fmt(r["actual"]) if r["n_actual"] > 0 else "—", axis=1
)
grp["Variance €"]  = grp.apply(
    lambda r: fmt_delta(r["actual"] - r["budget"]) if r["n_actual"] > 0 else "—", axis=1
)
grp["Var %"]       = grp.apply(
    lambda r: f"{(r['actual'] - r['budget']) / r['budget'] * 100:+.1f}%"
              if r["n_actual"] > 0 and r["budget"] else "—", axis=1
)
grp["Coverage"]    = grp.apply(lambda r: f"{r['n_actual']}/{r['n_lines']} lines", axis=1)

# Side-by-side bar chart
chart_df = grp[grp["n_actual"] > 0].set_index("Subsystem")[["budget", "actual"]].rename(
    columns={"budget": "Budget", "actual": "Actual"}
)
if not chart_df.empty:
    col_c, col_t = st.columns([2, 1])
    with col_c:
        st.bar_chart(chart_df)
    with col_t:
        st.dataframe(
            grp[["Subsystem", "Budget €", "Actual €", "Variance €", "Var %", "Coverage"]],
            use_container_width=True, hide_index=True,
        )

st.divider()

# ── Line-by-line detail ───────────────────────────────────────────────────────
st.subheader("Line-by-line detail")

detail = df[has_actuals].copy()
detail["Variance €"] = detail["actual_total_cost"] - detail["budget_total"]
detail["Var %"] = (
    detail["Variance €"] / detail["budget_total"].replace(0, float("nan")) * 100
).round(1)

detail_disp = detail[[
    "line_id", "part_name", "status",
    "budget_total", "actual_total_cost", "Variance €", "Var %", "notes",
]].copy()
detail_disp.rename(columns={
    "line_id": "Line", "part_name": "Component", "status": "Status",
    "budget_total": "Budget €", "actual_total_cost": "Actual €",
    "notes": "Notes",
}, inplace=True)
detail_disp["Status"]    = detail_disp["Status"].map(lambda s: f"{STATUS_COLOURS.get(s, '')} {s}")
detail_disp["Budget €"]  = detail_disp["Budget €"].map(lambda x: fmt(x, 2))
detail_disp["Actual €"]  = detail_disp["Actual €"].map(lambda x: fmt(x, 2))
detail_disp["Variance €"]= detail_disp["Variance €"].map(lambda x: fmt_delta(x, 2))
detail_disp["Var %"]     = detail_disp["Var %"].map(
    lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
)

st.dataframe(detail_disp, use_container_width=True, hide_index=True)

st.divider()

# ── Downloads ─────────────────────────────────────────────────────────────────
st.subheader("Downloads")
dl1, dl2 = st.columns(2)

template_cols = ["line_id", "actual_material_cost", "actual_process_cost",
                 "actual_total_cost", "notes", "status"]
template_df = df[["line_id", "part_name"]].copy()
template_df["actual_material_cost"] = ""
template_df["actual_process_cost"]  = ""
template_df["actual_total_cost"]    = ""
template_df["notes"]                = ""
template_df["status"]               = "not_started"

with dl1:
    st.download_button(
        "⬇️ Download actuals template (Excel)",
        data=df_to_excel_bytes(template_df.drop(columns=["part_name"]), "Actuals"),
        file_name="actuals_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Fill in actuals and upload back above.",
    )

report = df.copy()
report["variance"] = report["actual_total_cost"] - report["budget_total"]
report["var_pct"]  = (
    report["variance"] / report["budget_total"].replace(0, float("nan")) * 100
).round(1)
report_cols = ["line_id", "part_name", "status", "budget_total",
               "actual_total_cost", "variance", "var_pct", "notes"]

with dl2:
    st.download_button(
        "⬇️ Download pre/post report (Excel)",
        data=df_to_excel_bytes(report[report_cols], "Pre-Post"),
        file_name="pre_post_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Full budget vs actuals comparison.",
    )
