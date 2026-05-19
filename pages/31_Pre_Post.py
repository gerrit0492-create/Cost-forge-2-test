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
valid_line_ids = set(df_budget["line_id"].astype(str))

# ── Load / upload actuals ─────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load_saved_actuals() -> pd.DataFrame:
    from utils.io import load_actuals
    return load_actuals()


# ── SAP Import ────────────────────────────────────────────────────────────────
st.subheader("Actuals source")
tab_saved, tab_sap, tab_upload = st.tabs([
    "💾 Saved actuals",
    "🔵 Import from SAP",
    "📂 Upload file",
])

df_actuals_raw: pd.DataFrame = pd.DataFrame()

with tab_saved:
    df_actuals_raw = _load_saved_actuals()
    if df_actuals_raw.empty or df_actuals_raw["actual_total_cost"].isna().all():
        st.info("No actuals saved yet. Enter them in the table below or import from SAP.")
    else:
        n_filled = df_actuals_raw["actual_total_cost"].notna().sum()
        st.success(f"{n_filled} lines with actuals loaded from cost_forge.xlsx.")

with tab_sap:
    st.markdown("#### How to export from SAP")
    with st.expander("Step-by-step export guide", expanded=False):
        st.markdown("""
**Option A — S_ALR_87013533 (Plan vs Actual by project)**
1. SAP GUI → transaction `S_ALR_87013533`
2. Enter your Project / WBS selection, fiscal year, period
3. Execute (F8)
4. Toolbar → **List → Export → Spreadsheet** (or the Excel icon)
5. Save as `.xlsx`
6. Upload below — the report has columns like *WBS Element*, *Plan*, *Actual*, *Variance*

**Option B — CJI3 (Actual cost line items)**
1. SAP GUI → transaction `CJI3`
2. Enter Project number and posting date range
3. Execute (F8)
4. Toolbar → **List → Export → Spreadsheet**
5. Save as `.xlsx`
6. Upload below — one row per posting with *WBS Element* and *Value*

**Option C — KSB1 (Cost centre line items)**
1. SAP GUI → transaction `KSB1`
2. Enter Cost Centre and period
3. Execute → Export to Excel
4. Upload below

**Tip:** your WBS elements should contain the BOM line IDs (e.g. `MWJ720.I01`, `PRJ-001/H03`).
The importer will extract the line ID suffix automatically.
        """)

    st.markdown("#### Upload SAP export")
    sap_file = st.file_uploader(
        "SAP Excel or CSV export",
        type=["xlsx", "csv"],
        key="sap_uploader",
        label_visibility="collapsed",
    )

    if sap_file:
        try:
            df_sap = pd.read_excel(sap_file) if sap_file.name.endswith(".xlsx") else pd.read_csv(sap_file)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            df_sap = None

        if df_sap is not None and not df_sap.empty:
            # Strip whitespace from column names
            df_sap.columns = df_sap.columns.str.strip()

            st.markdown("**Preview (first 5 rows)**")
            st.dataframe(df_sap.head(), use_container_width=True, hide_index=True)

            cols = ["— select —"] + df_sap.columns.tolist()

            st.markdown("#### Map SAP columns to Cost Forge fields")
            mc1, mc2, mc3 = st.columns(3)
            id_col     = mc1.selectbox("WBS / identifier column", cols, key="sap_id_col")
            actual_col = mc2.selectbox("Actual cost column", cols, key="sap_act_col")
            mat_col    = mc3.selectbox("Material cost column (optional)", cols, key="sap_mat_col")

            if id_col != "— select —" and actual_col != "— select —":
                # Auto-extract BOM line_id from the WBS element value
                # Try to match the last dot/slash/dash separated segment to a known line_id
                import re

                def _extract_line_id(val: str) -> str | None:
                    val = str(val).strip().upper()
                    # Try exact match first
                    if val in valid_line_ids:
                        return val
                    # Try segments split by . / - _
                    for seg in re.split(r"[.\-/_]", val):
                        if seg in valid_line_ids:
                            return seg
                    # Try trailing alphanumeric token
                    m = re.search(r"([A-Z]{1,3}\d{2,3})$", val)
                    if m and m.group(1) in valid_line_ids:
                        return m.group(1)
                    return None

                mapped = df_sap[[id_col, actual_col]].copy()
                if mat_col != "— select —":
                    mapped["_mat"] = pd.to_numeric(df_sap[mat_col], errors="coerce").fillna(0)
                else:
                    mapped["_mat"] = 0.0

                mapped["line_id"] = mapped[id_col].apply(_extract_line_id)
                mapped["actual_total_cost"] = pd.to_numeric(mapped[actual_col], errors="coerce")

                matched   = mapped[mapped["line_id"].notna() & mapped["actual_total_cost"].notna()]
                unmatched = mapped[mapped["line_id"].isna()]

                st.markdown(f"**Matched:** {len(matched)} lines &nbsp;|&nbsp; **Unmatched:** {len(unmatched)} rows")

                if not matched.empty:
                    # Group by line_id (sum if multiple postings per line)
                    grp_sap = (
                        matched.groupby("line_id")
                        .agg(
                            actual_total_cost=("actual_total_cost", "sum"),
                            actual_material_cost=("_mat", "sum"),
                        )
                        .reset_index()
                    )
                    grp_sap["actual_process_cost"] = (
                        grp_sap["actual_total_cost"] - grp_sap["actual_material_cost"]
                    ).clip(lower=0)
                    grp_sap["notes"]  = f"Imported from SAP: {sap_file.name}"
                    grp_sap["status"] = "in_progress"

                    st.dataframe(
                        grp_sap[["line_id", "actual_total_cost", "actual_material_cost", "actual_process_cost"]],
                        use_container_width=True, hide_index=True,
                    )

                if unmatched[id_col].notna().any():
                    with st.expander(f"Unmatched rows ({len(unmatched)}) — manual mapping"):
                        st.caption(
                            "These SAP identifiers could not be matched to a BOM line ID. "
                            "Assign them manually below."
                        )
                        line_options = ["— skip —"] + sorted(valid_line_ids)
                        manual_rows = []
                        for _, row in unmatched.head(30).iterrows():
                            c_id, c_amt, c_map = st.columns([3, 2, 2])
                            c_id.text(str(row[id_col]))
                            c_amt.text(str(row[actual_col]))
                            chosen = c_map.selectbox(
                                "Map to line",
                                line_options,
                                key=f"manual_map_{row[id_col]}",
                                label_visibility="collapsed",
                            )
                            if chosen != "— skip —":
                                manual_rows.append({
                                    "line_id": chosen,
                                    "actual_total_cost": pd.to_numeric(row[actual_col], errors="coerce"),
                                    "actual_material_cost": 0.0,
                                    "actual_process_cost": 0.0,
                                    "notes": f"Manually mapped from {row[id_col]}",
                                    "status": "in_progress",
                                })
                        if manual_rows:
                            grp_sap = pd.concat(
                                [grp_sap, pd.DataFrame(manual_rows)], ignore_index=True
                            )

                if not matched.empty and st.button("✅ Apply SAP actuals", type="primary"):
                    st.session_state["sap_actuals"] = grp_sap
                    st.success(f"Applied {len(grp_sap)} lines from SAP. Scroll down to review and save.")
                    st.cache_data.clear()

