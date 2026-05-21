"""
Full Cost Waterfall — the senior cost engineer's integration view.
Aggregates all cost modules into a single P&L-style waterfall.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.escalation import risk_expected_value, total_escalation_cost, escalation_pct
from utils.io import (df_to_excel_bytes, load_bom, load_escalation,
                      load_materials, load_nre, load_outbound, load_processes,
                      load_quotes, load_risk, load_transport)
from utils.nav import home_button
from utils.nre import nre_per_unit, nre_total
from utils.pricing import compute_costs
from utils.project import load_project_meta
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header
from utils.transport import compute_inbound_costs, outbound_cost
from utils.waterfall import build_waterfall, pnl_summary, waterfall_per_unit

MATURITY_CONTINGENCY = {
    "RoM (±30%)":        0.25,
    "Budget (±15%)":     0.12,
    "Definitive (±5%)":  0.05,
    "Firm":              0.02,
}


def main() -> None:
    st.set_page_config(page_title="Full Cost Summary", layout="wide", page_icon="🌊")
    inject_css()
    home_button()

    meta     = load_project_meta()
    maturity = meta.get("maturity", "Budget (±15%)")
    project  = meta.get("name", "")

    page_header(
        title="Full Cost Summary",
        icon="🌊",
        caption="Complete cost waterfall — all elements from material to delivery.",
        project=project,
        maturity=maturity,
    )

    # ── Load all data ─────────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM data: {exc}")
        st.stop()

    nre_df      = load_nre()
    transport_df = load_transport()
    outbound_df  = load_outbound()
    esc_df       = load_escalation()
    risk_df      = load_risk()

    # ── Sidebar — scenario toggles ────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Scenario toggles")

    num_units = st.sidebar.number_input(
        "Production volume (units)", min_value=1, value=1, step=1,
    )
    include_nre       = st.sidebar.toggle("Include NRE / Engineering", value=not nre_df.empty)
    include_transport = st.sidebar.toggle("Include Transport & Logistics", value=not transport_df.empty)
    include_escalation = st.sidebar.toggle("Include Escalation", value=not esc_df.empty)
    include_contingency = st.sidebar.toggle("Include Contingency", value=True)

    cont_method = st.sidebar.selectbox(
        "Contingency method",
        ["Maturity-driven", "Manual %"],
        help="How to calculate contingency.",
    )
    if cont_method == "Manual %":
        cont_pct = st.sidebar.slider("Contingency %", 0, 50, 10) / 100
    else:
        cont_pct = MATURITY_CONTINGENCY.get(maturity, 0.12)

    # ── Compute all elements ──────────────────────────────────────────────────
    n = max(int(num_units), 1)

    base_mat  = df["material_cost"].sum()
    base_proc = df["process_cost"].sum()
    base_oh   = df["overhead"].sum()
    base_sell = df["total_cost"].sum()
    base_mar  = df["margin"].sum()
    base_cost_ex_margin = base_sell - base_mar

    # Margin% from data
    margin_pct = base_mar / base_cost_ex_margin if base_cost_ex_margin > 0 else 0

    qty_s      = pd.to_numeric(df["qty"], errors="coerce").fillna(1)
    total_mass = (qty_s * df["mass_kg"].fillna(0)).sum()

    # NRE
    nre_run = nre_per_unit(nre_df, n) * n if include_nre else 0.0

    # Inbound freight & duties
    if include_transport and not transport_df.empty:
        with_in        = compute_inbound_costs(df, transport_df)
        in_freight_tot = with_in["inbound_freight_eur"].sum()
        duties_tot     = with_in["duties_eur"].sum()
    else:
        in_freight_tot = duties_tot = 0.0

    # Outbound
    if include_transport and not outbound_df.empty:
        route = outbound_df.iloc[0]
        ob    = outbound_cost(total_mass * n, base_sell * n, route)
        ob_cost = ob["total"]
    else:
        ob_cost = 0.0

    # Escalation delta
    esc_delta = 0.0
    if include_escalation and not esc_df.empty:
        for _, row in esc_df.iterrows():
            pct   = escalation_pct(row)
            commod = str(row.get("applies_to", "")).upper()
            if commod in ("GENERAL", "ALL"):
                spend = base_cost_ex_margin
            elif "commodity" in df.columns:
                matched = df[df.get("commodity", pd.Series(dtype=str)).str.upper() == commod]
                spend   = float(matched["material_cost"].sum()) if not matched.empty else 0.0
            else:
                spend = 0.0
            esc_delta += spend * pct

    # Contingency
    if include_contingency:
        pre_cont = (base_mat + in_freight_tot + duties_tot + base_proc +
                    base_oh + nre_run + ob_cost + esc_delta)
        cont_eur = pre_cont * cont_pct
    else:
        cont_eur = 0.0

    # ── Build waterfall ───────────────────────────────────────────────────────
    wf = build_waterfall(
        material_cost    = base_mat * n,
        inbound_freight  = in_freight_tot * n,
        duties           = duties_tot * n,
        process_cost     = base_proc * n,
        overhead         = base_oh * n,
        nre_per_run      = nre_run,
        outbound_freight = ob_cost,
        escalation_delta = esc_delta * n,
        contingency      = cont_eur,
        margin_pct       = margin_pct,
        num_units        = n,
    )

    sell_total = float(wf[wf["Step"].str.startswith("══")]["Amount €"].iloc[0]) \
        if not wf[wf["Step"].str.startswith("══")].empty else base_sell * n

    # ── KPI row ───────────────────────────────────────────────────────────────
    ppu = sell_total / n if n > 0 else sell_total
    base_ppu = base_sell

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Sell price (run)",   fmt(sell_total, 0))
    k2.metric("Sell price / unit",  fmt(ppu, 0),
              delta=f"{(ppu/base_ppu-1)*100:+.1f}% vs BOM-only" if base_ppu else None,
              delta_color="inverse")
    k3.metric("Transport & duties", fmt((in_freight_tot + duties_tot + ob_cost) * n, 0))
    k4.metric("NRE (run)",          fmt(nre_run, 0))
    k5.metric("Escalation",         fmt(esc_delta * n, 0))
    k6.metric("Contingency",        fmt(cont_eur, 0),
              delta=f"{cont_pct*100:.0f}%", delta_color="off")

    st.divider()

    tab_wf, tab_pnl, tab_detail, tab_sub = st.tabs(
        ["🌊 Waterfall", "💼 P&L Summary", "📋 Cost Detail", "🔧 Subsystem Split"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — WATERFALL CHART
    # ══════════════════════════════════════════════════════════════════════════
    with tab_wf:
        st.subheader(f"Cost build-up waterfall — {n} unit(s)")

        view = st.radio("View", ["Run total", "Per unit"], horizontal=True)
        wf_show = waterfall_per_unit(wf, n) if view == "Per unit" else wf

        # Separate structural rows from data rows
        data_rows = wf_show[~wf_show["Step"].str.startswith("──") &
                            ~wf_show["Step"].str.startswith("══")].copy()

        col_chart, col_tbl = st.columns([3, 2])
        with col_chart:
            chart_data = data_rows.set_index("Step")[["Amount €"]].rename(
                columns={"Amount €": "Cost €"}
            )
            st.bar_chart(chart_data, color="#2196F3")

        with col_tbl:
            # Style total rows
            def _highlight(row):
                if "══" in str(row["Step"]) or "──" in str(row["Step"]):
                    return ["font-weight:bold"] * len(row)
                return [""] * len(row)

            disp = wf_show.copy()
            disp["Amount €"]     = disp["Amount €"].map(lambda x: fmt(x, 0))
            disp["Cumulative €"] = disp["Cumulative €"].map(lambda x: fmt(x, 0))
            disp["% of sell"]    = disp["% of sell"].map(lambda x: f"{x:.1f}%")
            st.dataframe(
                disp.rename(columns={"Step": "Cost element"}),
                use_container_width=True, hide_index=True,
            )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — P&L SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    with tab_pnl:
        st.subheader("P&L summary")

        pnl = pnl_summary(wf, n)
        if not pnl.empty:
            disp_pnl = pnl.copy()
            disp_pnl["€ (run)"] = disp_pnl["€ (run)"].map(
                lambda x: fmt(x, 0) if isinstance(x, (int, float)) else x
            )
            disp_pnl["Running €"] = disp_pnl["Running €"].map(
                lambda x: fmt(x, 0) if isinstance(x, (int, float)) and x else "—"
            )
            st.dataframe(disp_pnl, use_container_width=True, hide_index=True)

        gross_margin_eur = (
            float(wf[wf["Step"] == "10. Margin"]["Amount €"].iloc[0])
            if not wf[wf["Step"] == "10. Margin"].empty else base_mar * n
        )
        gm_pct = gross_margin_eur / sell_total * 100 if sell_total else 0

        st.metric("Gross margin", fmt(gross_margin_eur, 0),
                  delta=f"{gm_pct:.1f}%", delta_color="off")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — COST DETAIL
    # ══════════════════════════════════════════════════════════════════════════
    with tab_detail:
        st.subheader("Cost assumptions & inputs")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**BOM cost summary**")
            bom_rows = [
                ("Material (purchase)",  base_mat),
                ("Machining & labour",   base_proc),
                ("Overhead",             base_oh),
                ("Margin",               base_mar),
                ("Total sell price",     base_sell),
            ]
            st.dataframe(
                pd.DataFrame(bom_rows, columns=["Element", "€ / unit"]).assign(
                    **{"€ / unit": lambda d: d["€ / unit"].map(lambda x: fmt(x, 0))}
                ),
                use_container_width=True, hide_index=True,
            )

            st.markdown("**Transport assumptions**")
            t_rows = [
                ("Inbound freight + pkg", fmt(in_freight_tot, 2)),
                ("Import duties",         fmt(duties_tot, 2)),
                ("Outbound freight",      fmt(ob_cost / n if n else ob_cost, 2)),
            ]
            st.dataframe(pd.DataFrame(t_rows, columns=["Element", "€ / unit"]),
                         use_container_width=True, hide_index=True)

        with col_b:
            st.markdown("**NRE assumptions**")
            n_rows = [
                ("Total NRE",            fmt(nre_total(nre_df), 0)),
                ("Volume",               str(n)),
                ("NRE per unit",         fmt(nre_per_unit(nre_df, n), 2)),
            ]
            st.dataframe(pd.DataFrame(n_rows, columns=["Item", "Value"]),
                         use_container_width=True, hide_index=True)

            st.markdown("**Risk & contingency**")
            r_rows = [
                ("Maturity",             maturity),
                ("Contingency %",        f"{cont_pct*100:.0f}%"),
                ("Contingency €",        fmt(cont_eur, 0)),
                ("Escalation delta €",   fmt(esc_delta * n, 0)),
            ]
            st.dataframe(pd.DataFrame(r_rows, columns=["Item", "Value"]),
                         use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — SUBSYSTEM SPLIT
    # ══════════════════════════════════════════════════════════════════════════
    with tab_sub:
        st.subheader("Cost by subsystem")

        from utils.completeness import WATERJET_SUBSYSTEMS

        def _prefix(lid):
            u = str(lid).upper()
            for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
                if u.startswith(p):
                    return p
            return "?"

        sub_df = df.copy()
        sub_df["subsystem"] = sub_df["line_id"].apply(_prefix)
        sub_names = {p: f"{info['icon']} {info['name']}" for p, info in WATERJET_SUBSYSTEMS.items()}

        agg = (
            sub_df.groupby("subsystem")[["material_cost", "process_cost", "overhead", "margin", "total_cost"]]
            .sum()
            .reset_index()
        )
        agg["name"] = agg["subsystem"].map(lambda p: sub_names.get(p, p))
        agg["Share %"] = (agg["total_cost"] / agg["total_cost"].sum() * 100).map(lambda x: f"{x:.1f}%")

        col_c, col_d = st.columns([3, 2])
        with col_c:
            chart = agg.set_index("name")[["material_cost", "process_cost", "overhead", "margin"]].rename(
                columns={"material_cost": "Material", "process_cost": "Process",
                         "overhead": "Overhead", "margin": "Margin"}
            )
            st.bar_chart(chart, color=["#2196F3", "#FF9800", "#9C27B0", "#4CAF50"])
        with col_d:
            tbl = agg[["name", "total_cost", "Share %"]].copy()
            tbl["total_cost"] = tbl["total_cost"].map(lambda x: fmt(x, 0))
            st.dataframe(tbl.rename(columns={"name": "Subsystem", "total_cost": "Total €"}),
                         use_container_width=True, hide_index=True)

    # ── Download all ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("⬇️ Export full cost summary")

    def _build_excel_export() -> bytes:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            wf.to_excel(w, sheet_name="Waterfall", index=False)
            pnl_summary(wf, n).to_excel(w, sheet_name="P&L Summary", index=False)
            df[["line_id", "material_id", "material_cost", "process_cost",
                "overhead", "margin", "total_cost"]].to_excel(w, sheet_name="BOM Detail", index=False)
            assumptions = pd.DataFrame([
                ("Maturity",             maturity),
                ("Production volume",    n),
                ("Total NRE €",          round(nre_total(nre_df), 2)),
                ("NRE per unit €",       round(nre_per_unit(nre_df, n), 2)),
                ("Inbound freight €",    round(in_freight_tot, 2)),
                ("Import duties €",      round(duties_tot, 2)),
                ("Outbound freight €",   round(ob_cost, 2)),
                ("Escalation delta €",   round(esc_delta, 2)),
                ("Contingency %",        f"{cont_pct*100:.0f}%"),
                ("Contingency €",        round(cont_eur, 2)),
                ("Sell price / unit €",  round(ppu, 2)),
            ], columns=["Assumption", "Value"])
            assumptions.to_excel(w, sheet_name="Assumptions", index=False)
        return buf.getvalue()

    st.download_button(
        "⬇️ Export full cost summary (Excel)",
        data=_build_excel_export(),
        file_name="full_cost_summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


guard(main)
