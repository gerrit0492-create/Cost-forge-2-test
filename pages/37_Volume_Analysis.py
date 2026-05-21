"""
Volume & Batch Analysis — Wright's learning curve, batch pricing, break-even.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import load_bom, load_materials, load_processes, load_quotes, load_nre
from utils.learning import (
    batch_cost_table, learning_curve_series,
    optimal_qty_for_target, wright_unit_cost,
)
from utils.nav import home_button
from utils.nre import nre_total
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header


def main() -> None:
    st.set_page_config(page_title="Volume Analysis", layout="wide", page_icon="📈")
    inject_css()
    home_button()
    page_header(
        title="Volume Analysis",
        icon="📈",
        caption="Learning curve, batch pricing and break-even analysis across production volumes.",
    )

    # ── Load cost data ────────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM data: {exc}")
        st.stop()

    nre_df = load_nre()

    base_unit_cost = df["total_cost"].sum()
    base_mat_cost  = df["material_cost"].sum()
    base_proc_cost = df["process_cost"].sum()
    fixed_nre      = nre_total(nre_df)

    # ── Sidebar parameters ────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Learning curve parameters")
    learning_rate = st.sidebar.slider(
        "Learning rate",
        min_value=0.70, max_value=1.00, value=0.90, step=0.01,
        format="%.2f",
        help="Fraction of cost retained per doubling of cumulative volume. "
             "0.85 = 15% reduction per doubling (typical marine manufacturing).",
    )
    nre_override = st.sidebar.number_input(
        "NRE to amortise €",
        min_value=0.0,
        value=float(round(fixed_nre, 0)),
        step=1000.0,
        format="%.0f",
        help="Pre-filled from NRE register. Override for what-if scenarios.",
    )
    target_price = st.sidebar.number_input(
        "Target unit price €",
        min_value=0.0,
        value=float(round(base_unit_cost * 0.80, 0)),
        step=1000.0,
        format="%.0f",
        help="Volume required to achieve this sell price.",
    )
    max_qty = st.sidebar.selectbox(
        "Max quantity to model",
        [10, 25, 50, 100, 200, 500],
        index=2,
    )

    # ── Build batch table ─────────────────────────────────────────────────────
    quantities = [1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 300, 500]
    quantities = [q for q in quantities if q <= max_qty]
    if max_qty not in quantities:
        quantities.append(max_qty)

    batch_df = batch_cost_table(
        base_unit_cost=base_unit_cost,
        learning_rate=learning_rate,
        quantities=quantities,
        fixed_nre=nre_override,
    )

    opt_qty = optimal_qty_for_target(
        base_unit_cost=base_unit_cost,
        learning_rate=learning_rate,
        target_unit_cost=target_price,
        fixed_nre=nre_override,
        max_qty=max_qty,
    )

    # ── KPI row ───────────────────────────────────────────────────────────────
    cost_at_10 = wright_unit_cost(base_unit_cost, learning_rate, 10)
    cost_at_50 = wright_unit_cost(base_unit_cost, learning_rate, min(50, max_qty))

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Unit cost (1st article)",   fmt(base_unit_cost, 0))
    k2.metric(f"Unit cost at 10",          fmt(cost_at_10, 0),
              delta=f"{(cost_at_10/base_unit_cost-1)*100:+.1f}%",
              delta_color="inverse")
    k3.metric(f"Unit cost at {min(50,max_qty)}",
              fmt(cost_at_50, 0),
              delta=f"{(cost_at_50/base_unit_cost-1)*100:+.1f}%",
              delta_color="inverse")
    k4.metric("NRE to amortise",           fmt(nre_override, 0))
    k5.metric("Qty for target price",
              str(opt_qty) if opt_qty else "Not achievable",
              delta=f"≤ {fmt(target_price, 0)}" if opt_qty else "increase volume",
              delta_color="normal" if opt_qty else "off")

    tab_curve, tab_batch, tab_break = st.tabs(
        ["📉 Learning Curve", "📋 Batch Cost Table", "🎯 Break-Even"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — LEARNING CURVE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_curve:
        st.subheader("Unit cost vs cumulative production quantity")
        st.caption(
            f"Learning rate **{learning_rate:.0%}** — cost reduces by "
            f"**{(1-learning_rate)*100:.0f}%** with each doubling of volume."
        )

        curve_df = learning_curve_series(base_unit_cost, learning_rate, max_qty)
        curve_df["all_in"] = (curve_df["unit_cost"] + nre_override / curve_df["qty"]).round(2)

        chart_data = curve_df.set_index("qty")[["unit_cost", "all_in"]].rename(
            columns={"unit_cost": "Direct unit cost €", "all_in": "All-in (incl. NRE) €"}
        )
        if target_price > 0:
            chart_data["Target price €"] = target_price

        st.line_chart(chart_data, color=["#2196F3", "#FF9800", "#F44336"])

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Learning rate",      f"{learning_rate:.0%}")
        col_b.metric("Process learning",   f"{(1 - learning_rate) * 100:.0f}% per doubling")
        col_c.metric("Material share",
                     f"{base_mat_cost/base_unit_cost*100:.0f}%",
                     delta="insensitive to learning curve", delta_color="off")

        st.info(
            "ℹ️ **Note:** Learning curves primarily affect **process costs** (machining, assembly). "
            "Material costs are commodity-driven and less sensitive to production volume. "
            "Consider modelling material cost separately with supplier volume discounts."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — BATCH COST TABLE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_batch:
        st.subheader("Batch pricing table")
        st.caption("Full cost breakdown at each production quantity break.")

        display = batch_df.copy()
        display["unit_cost"]       = display["unit_cost"].map(lambda x: fmt(x, 0))
        display["total_direct"]    = display["total_direct"].map(lambda x: fmt(x, 0))
        display["nre_amortised"]   = display["nre_amortised"].map(lambda x: fmt(x, 2))
        display["all_in_per_unit"] = display["all_in_per_unit"].map(lambda x: fmt(x, 0))
        display["all_in_total"]    = display["all_in_total"].map(lambda x: fmt(x, 0))
        display["vs_qty1_pct"]     = display["vs_qty1_pct"].map(lambda x: f"{x:+.1f}%")

        st.dataframe(
            display.rename(columns={
                "qty":             "Units",
                "unit_cost":       "Direct unit €",
                "total_direct":    "Total direct €",
                "nre_amortised":   "NRE / unit €",
                "all_in_per_unit": "All-in / unit €",
                "all_in_total":    "All-in total €",
                "vs_qty1_pct":     "vs 1 unit",
            }).drop(columns=["setup_amortised"], errors="ignore"),
            use_container_width=True, hide_index=True,
        )

        from utils.io import df_to_excel_bytes
        st.download_button(
            "⬇️ Download batch table",
            data=df_to_excel_bytes(batch_df, "BatchPricing"),
            file_name="batch_pricing.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — BREAK-EVEN
    # ══════════════════════════════════════════════════════════════════════════
    with tab_break:
        st.subheader("Break-even & target price analysis")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Volume needed to hit target price**")
            if target_price <= 0:
                st.info("Set a target price in the sidebar.")
            elif not opt_qty:
                st.error(
                    f"Target {fmt(target_price, 0)} not achievable within {max_qty} units. "
                    "Increase max quantity or raise the target."
                )
            else:
                st.success(
                    f"Target **{fmt(target_price, 0)}** achieved at **{opt_qty} units**."
                )
                achieved_cost = wright_unit_cost(base_unit_cost, learning_rate, opt_qty) + nre_override / opt_qty
                st.metric("All-in cost at target qty", fmt(achieved_cost, 0))

        with c2:
            st.markdown("**Price at key quantities**")
            key_qtys = [1, 5, 10, 25, 50, 100]
            key_qtys = [q for q in key_qtys if q <= max_qty]
            key_rows = []
            for q in key_qtys:
                uc  = wright_unit_cost(base_unit_cost, learning_rate, q)
                ain = uc + nre_override / q
                key_rows.append({
                    "Units":          q,
                    "Direct unit €":  fmt(uc, 0),
                    "All-in / unit €": fmt(ain, 0),
                    "vs 1st article": f"{(ain/base_unit_cost - 1)*100:+.1f}%",
                })
            st.dataframe(pd.DataFrame(key_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Process vs material cost sensitivity")
        st.caption(
            "Material costs are commodity-driven; process costs benefit from learning. "
            "This split shows how much of your cost is learnable."
        )

        mat_pct  = base_mat_cost / base_unit_cost * 100 if base_unit_cost > 0 else 0
        proc_pct = base_proc_cost / base_unit_cost * 100 if base_unit_cost > 0 else 0

        sens_data = pd.DataFrame({
            "Cost element": ["Material (commodity)", "Process (learnable)"],
            "% of total":   [mat_pct, proc_pct],
        })
        st.bar_chart(sens_data.set_index("Cost element"), color="#FF9800")
        st.caption(
            f"**{proc_pct:.0f}%** of cost is process-driven → maximum achievable reduction "
            f"= **{proc_pct * (1 - learning_rate):.1f}%** per volume doubling."
        )


guard(main)
