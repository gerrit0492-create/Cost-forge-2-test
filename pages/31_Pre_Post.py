from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.currency import fmt, fmt_delta
from utils.io import (
    load_bom, load_materials, load_processes, load_quotes,
    save_sheet, df_to_excel_bytes,
)
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
    caption="Track estimated vs actual cost at subsystem scope-line level.",
)

if st.button("🔄 Refresh", help="Clear cache and reload"):
    st.cache_data.clear()
    st.rerun()

STATUS_COLOURS = {
    "complete":    "🟢",
    "in_progress": "🟡",
    "not_started": "⚪",
    "cancelled":   "🔴",
}

# ── Load budget costs rolled up to subsystem scope lines ─────────────────────
@st.cache_data(ttl=30)
def _load_budget_by_subsystem() -> pd.DataFrame:
    """Return one row per waterjet subsystem with summed budget costs."""
    mats  = apply_best_quotes(load_materials(), load_quotes())
    df    = compute_costs(mats, load_processes(), load_bom())

    def _pfx(lid: str) -> str:
        u = str(lid).upper()
        for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
            if u.startswith(p):
                return p
        return "OTHER"

    df["_sub"] = df["line_id"].apply(_pfx)

    _agg_cols = {c: "sum" for c in
                 ["material_cost", "process_cost", "overhead",
                  "pattern_cost", "moq_excess_cost", "base_cost",
                  "margin", "total_cost"]
                 if c in df.columns}
    _agg_cols["line_id"] = "count"

    grp = df.groupby("_sub").agg(_agg_cols).reset_index()
    grp.rename(columns={"_sub": "subsystem", "line_id": "bom_lines"}, inplace=True)

    # Only keep known subsystems (drop OTHER if any)
    grp = grp[grp["subsystem"].isin(WATERJET_SUBSYSTEMS)]
    # Preserve display order
    order = {p: i for i, p in enumerate(WATERJET_SUBSYSTEMS)}
    grp["_ord"] = grp["subsystem"].map(order)
    grp = grp.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)

    grp["scope_line"] = grp["subsystem"].map(
        lambda p: f"{WATERJET_SUBSYSTEMS[p]['icon']} {WATERJET_SUBSYSTEMS[p]['name']}"
    )
    return grp


@st.cache_data(ttl=30)
def _load_saved_actuals() -> pd.DataFrame:
    from utils.io import load_actuals
    df = load_actuals()
    # Support both old (line_id based) and new (subsystem based) actuals
    if not df.empty and "subsystem" not in df.columns and "line_id" in df.columns:
        # Legacy format — ignore; user needs to re-enter at subsystem level
        return pd.DataFrame()
    return df


try:
    bgt = _load_budget_by_subsystem()
except Exception as exc:
    st.error(f"Could not load BOM cost data: {exc}")
    st.stop()

# ── Actuals source ────────────────────────────────────────────────────────────
st.subheader("Actuals source")
tab_saved, tab_sap, tab_upload = st.tabs(["💾 Saved actuals", "🔵 SAP import", "📂 Upload file"])

df_actuals_raw: pd.DataFrame = pd.DataFrame()

with tab_saved:
    df_actuals_raw = _load_saved_actuals()
    if df_actuals_raw.empty:
        st.info("No actuals saved yet. Fill in the scope-line table below.")
    else:
        n_filled = df_actuals_raw["actual_total_cost"].notna().sum()
        st.success(f"{n_filled} scope lines with actuals loaded.")

