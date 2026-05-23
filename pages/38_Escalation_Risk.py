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


def _safe_material_spend(df: pd.DataFrame, mats: pd.DataFrame, base_cost: float) -> pd.DataFrame:
    """Build a safe commodity spend table for legacy and mixed schemas."""

    material_cols = [c for c in ["material_id", "commodity"] if c in mats.columns]

    if "material_id" not in material_cols:
        return pd.DataFrame({
            "commodity": ["GENERAL"],
            "material_cost": [base_cost],
        })

    merged = df.merge(
        mats[material_cols].copy(),
        on="material_id",
        how="left",
    )

    commodity_candidates = [
        c for c in ["commodity", "commodity_x", "commodity_y"]
        if c in merged.columns
    ]

    if not commodity_candidates:
        merged["commodity"] = "GENERAL"
    else:
        primary = commodity_candidates[0]
        merged["commodity"] = (
            merged[primary]
            .astype("string")
            .fillna("GENERAL")
            .replace("", "GENERAL")
        )

    if "material_cost" not in merged.columns:
        merged["material_cost"] = 0.0

    return (
        merged.groupby("commodity", dropna=False)["material_cost"]
        .sum()
        .reset_index()
    )


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

    with tab_esc:
        st.subheader("Commodity price escalation indices")

        commodities = sorted(mats["commodity"].dropna().unique().tolist()) if "commodity" in mats.columns else []

        if esc_df.empty and commodities:
            seed_esc = pd.DataFrame({
                "esc_id":        [f"ESC-{i+1:03d}" for i in range(len(commodities))],
                "applies_to":    commodities,
                "description":   commodities,
                "index_name":    [""] * len(commodities),
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

        if not edited_esc.empty:
            st.divider()
            st.subheader("Escalation impact on material cost")

            mat_spend = _safe_material_spend(df, mats, base_cost)

            rows_esc = []
            for _, row in edited_esc.iterrows():
                pct = escalation_pct(row)
                commod = str(row.get("applies_to", "")).upper()

                if commod in ("GENERAL", "LABOUR", "ALL"):
                    spend = base_cost
                else:
                    matched = mat_spend[
                        mat_spend["commodity"].astype(str).str.upper() == commod
                    ]
                    spend = float(matched["material_cost"].sum()) if not matched.empty else 0.0

                rows_esc.append({
                    "Commodity": row.get("applies_to", ""),
                    "Escalation %": f"{pct*100:+.2f}%",
                    "Current spend €": fmt(spend, 0),
                    "Delta €": fmt(spend * pct, 0),
                })

            esc_impact = pd.DataFrame(rows_esc)

            st.dataframe(
                esc_impact,
                use_container_width=True,
                hide_index=True,
            )


guard(main)
