"""
Escalation & Risk module.
Material escalation, contingency allowance and risk register.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.escalation import (
    RISK_CATEGORIES,
    RISK_STATUSES,
    SCHEMA_ESCALATION,
    escalation_pct,
    risk_expected_value,
    risk_summary,
)
from utils.io import (
    load_bom,
    load_escalation,
    load_materials,
    load_processes,
    load_quotes,
    load_risk,
    save_sheet,
)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

MATURITY_CONTINGENCY = {
    "RoM (±30%)": 0.25,
    "Budget (±15%)": 0.12,
    "Definitive (±5%)": 0.05,
    "Firm": 0.02,
}


def _material_groups(mats: pd.DataFrame) -> list[str]:
    """Return safe material escalation groups without requiring commodity."""
    for column in ["commodity", "Commodity", "commodity_group", "material_group", "category"]:
        if column in mats.columns:
            values = mats[column].astype("string").fillna("General").replace("", "General")
            return sorted(values.dropna().unique().tolist())
    return ["General"]


def _safe_material_spend(df: pd.DataFrame, mats: pd.DataFrame, base_cost: float) -> pd.DataFrame:
    """Build a safe material-group spend table without direct commodity dependency."""
    if "material_id" not in df.columns or "material_id" not in mats.columns:
        return pd.DataFrame({"group": ["GENERAL"], "material_cost": [base_cost]})

    group_column = None
    for candidate in ["commodity", "Commodity", "commodity_group", "material_group", "category"]:
        if candidate in mats.columns:
            group_column = candidate
            break

    if group_column is None:
        return pd.DataFrame({"group": ["GENERAL"], "material_cost": [base_cost]})

    merged = df.merge(
        mats[["material_id", group_column]].copy(),
        on="material_id",
        how="left",
    )

    merged["group"] = (
        merged[group_column]
        .astype("string")
        .fillna("GENERAL")
        .replace("", "GENERAL")
        .str.upper()
    )

    if "material_cost" not in merged.columns:
        merged["material_cost"] = 0.0

    return merged.groupby("group", dropna=False)["material_cost"].sum().reset_index()


def main() -> None:
    st.set_page_config(page_title="Escalation & Risk", layout="wide", page_icon="📉")
    inject_css()
    home_button()
    page_header(
        title="Escalation & Risk",
        icon="📉",
        caption="Material price escalation, contingency allowance and risk register.",
    )

    try:
        mats = load_materials()
        procs = load_processes()
        bom = load_bom()
        quotes = load_quotes()
        df = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM data: {exc}")
        st.stop()

    esc_df = load_escalation()
    risk_df = load_risk()

    base_cost = float(df["base_cost"].sum()) if "base_cost" in df.columns else 0.0
    base_sell = float(df["total_cost"].sum()) if "total_cost" in df.columns else 0.0
    material_total = float(df["material_cost"].sum()) if "material_cost" in df.columns else 0.0

    tab_esc, tab_risk, tab_cont = st.tabs([
        "📈 Material Escalation",
        "⚠️ Risk Register",
        "🎲 Contingency",
    ])

    with tab_esc:
        st.subheader("Material price escalation indices")
        st.caption("Track market movement against estimate baseline. Missing group data falls back to General.")

        groups = _material_groups(mats)
        if esc_df.empty and groups:
            seed_esc = pd.DataFrame({
                "esc_id": [f"ESC-{i + 1:03d}" for i in range(len(groups))],
                "applies_to": groups,
                "description": groups,
                "index_name": [""] * len(groups),
                "base_value": [100.0] * len(groups),
                "current_value": [100.0] * len(groups),
                "base_date": [""] * len(groups),
                "override_pct": [0.0] * len(groups),
                "notes": [""] * len(groups),
            })
        else:
            seed_esc = esc_df.copy() if not esc_df.empty else pd.DataFrame(columns=list(SCHEMA_ESCALATION.keys()))

        edited_esc = st.data_editor(
            seed_esc,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="esc_editor",
        )

        if st.button("💾 Save escalation", use_container_width=True):
            save_sheet(edited_esc, "escalation")
            st.success("Escalation indices saved.")
            st.cache_data.clear()

        if not edited_esc.empty:
            st.divider()
            st.subheader("Escalation impact on material cost")

            spend_by_group = _safe_material_spend(df, mats, material_total or base_cost)
            rows = []
            total_delta = 0.0

            for _, row in edited_esc.iterrows():
                pct = escalation_pct(row)
                applies_to = str(row.get("applies_to", "General"))
                key = applies_to.upper()

                if key in {"GENERAL", "ALL", "LABOUR", "LABOR"}:
                    spend = material_total or base_cost
                else:
                    matched = spend_by_group[spend_by_group["group"].astype(str).str.upper() == key]
                    spend = float(matched["material_cost"].sum()) if not matched.empty else 0.0

                delta = spend * pct
                total_delta += delta

                rows.append({
                    "Group": applies_to,
                    "Escalation %": f"{pct * 100:+.2f}%",
                    "Current spend €": fmt(spend, 0),
                    "Delta €": fmt(delta, 0),
                    "Adjusted €": fmt(spend + delta, 0),
                })

            c1, c2, c3 = st.columns(3)
            c1.metric("Base material cost", fmt(material_total, 0))
            c2.metric("Escalation delta", fmt(total_delta, 0))
            c3.metric("Escalated material", fmt(material_total + total_delta, 0))

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_risk:
        st.subheader("Risk register")
        seed_risk = risk_df.copy() if not risk_df.empty else pd.DataFrame(columns=[
            "risk_id", "category", "title", "description", "probability",
            "cost_impact_eur", "status", "mitigation", "owner", "notes",
        ])
        edited_risk = st.data_editor(
            seed_risk,
            column_config={
                "category": st.column_config.SelectboxColumn("Category", options=RISK_CATEGORIES),
                "status": st.column_config.SelectboxColumn("Status", options=RISK_STATUSES),
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="risk_editor",
        )

        if st.button("💾 Save risk register", use_container_width=True):
            save_sheet(edited_risk, "risk")
            st.success("Risk register saved.")
            st.cache_data.clear()

        if not edited_risk.empty:
            rs = risk_summary(edited_risk)
            open_risks = rs[rs["status"].astype(str).str.upper() != "CLOSED"] if "status" in rs.columns else rs
            expected = risk_expected_value(edited_risk)
            max_exposure = float(pd.to_numeric(open_risks.get("cost_impact_eur", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Open risks", len(open_risks))
            k2.metric("Max exposure", fmt(max_exposure, 0))
            k3.metric("Expected value", fmt(expected, 0))
            k4.metric("Risk % of sell", f"{expected / base_sell * 100:.1f}%" if base_sell else "—")

    with tab_cont:
        st.subheader("Contingency allowance")
        maturity = "Budget (±15%)"
        default_cont_pct = MATURITY_CONTINGENCY.get(maturity, 0.12)
        cont_pct = st.number_input("Contingency %", min_value=0.0, max_value=1.0, value=default_cont_pct, step=0.01)
        contingency_eur = base_cost * cont_pct

        c1, c2, c3 = st.columns(3)
        c1.metric("Base cost", fmt(base_cost, 0))
        c2.metric("Contingency", fmt(contingency_eur, 0), delta=f"{cont_pct * 100:.1f}%")
        c3.metric("Cost with contingency", fmt(base_cost + contingency_eur, 0))


guard(main)
