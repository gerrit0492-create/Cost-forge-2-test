"""
Contract & Cash Flow — milestone payments, commercial terms, cost outflows, cash flow chart.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.contract import (
    INCOTERMS, WARRANTY_OPTIONS,
    apg_cost, bond_cost, cash_flow_series, default_milestones,
    ld_exposure, retention_amount, working_capital_peak,
    SCHEMA_MILESTONES, SCHEMA_COST_TIMELINE,
)
from utils.currency import fmt
from utils.io import df_to_excel_bytes, load_cost_timeline, load_milestones, save_sheet
from utils.nav import home_button
from utils.project import load_project_meta, save_project_meta
from utils.safe import guard
from utils.style import inject_css, page_header


def _load_contract_meta() -> dict:
    meta = load_project_meta()
    defaults = {
        "contract_number":      "",
        "customer":             "",
        "contract_value_eur":   0.0,
        "signing_date":         "",
        "delivery_date":        "",
        "warranty_months":      12,
        "incoterms":            "DAP",
        "ld_pct_per_week":      0.005,
        "ld_cap_pct":           0.10,
        "retention_pct":        0.05,
        "apg_required":         False,
        "apg_fee_pct":          0.015,
        "bond_required":        False,
        "bond_pct":             0.10,
        "bond_fee_pct":         0.015,
    }
    for k, v in defaults.items():
        meta.setdefault(k, v)
    return meta


def _tab_contract_terms(meta: dict) -> None:
    st.subheader("Commercial Terms")
    st.caption("Define the contract parameters. These are saved to project.json and used across the module.")

    col1, col2 = st.columns(2)
    with col1:
        contract_number = st.text_input("Contract number", value=str(meta.get("contract_number", "")))
        customer        = st.text_input("Customer / Client", value=str(meta.get("customer", "")))
        contract_value  = st.number_input(
            "Contract value (€)", min_value=0.0, step=1000.0,
            value=float(meta.get("contract_value_eur", 0.0)), format="%.2f",
        )
        incoterms_val = meta.get("incoterms", "DAP")
        incoterms = st.selectbox(
            "Incoterms", INCOTERMS,
            index=INCOTERMS.index(incoterms_val) if incoterms_val in INCOTERMS else INCOTERMS.index("DAP"),
        )

    with col2:
        signing_date  = st.text_input("Signing date (YYYY-MM-DD)", value=str(meta.get("signing_date", "")))
        delivery_date = st.text_input("Delivery date (YYYY-MM-DD)", value=str(meta.get("delivery_date", "")))
        warranty_val  = int(meta.get("warranty_months", 12))
        if warranty_val not in WARRANTY_OPTIONS:
            warranty_val = 12
        warranty_months = st.selectbox(
            "Warranty period (months)", WARRANTY_OPTIONS,
            index=WARRANTY_OPTIONS.index(warranty_val),
        )

    st.divider()
    st.subheader("Penalty & Financial Conditions")
    col3, col4, col5 = st.columns(3)
    with col3:
        ld_pct_per_week = st.number_input(
            "LD rate (%/week)", min_value=0.0, max_value=0.10, step=0.001,
            value=float(meta.get("ld_pct_per_week", 0.005)), format="%.3f",
            help="Liquidated damages as % of contract value per week of delay",
        )
        ld_cap_pct = st.number_input(
            "LD cap (%)", min_value=0.0, max_value=0.50, step=0.01,
            value=float(meta.get("ld_cap_pct", 0.10)), format="%.2f",
            help="Maximum total LD as % of contract value",
        )
    with col4:
        retention_pct = st.number_input(
            "Retention (%)", min_value=0.0, max_value=0.30, step=0.01,
            value=float(meta.get("retention_pct", 0.05)), format="%.2f",
            help="% of contract value held until warranty release",
        )
    with col5:
        delay_weeks_input = st.number_input(
            "Delay scenario (weeks)", min_value=0, max_value=52, value=4,
            help="Hypothetical delay weeks for LD exposure calculation",
        )

    st.divider()
    st.subheader("Bank Instruments")
    col6, col7 = st.columns(2)
    with col6:
        apg_required = st.toggle("APG / Advance Payment Guarantee required", value=bool(meta.get("apg_required", False)))
        apg_fee_pct  = st.number_input(
            "APG fee (%/year)", min_value=0.0, max_value=0.10, step=0.001,
            value=float(meta.get("apg_fee_pct", 0.015)), format="%.3f",
            disabled=not apg_required,
        )
    with col7:
        bond_required = st.toggle("Performance bond required", value=bool(meta.get("bond_required", False)))
        bond_pct = st.number_input(
            "Bond value (%)", min_value=0.0, max_value=0.30, step=0.01,
            value=float(meta.get("bond_pct", 0.10)), format="%.2f",
            disabled=not bond_required,
            help="Bond face value as % of contract value",
        )
        bond_fee_pct = st.number_input(
            "Bond fee (%/year)", min_value=0.0, max_value=0.10, step=0.001,
            value=float(meta.get("bond_fee_pct", 0.015)), format="%.3f",
            disabled=not bond_required,
        )

    # ── Save ──────────────────────────────────────────────────────────────────
    if st.button("💾 Save contract terms", use_container_width=False):
        save_project_meta(
            contract_number=contract_number,
            customer=customer,
            contract_value_eur=contract_value,
            signing_date=signing_date,
            delivery_date=delivery_date,
            warranty_months=warranty_months,
            incoterms=incoterms,
            ld_pct_per_week=ld_pct_per_week,
            ld_cap_pct=ld_cap_pct,
            retention_pct=retention_pct,
            apg_required=apg_required,
            apg_fee_pct=apg_fee_pct,
            bond_required=bond_required,
            bond_pct=bond_pct,
            bond_fee_pct=bond_fee_pct,
        )
        st.success("Contract terms saved to project.json.")

    # ── Commercial exposure summary ──────────────────────────────────────────
    st.divider()
    st.subheader("Commercial Exposure Summary")

    warranty_months_int = int(warranty_months)

    ld_max      = ld_exposure(contract_value, ld_pct_per_week, ld_cap_pct, delay_weeks_input)
    ret_amt     = retention_amount(contract_value, retention_pct)
    advance_pct = 0.30  # typical first milestone
    apg_c       = apg_cost(contract_value * advance_pct, apg_fee_pct, warranty_months_int) if apg_required else 0.0
    bond_c      = bond_cost(contract_value, bond_pct, bond_fee_pct, warranty_months_int) if bond_required else 0.0

    ec1, ec2, ec3, ec4 = st.columns(4)
    ec1.metric(
        f"LD max ({delay_weeks_input}w delay)",
        fmt(ld_max),
        delta=f"{ld_cap_pct*100:.0f}% cap",
        delta_color="off",
    )
    ec2.metric(
        "Retention held",
        fmt(ret_amt),
        delta=f"{retention_pct*100:.0f}% of contract",
        delta_color="off",
    )
    ec3.metric(
        "APG cost" if apg_required else "APG cost (n/a)",
        fmt(apg_c),
        delta="APG not required" if not apg_required else f"{warranty_months_int}m",
        delta_color="off",
    )
    ec4.metric(
        "Bond cost" if bond_required else "Bond cost (n/a)",
        fmt(bond_c),
        delta="Bond not required" if not bond_required else f"{warranty_months_int}m",
        delta_color="off",
    )


def _tab_milestones(meta: dict) -> pd.DataFrame:
    contract_value = float(meta.get("contract_value_eur", 0.0))

    st.subheader("Milestone Payment Schedule")
    st.caption(
        "Define payment milestones. Pre-populated with a standard 30/30/30/10 schedule. "
        "Mark as **Received: Yes** when payment is collected."
    )

    raw = load_milestones()
    if raw.empty:
        seed = default_milestones(contract_value)
    else:
        seed = raw.copy()
        # Re-scale amounts if contract value changed
        if contract_value > 0:
            for i, row in seed.iterrows():
                pct = float(row.get("pct_of_contract") or 0)
                if pct > 0 and float(row.get("amount_eur") or 0) == 0:
                    seed.at[i, "amount_eur"] = round(contract_value * pct, 2)

    edited = st.data_editor(
        seed,
        column_config={
            "milestone_id":    st.column_config.TextColumn("ID", width="small"),
            "description":     st.column_config.TextColumn("Description", width="medium"),
            "trigger_event":   st.column_config.TextColumn("Trigger event", width="large"),
            "pct_of_contract": st.column_config.NumberColumn(
                "% of contract", min_value=0.0, max_value=1.0, format="%.2f",
                help="Decimal: 0.30 = 30%",
            ),
            "amount_eur":      st.column_config.NumberColumn("Amount €", min_value=0.0, format="%.2f"),
            "planned_date":    st.column_config.TextColumn("Planned date", help="YYYY-MM-DD"),
            "actual_date":     st.column_config.TextColumn("Actual date", help="YYYY-MM-DD"),
            "received":        st.column_config.SelectboxColumn("Received", options=["Yes", "No", ""]),
            "notes":           st.column_config.TextColumn("Notes"),
        },
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="milestones_editor",
    )

    col_save, col_dl, _ = st.columns([1, 1, 4])
    if col_save.button("💾 Save milestones", use_container_width=True):
        save_sheet(edited, "milestones")
        st.success("Milestones saved.")
        st.cache_data.clear()

    xl_bytes = df_to_excel_bytes(edited, "Milestones")
    col_dl.download_button(
        "⬇ Download", data=xl_bytes,
        file_name="milestones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # ── KPI row ───────────────────────────────────────────────────────────────
    st.divider()
    total_amount = pd.to_numeric(edited["amount_eur"], errors="coerce").fillna(0).sum()
    received_mask = edited["received"].str.upper() == "YES"
    received_amt  = pd.to_numeric(edited.loc[received_mask, "amount_eur"], errors="coerce").fillna(0).sum()
    outstanding   = total_amount - received_amt
    pct_collected = received_amt / total_amount * 100 if total_amount > 0 else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Contract value", fmt(contract_value))
    k2.metric("Received so far", fmt(received_amt))
    k3.metric("Outstanding", fmt(outstanding))
    k4.metric("% collected", f"{pct_collected:.1f}%")

    # ── Bar chart ─────────────────────────────────────────────────────────────
    if not edited.empty:
        chart_df = edited[["description", "amount_eur"]].copy()
        chart_df["amount_eur"] = pd.to_numeric(chart_df["amount_eur"], errors="coerce").fillna(0)
        chart_df = chart_df.set_index("description")
        st.bar_chart(chart_df, color="#4da6ff")

    return edited


def _tab_cost_timeline(meta: dict) -> pd.DataFrame:
    st.subheader("Cost Outflow Timeline")
    st.caption(
        "Plan when costs are paid out. Add rows for material purchases, subcontracts, "
        "transport, NRE, etc. This feeds the cash flow model."
    )

    raw = load_cost_timeline()
    if raw.empty:
        # Try to seed from BOM if available
        try:
            from utils.io import load_bom, load_materials, load_processes, load_quotes
            from utils.pricing import compute_costs
            from utils.quotes import apply_best_quotes
            mats   = load_materials()
            procs  = load_processes()
            bom    = load_bom()
            quotes = load_quotes()
            df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)

            signing_date = str(meta.get("signing_date", ""))
            rows = []
            for i, row in df.iterrows():
                base_date = signing_date or pd.Timestamp.today().strftime("%Y-%m-%d")
                try:
                    lead = int(row.get("lead_time_days") or 60)
                except Exception:
                    lead = 60
                try:
                    planned = (pd.Timestamp(base_date) + pd.Timedelta(days=lead)).strftime("%Y-%m-%d")
                except Exception:
                    planned = ""

                mat_cost = float(row.get("material_cost") or 0)
                proc_cost = float(row.get("process_cost") or 0)
                total = mat_cost + proc_cost
                if total <= 0:
                    continue

                rows.append({
                    "cost_id":      f"CT-{i+1:03d}",
                    "category":     "Material",
                    "description":  str(row.get("part_name", f"Line {i+1}")),
                    "amount_eur":   round(total, 2),
                    "planned_date": planned,
                    "actual_date":  "",
                    "paid":         "No",
                    "notes":        "",
                })
            seed = pd.DataFrame(rows) if rows else pd.DataFrame(columns=list(SCHEMA_COST_TIMELINE.keys()))
        except Exception:
            seed = pd.DataFrame(columns=list(SCHEMA_COST_TIMELINE.keys()))
    else:
        seed = raw.copy()

    edited = st.data_editor(
        seed,
        column_config={
            "cost_id":      st.column_config.TextColumn("ID", width="small"),
            "category":     st.column_config.SelectboxColumn(
                "Category", options=["Material", "Process", "NRE", "Transport", "Other"],
            ),
            "description":  st.column_config.TextColumn("Description", width="large"),
            "amount_eur":   st.column_config.NumberColumn("Amount €", min_value=0.0, format="%.2f"),
            "planned_date": st.column_config.TextColumn("Planned date", help="YYYY-MM-DD"),
            "actual_date":  st.column_config.TextColumn("Actual date", help="YYYY-MM-DD"),
            "paid":         st.column_config.SelectboxColumn("Paid", options=["Yes", "No", ""]),
            "notes":        st.column_config.TextColumn("Notes"),
        },
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="cost_timeline_editor",
    )

    col_save, col_dl, _ = st.columns([1, 1, 4])
    if col_save.button("💾 Save cost timeline", use_container_width=True):
        save_sheet(edited, "cost_timeline")
        st.success("Cost timeline saved.")
        st.cache_data.clear()

    xl_bytes = df_to_excel_bytes(edited, "CostTimeline")
    col_dl.download_button(
        "⬇ Download", data=xl_bytes,
        file_name="cost_timeline.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.divider()
    total_costs = pd.to_numeric(edited["amount_eur"], errors="coerce").fillna(0).sum()
    paid_mask   = edited["paid"].str.upper() == "YES"
    paid_amt    = pd.to_numeric(edited.loc[paid_mask, "amount_eur"], errors="coerce").fillna(0).sum()
    unpaid_amt  = total_costs - paid_amt

    k1, k2, k3 = st.columns(3)
    k1.metric("Total planned outflows", fmt(total_costs))
    k2.metric("Already paid", fmt(paid_amt))
    k3.metric("Still to pay", fmt(unpaid_amt))

    return edited


def _tab_cash_flow(milestones: pd.DataFrame, cost_timeline: pd.DataFrame, meta: dict) -> None:
    st.subheader("Monthly Cash Flow Model")
    st.caption(
        "Monthly view of receipts (milestone payments in) vs costs (outflows). "
        "Requires planned/actual dates on milestones and cost timeline."
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        project_start = st.text_input(
            "Project start (YYYY-MM-DD)",
            value=str(meta.get("signing_date", "")) or pd.Timestamp.today().strftime("%Y-%m-%d"),
        )
    with col_b:
        project_end = st.text_input(
            "Project end (YYYY-MM-DD)",
            value=str(meta.get("delivery_date", "")) or
                  (pd.Timestamp.today() + pd.DateOffset(months=18)).strftime("%Y-%m-%d"),
        )
    with col_c:
        interest_rate = st.number_input(
            "Financing interest rate (%/year)",
            min_value=0.0, max_value=0.30, value=0.06, step=0.005, format="%.3f",
            help="Used to estimate financing cost on peak working capital",
        )

    cf = cash_flow_series(milestones, cost_timeline, project_start, project_end)

    if cf.empty:
        st.warning(
            "No cash flow data. Add planned dates to milestones and cost timeline entries, "
            "and ensure project start/end dates are valid."
        )
        return

    # ── KPI metrics ───────────────────────────────────────────────────────────
    peak_wc, peak_month = working_capital_peak(cf)
    total_receipts = float(cf["receipts"].sum())
    total_costs    = float(cf["costs"].sum())

    # Estimate months in negative territory for financing cost
    neg_months = int((cf["cumulative"] < 0).sum())
    financing_cost = peak_wc * interest_rate * (neg_months / 12) if neg_months > 0 else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total receipts", fmt(total_receipts))
    k2.metric("Total outflows", fmt(total_costs))
    k3.metric("Peak WC need", fmt(peak_wc), delta=f"Month: {peak_month}", delta_color="off")
    k4.metric(
        "Est. financing cost",
        fmt(financing_cost),
        delta=f"{interest_rate*100:.1f}%/yr × {neg_months}m",
        delta_color="off",
    )

    # ── Chart ─────────────────────────────────────────────────────────────────
    st.divider()
    chart_df = cf.copy()
    chart_df["month_str"] = chart_df["month"].dt.strftime("%Y-%m")
    chart_df = chart_df.set_index("month_str")[["receipts", "costs", "net", "cumulative"]]

    st.subheader("Cash flow chart")
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.caption("Receipts vs costs per month")
        st.bar_chart(chart_df[["receipts", "costs"]], color=["#4da6ff", "#F44336"])
    with col_chart2:
        st.caption("Cumulative cash position")
        st.line_chart(chart_df[["cumulative"]], color=["#66bb6a"])

    # ── Detail table ──────────────────────────────────────────────────────────
    st.divider()
    display_cf = cf.copy()
    display_cf["month"] = display_cf["month"].dt.strftime("%Y-%m")
    for col in ["receipts", "costs", "net", "cumulative"]:
        display_cf[col] = display_cf[col].map(lambda x: fmt(x, 0))
    st.dataframe(display_cf, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Contract & Cash Flow", layout="wide", page_icon="💰")
    inject_css()
    home_button()

    meta = _load_contract_meta()
    customer = meta.get("customer", "")
    contract_value = float(meta.get("contract_value_eur", 0.0))

    page_header(
        title="Contract & Cash Flow",
        icon="💰",
        caption="Milestone payments, commercial terms, cost outflows and working capital analysis.",
        project=customer or "",
    )

    tab_terms, tab_milestones, tab_costs, tab_cf = st.tabs([
        "📋 Contract Terms",
        "📅 Milestone Payments",
        "💸 Cost Timeline",
        "📊 Cash Flow Chart",
    ])

    with tab_terms:
        _tab_contract_terms(meta)

    # Reload meta after possible save in tab_terms
    meta = _load_contract_meta()

    with tab_milestones:
        milestones_df = _tab_milestones(meta)

    with tab_costs:
        cost_timeline_df = _tab_cost_timeline(meta)

    with tab_cf:
        _tab_cash_flow(milestones_df, cost_timeline_df, meta)


guard(main)
