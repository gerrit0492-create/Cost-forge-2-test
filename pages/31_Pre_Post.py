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
from utils.style import inject_css, page_header

st.set_page_config(page_title="Pre / Post", layout="wide", page_icon="📊")
inject_css()
home_button()
page_header(
    title="Pre / Post — Budget vs Actuals",
    icon="📊",
    caption="Compare estimated (budget) costs against recorded actuals, line by line and per subsystem.",
)

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
                import re

                def _extract_line_id(val: str) -> str | None:
                    val = str(val).strip().upper()
                    if val in valid_line_ids:
                        return val
                    for seg in re.split(r"[.\-/_]", val):
                        if seg in valid_line_ids:
                            return seg
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
        df_actuals_raw = df_actuals_raw[
            ~df_actuals_raw["line_id"].isin(sap_act["line_id"])
        ]
        df_actuals_raw = pd.concat([df_actuals_raw, sap_act], ignore_index=True)

st.divider()

# ── Editable actuals table ────────────────────────────────────────────────────
st.subheader("Enter / edit actuals per scope line")
st.caption("Fill in what was actually spent per line. Leave blank if not yet incurred. All BOM scope lines shown.")

# Pull full budget breakdown per line
_bgt_cols = ["line_id", "part_name", "material_cost", "process_cost"]
for _c in ["overhead", "base_cost", "margin", "pattern_cost", "moq_excess_cost", "total_cost"]:
    if _c in df_budget.columns:
        _bgt_cols.append(_c)

edit_base = df_budget[_bgt_cols].copy()
edit_base.rename(columns={
    "material_cost":   "budget_material",
    "process_cost":    "budget_process",
    "overhead":        "budget_overhead",
    "base_cost":       "budget_base",
    "margin":          "budget_margin",
    "pattern_cost":    "budget_pattern",
    "moq_excess_cost": "budget_moq",
    "total_cost":      "budget_total",
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

# Build column_config — only include budget columns that exist
_col_cfg: dict = {
    "line_id":   st.column_config.TextColumn("Line", disabled=True, width="small"),
    "part_name": st.column_config.TextColumn("Component", disabled=True, width="large"),
}
_budget_cols_display = [
    ("budget_material", "Budget mat €"),
    ("budget_process",  "Budget proc €"),
    ("budget_overhead", "Budget OH €"),
    ("budget_pattern",  "Budget pattern €"),
    ("budget_moq",      "Budget MOQ €"),
    ("budget_base",     "Budget base €"),
    ("budget_margin",   "Budget margin €"),
    ("budget_total",    "Budget sell €"),
]
for _col, _label in _budget_cols_display:
    if _col in edit_base.columns:
        _col_cfg[_col] = st.column_config.NumberColumn(_label, disabled=True, format="%.0f")

_col_cfg.update({
    "actual_material_cost": st.column_config.NumberColumn("Actual mat €",   format="%.0f"),
    "actual_process_cost":  st.column_config.NumberColumn("Actual proc €",  format="%.0f"),
    "actual_total_cost":    st.column_config.NumberColumn("Actual total €", format="%.0f"),
    "notes":                st.column_config.TextColumn("Notes"),
    "status":               st.column_config.SelectboxColumn(
        "Status",
        options=list(STATUS_COLOURS.keys()),
        width="small",
    ),
})

edited = st.data_editor(
    edit_base,
    column_config=_col_cfg,
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
n_total    = len(df)
n_actual   = has_actuals.sum()
n_complete = (df["status"] == "complete").sum()

budget_total  = df["budget_total"].sum()
actual_total  = df.loc[has_actuals, "actual_total_cost"].sum()
budget_scope  = df.loc[has_actuals, "budget_total"].sum()
variance_abs  = actual_total - budget_scope

# ── Summary KPIs ──────────────────────────────────────────────────────────────
st.subheader("Summary")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Budget (full scope)",     fmt(budget_total))
k2.metric("Budget (actuals scope)",  fmt(budget_scope))
k3.metric("Actuals to date",         fmt(actual_total))
k4.metric(
    "Variance (actuals scope)",
    fmt_delta(variance_abs),
    delta=f"{variance_abs / budget_scope * 100:+.1f}%" if budget_scope else None,
    delta_color="inverse",
)
k5.metric("Lines with actuals",  f"{n_actual} / {n_total}")
k6.metric("Lines complete",      f"{n_complete} / {n_total}")

st.divider()

# ── Subsystem prefix helper ───────────────────────────────────────────────────
def _prefix(lid: str) -> str:
    u = str(lid).upper()
    for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
        if u.startswith(p):
            return p
    return "?"

df["subsystem"] = df["line_id"].apply(_prefix)
subsystem_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}

# ── Per-subsystem comparison ──────────────────────────────────────────────────
st.subheader("Subsystem comparison")

grp = (
    df.groupby("subsystem")
    .agg(
        budget=("budget_total", "sum"),
        actual=("actual_total_cost", lambda s: s.dropna().sum()),
        n_lines=("line_id", "count"),
        n_actual=("actual_total_cost", lambda s: s.notna().sum()),
        n_complete=("status", lambda s: (s == "complete").sum()),
    )
    .reset_index()
)
grp["Subsystem"]  = grp["subsystem"].map(lambda p: subsystem_names.get(p, p))
grp["Budget €"]   = grp["budget"].map(lambda x: fmt(x))
grp["Actual €"]   = grp.apply(lambda r: fmt(r["actual"]) if r["n_actual"] > 0 else "—", axis=1)
grp["Variance €"] = grp.apply(
    lambda r: fmt_delta(r["actual"] - r["budget"]) if r["n_actual"] > 0 else "—", axis=1
)
grp["Var %"] = grp.apply(
    lambda r: f"{(r['actual'] - r['budget']) / r['budget'] * 100:+.1f}%"
              if r["n_actual"] > 0 and r["budget"] else "—", axis=1
)
grp["Coverage"] = grp.apply(
    lambda r: f"{r['n_actual']}/{r['n_lines']} lines ({r['n_complete']} done)", axis=1
)

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
else:
    st.info("No actuals entered yet — fill in the table above or import from SAP.")

st.divider()

# ── Per-scope-line detail (ALL lines) ─────────────────────────────────────────
st.subheader("Per-scope-line detail")
st.caption(
    "All BOM scope lines. Lines without actuals show budget only. "
    "Filter by subsystem, status, or search to drill down."
)

# Filters
fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])

