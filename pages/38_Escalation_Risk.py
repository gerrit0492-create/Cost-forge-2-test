"""
Escalation & Risk module.
Commodity price escalation indices, contingency and risk register.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.escalation import (
    RISK_CATEGORIES, RISK_STATUSES, SCHEMA_ESCALATION, SCHEMA_RISK,
    escalation_pct, risk_expected_value, risk_summary, total_escalation_cost,
)
from utils.io import (load_bom, load_escalation, load_materials, load_processes,
                      load_quotes, load_risk, save_sheet)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

MATURITY_CONTINGENCY = {
    "RoM (±30%)":        0.25,
    "Budget (±15%)":     0.12,
    "Definitive (±5%)":  0.05,
    "Firm":              0.02,
}


def main() -> None:
    st.set_page_config(page_title="Escalation & Risk", layout="wide", page_icon="📉")
    inject_css()
    home_button()
    page_header(
        title="Escalation & Risk",
        icon="📉",
        caption="Material price escalation, contingency allowance and risk register.",
    )

    # ── Load ──────────────────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM data: {exc}")
        st.stop()

    esc_df  = load_escalation()
    risk_df = load_risk()

    base_cost = df["base_cost"].sum()
    base_sell = df["total_cost"].sum()

    tab_esc, tab_risk, tab_cont = st.tabs(
        ["📈 Material Escalation", "⚠️ Risk Register", "🎲 Contingency"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — ESCALATION
    # ══════════════════════════════════════════════════════════════════════════
    with tab_esc:
        st.subheader("Commodity price escalation indices")
        st.caption(
            "Track market price movement vs your estimate base date. "
            "`Base value` = index at estimate date. `Current value` = latest observed. "
            "Leave `Override %` blank to auto-calculate from index values."
        )

        # Seed from unique commodities in materials
        commodities = sorted(mats["commodity"].dropna().unique().tolist()) if "commodity" in mats.columns else []
        if esc_df.empty and commodities:
            seed_esc = pd.DataFrame({
                "esc_id":        [f"ESC-{i+1:03d}" for i in range(len(commodities))],
                "applies_to":    commodities,
                "description":   commodities,
                "index_name":    ["" ] * len(commodities),
                "base_value":    [100.0] * len(commodities),
                "current_value": [100.0] * len(commodities),
                "base_date":     [""] * len(commodities),
                "override_pct":  [0.0] * len(commodities),
                "notes":         [""] * len(commodities),
            })
        else:
            seed_esc = esc_df.copy() if not esc_df.empty else pd.DataFrame(columns=list(SCHEMA_ESCALATION.keys()))

        edited_esc = st.data_editor(
            seed_esc,
            column_config={
                "esc_id":        st.column_config.TextColumn("ID", width="small"),
                "applies_to":    st.column_config.TextColumn("Commodity / Material", width="medium"),
                "description":   st.column_config.TextColumn("Description"),
                "index_name":    st.column_config.TextColumn("Index name", help="e.g. LME Copper, Steel HRC EU"),
                "base_value":    st.column_config.NumberColumn("Base index", min_value=0.0, format="%.2f"),
                "current_value": st.column_config.NumberColumn("Current index", min_value=0.0, format="%.2f"),
                "base_date":     st.column_config.TextColumn("Base date", help="ISO format: 2024-01-01"),
                "override_pct":  st.column_config.NumberColumn(
                                     "Override %", min_value=-1.0, max_value=5.0, format="%.3f",
                                     help="Manual override as decimal (0.05 = 5%). Overrides index calculation."),
                "notes":         st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="esc_editor",
        )

        c1, _ = st.columns([1, 4])
        if c1.button("💾 Save escalation", use_container_width=True):
            save_sheet(edited_esc, "escalation")
            st.success("Escalation indices saved.")
            st.cache_data.clear()

        # ── Escalation impact ─────────────────────────────────────────────────
        if not edited_esc.empty:
            st.divider()
            st.subheader("Escalation impact on material cost")

            # Compute per-commodity material spend
            if "commodity" in mats.columns:
                mat_spend = (
                    df.merge(mats[["material_id", "commodity"]], on="material_id", how="left")
                      .groupby("commodity", dropna=False)["material_cost"]
                      .sum()
                      .reset_index()
                )
            else:
                mat_spend = pd.DataFrame({"commodity": ["ALL"], "material_cost": [df["material_cost"].sum()]})

            rows_esc = []
            for _, row in edited_esc.iterrows():
                pct   = escalation_pct(row)
                commod = str(row.get("applies_to", "")).upper()
                # Match spend
                if commod in ("GENERAL", "LABOUR", "ALL"):
                    spend = base_cost
                else:
                    matched = mat_spend[mat_spend["commodity"].str.upper() == commod]
                    spend   = float(matched["material_cost"].sum()) if not matched.empty else 0.0

                rows_esc.append({
                    "Commodity":       row.get("applies_to", ""),
                    "Index":           row.get("index_name", ""),
                    "Escalation %":    f"{pct*100:+.2f}%",
                    "Current spend €": fmt(spend, 0),
                    "Delta €":         fmt(spend * pct, 0),
                    "Adjusted €":      fmt(spend * (1 + pct), 0),
                })

            esc_impact = pd.DataFrame(rows_esc)
            total_delta = sum(float(r["Delta €"].replace(",", "").replace("€", "").replace(" ", "").replace("−", "-"))
                              for _, r in esc_impact.iterrows()
                              if r["Delta €"] not in ("—", "")) if not esc_impact.empty else 0

            k1, k2, k3 = st.columns(3)
            k1.metric("Base material cost", fmt(df["material_cost"].sum(), 0))
            k2.metric("Escalation delta",   fmt(total_delta, 0),
                      delta=f"{total_delta/df['material_cost'].sum()*100:+.1f}%"
                      if df["material_cost"].sum() > 0 else "—",
                      delta_color="inverse" if total_delta > 0 else "normal")
            k3.metric("Escalated material", fmt(df["material_cost"].sum() + total_delta, 0))

            st.dataframe(esc_impact, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — RISK REGISTER
    # ══════════════════════════════════════════════════════════════════════════
    with tab_risk:
        st.subheader("Risk register")
        st.caption(
            "Log cost risks, estimate probability (0–1) and maximum cost impact. "
            "Expected value = Probability × Impact. Closed risks are excluded from totals."
        )

        if risk_df.empty:
            seed_risk = pd.DataFrame([
                {
                    "risk_id":         "R-001",
                    "category":        "Material",
                    "title":           "Nickel price surge",
                    "description":     "NAB material cost could increase if nickel spot rises above €15/kg",
                    "probability":     0.3,
                    "cost_impact_eur": df["material_cost"].sum() * 0.1 if df["material_cost"].sum() > 0 else 10000,
                    "status":          "Open",
                    "mitigation":      "Back-to-back material supply contract with price cap",
                    "owner":           "Procurement",
                    "notes":           "",
                },
                {
                    "risk_id":         "R-002",
                    "category":        "Schedule",
                    "title":           "Machining capacity",
                    "description":     "Main machining centre congested in Q3 — delivery delay risk",
                    "probability":     0.2,
                    "cost_impact_eur": 15000.0,
                    "status":          "Open",
                    "mitigation":      "Qualified alternative subcontractor identified",
                    "owner":           "Engineering",
                    "notes":           "",
                },
                {
                    "risk_id":         "R-003",
                    "category":        "Commercial",
                    "title":           "Exchange rate EUR/USD",
                    "description":     "Components quoted in USD — exchange rate movement risk",
                    "probability":     0.4,
                    "cost_impact_eur": 5000.0,
                    "status":          "Open",
                    "mitigation":      "Forward contract on USD exposure",
                    "owner":           "Finance",
                    "notes":           "",
                },
            ])
        else:
            seed_risk = risk_df.copy()

        edited_risk = st.data_editor(
            seed_risk,
            column_config={
                "risk_id":         st.column_config.TextColumn("ID", width="small"),
                "category":        st.column_config.SelectboxColumn("Category", options=RISK_CATEGORIES),
                "title":           st.column_config.TextColumn("Title", width="medium"),
                "description":     st.column_config.TextColumn("Description", width="large"),
                "probability":     st.column_config.NumberColumn(
                                       "Probability", min_value=0.0, max_value=1.0, format="%.2f",
                                       help="0 = impossible, 1 = certain"),
                "cost_impact_eur": st.column_config.NumberColumn("Max impact €", min_value=0.0, format="%.0f"),
                "status":          st.column_config.SelectboxColumn("Status", options=RISK_STATUSES),
                "mitigation":      st.column_config.TextColumn("Mitigation"),
                "owner":           st.column_config.TextColumn("Owner", width="small"),
                "notes":           st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="risk_editor",
        )

        c1, _ = st.columns([1, 4])
        if c1.button("💾 Save risk register", use_container_width=True):
            save_sheet(edited_risk, "risk")
            st.success("Risk register saved.")
            st.cache_data.clear()

        # ── Risk summary ──────────────────────────────────────────────────────
        if not edited_risk.empty:
            st.divider()
            rs = risk_summary(edited_risk)
            open_risks = rs[rs["status"].str.upper() != "CLOSED"]
            total_exp  = float((pd.to_numeric(open_risks["probability"], errors="coerce").fillna(0) *
                                 pd.to_numeric(open_risks["cost_impact_eur"], errors="coerce").fillna(0)).sum())
            total_exp_v = risk_expected_value(edited_risk)
            max_exposure = float(pd.to_numeric(open_risks["cost_impact_eur"], errors="coerce").fillna(0).sum())

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Open risks",         len(open_risks))
            k2.metric("Max exposure",       fmt(max_exposure, 0))
            k3.metric("Expected value",     fmt(total_exp_v, 0),
                      delta="prob × impact",
                      delta_color="off")
            k4.metric("Risk % of sell",
                      f"{total_exp_v / base_sell * 100:.1f}%" if base_sell else "—")

            # Risk matrix summary by category
            if "category" in open_risks.columns:
                open_risks = open_risks.copy()
                open_risks["_ev"] = (
                    pd.to_numeric(open_risks["probability"], errors="coerce").fillna(0) *
                    pd.to_numeric(open_risks["cost_impact_eur"], errors="coerce").fillna(0)
                )
                cat_sum = (
                    open_risks.groupby("category")["_ev"]
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index()
                    .rename(columns={"category": "Category", "_ev": "Expected Value €"})
                )
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.bar_chart(cat_sum.set_index("Category"), color="#F44336")
                with col_b:
                    cat_sum["Expected Value €"] = cat_sum["Expected Value €"].map(lambda x: fmt(x, 0))
                    st.dataframe(cat_sum, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — CONTINGENCY
    # ══════════════════════════════════════════════════════════════════════════
    with tab_cont:
        st.subheader("Contingency allowance")
        st.caption(
            "Contingency is added to the estimate to cover inherent uncertainty at the current maturity level. "
            "It is separate from the commercial margin and from quantified risk."
        )

        from utils.project import load_project_meta
        meta    = load_project_meta()
        maturity = meta.get("maturity", "Budget (±15%)")

        # Maturity-driven default
        default_cont_pct = MATURITY_CONTINGENCY.get(maturity, 0.12)

        col_a, col_b = st.columns(2)
        with col_a:
            cont_method = st.radio(
                "Contingency method",
                ["% of base cost (maturity-driven)", "% of base cost (manual)", "Risk expected value"],
                help="Choose how to calculate the contingency allowance.",
            )
        with col_b:
            if cont_method == "% of base cost (maturity-driven)":
                cont_pct = default_cont_pct
                st.info(
                    f"Maturity: **{maturity}** → recommended contingency: **{cont_pct*100:.0f}%** of base cost."
                )
            elif cont_method == "% of base cost (manual)":
                cont_pct_input = st.number_input(
                    "Contingency %", min_value=0.0, max_value=1.0,
                    value=default_cont_pct, step=0.01, format="%.2f",
                )
                cont_pct = cont_pct_input
            else:
                ev = risk_expected_value(edited_risk) if not edited_risk.empty else 0.0
                cont_pct = ev / base_cost if base_cost > 0 else 0
                st.info(
                    f"Risk expected value: **{fmt(ev, 0)}** = "
                    f"**{cont_pct*100:.1f}%** of base cost."
                )

        contingency_eur = base_cost * cont_pct
        base_with_cont  = base_cost + contingency_eur

        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Base cost",           fmt(base_cost, 0))
        k2.metric("Contingency",         fmt(contingency_eur, 0),
                  delta=f"{cont_pct*100:.1f}%", delta_color="off")
        k3.metric("Cost with contingency", fmt(base_with_cont, 0))
        k4.metric("Contingency vs sell",
                  f"{contingency_eur/base_sell*100:.1f}%" if base_sell else "—")

        st.markdown("---")
        st.markdown("**Maturity-contingency reference table**")
        ref_rows = []
        for mat_level, pct in MATURITY_CONTINGENCY.items():
            cont_eur = base_cost * pct
            ref_rows.append({
                "Maturity":      mat_level,
                "Contingency %": f"{pct*100:.0f}%",
                "Contingency €": fmt(cont_eur, 0),
                "Total €":       fmt(base_cost + cont_eur, 0),
                "Active":        "✓" if mat_level == maturity else "",
            })
        st.dataframe(pd.DataFrame(ref_rows), use_container_width=True, hide_index=True)


guard(main)
