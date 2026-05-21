"""
NRE & Engineering Cost module.
Design hours, project management, testing, tooling and commissioning.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import load_nre, save_sheet
from utils.nav import home_button
from utils.nre import (
    NRE_CATEGORIES, SCHEMA_NRE, default_nre_df,
    nre_by_category, nre_cashflow, nre_per_unit, nre_total,
)
from utils.safe import guard
from utils.style import inject_css, page_header


def main() -> None:
    st.set_page_config(page_title="Engineering & NRE", layout="wide", page_icon="🔬")
    inject_css()
    home_button()
    page_header(
        title="Engineering & NRE",
        icon="🔬",
        caption="Non-Recurring Engineering: design hours, PM, testing, tooling, commissioning.",
    )

    # ── Load ──────────────────────────────────────────────────────────────────
    nre_df = load_nre()

    # ── Sidebar — production volume ───────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Amortisation")
    num_units = st.sidebar.number_input(
        "Production volume (units)",
        min_value=1, value=1, step=1,
        help="NRE costs are spread over this many units for the per-unit calculation.",
    )
    show_per_unit = st.sidebar.toggle("Show per-unit view", value=True)

    # ── KPI row ───────────────────────────────────────────────────────────────
    total   = nre_total(nre_df)
    per_u   = nre_per_unit(nre_df, num_units)
    cat_df  = nre_by_category(nre_df)

    eng_cost = float(cat_df[cat_df["category"] == "Engineering"]["cost_eur"].sum()) if not cat_df.empty else 0
    pm_cost  = float(cat_df[cat_df["category"] == "Project Management"]["cost_eur"].sum()) if not cat_df.empty else 0
    tl_cost  = float(cat_df[cat_df["category"] == "Tooling"]["cost_eur"].sum()) if not cat_df.empty else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total NRE",          fmt(total, 0))
    k2.metric("NRE per unit",       fmt(per_u, 2),   delta=f"at {num_units} units")
    k3.metric("Engineering",        fmt(eng_cost, 0))
    k4.metric("Project Mgmt",       fmt(pm_cost, 0))
    k5.metric("Tooling",            fmt(tl_cost, 0))

    tab_reg, tab_cat, tab_amort = st.tabs(
        ["📋 NRE Register", "📊 Category Summary", "📈 Amortisation Curve"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — NRE REGISTER
    # ══════════════════════════════════════════════════════════════════════════
    with tab_reg:
        st.subheader("NRE line items")
        st.caption(
            "Enter every non-recurring cost here. For time-based costs: fill Hours × Rate. "
            "For fixed-cost items (tooling, test rigs): use Fixed € column. "
            "`Amortise over` controls how many units share this cost."
        )

        if nre_df.empty:
            seed = pd.DataFrame([
                {
                    "nre_id":        "ENG-001",
                    "category":      "Engineering",
                    "description":   "Design & drawing package",
                    "hours":         200.0,
                    "rate_eur_h":    95.0,
                    "fixed_eur":     0.0,
                    "amortize_over": num_units,
                    "status":        "Active",
                    "notes":         "",
                },
                {
                    "nre_id":        "PM-001",
                    "category":      "Project Management",
                    "description":   "Project management",
                    "hours":         80.0,
                    "rate_eur_h":    110.0,
                    "fixed_eur":     0.0,
                    "amortize_over": num_units,
                    "status":        "Active",
                    "notes":         "",
                },
                {
                    "nre_id":        "TL-001",
                    "category":      "Tooling",
                    "description":   "Special tooling / fixtures",
                    "hours":         0.0,
                    "rate_eur_h":    0.0,
                    "fixed_eur":     5000.0,
                    "amortize_over": num_units,
                    "status":        "Active",
                    "notes":         "",
                },
                {
                    "nre_id":        "TST-001",
                    "category":      "Testing & Qualification",
                    "description":   "FAT / pressure test",
                    "hours":         16.0,
                    "rate_eur_h":    85.0,
                    "fixed_eur":     0.0,
                    "amortize_over": num_units,
                    "status":        "Active",
                    "notes":         "",
                },
            ])
        else:
            seed = nre_df.copy()
            seed["amortize_over"] = seed["amortize_over"].fillna(num_units)

        edited = st.data_editor(
            seed,
            column_config={
                "nre_id":        st.column_config.TextColumn("ID", width="small"),
                "category":      st.column_config.SelectboxColumn(
                                     "Category", options=NRE_CATEGORIES, width="medium"),
                "description":   st.column_config.TextColumn("Description", width="large"),
                "hours":         st.column_config.NumberColumn("Hours", min_value=0.0, format="%.1f"),
                "rate_eur_h":    st.column_config.NumberColumn("Rate €/h", min_value=0.0, format="%.2f"),
                "fixed_eur":     st.column_config.NumberColumn("Fixed €", min_value=0.0, format="%.2f"),
                "amortize_over": st.column_config.NumberColumn("Amortise over", min_value=1, format="%d"),
                "status":        st.column_config.SelectboxColumn(
                                     "Status", options=["Active", "Complete", "On Hold", "Cancelled"]),
                "notes":         st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="nre_editor",
        )

        # Computed preview
        if not edited.empty:
            hours  = pd.to_numeric(edited["hours"],     errors="coerce").fillna(0)
            rate   = pd.to_numeric(edited["rate_eur_h"], errors="coerce").fillna(0)
            fixed  = pd.to_numeric(edited["fixed_eur"],  errors="coerce").fillna(0)
            amort  = pd.to_numeric(edited["amortize_over"], errors="coerce").fillna(num_units).clip(lower=1)
            line_cost = hours * rate + fixed
            per_unit_col = line_cost / amort

            preview = edited[["nre_id", "category", "description"]].copy()
            preview["Line cost €"]    = line_cost.map(lambda x: fmt(x, 0))
            preview["Per unit €"]     = per_unit_col.map(lambda x: fmt(x, 2))
            with st.expander("💰 Cost preview"):
                st.dataframe(preview, use_container_width=True, hide_index=True)
                tot = line_cost.sum()
                ppu = per_unit_col.sum()
                st.markdown(f"**Total NRE: {fmt(tot, 0)} | Per unit at {num_units}: {fmt(ppu, 2)}**")

        c1, _ = st.columns([1, 4])
        if c1.button("💾 Save NRE register", use_container_width=True):
            save_sheet(edited, "nre")
            st.success("NRE register saved.")
            st.cache_data.clear()

        # Download
        from utils.io import df_to_excel_bytes
        st.download_button(
            "⬇️ Download NRE register",
            data=df_to_excel_bytes(edited, "NRE"),
            file_name="nre_register.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — CATEGORY SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    with tab_cat:
        st.subheader("NRE by category")

        active = edited[edited["status"].isin(["Active", "Complete"])]
        if active.empty:
            st.info("No active NRE items.")
        else:
            hours_col  = pd.to_numeric(active["hours"],      errors="coerce").fillna(0)
            rate_col   = pd.to_numeric(active["rate_eur_h"],  errors="coerce").fillna(0)
            fixed_col  = pd.to_numeric(active["fixed_eur"],   errors="coerce").fillna(0)
            active = active.copy()
            active["_cost"] = hours_col * rate_col + fixed_col

            summary = (
                active.groupby("category")
                .agg(cost_eur=("_cost", "sum"), hours=("hours", "sum"), items=("nre_id", "count"))
                .reset_index()
                .sort_values("cost_eur", ascending=False)
            )
            total_live = summary["cost_eur"].sum()
            summary["Share %"] = (summary["cost_eur"] / total_live * 100).map(lambda x: f"{x:.1f}%")

            c_chart, c_tbl = st.columns([3, 2])
            with c_chart:
                chart_data = summary.set_index("category")[["cost_eur"]].rename(
                    columns={"cost_eur": "NRE Cost €"})
                st.bar_chart(chart_data, color="#9C27B0")
            with c_tbl:
                disp = summary.copy()
                disp["cost_eur"] = disp["cost_eur"].map(lambda x: fmt(x, 0))
                disp["hours"]    = disp["hours"].map(lambda x: f"{x:,.0f} h")
                st.dataframe(disp.rename(columns={"category": "Category",
                                                   "cost_eur": "Cost €",
                                                   "hours":    "Hours",
                                                   "items":    "Items"}),
                             use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — AMORTISATION CURVE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_amort:
        st.subheader("NRE amortisation vs production volume")
        st.caption("Shows how the NRE cost per unit decreases as the production run grows.")

        if edited.empty or nre_total(edited) == 0:
            st.info("Enter NRE costs in the Register tab to see the amortisation curve.")
        else:
            total_nre = nre_total(edited)
            max_qty   = st.slider("Max quantity to plot", 5, 500, 100, 5)

            amort_rows = []
            for q in range(1, max_qty + 1):
                amort_rows.append({
                    "qty":          q,
                    "nre_per_unit": round(total_nre / q, 2),
                })
            amort_df = pd.DataFrame(amort_rows)

            current_npu = total_nre / num_units if num_units > 0 else total_nre
            st.metric(f"NRE per unit at {num_units} unit(s)", fmt(current_npu, 2))

            chart_df = amort_df.set_index("qty")
            st.line_chart(chart_df, color="#4CAF50")

            with st.expander("📄 Full amortisation table"):
                amort_df["nre_per_unit"] = amort_df["nre_per_unit"].map(lambda x: fmt(x, 2))
                st.dataframe(amort_df.rename(columns={"qty": "Units", "nre_per_unit": "NRE per unit €"}),
                             use_container_width=True, hide_index=True)


guard(main)