# Subsystem filter
_sub_options_all = ["All subsystems"] + [
    subsystem_names[p] for p in WATERJET_SUBSYSTEMS if p in df["subsystem"].values
]
chosen_sub = fc1.selectbox("Subsystem", _sub_options_all, key="pp_sub")

# Status filter
chosen_status = fc2.selectbox(
    "Status",
    ["All statuses"] + list(STATUS_COLOURS.keys()),
    key="pp_status",
)

# Actuals filter
chosen_actuals = fc3.selectbox(
    "Show",
    ["All lines", "Lines with actuals only", "Lines without actuals"],
    key="pp_actuals_filter",
)

# Search
search_pp = fc4.text_input("Search line ID / component", key="pp_search")

# Apply filters
view = df.copy()
if chosen_sub != "All subsystems":
    pfx = next(p for p, n in subsystem_names.items() if n == chosen_sub)
    view = view[view["subsystem"] == pfx]
if chosen_status != "All statuses":
    view = view[view["status"] == chosen_status]
if chosen_actuals == "Lines with actuals only":
    view = view[view["actual_total_cost"].notna()]
elif chosen_actuals == "Lines without actuals":
    view = view[view["actual_total_cost"].isna()]
if search_pp:
    desc = view["part_name"] if "part_name" in view.columns else pd.Series("", index=view.index)
    mask = (
        view["line_id"].astype(str).str.contains(search_pp, case=False, na=False) |
        desc.astype(str).str.contains(search_pp, case=False, na=False)
    )
    view = view[mask]

st.caption(f"Showing **{len(view)}** of **{len(df)}** scope lines")