with tab_sap:
    st.markdown("#### Upload SAP export (plan vs actual by subsystem / WBS)")
    with st.expander("SAP export guide", expanded=False):
        st.markdown("""
**S_ALR_87013533** — Plan vs Actual by project/WBS
1. Enter Project / WBS selection → Execute (F8)
2. List → Export → Spreadsheet → `.xlsx`
3. Upload below — expects *WBS Element* and *Actual* columns

**CJI3** — Actual cost line items
1. Enter Project number and posting date range → Execute → Export

The importer groups postings by subsystem prefix (I, SB, H, S, …).
        """)

    sap_file = st.file_uploader("SAP export", type=["xlsx", "csv"], key="sap_up")
    if sap_file:
        try:
            df_sap = (pd.read_excel(sap_file) if sap_file.name.endswith(".xlsx")
                      else pd.read_csv(sap_file))
            df_sap.columns = df_sap.columns.str.strip()
            st.dataframe(df_sap.head(), use_container_width=True, hide_index=True)

            cols_sel = ["— select —"] + df_sap.columns.tolist()
            sc1, sc2 = st.columns(2)
            wbs_col = sc1.selectbox("WBS / subsystem column", cols_sel, key="sap_wbs")
            act_col = sc2.selectbox("Actual cost column",    cols_sel, key="sap_act")

            if wbs_col != "— select —" and act_col != "— select —":
                import re
                _sub_keys = list(WATERJET_SUBSYSTEMS.keys())

                def _find_sub(val: str) -> str | None:
                    u = str(val).strip().upper()
                    for p in sorted(_sub_keys, key=len, reverse=True):
                        if u.startswith(p) or p in u:
                            return p
                    return None

                mapped = df_sap[[wbs_col, act_col]].copy()
                mapped["subsystem"]        = mapped[wbs_col].apply(_find_sub)
                mapped["actual_total_cost"] = pd.to_numeric(mapped[act_col], errors="coerce")
                matched = mapped[mapped["subsystem"].notna() & mapped["actual_total_cost"].notna()]

                if not matched.empty:
                    grp_sap = (
                        matched.groupby("subsystem")
                        .agg(actual_total_cost=("actual_total_cost", "sum"))
                        .reset_index()
                    )
                    grp_sap["status"] = "in_progress"
                    grp_sap["notes"]  = f"SAP: {sap_file.name}"
                    st.dataframe(grp_sap, use_container_width=True, hide_index=True)

                    if st.button("✅ Apply SAP actuals", type="primary"):
                        st.session_state["sap_actuals_sub"] = grp_sap
                        st.success("Applied. Scroll down to review and save.")
                        st.cache_data.clear()
                else:
                    st.warning("No subsystem codes matched. Check the WBS column values.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

with tab_upload:
    up = st.file_uploader("Upload actuals (Excel/CSV)", type=["xlsx", "csv"], key="up_file")
    if up:
        try:
            raw = (pd.read_excel(up) if up.name.endswith(".xlsx") else pd.read_csv(up))
            for c in ["actual_material_cost", "actual_process_cost", "actual_total_cost"]:
                if c in raw.columns:
                    raw[c] = pd.to_numeric(raw[c], errors="coerce")
            df_actuals_raw = raw
            st.success(f"Loaded {len(raw)} rows from {up.name}.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

# Merge SAP actuals
if "sap_actuals_sub" in st.session_state:
    sap = st.session_state["sap_actuals_sub"]
    if df_actuals_raw.empty or "subsystem" not in df_actuals_raw.columns:
        df_actuals_raw = sap
    else:
        df_actuals_raw = df_actuals_raw[~df_actuals_raw["subsystem"].isin(sap["subsystem"])]
        df_actuals_raw = pd.concat([df_actuals_raw, sap], ignore_index=True)

st.divider()

# ── Build editable scope-line table ──────────────────────────────────────────
st.subheader("Enter / edit actuals per scope line")
st.caption("One row per waterjet subsystem. Fill in what was actually spent; leave blank if not yet incurred.")

edit_base = bgt[["subsystem", "scope_line", "bom_lines",
                  "material_cost", "process_cost", "overhead",
                  "base_cost", "margin", "total_cost"]].copy()
edit_base.rename(columns={
    "material_cost": "budget_material",
    "process_cost":  "budget_process",
    "overhead":      "budget_overhead",
    "base_cost":     "budget_base",
    "margin":        "budget_margin",
    "total_cost":    "budget_total",
}, inplace=True)

# Merge saved actuals
if not df_actuals_raw.empty and "subsystem" in df_actuals_raw.columns:
    act_merge_cols = ["subsystem"] + [c for c in
        ["actual_material_cost", "actual_process_cost", "actual_total_cost", "notes", "status"]
        if c in df_actuals_raw.columns]
    edit_base = edit_base.merge(df_actuals_raw[act_merge_cols], on="subsystem", how="left")
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
        "subsystem":              st.column_config.TextColumn("Code",      disabled=True, width="small"),
        "scope_line":             st.column_config.TextColumn("Scope line", disabled=True, width="large"),
        "bom_lines":              st.column_config.NumberColumn("BOM lines", disabled=True, format="%d", width="small"),
        "budget_material":        st.column_config.NumberColumn("Bgt mat €",    disabled=True, format="%.0f"),
        "budget_process":         st.column_config.NumberColumn("Bgt proc €",   disabled=True, format="%.0f"),
        "budget_overhead":        st.column_config.NumberColumn("Bgt OH €",     disabled=True, format="%.0f"),
        "budget_base":            st.column_config.NumberColumn("Bgt base €",   disabled=True, format="%.0f"),
        "budget_margin":          st.column_config.NumberColumn("Bgt margin €", disabled=True, format="%.0f"),
        "budget_total":           st.column_config.NumberColumn("Bgt sell €",   disabled=True, format="%.0f"),
        "actual_material_cost":   st.column_config.NumberColumn("Act mat €",    format="%.0f"),
        "actual_process_cost":    st.column_config.NumberColumn("Act proc €",   format="%.0f"),
        "actual_total_cost":      st.column_config.NumberColumn("Act total €",  format="%.0f"),
        "notes":                  st.column_config.TextColumn("Notes"),
        "status":                 st.column_config.SelectboxColumn(
                                      "Status", options=list(STATUS_COLOURS.keys()), width="small"
                                  ),
    },
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="actuals_editor",
)

