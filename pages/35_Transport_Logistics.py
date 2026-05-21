"""
Transport & Logistics cost module.
Configure inbound freight rates, packaging, import duties and outbound shipping.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import (load_bom, load_materials, load_processes, load_quotes,
                      load_transport, load_outbound, save_sheet)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header
from utils.transport import (
    FREIGHT_MODES, INCOTERMS, SCHEMA_TRANSPORT, SCHEMA_OUTBOUND,
    compute_inbound_costs, outbound_cost, default_transport_df, default_outbound_df,
)


def main() -> None:
    st.set_page_config(page_title="Transport & Logistics", layout="wide", page_icon="🚢")
    inject_css()
    home_button()
    page_header(
        title="Transport & Logistics",
        icon="🚢",
        caption="Inbound freight, packaging, import duties and outbound shipping costs.",
    )

    # ── Load base costs ───────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM data: {exc}")
        st.stop()

    transport_df = load_transport()
    outbound_df  = load_outbound()

    total_sell  = df["total_cost"].sum()
    qty_s       = pd.to_numeric(df["qty"], errors="coerce").fillna(1)
    total_mass  = (qty_s * df["mass_kg"].fillna(0)).sum()

    tab_in, tab_out, tab_summary = st.tabs(
        ["📦 Inbound Freight & Duties", "🚢 Outbound Shipping", "📊 Landed Cost Summary"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — INBOUND
    # ══════════════════════════════════════════════════════════════════════════
    with tab_in:
        st.subheader("Inbound freight rates per material")
        st.caption(
            "Set freight cost (€/kg), minimum charge, packaging cost and import duty per material. "
            "Leave blank for materials with no inbound freight cost."
        )

        # Seed the editor with all unique material IDs from the BOM
        mat_ids = sorted(df["material_id"].dropna().unique().tolist())
        if transport_df.empty:
            seed = pd.DataFrame({
                "material_id":      mat_ids,
                "supplier":         [""] * len(mat_ids),
                "freight_mode":     ["ROAD"] * len(mat_ids),
                "inbound_eur_kg":   [0.0] * len(mat_ids),
                "min_freight_eur":  [0.0] * len(mat_ids),
                "packaging_eur_kg": [0.0] * len(mat_ids),
                "duties_pct":       [0.0] * len(mat_ids),
                "notes":            [""] * len(mat_ids),
            })
        else:
            # Merge so that any new material IDs appear
            existing = transport_df.copy()
            new_ids  = [m for m in mat_ids if m not in existing["material_id"].values]
            if new_ids:
                new_rows = pd.DataFrame({
                    "material_id":      new_ids,
                    "supplier":         [""] * len(new_ids),
                    "freight_mode":     ["ROAD"] * len(new_ids),
                    "inbound_eur_kg":   [0.0] * len(new_ids),
                    "min_freight_eur":  [0.0] * len(new_ids),
                    "packaging_eur_kg": [0.0] * len(new_ids),
                    "duties_pct":       [0.0] * len(new_ids),
                    "notes":            [""] * len(new_ids),
                })
                seed = pd.concat([existing, new_rows], ignore_index=True)
            else:
                seed = existing

        edited_in = st.data_editor(
            seed,
            column_config={
                "material_id":      st.column_config.TextColumn("Material ID", width="small"),
                "supplier":         st.column_config.TextColumn("Supplier", width="small"),
                "freight_mode":     st.column_config.SelectboxColumn(
                                        "Mode", options=FREIGHT_MODES, width="small"),
                "inbound_eur_kg":   st.column_config.NumberColumn("Freight €/kg", min_value=0.0, format="%.4f"),
                "min_freight_eur":  st.column_config.NumberColumn("Min charge €", min_value=0.0, format="%.2f"),
                "packaging_eur_kg": st.column_config.NumberColumn("Packaging €/kg", min_value=0.0, format="%.4f"),
                "duties_pct":       st.column_config.NumberColumn("Duties %", min_value=0.0, max_value=1.0,
                                                                    format="%.3f",
                                                                    help="Import duty as decimal, e.g. 0.03 = 3%"),
                "notes":            st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="transport_editor",
        )

        c1, c2 = st.columns([1, 4])
        if c1.button("💾 Save inbound rates", use_container_width=True):
            save_sheet(edited_in, "transport")
            st.success("Inbound freight rates saved.")
            st.cache_data.clear()

        # ── Live inbound summary ──────────────────────────────────────────────
        st.divider()
        st.subheader("Inbound freight summary (preview)")
        active_in = edited_in[
            (edited_in["inbound_eur_kg"].fillna(0) > 0) |
            (edited_in["packaging_eur_kg"].fillna(0) > 0) |
            (edited_in["duties_pct"].fillna(0) > 0)
        ]
        if active_in.empty:
            st.info("No inbound rates entered yet — fill in the table above.")
        else:
            with_transport = compute_inbound_costs(df, active_in)
            in_freight_tot = with_transport["inbound_freight_eur"].sum()
            duties_tot     = with_transport["duties_eur"].sum()
            landed_mat     = df["material_cost"].sum() + in_freight_tot + duties_tot

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Inbound freight + pkg", fmt(in_freight_tot, 2))
            k2.metric("Import duties",         fmt(duties_tot, 2))
            k3.metric("Landed material cost",  fmt(landed_mat, 2))
            k4.metric("Freight % of material",
                      f"{in_freight_tot / df['material_cost'].sum() * 100:.1f}%"
                      if df["material_cost"].sum() > 0 else "—")

            detail = (
                with_transport[["material_id", "line_id", "material_cost",
                                 "inbound_freight_eur", "duties_eur"]]
                .assign(landed=lambda x: x["material_cost"] + x["inbound_freight_eur"] + x["duties_eur"])
            )
            with st.expander("📄 Per-line inbound cost"):
                st.dataframe(
                    detail.style.format({
                        "material_cost":        lambda x: fmt(x, 2),
                        "inbound_freight_eur":  lambda x: fmt(x, 2),
                        "duties_eur":           lambda x: fmt(x, 2),
                        "landed":               lambda x: fmt(x, 2),
                    }),
                    use_container_width=True, hide_index=True,
                )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — OUTBOUND
    # ══════════════════════════════════════════════════════════════════════════
    with tab_out:
        st.subheader("Outbound shipping routes")
        st.caption(
            "Define shipping routes to customers. Costs are calculated on the product's total "
            "mass and sell value. Add multiple routes for different markets or Incoterms."
        )

        if outbound_df.empty:
            out_seed = pd.DataFrame([{
                "route_id":       "ROUTE-01",
                "destination":    "Rotterdam, NL",
                "freight_mode":   "ROAD",
                "rate_eur_kg":    0.15,
                "min_charge_eur": 500.0,
                "insurance_pct":  0.003,
                "handling_eur":   250.0,
                "incoterms":      "DAP",
                "transit_days":   3,
                "notes":          "",
            }])
        else:
            out_seed = outbound_df.copy()

        edited_out = st.data_editor(
            out_seed,
            column_config={
                "route_id":       st.column_config.TextColumn("Route ID", width="small"),
                "destination":    st.column_config.TextColumn("Destination"),
                "freight_mode":   st.column_config.SelectboxColumn("Mode", options=FREIGHT_MODES),
                "rate_eur_kg":    st.column_config.NumberColumn("Rate €/kg", min_value=0.0, format="%.4f"),
                "min_charge_eur": st.column_config.NumberColumn("Min charge €", min_value=0.0, format="%.2f"),
                "insurance_pct":  st.column_config.NumberColumn("Insurance %", min_value=0.0, max_value=0.1,
                                                                  format="%.4f",
                                                                  help="e.g. 0.003 = 0.3% of shipment value"),
                "handling_eur":   st.column_config.NumberColumn("Handling €", min_value=0.0, format="%.2f"),
                "incoterms":      st.column_config.SelectboxColumn("Incoterms", options=INCOTERMS),
                "transit_days":   st.column_config.NumberColumn("Transit days", min_value=0, format="%d"),
                "notes":          st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="outbound_editor",
        )

        c1, c2 = st.columns([1, 4])
        if c1.button("💾 Save outbound routes", use_container_width=True):
            save_sheet(edited_out, "outbound")
            st.success("Outbound routes saved.")
            st.cache_data.clear()

        # ── Outbound cost per route ───────────────────────────────────────────
        if not edited_out.empty and total_mass > 0:
            st.divider()
            st.subheader("Outbound cost per route")
            rows = []
            for _, row in edited_out.iterrows():
                c = outbound_cost(total_mass, total_sell, row)
                rows.append({
                    "Route":          row.get("route_id", ""),
                    "Destination":    row.get("destination", ""),
                    "Incoterms":      row.get("incoterms", ""),
                    "Mode":           row.get("freight_mode", ""),
                    "Freight €":      c["freight"],
                    "Insurance €":    c["insurance"],
                    "Handling €":     c["handling"],
                    "Total €":        c["total"],
                    "Transit days":   row.get("transit_days", ""),
                })
            out_tbl = pd.DataFrame(rows)
            st.dataframe(
                out_tbl.style.format({
                    "Freight €":    lambda x: fmt(x, 2),
                    "Insurance €":  lambda x: fmt(x, 2),
                    "Handling €":   lambda x: fmt(x, 2),
                    "Total €":      lambda x: fmt(x, 2),
                }),
                use_container_width=True, hide_index=True,
            )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — LANDED COST SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    with tab_summary:
        st.subheader("Total landed cost build-up")

        in_df = load_transport()
        ob_df = load_outbound()

        base_mat  = df["material_cost"].sum()
        base_proc = df["process_cost"].sum()
        base_oh   = df["overhead"].sum()
        base_mar  = df["margin"].sum()
        base_sell = df["total_cost"].sum()

        # Inbound
        if not in_df.empty:
            with_in   = compute_inbound_costs(df, in_df)
            in_freight = with_in["inbound_freight_eur"].sum()
            duties     = with_in["duties_eur"].sum()
        else:
            in_freight = duties = 0.0

        # Outbound (first active route)
        ob_cost = 0.0
        if not ob_df.empty:
            first_route = ob_df.iloc[0]
            ob_cost = outbound_cost(total_mass, base_sell, first_route)["total"]

        landed_total = base_sell + in_freight + duties + ob_cost

        waterfall = pd.DataFrame([
            {"Element": "Material (purchase)",   "Cost €": base_mat},
            {"Element": "Inbound freight & pkg", "Cost €": in_freight},
            {"Element": "Import duties",          "Cost €": duties},
            {"Element": "Machining & labour",     "Cost €": base_proc},
            {"Element": "Overhead",               "Cost €": base_oh},
            {"Element": "Margin",                 "Cost €": base_mar},
            {"Element": "Outbound shipping",      "Cost €": ob_cost},
            {"Element": "═ TOTAL LANDED",         "Cost €": landed_total},
        ])

        c_chart, c_tbl = st.columns([3, 2])
        with c_chart:
            chart_data = waterfall[waterfall["Element"] != "═ TOTAL LANDED"].set_index("Element")
            st.bar_chart(chart_data, color="#2196F3")
        with c_tbl:
            st.dataframe(
                waterfall.style.format({"Cost €": lambda x: fmt(x, 2)})
                    .apply(lambda r: ["font-weight:bold" if "TOTAL" in str(r["Element"])
                                      else "" for _ in r], axis=1),
                use_container_width=True, hide_index=True,
            )

        transport_pct = (in_freight + duties + ob_cost) / base_sell * 100 if base_sell > 0 else 0
        st.metric("Transport as % of sell price", f"{transport_pct:.1f}%",
                  delta="of quote value",
                  delta_color="off")


guard(main)