# Compute per-line variance (NaN when no actuals)
view = view.copy()
view["variance_eur"] = view["actual_total_cost"] - view["budget_total"]
view["variance_pct"] = (
    view["variance_eur"] / view["budget_total"].replace(0, float("nan")) * 100
).round(1)

# Build display table with all budget component columns
_disp_detail: dict = {}
_disp_detail["line_id"]   = "Line"
_disp_detail["part_name"] = "Component"
_disp_detail["status"]    = "Status"
for _c, _l in [("budget_material","Bgt mat €"), ("budget_process","Bgt proc €"),
                ("budget_overhead","Bgt OH €"),  ("budget_pattern","Bgt pattern €"),
                ("budget_base","Bgt base €"),     ("budget_total","Bgt sell €")]:
    if _c in view.columns:
        _disp_detail[_c] = _l
_disp_detail["actual_material_cost"] = "Act mat €"
_disp_detail["actual_process_cost"]  = "Act proc €"
_disp_detail["actual_total_cost"]    = "Act total €"
_disp_detail["variance_eur"]         = "Variance €"
_disp_detail["variance_pct"]         = "Var %"
_disp_detail["notes"]                = "Notes"

detail_tbl = view[[c for c in _disp_detail if c in view.columns]].rename(columns=_disp_detail).copy()

# Format numeric columns
_money_cols = ["Bgt mat €","Bgt proc €","Bgt OH €","Bgt pattern €","Bgt base €","Bgt sell €",
               "Act mat €","Act proc €","Act total €"]
for _mc in _money_cols:
    if _mc in detail_tbl.columns:
        detail_tbl[_mc] = detail_tbl[_mc].map(
            lambda x: fmt(x, 2) if pd.notna(x) else "—"
        )
if "Variance €" in detail_tbl.columns:
    detail_tbl["Variance €"] = detail_tbl["Variance €"].map(
        lambda x: fmt_delta(x, 2) if pd.notna(x) else "—"
    )
if "Var %" in detail_tbl.columns:
    detail_tbl["Var %"] = detail_tbl["Var %"].map(
        lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
    )
if "Status" in detail_tbl.columns:
    detail_tbl["Status"] = detail_tbl["Status"].map(
        lambda s: f"{STATUS_COLOURS.get(s, '')} {s}"
    )

st.dataframe(detail_tbl, use_container_width=True, hide_index=True)

# Quick stats for filtered view
with st.expander("📊 Filtered-view statistics"):
    _fv = view.copy()
    _fv_has = _fv["actual_total_cost"].notna()
    _stat_cols = st.columns(5)
    _stat_cols[0].metric("Lines shown",        len(_fv))
    _stat_cols[1].metric("With actuals",       int(_fv_has.sum()))
    _stat_cols[2].metric("Budget (shown)",     fmt(_fv["budget_total"].sum()))
    _stat_cols[3].metric("Actuals (shown)",    fmt(_fv.loc[_fv_has, "actual_total_cost"].sum()))
    _var_shown = _fv.loc[_fv_has, "actual_total_cost"].sum() - _fv.loc[_fv_has, "budget_total"].sum()
    _stat_cols[4].metric("Variance (shown)",   fmt_delta(_var_shown))

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
report["variance"]  = report["actual_total_cost"] - report["budget_total"]
report["var_pct"]   = (
    report["variance"] / report["budget_total"].replace(0, float("nan")) * 100
).round(1)

# All budget breakdown columns in export
_rpt_cols = ["line_id", "part_name", "subsystem", "status"]
for _c in ["budget_material","budget_process","budget_overhead","budget_pattern",
           "budget_moq","budget_base","budget_margin","budget_total"]:
    if _c in report.columns:
        _rpt_cols.append(_c)
_rpt_cols += ["actual_material_cost","actual_process_cost","actual_total_cost",
              "variance","var_pct","notes"]

with dl2:
    st.download_button(
        "⬇️ Download full pre/post report (Excel)",
        data=df_to_excel_bytes(report[[c for c in _rpt_cols if c in report.columns]], "Pre-Post"),
        file_name="pre_post_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Full budget vs actuals comparison — all scope lines, all budget components.",
    )