sa1, _ = st.columns([1, 5])
if sa1.button("💾 Save to workbook", type="primary"):
    save_cols = ["subsystem", "actual_material_cost", "actual_process_cost",
                 "actual_total_cost", "notes", "status"]
    save_sheet(edited[save_cols], "actuals")
    st.session_state.pop("sap_actuals_sub", None)
    st.success("Actuals saved to cost_forge.xlsx.")
    st.cache_data.clear()

st.divider()

# ── Analysis ──────────────────────────────────────────────────────────────────
df = edited.copy()

# Auto-fill actual_total if parts entered but total blank
_blank = df["actual_total_cost"].isna()
_parts = df["actual_material_cost"].notna() & df["actual_process_cost"].notna()
df.loc[_blank & _parts, "actual_total_cost"] = (
    df["actual_material_cost"] + df["actual_process_cost"]
)

has_act      = df["actual_total_cost"].notna()
n_lines      = len(df)
n_with_act   = has_act.sum()
n_complete   = (df["status"] == "complete").sum()
budget_full  = df["budget_total"].sum()
actual_total = df.loc[has_act, "actual_total_cost"].sum()
budget_scope = df.loc[has_act, "budget_total"].sum()
variance_abs = actual_total - budget_scope

# ── Summary KPIs ──────────────────────────────────────────────────────────────
st.subheader("Summary")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Budget (full scope)",    fmt(budget_full))
k2.metric("Budget (actuals scope)", fmt(budget_scope))
k3.metric("Actuals to date",        fmt(actual_total))
k4.metric(
    "Variance",
    fmt_delta(variance_abs),
    delta=f"{variance_abs / budget_scope * 100:+.1f}%" if budget_scope else None,
    delta_color="inverse",
)
k5.metric("Scope lines with actuals", f"{n_with_act} / {n_lines}")
k6.metric("Complete",                 f"{n_complete} / {n_lines}")

st.divider()

# ── Scope-line comparison chart + table ──────────────────────────────────────
st.subheader("Scope-line comparison")

df["variance_eur"] = df["actual_total_cost"] - df["budget_total"]
df["variance_pct"] = (
    df["variance_eur"] / df["budget_total"].replace(0, float("nan")) * 100
).round(1)

# Chart: budget vs actual for lines with actuals
chart_df = (
    df[has_act]
    .set_index("scope_line")[["budget_total", "actual_total_cost"]]
    .rename(columns={"budget_total": "Budget", "actual_total_cost": "Actual"})
)

