"""
Change Orders — scope variation register, cost/revenue impact tracking and margin analysis.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.change_orders import (
    CO_CATEGORIES, CO_DELIVERY_IMPACTS, CO_REQUESTORS, CO_STATUSES,
    SCHEMA_CHANGE_ORDERS,
)
from utils.currency import fmt, fmt_delta
from utils.io import df_to_excel_bytes, load_change_orders, save_sheet
from utils.nav import home_button
from utils.project import load_project_meta
from utils.safe import guard
from utils.style import inject_css, page_header


_STATUS_COLOURS = {
    "Approved": ("#66bb6a", "#00180a"),
    "Pending":  ("#f0a500", "#2a1f00"),
    "Rejected": ("#5a7a9a", "#0a111a"),
    "On hold":  ("#ff7043", "#2a0f00"),
}


def _kpi_row(df: pd.DataFrame, base_contract_value: float) -> None:
    """Render the top KPI metrics row."""
    total_cos        = len(df)
    approved         = df[df["status"] == "Approved"]
    pending          = df[df["status"] == "Pending"]

    approved_rev_delta = pd.to_numeric(approved["revenue_delta_eur"], errors="coerce").fillna(0).sum()
    pending_count      = len(pending)
    total_cost_delta   = pd.to_numeric(df["cost_delta_eur"], errors="coerce").fillna(0).sum()
    total_rev_delta    = pd.to_numeric(approved["revenue_delta_eur"], errors="coerce").fillna(0).sum()
    net_margin_impact  = total_rev_delta - total_cost_delta

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total COs", total_cos)
    k2.metric("Approved revenue delta", fmt(approved_rev_delta))
    k3.metric("Pending COs", pending_count)
    k4.metric(
        "Total cost delta",
        fmt(total_cost_delta),
        delta=fmt_delta(total_cost_delta) if total_cost_delta != 0 else None,
        delta_color="inverse",
    )
    k5.metric(
        "Net margin impact",
        fmt(net_margin_impact),
        delta=fmt_delta(net_margin_impact) if net_margin_impact != 0 else None,
        delta_color="normal",
    )


def _tab_register(df: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Change Order Register")
    st.caption(
        "Log all scope changes, design changes, and commercial variations. "
        "Track cost and revenue impact for each CO."
    )

    # Status legend
    st.markdown(
        " &nbsp;".join(
            f"<span style='background:{bg}; border:1px solid {fg}; border-radius:4px; "
            f"padding:2px 8px; font-size:0.8em; color:{fg}; font-weight:600;'>{s}</span>"
            for s, (fg, bg) in _STATUS_COLOURS.items()
        ),
        unsafe_allow_html=True,
    )
    st.markdown("")

    if df.empty:
        seed = pd.DataFrame([
            {
                "co_id":              "CO-001",
                "title":              "Additional sea-fastening brackets",
                "description":        "Customer requests 4 additional sea-fastening points",
                "requested_by":       "Customer",
                "category":           "Scope addition",
                "cost_delta_eur":     3500.0,
                "revenue_delta_eur":  4500.0,
                "status":             "Pending",
                "submitted_date":     "",
                "approved_date":      "",
                "approved_by":        "",
                "impact_on_delivery": "None",
                "notes":              "",
            }
        ])
    else:
        seed = df.copy()

    edited = st.data_editor(
        seed,
        column_config={
            "co_id":              st.column_config.TextColumn("CO ID", width="small"),
            "title":              st.column_config.TextColumn("Title", width="medium"),
            "description":        st.column_config.TextColumn("Description", width="large"),
            "requested_by":       st.column_config.SelectboxColumn("Requested by", options=CO_REQUESTORS),
            "category":           st.column_config.SelectboxColumn("Category", options=CO_CATEGORIES),
            "cost_delta_eur":     st.column_config.NumberColumn(
                "Cost delta €", format="%.2f",
                help="Positive = cost increase, negative = cost reduction",
            ),
            "revenue_delta_eur":  st.column_config.NumberColumn(
                "Revenue delta €", format="%.2f",
                help="Positive = additional revenue",
            ),
            "status":             st.column_config.SelectboxColumn("Status", options=CO_STATUSES),
            "submitted_date":     st.column_config.TextColumn("Submitted", help="YYYY-MM-DD"),
            "approved_date":      st.column_config.TextColumn("Approved", help="YYYY-MM-DD"),
            "approved_by":        st.column_config.TextColumn("Approved by", width="small"),
            "impact_on_delivery": st.column_config.SelectboxColumn(
                "Delivery impact", options=CO_DELIVERY_IMPACTS,
            ),
            "notes":              st.column_config.TextColumn("Notes"),
        },
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="co_register_editor",
    )

    col_save, col_dl, _ = st.columns([1, 1, 4])
    if col_save.button("💾 Save change orders", use_container_width=True):
        save_sheet(edited, "change_orders")
        st.success("Change orders saved.")
        st.cache_data.clear()

    xl_bytes = df_to_excel_bytes(edited, "ChangeOrders")
    col_dl.download_button(
        "⬇ Download", data=xl_bytes,
        file_name="change_orders.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    return edited


def _tab_summary(df: pd.DataFrame) -> None:
    st.subheader("Summary Analysis")

    if df.empty:
        st.info("No change orders to summarise.")
        return

    df = df.copy()
    df["cost_delta_eur"]    = pd.to_numeric(df["cost_delta_eur"], errors="coerce").fillna(0)
    df["revenue_delta_eur"] = pd.to_numeric(df["revenue_delta_eur"], errors="coerce").fillna(0)

    col_left, col_right = st.columns(2)

    # ── By status ─────────────────────────────────────────────────────────────
    with col_left:
        st.markdown("**By status**")
        status_summary = (
            df.groupby("status", dropna=False)
              .agg(
                  Count=("co_id", "count"),
                  Cost_Delta=("cost_delta_eur", "sum"),
                  Revenue_Delta=("revenue_delta_eur", "sum"),
              )
              .reset_index()
        )
        status_summary["Net margin"] = status_summary["Revenue_Delta"] - status_summary["Cost_Delta"]
        status_display = status_summary.copy()
        for col in ["Cost_Delta", "Revenue_Delta", "Net margin"]:
            status_display[col] = status_display[col].map(lambda x: fmt(x, 0))
        status_display.columns = ["Status", "Count", "Cost delta", "Revenue delta", "Net margin"]
        st.dataframe(status_display, use_container_width=True, hide_index=True)

        # Bar chart of cost delta by status
        if not status_summary.empty:
            chart_data = status_summary.set_index("status")[["Cost_Delta", "Revenue_Delta"]]
            st.bar_chart(chart_data, color=["#F44336", "#4da6ff"])

    # ── By category ───────────────────────────────────────────────────────────
    with col_right:
        st.markdown("**By category**")
        cat_summary = (
            df.groupby("category", dropna=False)
              .agg(
                  Count=("co_id", "count"),
                  Cost_Delta=("cost_delta_eur", "sum"),
                  Revenue_Delta=("revenue_delta_eur", "sum"),
              )
              .reset_index()
        )
        cat_summary["Net margin"] = cat_summary["Revenue_Delta"] - cat_summary["Cost_Delta"]
        cat_display = cat_summary.copy()
        for col in ["Cost_Delta", "Revenue_Delta", "Net margin"]:
            cat_display[col] = cat_display[col].map(lambda x: fmt(x, 0))
        cat_display.columns = ["Category", "Count", "Cost delta", "Revenue delta", "Net margin"]
        st.dataframe(cat_display, use_container_width=True, hide_index=True)

        if not cat_summary.empty:
            chart_cat = cat_summary.set_index("category")[["Cost_Delta", "Revenue_Delta"]]
            st.bar_chart(chart_cat, color=["#F44336", "#4da6ff"])

    # ── Delivery impact breakdown ─────────────────────────────────────────────
    st.divider()
    st.markdown("**Delivery impact distribution**")
    impact_counts = df["impact_on_delivery"].value_counts().reset_index()
    impact_counts.columns = ["Impact", "Count"]
    st.dataframe(impact_counts, use_container_width=True, hide_index=True)


def _tab_impact(df: pd.DataFrame, base_contract_value: float) -> None:
    st.subheader("Revised Sell Price & Margin Impact")
    st.caption(
        "Shows the effect of approved change orders on the revised contract value. "
        "Pending COs are shown separately as potential upside/downside."
    )

    if df.empty:
        st.info("No change orders to analyse.")
        return

    df = df.copy()
    df["cost_delta_eur"]    = pd.to_numeric(df["cost_delta_eur"], errors="coerce").fillna(0)
    df["revenue_delta_eur"] = pd.to_numeric(df["revenue_delta_eur"], errors="coerce").fillna(0)

    approved = df[df["status"] == "Approved"]
    pending  = df[df["status"] == "Pending"]

    approved_rev  = float(approved["revenue_delta_eur"].sum())
    approved_cost = float(approved["cost_delta_eur"].sum())
    pending_rev   = float(pending["revenue_delta_eur"].sum())
    pending_cost  = float(pending["cost_delta_eur"].sum())

    revised_contract = base_contract_value + approved_rev
    revised_cost_delta = approved_cost

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Approved COs — effect on contract**")
        rows = [
            {"Item": "Original contract value",    "Amount": fmt(base_contract_value)},
            {"Item": "Approved revenue changes",   "Amount": fmt_delta(approved_rev)},
            {"Item": "Revised contract value",     "Amount": fmt(revised_contract)},
            {"Item": "",                           "Amount": ""},
            {"Item": "Approved cost increases",    "Amount": fmt_delta(approved_cost)},
            {"Item": "Net margin impact (approved)", "Amount": fmt_delta(approved_rev - approved_cost)},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**Pending COs — potential impact**")
        rows_p = [
            {"Item": "Pending revenue upside",    "Amount": fmt_delta(pending_rev)},
            {"Item": "Pending cost exposure",     "Amount": fmt_delta(pending_cost)},
            {"Item": "Pending net margin",        "Amount": fmt_delta(pending_rev - pending_cost)},
            {"Item": "",                          "Amount": ""},
            {"Item": "Revised contract (if all approved)", "Amount": fmt(base_contract_value + approved_rev + pending_rev)},
        ]
        st.dataframe(pd.DataFrame(rows_p), use_container_width=True, hide_index=True)

    # ── Approved COs detail ───────────────────────────────────────────────────
    if not approved.empty:
        st.divider()
        st.markdown("**Approved change orders detail**")
        detail = approved[["co_id", "title", "category", "cost_delta_eur", "revenue_delta_eur",
                            "approved_date", "approved_by", "impact_on_delivery"]].copy()
        detail["margin_delta"] = detail["revenue_delta_eur"] - detail["cost_delta_eur"]
        for col in ["cost_delta_eur", "revenue_delta_eur", "margin_delta"]:
            detail[col] = detail[col].map(lambda x: fmt(x, 0))
        detail.columns = ["CO ID", "Title", "Category", "Cost delta", "Revenue delta",
                          "Approved", "By", "Delivery impact", "Margin delta"]
        st.dataframe(detail, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Change Orders", layout="wide", page_icon="🔄")
    inject_css()
    home_button()

    meta = load_project_meta()
    base_contract_value = float(meta.get("contract_value_eur", 0.0))
    customer = str(meta.get("customer", ""))

    page_header(
        title="Change Orders",
        icon="🔄",
        caption="Scope variation register — track cost, revenue and margin impact of each change.",
        project=customer or "",
    )

    raw_df = load_change_orders()

    # ── KPI row ───────────────────────────────────────────────────────────────
    if not raw_df.empty:
        _kpi_row(raw_df, base_contract_value)
        st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_reg, tab_sum, tab_impact = st.tabs([
        "📝 Register",
        "📊 Summary",
        "💹 Impact",
    ])

    with tab_reg:
        edited_df = _tab_register(raw_df)

    with tab_sum:
        _tab_summary(edited_df if not edited_df.empty else raw_df)

    with tab_impact:
        _tab_impact(edited_df if not edited_df.empty else raw_df, base_contract_value)


guard(main)
