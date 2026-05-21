"""
Project Close-out P&L.
Final margin, actual vs quoted, variance analysis, lessons learned.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import (df_to_excel_bytes, load_actuals, load_bom, load_change_orders,
                      load_materials, load_nre, load_processes, load_quotes, save_sheet)
from utils.nav import home_button
from utils.nre import nre_total
from utils.pricing import compute_costs
from utils.project import load_project_meta
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

SCHEMA_LESSONS = {
    "lesson_id":   "string",
    "category":    "string",
    "finding":     "string",
    "root_cause":  "string",
    "action":      "string",
    "owner":       "string",
    "status":      "string",
}
LESSON_CATEGORIES = [
    "Material cost", "Process cost", "NRE / Engineering", "Transport",
    "Subcontracting", "Commissioning", "Schedule", "Commercial", "Quality", "Other",
]


def load_lessons() -> pd.DataFrame:
    from utils.io import _read, SHEET_MAP
    try:
        return _read("lessons", SCHEMA_LESSONS)
    except Exception:
        return pd.DataFrame(columns=list(SCHEMA_LESSONS.keys()))


# Register sheet key if not present
try:
    from utils.io import SHEET_MAP
    if "lessons" not in SHEET_MAP:
        SHEET_MAP["lessons"] = "Lessons"
except Exception:
    pass


def _variance_pct(actual: float, budget: float) -> str:
    if budget == 0:
        return "—"
    v = (actual - budget) / budget * 100
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def main() -> None:
    st.set_page_config(page_title="Project Close-out", layout="wide", page_icon="📁")
    inject_css()
    home_button()

    meta    = load_project_meta()
    project = meta.get("name", "")

    page_header(
        title="Project Close-out P&L",
        icon="📁",
        caption="Final margin, budget vs actuals, variance analysis and lessons learned.",
        project=project,
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df_budget = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM: {exc}")
        st.stop()

    actuals    = load_actuals()
    nre_df     = load_nre()
    co_df      = load_change_orders()
    lessons_df = load_lessons()

    # ── Budget totals ─────────────────────────────────────────────────────────
    bud_mat  = df_budget["material_cost"].sum()
    bud_proc = df_budget["process_cost"].sum()
    bud_oh   = df_budget["overhead"].sum()
    bud_mar  = df_budget["margin"].sum()
    bud_sell = df_budget["total_cost"].sum()
    bud_nre  = nre_total(nre_df)

    # Change order impact
    co_rev_delta  = 0.0
    co_cost_delta = 0.0
    if not co_df.empty:
        approved = co_df[co_df["status"].str.lower() == "approved"] if "status" in co_df.columns else co_df
        co_rev_delta  = pd.to_numeric(approved.get("revenue_delta_eur",  pd.Series([0])), errors="coerce").fillna(0).sum()
        co_cost_delta = pd.to_numeric(approved.get("cost_delta_eur",     pd.Series([0])), errors="coerce").fillna(0).sum()

    revised_sell = bud_sell + co_rev_delta

    tab_pnl, tab_var, tab_lines, tab_lessons = st.tabs(
        ["💰 Final P&L", "📊 Variance Analysis", "📋 Line Detail", "📝 Lessons Learned"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — FINAL P&L
    # ══════════════════════════════════════════════════════════════════════════
    with tab_pnl:
        st.subheader("Project P&L — budget vs actuals")

        # Actual totals from actuals sheet
        act_mat  = pd.to_numeric(actuals.get("actual_material_cost",  pd.Series([0])), errors="coerce").fillna(0).sum() if not actuals.empty else 0.0
        act_proc = pd.to_numeric(actuals.get("actual_process_cost",   pd.Series([0])), errors="coerce").fillna(0).sum() if not actuals.empty else 0.0
        act_tot  = pd.to_numeric(actuals.get("actual_total_cost",     pd.Series([0])), errors="coerce").fillna(0).sum() if not actuals.empty else 0.0

        if actuals.empty:
            st.info(
                "No actuals recorded yet. Import actuals via **Pre / Post** page or enter them below. "
                "The P&L will populate once actuals are available."
            )
            act_mat = act_proc = act_tot = 0.0

        act_oh  = act_tot - act_mat - act_proc if act_tot > 0 else 0.0
        act_cost_total = act_mat + act_proc + act_oh + co_cost_delta + bud_nre
        act_margin = revised_sell - act_cost_total
        act_margin_pct = act_margin / revised_sell * 100 if revised_sell > 0 else 0

        bud_margin_pct = bud_mar / bud_sell * 100 if bud_sell > 0 else 0
        margin_delta   = act_margin_pct - bud_margin_pct

        # KPI row
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Contract value (revised)",  fmt(revised_sell, 0),
                  delta=fmt(co_rev_delta, 0) + " change orders" if co_rev_delta else None,
                  delta_color="normal")
        k2.metric("Actual total cost",         fmt(act_cost_total, 0))
        k3.metric("Actual margin",             fmt(act_margin, 0),
                  delta=f"{act_margin_pct:.1f}%", delta_color="off")
        k4.metric("Budget margin",             fmt(bud_mar, 0),
                  delta=f"{bud_margin_pct:.1f}%", delta_color="off")
        k5.metric("Margin variance",
                  f"{margin_delta:+.1f}pp",
                  delta="better" if margin_delta >= 0 else "worse",
                  delta_color="normal" if margin_delta >= 0 else "inverse")

        st.divider()

        # P&L table
        pnl_rows = [
            ("Revenue (contract value)",     revised_sell,     ""),
            ("  Quoted BOM sell",             bud_sell,         ""),
            ("  Change order revenue",        co_rev_delta,     ""),
            ("Direct material (actual)",     -act_mat,         _variance_pct(act_mat, bud_mat)),
            ("Direct process (actual)",      -act_proc,        _variance_pct(act_proc, bud_proc)),
            ("Overhead (actual est.)",       -act_oh,          _variance_pct(act_oh, bud_oh)),
            ("NRE (budgeted)",               -bud_nre,         "—"),
            ("Change order cost",            -co_cost_delta,   "—"),
            ("Gross margin",                  act_margin,       f"{act_margin_pct:.1f}%"),
            ("Budget margin",                 bud_mar,          f"{bud_margin_pct:.1f}%"),
            ("Margin improvement / erosion",  act_margin - bud_mar, f"{margin_delta:+.1f}pp"),
        ]
        pnl_df = pd.DataFrame(pnl_rows, columns=["Item", "€", "Note"])
        pnl_df["€"] = pnl_df["€"].map(lambda x: fmt(x, 0) if isinstance(x, (int, float)) else x)

        st.dataframe(pnl_df, use_container_width=True, hide_index=True)

        # Change orders impact summary
        if not co_df.empty:
            st.divider()
            st.subheader("Change order summary")
            approved_cos = co_df[co_df.get("status", pd.Series(dtype=str)).str.lower() == "approved"] if "status" in co_df.columns else pd.DataFrame()
            pending_cos  = co_df[co_df.get("status", pd.Series(dtype=str)).str.lower() == "pending"]  if "status" in co_df.columns else pd.DataFrame()
            k1, k2, k3 = st.columns(3)
            k1.metric("Approved change orders", len(approved_cos),
                      delta=fmt(co_rev_delta, 0) + " revenue", delta_color="normal")
            k2.metric("Pending change orders",  len(pending_cos))
            k3.metric("Net cost impact",        fmt(co_cost_delta, 0),
                      delta_color="inverse" if co_cost_delta > 0 else "normal")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — VARIANCE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_var:
        st.subheader("Budget vs actuals variance")

        var_rows = [
            ("Material",  bud_mat,  act_mat,  act_mat  - bud_mat),
            ("Process",   bud_proc, act_proc, act_proc - bud_proc),
            ("Overhead",  bud_oh,   act_oh,   act_oh   - bud_oh),
            ("NRE",       bud_nre,  bud_nre,  0.0),  # assume NRE = budget unless entered
        ]
        var_df = pd.DataFrame(var_rows, columns=["Element", "Budget €", "Actual €", "Variance €"])
        var_df["Variance %"] = var_df.apply(
            lambda r: _variance_pct(r["Actual €"], r["Budget €"]), axis=1
        )

        c_chart, c_tbl = st.columns([2, 2])
        with c_chart:
            chart = var_df.set_index("Element")[["Budget €", "Actual €"]]
            st.bar_chart(chart, color=["#2196F3", "#FF9800"])
        with c_tbl:
            disp = var_df.copy()
            for col in ["Budget €", "Actual €", "Variance €"]:
                disp[col] = disp[col].map(lambda x: fmt(x, 0))
            st.dataframe(disp, use_container_width=True, hide_index=True)

        # Highlight biggest over-runs
        over = var_df[var_df["Variance €"] > 0].sort_values("Variance €", ascending=False)
        if not over.empty:
            for _, row in over.iterrows():
                if row["Variance €"] > 0:
                    st.warning(
                        f"⚠️ **{row['Element']}** over budget by **{fmt(row['Variance €'], 0)}** "
                        f"({row['Variance %']}) — investigate root cause and record lesson below."
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — LINE DETAIL
    # ══════════════════════════════════════════════════════════════════════════
    with tab_lines:
        st.subheader("Line-by-line budget vs actuals")

        if actuals.empty:
            st.info("No actuals loaded. Import from the Pre / Post page.")
        else:
            merged = df_budget[["line_id", "material_id", "material_cost", "process_cost",
                                  "overhead", "total_cost"]].merge(
                actuals[["line_id", "actual_material_cost", "actual_process_cost",
                          "actual_total_cost", "status"]],
                on="line_id", how="left"
            )
            merged["total_variance"] = (
                merged["actual_total_cost"].fillna(0) - merged["total_cost"]
            )
            merged["var_pct"] = merged.apply(
                lambda r: _variance_pct(r["actual_total_cost"] or 0, r["total_cost"]), axis=1
            )
            for col in ["material_cost", "process_cost", "overhead", "total_cost",
                        "actual_material_cost", "actual_process_cost", "actual_total_cost",
                        "total_variance"]:
                merged[col] = merged[col].map(lambda x: fmt(x, 0) if pd.notna(x) else "—")

            st.dataframe(merged.rename(columns={
                "line_id": "Line", "material_id": "Material",
                "material_cost": "Bud Mat €", "process_cost": "Bud Proc €",
                "total_cost": "Budget €",
                "actual_material_cost": "Act Mat €", "actual_process_cost": "Act Proc €",
                "actual_total_cost": "Actuals €", "total_variance": "Variance €",
                "var_pct": "Var %",
            }), use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — LESSONS LEARNED
    # ══════════════════════════════════════════════════════════════════════════
    with tab_lessons:
        st.subheader("Lessons learned register")
        st.caption(
            "Document every significant cost variance and what to do differently next time. "
            "This register feeds directly into future quote accuracy."
        )

        if lessons_df.empty:
            seed = pd.DataFrame([{
                "lesson_id":  "LL-001",
                "category":   "Material cost",
                "finding":    "NAB casting price 12% above quote",
                "root_cause": "Nickel spot price moved +18% between quote and purchase",
                "action":     "Add 15% buffer on NAB in future quotes; use escalation clause",
                "owner":      "Procurement",
                "status":     "Open",
            }])
        else:
            seed = lessons_df.copy()

        edited_ll = st.data_editor(
            seed,
            column_config={
                "lesson_id":  st.column_config.TextColumn("ID", width="small"),
                "category":   st.column_config.SelectboxColumn("Category", options=LESSON_CATEGORIES),
                "finding":    st.column_config.TextColumn("Finding", width="large"),
                "root_cause": st.column_config.TextColumn("Root cause", width="large"),
                "action":     st.column_config.TextColumn("Action for next quote", width="large"),
                "owner":      st.column_config.TextColumn("Owner", width="small"),
                "status":     st.column_config.SelectboxColumn("Status",
                                  options=["Open", "In progress", "Closed"]),
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="lessons_editor",
        )

        c1, _ = st.columns([1, 4])
        if c1.button("💾 Save lessons", use_container_width=True):
            from utils.io import SHEET_MAP
            SHEET_MAP["lessons"] = "Lessons"
            save_sheet(edited_ll, "lessons")
            st.success("Lessons learned saved.")

        # Download close-out pack
        st.divider()

        def _closeout_excel() -> bytes:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.DataFrame(pnl_rows, columns=["Item", "€", "Note"]).to_excel(
                    w, sheet_name="P&L", index=False)
                var_df.to_excel(w, sheet_name="Variance", index=False)
                if not actuals.empty:
                    actuals.to_excel(w, sheet_name="Actuals", index=False)
                edited_ll.to_excel(w, sheet_name="Lessons Learned", index=False)
            return buf.getvalue()

        st.download_button(
            "⬇️ Download close-out pack (Excel)",
            data=_closeout_excel(),
            file_name="project_closeout.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


guard(main)