if not chart_df.empty:
    col_c, col_t = st.columns([3, 2])
    with col_c:
        st.bar_chart(chart_df, color=["#1565C0", "#4da6ff"])

    with col_t:
        tbl = df[["scope_line", "status", "budget_total",
                  "actual_total_cost", "variance_eur", "variance_pct"]].copy()
        tbl["Status"]     = tbl["status"].map(lambda s: f"{STATUS_COLOURS.get(s, '')} {s}")
        tbl["Budget €"]   = tbl["budget_total"].map(lambda x: fmt(x))
        tbl["Actual €"]   = tbl["actual_total_cost"].map(
                                lambda x: fmt(x) if pd.notna(x) else "—")
        tbl["Variance €"] = tbl["variance_eur"].map(
                                lambda x: fmt_delta(x) if pd.notna(x) else "—")
        tbl["Var %"]      = tbl["variance_pct"].map(
                                lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
        st.dataframe(
            tbl[["scope_line", "Status", "Budget €", "Actual €", "Variance €", "Var %"]]
            .rename(columns={"scope_line": "Scope line"}),
            use_container_width=True, hide_index=True,
        )
else:
    st.info("No actuals entered yet — fill in the table above.")

st.divider()

# ── Drill-down: BOM lines within a selected scope line ───────────────────────
st.subheader("Drill-down: BOM lines per scope line")

_sub_opts = ["— select a scope line —"] + df["scope_line"].tolist()
chosen_scope = st.selectbox("Scope line", _sub_opts, key="drill_sub")

if chosen_scope != "— select a scope line —":
    chosen_pfx = df.loc[df["scope_line"] == chosen_scope, "subsystem"].iloc[0]
    mats_d = apply_best_quotes(load_materials(), load_quotes())
    df_full = compute_costs(mats_d, load_processes(), load_bom())

    def _pfx(lid: str) -> str:
        u = str(lid).upper()
        for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
            if u.startswith(p):
                return p
        return "OTHER"

    df_full["_sub"] = df_full["line_id"].apply(_pfx)
    sub_lines = df_full[df_full["_sub"] == chosen_pfx].copy()

    _disp = sub_lines[
        ["line_id", "part_name"] +
        [c for c in ["material_cost", "process_cost", "overhead",
                     "base_cost", "margin", "total_cost"]
         if c in sub_lines.columns]
    ].copy()

    for _mc in ["material_cost", "process_cost", "overhead", "base_cost", "margin", "total_cost"]:
        if _mc in _disp.columns:
            _disp[_mc] = _disp[_mc].map(lambda x: fmt(x, 2) if pd.notna(x) else "—")

    _disp.rename(columns={
        "line_id":       "Line",
        "part_name":     "Component",
        "material_cost": "Material €",
        "process_cost":  "Process €",
        "overhead":      "Overhead €",
        "base_cost":     "Base cost €",
        "margin":        "Margin €",
        "total_cost":    "Sell price €",
    }, inplace=True)

    st.caption(f"**{len(sub_lines)}** BOM lines in {chosen_scope}")
    st.dataframe(_disp, use_container_width=True, hide_index=True)

st.divider()

# ── Downloads ─────────────────────────────────────────────────────────────────
st.subheader("Downloads")
dl1, dl2 = st.columns(2)

with dl1:
    tmpl = df[["subsystem", "scope_line"]].copy()
    tmpl["actual_material_cost"] = ""
    tmpl["actual_process_cost"]  = ""
    tmpl["actual_total_cost"]    = ""
    tmpl["notes"]                = ""
    tmpl["status"]               = "not_started"
    st.download_button(
        "⬇️ Actuals template (Excel)",
        data=df_to_excel_bytes(tmpl, "Actuals"),
        file_name="actuals_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with dl2:
    report = df.copy()
    _rpt = ["subsystem", "scope_line", "bom_lines", "status",
            "budget_material", "budget_process", "budget_overhead",
            "budget_base", "budget_margin", "budget_total",
            "actual_material_cost", "actual_process_cost", "actual_total_cost",
            "variance_eur", "variance_pct", "notes"]
    st.download_button(
        "⬇️ Pre/post report (Excel)",
        data=df_to_excel_bytes(report[[c for c in _rpt if c in report.columns]], "Pre-Post"),
        file_name="pre_post_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