with tab_upload:
    uploaded = st.file_uploader(
        "Upload actuals Excel or CSV",
        type=["xlsx", "csv"],
        key="manual_uploader",
        label_visibility="collapsed",
    )
    if uploaded:
        try:
            raw = pd.read_excel(uploaded) if uploaded.name.endswith(".xlsx") else pd.read_csv(uploaded)
            for c in ["actual_material_cost", "actual_process_cost", "actual_total_cost"]:
                if c in raw.columns:
                    raw[c] = pd.to_numeric(raw[c], errors="coerce")
            df_actuals_raw = raw
            st.success(f"Loaded {len(raw)} rows from {uploaded.name}.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

# Merge SAP actuals into df_actuals_raw if applied
if "sap_actuals" in st.session_state:
    sap_act = st.session_state["sap_actuals"]
    if df_actuals_raw.empty or "line_id" not in df_actuals_raw.columns:
        df_actuals_raw = sap_act
    else:
        # SAP actuals override saved actuals for matched lines
        df_actuals_raw = df_actuals_raw[
            ~df_actuals_raw["line_id"].isin(sap_act["line_id"])
        ]
        df_actuals_raw = pd.concat([df_actuals_raw, sap_act], ignore_index=True)

st.divider()

# ── Editable actuals table ────────────────────────────────────────────────────
st.subheader("Enter / edit actuals")
st.caption("Fill in what was actually spent per line. Leave blank if not yet incurred.")

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

sa1, sa2 = st.columns([1, 5])
if sa1.button("💾 Save actuals to workbook"):
    save_cols = ["line_id", "actual_material_cost", "actual_process_cost",
                 "actual_total_cost", "notes", "status"]
    save_sheet(edited[save_cols], "actuals")
    st.session_state.pop("sap_actuals", None)
    st.success("Actuals saved to cost_forge.xlsx.")
    st.cache_data.clear()

st.divider()

# ── Merge budget + actuals for analysis ───────────────────────────────────────
df = edited.copy()

mask_total_blank  = df["actual_total_cost"].isna()
mask_parts_filled = df["actual_material_cost"].notna() & df["actual_process_cost"].notna()
df.loc[mask_total_blank & mask_parts_filled, "actual_total_cost"] = (
    df["actual_material_cost"] + df["actual_process_cost"]
)

has_actuals = df["actual_total_cost"].notna()
n_total     = len(df)
n_actual    = has_actuals.sum()
n_complete  = (df["status"] == "complete").sum()

budget_total = df["budget_total"].sum()
actual_total = df.loc[has_actuals, "actual_total_cost"].sum()
budget_scope = df.loc[has_actuals, "budget_total"].sum()
variance_abs = actual_total - budget_scope

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
    st.info("No actuals entered yet. Fill in the table above or import from SAP.")
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
grp["Subsystem"]  = grp["subsystem"].map(lambda p: subsystem_names.get(p, p))
grp["Budget €"]   = grp["budget"].map(lambda x: fmt(x))
grp["Actual €"]   = grp.apply(lambda r: fmt(r["actual"]) if r["n_actual"] > 0 else "—", axis=1)
grp["Variance €"] = grp.apply(
    lambda r: fmt_delta(r["actual"] - r["budget"]) if r["n_actual"] > 0 else "—", axis=1
)
grp["Var %"]      = grp.apply(
    lambda r: f"{(r['actual'] - r['budget']) / r['budget'] * 100:+.1f}%"
              if r["n_actual"] > 0 and r["budget"] else "—", axis=1
)
grp["Coverage"]   = grp.apply(lambda r: f"{r['n_actual']}/{r['n_lines']} lines", axis=1)

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
    "budget_total": "Budget €", "actual_total_cost": "Actual €", "notes": "Notes",
}, inplace=True)
detail_disp["Status"]     = detail_disp["Status"].map(lambda s: f"{STATUS_COLOURS.get(s, '')} {s}")
detail_disp["Budget €"]   = detail_disp["Budget €"].map(lambda x: fmt(x, 2))
detail_disp["Actual €"]   = detail_disp["Actual €"].map(lambda x: fmt(x, 2))
detail_disp["Variance €"] = detail_disp["Variance €"].map(lambda x: fmt_delta(x, 2))
detail_disp["Var %"]      = detail_disp["Var %"].map(
    lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
)

st.dataframe(detail_disp, use_container_width=True, hide_index=True)

st.divider()

# ── Downloads ─────────────────────────────────────────────────────────────────
st.subheader("Downloads")
dl1, dl2 = st.columns(2)

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
