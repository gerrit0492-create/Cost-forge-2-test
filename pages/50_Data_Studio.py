"""
50_Data_Studio.py — Inline Data Editor
Unified editor for BOM, Materials, Processes, Quotes and Risk data.
All changes save directly to cost_forge.xlsx.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.io import (
    load_bom, load_materials, load_processes, load_quotes,
    load_risk, load_nre, load_escalation, load_milestones,
    save_sheet, SCHEMA_BOM, SCHEMA_MATERIALS, SCHEMA_PROCESSES, SCHEMA_QUOTES,
)
from utils.nav import home_button
from utils.safe import guard
from utils.style import inject_css, page_header

st.set_page_config(page_title="Data Studio", layout="wide", page_icon="✏️")
inject_css()

# ── Process routes available ───────────────────────────────────────────────────
_PROCESS_OPTIONS = [
    "5AX_MILL_IMP","CNC_LATHE_PREC","CNC_LATHE_GEN","CNC_MILL_3AX","CNC_MILL_4AX",
    "TURN_MILL","PREC_BORE","SURF_GRIND","HONING","LAPPING","DEEP_HOLE_DRILL",
    "JIG_BORE","THREAD_GRIND","GEAR_CUT","DYN_BALANCE","TIG_WELD_316","MIG_WELD",
    "PIPE_WELD","WELD_OVERLAY","LASER_WELD","PLASMA_CUT","WATERJET_CUT","LASER_CUT",
    "FLAME_CUT","PRESS_BRAKE","ROLL_FORM","SAND_CAST","INVEST_CAST","CENTRIFUGAL",
    "FORGING","HEAT_TREAT","SHOT_PEEN","HARD_CHROME","ELEC_NICKEL","POWDER_COAT",
    "HOT_DIP_GALV","NITRIDING","ANODIZE","RUBBER_BOND","PRESSURE_TEST","FLOW_TEST",
    "LEAK_TEST","VIBRATION_TEST","NDT_INSPECT","CMM_INSPECT","RADIOGRAPHY",
    "FINAL_ASSEMBLY","WELD_OVERLAY",
]
_MAKE_BUY = ["M", "B"]


def _save_btn(key: str, df: pd.DataFrame, sheet: str, label: str = "💾 Save changes") -> None:
    """Render a save button; on click writes df to the sheet and clears cache."""
    if st.button(label, key=key, type="primary", use_container_width=False):
        save_sheet(df, sheet)
        st.cache_data.clear()
        st.success(f"✅ Saved to **{sheet}** sheet.")
        st.rerun()


def _unsaved_badge() -> None:
    st.warning("⚠️ Unsaved — click **Save changes** to persist edits.", icon="💡")


def main() -> None:
    home_button()
    page_header(
        title="Data Studio",
        icon="✏️",
        caption="Inline editor for BOM, materials, processes, quotes and cost data — all changes save to cost_forge.xlsx",
    )

    st.markdown(
        "> **Who uses this:** Cost engineers and project managers who need to correct or "
        "add entries without uploading a new file. Management can view but should not edit "
        "process rates without engineering sign-off."
    )

    # ── Tab bar ────────────────────────────────────────────────────────────────
    tab_bom, tab_mat, tab_proc, tab_quotes, tab_risk, tab_nre, tab_esc, tab_ms = st.tabs([
        "📋 BOM",
        "🧱 Materials",
        "⚙️ Processes",
        "🛒 Quotes",
        "⚠️ Risks",
        "🔬 NRE",
        "📈 Escalation",
        "💰 Milestones",
    ])

    # ════════════════════════════════════════════════════════════════════════
    # BOM TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_bom:
        st.subheader("Bill of Materials")
        st.caption(
            "Add, edit or delete BOM lines. "
            "Line IDs must start with a subsystem prefix (I=Impeller, SB=Stator Bowl, H=Housing, "
            "S=Shaft, TB=Thrust Block, D=Duct, N=Nozzle, ST=Steering, R=Reverse, F=Frame, "
            "SE=Seals, HY=Hydraulics, HW=Hardware, QA=QA/Testing)."
        )

        bom = load_bom()

        # Filters
        col_sub, col_search, col_mb = st.columns([2, 3, 2])
        prefixes = sorted(set(
            str(lid)[:2].upper() if str(lid)[:2].upper().isalpha() else str(lid)[:1].upper()
            for lid in bom["line_id"].dropna()
        ))
        sub_filter = col_sub.selectbox("Filter subsystem", ["All"] + prefixes, key="bom_sub_filter")
        search_bom = col_search.text_input("Search line ID / part name", key="bom_search")
        mb_filter  = col_mb.selectbox("Make / Buy", ["All", "M", "B"], key="bom_mb_filter")

        view = bom.copy()
        if sub_filter != "All":
            view = view[view["line_id"].astype(str).str.upper().str.startswith(sub_filter)]
        if search_bom:
            mask = (
                view["line_id"].astype(str).str.contains(search_bom, case=False, na=False) |
                view["part_name"].astype(str).str.contains(search_bom, case=False, na=False)
            )
            view = view[mask]
        if mb_filter != "All" and "make_buy" in view.columns:
            view = view[view["make_buy"].fillna("M") == mb_filter]

        st.caption(f"Showing {len(view)} of {len(bom)} lines")

        # Editable columns (keep schema columns present in data)
        edit_cols = [c for c in [
            "line_id", "part_name", "material_id", "qty", "mass_kg",
            "make_buy", "process_route", "runtime_h", "setup_h",
            "yield_factor", "subcontract_price_eur",
            "pattern_cost_eur", "pattern_amort_qty",
        ] if c in view.columns]

        edited_bom = st.data_editor(
            view[edit_cols].reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "line_id":              st.column_config.TextColumn("Line ID", width="small"),
                "part_name":            st.column_config.TextColumn("Part / Description", width="large"),
                "material_id":          st.column_config.TextColumn("Material ID", width="small",
                                        help="Leave blank for pure service lines (NDT, assembly with no material purchase)"),
                "qty":                  st.column_config.NumberColumn("Qty", min_value=0, step=1, format="%d", width="small"),
                "mass_kg":              st.column_config.NumberColumn("Mass (kg)", min_value=0.0, format="%.3f", width="small",
                                        help="Unit mass in kg. Set 0 for service operations."),
                "make_buy":             st.column_config.SelectboxColumn("M/B", options=_MAKE_BUY, width="small",
                                        help="M=Manufacture in-house, B=Buy/subcontract"),
                "process_route":        st.column_config.SelectboxColumn("Process route", options=_PROCESS_OPTIONS, width="medium"),
                "runtime_h":            st.column_config.NumberColumn("Runtime (h)", min_value=0.0, format="%.2f", width="small"),
                "setup_h":              st.column_config.NumberColumn("Setup (h)", min_value=0.0, format="%.2f", width="small"),
                "yield_factor":         st.column_config.NumberColumn("Yield", min_value=0.05, max_value=1.0, format="%.3f", width="small",
                                        help="Material yield: 0.8 = 20% scrap. Default 1.0."),
                "subcontract_price_eur":st.column_config.NumberColumn("Subcontract €", min_value=0.0, format="%.2f", width="small",
                                        help="Fixed price from supplier (Buy items only)"),
                "pattern_cost_eur":     st.column_config.NumberColumn("Pattern NRE €", min_value=0.0, format="%.2f", width="small",
                                        help="One-time casting pattern / mould cost"),
                "pattern_amort_qty":    st.column_config.NumberColumn("Amort over qty", min_value=1.0, format="%.0f", width="small",
                                        help="Number of units over which pattern NRE is spread"),
            },
            key="bom_editor",
        )

        col_save, col_add, col_info = st.columns([2, 2, 5])
        with col_save:
            if st.button("💾 Save BOM changes", key="save_bom", type="primary", use_container_width=True):
                # Merge edited rows back into full bom (respecting filter)
                updated = bom.copy()
                edited_ids = edited_bom["line_id"].dropna().astype(str).tolist()
                # Remove rows that were in the view (may have been edited or deleted)
                view_ids = view["line_id"].astype(str).tolist()
                updated = updated[~updated["line_id"].astype(str).isin(view_ids)]
                # Add edited rows back
                for col in bom.columns:
                    if col not in edited_bom.columns:
                        edited_bom[col] = pd.NA
                updated = pd.concat([updated, edited_bom[[c for c in bom.columns if c in edited_bom.columns]]], ignore_index=True)
                # Sort by line_id prefix / number
                updated = updated.dropna(subset=["line_id"])
                save_sheet(updated, "bom")
                st.cache_data.clear()
                st.success(f"✅ BOM saved ({len(updated)} lines)")
                st.rerun()

        with col_add:
            if st.button("➕ Add blank row (use filter first)", key="bom_hint",
                         use_container_width=True, help="Switch to 'All' filter, then add a row at the bottom of the table"):
                pass  # Hint only — data_editor handles add via num_rows="dynamic"

        st.info(
            "💡 **Tips:** Double-click a cell to edit. Click the ➕ row at the bottom to add a new line. "
            "Click the checkbox on the left to select a row for deletion (Del key). "
            "Use the subsystem filter to focus on one area. Always click **Save BOM changes** when done."
        )

        # Quick stats
        with st.expander("📊 BOM summary stats"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total lines", len(bom))
            c2.metric("Make (M)", (bom["make_buy"].fillna("M") == "M").sum())
            c3.metric("Buy (B)", (bom["make_buy"].fillna("M") == "B").sum())
            c4.metric("Service (no mat)", (bom["material_id"].fillna("").str.strip() == "").sum())
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Total mass (kg)", f"{(pd.to_numeric(bom['qty'], errors='coerce').fillna(1) * bom['mass_kg'].fillna(0)).sum():,.1f}")
            c6.metric("Unique materials", bom["material_id"].dropna().nunique())
            c7.metric("Unique processes", bom["process_route"].dropna().nunique())
            c8.metric("Total runtime (h)", f"{bom['runtime_h'].fillna(0).sum():,.1f}")

    # ════════════════════════════════════════════════════════════════════════
    # MATERIALS TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_mat:
        st.subheader("Materials Library")
        st.caption(
            "Edit material base prices, MOQ, HS codes and supplier info. "
            "Prices here are the fallback if no supplier quote exists."
        )

        mats = load_materials()

        edited_mats = st.data_editor(
            mats.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "material_id":      st.column_config.TextColumn("Material ID", width="medium",
                                    help="Unique ID used in BOM (e.g. SS316L, NAB, PEEK)"),
                "description":      st.column_config.TextColumn("Description", width="large"),
                "commodity":        st.column_config.TextColumn("Commodity group", width="medium",
                                    help="Used by Scenario Planner for price sensitivity sliders"),
                "price_eur_per_kg": st.column_config.NumberColumn("Base price €/kg", min_value=0.0,
                                    format="%.4f", width="medium",
                                    help="Catalogue fallback price. Supplier quotes override this."),
                "moq_kg":           st.column_config.NumberColumn("MOQ (kg)", min_value=0.0,
                                    format="%.1f", width="small",
                                    help="Minimum order quantity. Below this = MOQ excess cost."),
                "hs_code":          st.column_config.TextColumn("HS tariff code", width="small",
                                    help="e.g. 7219.21 for SS316L plate. Used for import duty."),
                "lead_supplier":    st.column_config.SelectboxColumn("Supplier status",
                                    options=["Primary", "Sole source", "Approved", "Conditional", "Qualified"],
                                    width="medium"),
                "supplier":         st.column_config.TextColumn("Preferred supplier", width="medium"),
            },
            key="mats_editor",
        )

        col_sm, col_sm2 = st.columns([2, 8])
        with col_sm:
            if st.button("💾 Save materials", key="save_mats", type="primary", use_container_width=True):
                save_sheet(edited_mats.dropna(subset=["material_id"]), "materials")
                st.cache_data.clear()
                st.success("✅ Materials saved")
                st.rerun()

        st.info(
            "💡 **Add a new material:** Fill in a new row at the bottom. "
            "Assign it an ID (no spaces), add a base price, and add a BOM line or supplier quote referencing it. "
            "**Price hierarchy:** Supplier quote → this base price → 0 (warning)."
        )

        # Price comparison chart
        if not mats.empty and "price_eur_per_kg" in mats.columns:
            st.divider()
            st.subheader("Price per kg — visual comparison")
            chart = mats.set_index("material_id")[["price_eur_per_kg"]].sort_values("price_eur_per_kg", ascending=False)
            st.bar_chart(chart.rename(columns={"price_eur_per_kg": "€/kg"}), color="#4da6ff")

    # ════════════════════════════════════════════════════════════════════════
    # PROCESSES TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_proc:
        st.subheader("Process Routes & Rates")
        st.caption(
            "Machine rate, labour rate, overhead % and margin % drive all process cost calculations. "
            "⚠️ Changes here affect every BOM line using that process route. "
            "Get engineering / management sign-off before changing rates on live quotes."
        )

        procs = load_processes()

        edited_procs = st.data_editor(
            procs.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "process_id":               st.column_config.TextColumn("Process ID", width="medium"),
                "machine_rate_eur_h":        st.column_config.NumberColumn("Machine €/h", min_value=0.0,
                                            format="%.2f", width="small"),
                "labor_rate_eur_h":          st.column_config.NumberColumn("Labour €/h", min_value=0.0,
                                            format="%.2f", width="small"),
                "overhead_pct":             st.column_config.NumberColumn("Overhead %", min_value=0.0,
                                            max_value=1.0, format="%.2f", width="small",
                                            help="As decimal: 0.25 = 25%"),
                "margin_pct":               st.column_config.NumberColumn("Margin %", min_value=0.0,
                                            max_value=1.0, format="%.2f", width="small",
                                            help="As decimal: 0.18 = 18%"),
                "energy_kw":                st.column_config.NumberColumn("Energy (kW)", min_value=0.0,
                                            format="%.1f", width="small"),
                "rework_pct":               st.column_config.NumberColumn("Rework %", min_value=0.0,
                                            max_value=0.5, format="%.3f", width="small",
                                            help="Rework provision as fraction of process cost"),
                "tooling_consumable_eur_h":  st.column_config.NumberColumn("Tooling €/h", min_value=0.0,
                                            format="%.2f", width="small",
                                            help="Cutting tools / inserts per runtime hour"),
                "subcontract_markup_pct":    st.column_config.NumberColumn("Subcon markup %", min_value=0.0,
                                            max_value=0.5, format="%.2f", width="small"),
                "labour_grade":             st.column_config.TextColumn("Labour grade", width="medium"),
            },
            key="procs_editor",
        )

        col_sp, _ = st.columns([2, 8])
        with col_sp:
            if st.button("💾 Save processes", key="save_procs_studio", type="primary", use_container_width=True):
                save_sheet(edited_procs.dropna(subset=["process_id"]), "processes")
                st.cache_data.clear()
                st.success("✅ Processes saved")
                st.rerun()

        st.warning(
            "⚠️ **Audit note:** Process rate changes affect all open estimates. "
            "Record the reason for changes in a change order or project log. "
            "Consider using the **Scenario Planner** to model rate changes without saving them permanently."
        )

    # ════════════════════════════════════════════════════════════════════════
    # QUOTES TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_quotes:
        st.subheader("Supplier Quotes")
        st.caption(
            "Add or update supplier price quotes. Valid quotes override the base material price. "
            "Preferred=1 means this quote is used when multiple quotes exist for the same material."
        )

        quotes = load_quotes()
        today_ts = pd.Timestamp.today().normalize()

        if not quotes.empty and "valid_until" in quotes.columns:
            vd = pd.to_datetime(quotes["valid_until"], errors="coerce")
            n_exp = (vd < today_ts).sum()
            if n_exp:
                st.error(f"🔴 {n_exp} expired quote(s) — update valid_until and price below.")

        edited_quotes = st.data_editor(
            quotes.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "supplier":         st.column_config.TextColumn("Supplier", width="large"),
                "material_id":      st.column_config.TextColumn("Material ID", width="medium"),
                "price_eur_per_kg": st.column_config.NumberColumn("Price €/kg", min_value=0.0,
                                    format="%.4f", width="medium"),
                "price_eur_per_unit":st.column_config.NumberColumn("Price €/unit", min_value=0.0,
                                    format="%.2f", width="medium",
                                    help="Fixed unit price (castings, bought-out assemblies)"),
                "lead_time_days":   st.column_config.NumberColumn("Lead (days)", min_value=0,
                                    format="%d", width="small"),
                "valid_until":      st.column_config.TextColumn("Valid until", width="small",
                                    help="Format: YYYY-MM-DD"),
                "preferred":        st.column_config.NumberColumn("Preferred (1=yes)", min_value=0,
                                    max_value=1, format="%d", width="small"),
                "pattern_cost_eur": st.column_config.NumberColumn("Pattern NRE €", min_value=0.0,
                                    format="%.2f", width="small"),
                "pattern_amort_qty":st.column_config.NumberColumn("Amort qty", min_value=1.0,
                                    format="%.0f", width="small"),
                "notes":            st.column_config.TextColumn("Notes", width="large"),
            },
            key="quotes_editor",
        )

        col_sq, _ = st.columns([2, 8])
        with col_sq:
            if st.button("💾 Save quotes", key="save_quotes_studio", type="primary", use_container_width=True):
                save_sheet(edited_quotes.dropna(subset=["supplier", "material_id"]), "quotes")
                st.cache_data.clear()
                st.success("✅ Quotes saved")
                st.rerun()

        st.info(
            "💡 **Preferred quote:** Set Preferred=1 for your approved supplier. "
            "When multiple quotes exist, the system uses the preferred one, "
            "then falls back to lowest price. Expired quotes are automatically skipped."
        )

    # ════════════════════════════════════════════════════════════════════════
    # RISK TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_risk:
        st.subheader("Risk Register")
        st.caption(
            "Marine-specific risk register. Probability × Cost Impact = Expected Value added to contingency. "
            "Update status, owner and mitigation as risks are resolved."
        )

        risk = load_risk()

        if not risk.empty:
            ev_total = (risk["probability"] * risk["cost_impact_eur"]).sum()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total risks", len(risk))
            c2.metric("Open risks", (risk["status"].str.lower() == "open").sum() if "status" in risk.columns else len(risk))
            c3.metric("Risk EV (expected value)", f"€{ev_total:,.0f}")
            high_ev = risk.nlargest(1, "cost_impact_eur")
            c4.metric("Highest impact risk", f"€{high_ev['cost_impact_eur'].values[0]:,.0f}" if not high_ev.empty else "—",
                      delta=high_ev["title"].values[0][:30] if not high_ev.empty else "")

        edited_risk = st.data_editor(
            risk.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "risk_id":          st.column_config.TextColumn("ID", width="small"),
                "category":         st.column_config.SelectboxColumn("Category",
                                    options=["Manufacturing","Procurement","Schedule","Compliance",
                                             "Quality","Commercial","Technical","Lifecycle",
                                             "Supply Chain","Regulatory","Other"],
                                    width="medium"),
                "title":            st.column_config.TextColumn("Risk title", width="large"),
                "description":      st.column_config.TextColumn("Description", width="xlarge"),
                "probability":      st.column_config.NumberColumn("Probability", min_value=0.0,
                                    max_value=1.0, format="%.2f", width="small",
                                    help="0.0–1.0: 0.10=10% chance"),
                "cost_impact_eur":  st.column_config.NumberColumn("Impact €", min_value=0.0,
                                    format="%.0f", width="medium",
                                    help="Cost if risk materialises (worst case)"),
                "status":           st.column_config.SelectboxColumn("Status",
                                    options=["Open","In progress","Mitigated","Closed","Accepted"],
                                    width="small"),
                "mitigation":       st.column_config.TextColumn("Mitigation action", width="xlarge"),
                "owner":            st.column_config.SelectboxColumn("Owner",
                                    options=["Engineering","Procurement","QA","Commercial","PM",
                                             "Compliance","Management",""],
                                    width="small"),
                "notes":            st.column_config.TextColumn("Notes", width="large"),
            },
            key="risk_editor",
        )

        # Show EV column for edited data
        if not edited_risk.empty and "probability" in edited_risk and "cost_impact_eur" in edited_risk:
            edited_risk_display = edited_risk.copy()
            edited_risk_display["EV €"] = (
                pd.to_numeric(edited_risk_display["probability"], errors="coerce").fillna(0) *
                pd.to_numeric(edited_risk_display["cost_impact_eur"], errors="coerce").fillna(0)
            ).round(0)
            new_ev = edited_risk_display["EV €"].sum()
            st.caption(f"Total expected value with edits: **€{new_ev:,.0f}**")

        col_sr, _ = st.columns([2, 8])
        with col_sr:
            if st.button("💾 Save risk register", key="save_risk_studio", type="primary", use_container_width=True):
                save_sheet(edited_risk.dropna(subset=["risk_id", "title"]), "risk")
                st.cache_data.clear()
                st.success("✅ Risk register saved")
                st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # NRE TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_nre:
        st.subheader("NRE — Non-Recurring Engineering Costs")
        st.caption(
            "Engineering hours, documentation, test facility, classification fees, commissioning. "
            "NRE is in addition to BOM manufacturing cost — it represents the project overhead "
            "to deliver a certified, commissioned waterjet unit to the customer."
        )

        nre = load_nre()

        if not nre.empty:
            nre["_total"] = nre["hours"].fillna(0) * nre["rate_eur_h"].fillna(0) + nre["fixed_eur"].fillna(0)
            nre_total = nre["_total"].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("NRE lines", len(nre))
            c2.metric("Total NRE cost", f"€{nre_total:,.0f}")
            c3.metric("NRE as % of BOM sell", "",
                      delta="Enter BOM sell price in project settings to see %")

        nre_edit = nre.drop(columns=["_total"], errors="ignore") if not nre.empty else nre
        edited_nre = st.data_editor(
            nre_edit.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "nre_id":       st.column_config.TextColumn("ID", width="small"),
                "category":     st.column_config.SelectboxColumn("Category",
                                options=["Engineering","Project Management","Documentation",
                                         "Testing & Qualification","Commissioning","Tooling","Other"],
                                width="medium"),
                "description":  st.column_config.TextColumn("Description", width="xlarge"),
                "hours":        st.column_config.NumberColumn("Hours", min_value=0.0,
                                format="%.1f", width="small"),
                "rate_eur_h":   st.column_config.NumberColumn("Rate €/h", min_value=0.0,
                                format="%.2f", width="small"),
                "fixed_eur":    st.column_config.NumberColumn("Fixed cost €", min_value=0.0,
                                format="%.2f", width="small",
                                help="Lump sum cost (test facility hire, survey fee) independent of hours"),
                "amortize_over":st.column_config.NumberColumn("Amort. over (units)", min_value=1.0,
                                format="%.0f", width="small",
                                help="NRE spread over this many units. 1 = full cost on this project."),
                "status":       st.column_config.SelectboxColumn("Status",
                                options=["budgeted","committed","invoiced","paid","cancelled"],
                                width="small"),
                "notes":        st.column_config.TextColumn("Notes", width="large"),
            },
            key="nre_editor",
        )

        # Live total preview
        if not edited_nre.empty:
            h = pd.to_numeric(edited_nre.get("hours", 0), errors="coerce").fillna(0)
            r = pd.to_numeric(edited_nre.get("rate_eur_h", 0), errors="coerce").fillna(0)
            f = pd.to_numeric(edited_nre.get("fixed_eur", 0), errors="coerce").fillna(0)
            live_total = (h * r + f).sum()
            st.caption(f"Preview total NRE with edits: **€{live_total:,.0f}**")

        col_sn, _ = st.columns([2, 8])
        with col_sn:
            if st.button("💾 Save NRE", key="save_nre_studio", type="primary", use_container_width=True):
                save_sheet(edited_nre.dropna(subset=["nre_id"]), "nre")
                st.cache_data.clear()
                st.success("✅ NRE saved")
                st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # ESCALATION TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_esc:
        st.subheader("Commodity Escalation Indices")
        st.caption(
            "Track commodity price movements vs. baseline. "
            "The escalation % feeds into the Full Cost Summary waterfall as an escalation delta line."
        )

        esc = load_escalation()

        # Show escalation %
        if not esc.empty and "base_value" in esc.columns and "current_value" in esc.columns:
            esc_disp = esc.copy()
            esc_disp["_pct_change"] = (
                (pd.to_numeric(esc_disp["current_value"], errors="coerce") -
                 pd.to_numeric(esc_disp["base_value"], errors="coerce")) /
                pd.to_numeric(esc_disp["base_value"], errors="coerce").replace(0, 1) * 100
            ).round(2)
            c1, c2 = st.columns([3, 7])
            with c1:
                for _, row in esc_disp.iterrows():
                    pct = row.get("_pct_change", 0)
                    colour = "🔴" if pct > 5 else ("🟡" if pct > 0 else "🟢")
                    st.metric(str(row.get("applies_to", "")),
                              f"{pct:+.1f}%",
                              delta=row.get("index_name", ""),
                              delta_color="off")

        edited_esc = st.data_editor(
            esc.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "esc_id":       st.column_config.TextColumn("ID", width="small"),
                "applies_to":   st.column_config.TextColumn("Material / scope", width="medium",
                                help="Material ID, LABOUR, GENERAL, or ALL"),
                "description":  st.column_config.TextColumn("Description", width="large"),
                "index_name":   st.column_config.TextColumn("Index name", width="medium",
                                help="e.g. LME Copper, EU SS316L Surcharge"),
                "base_value":   st.column_config.NumberColumn("Base value", format="%.2f", width="small",
                                help="Index value at contract baseline date"),
                "current_value":st.column_config.NumberColumn("Current value", format="%.2f", width="small",
                                help="Today's index value"),
                "base_date":    st.column_config.TextColumn("Base date", width="small",
                                help="YYYY-MM-DD"),
                "override_pct": st.column_config.NumberColumn("Override %", min_value=-1.0,
                                max_value=1.0, format="%.4f", width="small",
                                help="Manual override escalation fraction (0.05=5%). Leave 0 to use base/current."),
                "notes":        st.column_config.TextColumn("Notes", width="large"),
            },
            key="esc_editor",
        )

        col_se, _ = st.columns([2, 8])
        with col_se:
            if st.button("💾 Save escalation", key="save_esc_studio", type="primary", use_container_width=True):
                save_sheet(edited_esc.dropna(subset=["esc_id"]), "escalation")
                st.cache_data.clear()
                st.success("✅ Escalation saved")
                st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # MILESTONES TAB
    # ════════════════════════════════════════════════════════════════════════
    with tab_ms:
        st.subheader("Contract Milestone Payment Schedule")
        st.caption(
            "Define payment milestones and planned dates. "
            "Used by Contract & Cash Flow to compute APG costs, working capital and cash timing."
        )

        ms = load_milestones()

        if not ms.empty and "amount_eur" in ms.columns:
            total_contract = ms["amount_eur"].sum()
            received = ms[ms["received"].fillna("No").str.strip().str.upper() == "YES"]["amount_eur"].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Contract value (milestones)", f"€{total_contract:,.0f}")
            c2.metric("Received", f"€{received:,.0f}")
            c3.metric("Outstanding", f"€{total_contract - received:,.0f}")

        edited_ms = st.data_editor(
            ms.reset_index(drop=True),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "milestone_id":     st.column_config.TextColumn("ID", width="small"),
                "description":      st.column_config.TextColumn("Milestone", width="large"),
                "trigger_event":    st.column_config.TextColumn("Trigger event", width="large",
                                    help="What must happen for this payment to be due"),
                "pct_of_contract":  st.column_config.NumberColumn("% of contract", min_value=0.0,
                                    max_value=1.0, format="%.2f", width="small",
                                    help="Fraction: 0.30 = 30%"),
                "amount_eur":       st.column_config.NumberColumn("Amount €", min_value=0.0,
                                    format="%.0f", width="medium"),
                "planned_date":     st.column_config.TextColumn("Planned date (YYYY-MM-DD)", width="medium"),
                "actual_date":      st.column_config.TextColumn("Actual date (YYYY-MM-DD)", width="medium"),
                "received":         st.column_config.SelectboxColumn("Received?",
                                    options=["No", "Yes", "Partial", "Disputed"],
                                    width="small"),
                "notes":            st.column_config.TextColumn("Notes", width="large"),
            },
            key="ms_editor",
        )

        col_sm2, _ = st.columns([2, 8])
        with col_sm2:
            if st.button("💾 Save milestones", key="save_ms_studio", type="primary", use_container_width=True):
                save_sheet(edited_ms.dropna(subset=["milestone_id"]), "milestones")
                st.cache_data.clear()
                st.success("✅ Milestones saved")
                st.rerun()


guard(main)
