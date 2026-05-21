"""
49_Quote_Management.py — Supplier Quote Management
Add, edit, delete, and update supplier quotes.
Also handles Buy (purchased) items with fixed prices.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.io import (
    load_bom,
    load_materials,
    load_processes,
    load_quotes,
    save_sheet,
)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

QUOTE_COLUMNS = ["supplier", "material_id", "price_eur_per_kg",
                 "lead_time_days", "valid_until", "preferred",
                 "pattern_cost_eur", "pattern_amort_qty", "notes"]

EMPTY_QUOTE: dict = {
    "supplier": "",
    "material_id": "",
    "price_eur_per_kg": 0.0,
    "lead_time_days": 14,
    "valid_until": pd.Timestamp.today().normalize() + pd.DateOffset(months=6),
    "preferred": 0,
    "pattern_cost_eur": 0.0,
    "pattern_amort_qty": 0.0,
    "notes": "",
}

BOM_COLUMNS = ["line_id", "part_name", "material_id", "qty", "mass_kg",
               "process_route", "runtime_h", "setup_h",
               "make_buy", "subcontract_price_eur",
               "pattern_cost_eur", "pattern_amort_qty"]


@st.cache_data(ttl=30)
def _load():
    quotes = load_quotes()
    mats   = load_materials()
    bom    = load_bom()
    procs  = load_processes()
    return quotes, mats, bom, procs


def _save_quotes(df: pd.DataFrame):
    """Persist quotes back to Excel, clear cache."""
    save_sheet(df[QUOTE_COLUMNS], "quotes")
    st.cache_data.clear()


def _save_bom(df: pd.DataFrame):
    """Persist BOM back to Excel, clear cache."""
    save_sheet(df, "bom")
    st.cache_data.clear()


def main():
    inject_css()
    home_button()
    quotes, mats, bom, procs = _load()
    all_mat_ids = sorted(mats["material_id"].tolist()) if not mats.empty else []

    page_header(
        title="Quote Management",
        icon="🛒",
        caption="Add/edit supplier quotes · manage buy (purchased) items · track validity",
    )

    tab_quotes, tab_castings, tab_buy, tab_coverage, tab_history = st.tabs([
        "📋 Supplier Quotes",
        "🏭 Casting Patterns",
        "📦 Buy Items (no manufacturing)",
        "🔍 Coverage & gaps",
        "📈 Impact on cost",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — SUPPLIER QUOTES
    # ══════════════════════════════════════════════════════════════════════════
    with tab_quotes:
        st.markdown(
            "Edit quotes directly in the table. Add a row for each supplier–material combination. "
            "Set **Preferred = 1** to force that supplier; 0 = cost engine picks cheapest valid quote."
        )

        today = pd.Timestamp.today().normalize()
        q = quotes.copy() if not quotes.empty else pd.DataFrame(columns=QUOTE_COLUMNS)

        # Ensure correct types for data_editor
        if not q.empty:
            q["price_eur_per_kg"]   = pd.to_numeric(q["price_eur_per_kg"], errors="coerce").fillna(0.0)
            q["lead_time_days"]     = pd.to_numeric(q["lead_time_days"], errors="coerce").fillna(14).astype(int)
            q["preferred"]          = pd.to_numeric(q["preferred"], errors="coerce").fillna(0).astype(int)
            q["valid_until"]        = pd.to_datetime(q["valid_until"], errors="coerce")
            q["pattern_cost_eur"]   = pd.to_numeric(q.get("pattern_cost_eur", 0), errors="coerce").fillna(0.0)
            q["pattern_amort_qty"]  = pd.to_numeric(q.get("pattern_amort_qty", 0), errors="coerce").fillna(0.0)
            q["notes"]              = q.get("notes", pd.Series("", index=q.index)).fillna("")

        # Colour-code expiry
        def _status_flag(row):
            vd = row.get("valid_until")
            if pd.isna(vd):
                return "🟡 No date"
            if vd < today:
                return "🔴 Expired"
            if (vd - today).days <= 30:
                return "🟡 ≤30 days"
            return "🟢 Valid"

        q_display = q.copy()
        if not q_display.empty:
            q_display["Status"] = q_display.apply(_status_flag, axis=1)
            q_display["days_left"] = (pd.to_datetime(q_display["valid_until"]) - today).dt.days
        else:
            q_display["Status"] = pd.Series(dtype=str)
            q_display["days_left"] = pd.Series(dtype=float)

        # KPIs
        n_exp  = int((q_display["Status"] == "🔴 Expired").sum()) if not q_display.empty else 0
        n_warn = int((q_display["Status"] == "🟡 ≤30 days").sum()) if not q_display.empty else 0
        n_supp = q["supplier"].nunique() if not q.empty else 0
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total quotes", len(q))
        k2.metric("Suppliers", n_supp)
        k3.metric("Expired", n_exp, delta="renew" if n_exp else "✓ ok",
                  delta_color="inverse" if n_exp else "off")
        k4.metric("Expiring ≤30d", n_warn, delta="check" if n_warn else "✓ ok",
                  delta_color="inverse" if n_warn else "off")

        if n_exp:
            st.error(f"⚠️ {n_exp} quote(s) expired — update before generating reports.")
        if n_warn:
            st.warning(f"⏰ {n_warn} quote(s) expire within 30 days.")

        st.divider()
        st.subheader("Edit quotes")

        # Ensure all QUOTE_COLUMNS exist
        for _qc in QUOTE_COLUMNS:
            if _qc not in q.columns:
                q[_qc] = 0.0 if _qc not in ("supplier", "material_id", "valid_until", "notes") else ""

        # Editable table
        edited = st.data_editor(
            q[[c for c in QUOTE_COLUMNS if c in q.columns]] if not q.empty else pd.DataFrame([EMPTY_QUOTE]),
            num_rows="dynamic",
            use_container_width=True,
            key="quote_editor",
            column_config={
                "supplier": st.column_config.TextColumn("Supplier", width="medium"),
                "material_id": st.column_config.SelectboxColumn(
                    "Material ID", options=all_mat_ids, width="medium"
                ),
                "price_eur_per_kg": st.column_config.NumberColumn(
                    "Price €/kg",
                    min_value=0.0, format="€ %.3f", width="small",
                    help="For castings priced per piece, leave this 0 and use the BOM's "
                         "subcontract_price_eur field instead.",
                ),
                "lead_time_days": st.column_config.NumberColumn(
                    "Lead time (days)", min_value=0, step=1, width="small"
                ),
                "valid_until": st.column_config.DateColumn(
                    "Valid until", format="YYYY-MM-DD", width="small"
                ),
                "preferred": st.column_config.CheckboxColumn(
                    "Preferred", width="small"
                ),
                "pattern_cost_eur": st.column_config.NumberColumn(
                    "Pattern cost EUR",
                    min_value=0.0, format="€ %.0f", width="small",
                    help="One-time casting pattern / die / mould cost quoted by the foundry. "
                         "Leave 0 for non-casting materials. "
                         "Set this in the BOM (per part) or here as a reference for your BOM entry.",
                ),
                "pattern_amort_qty": st.column_config.NumberColumn(
                    "Amort. qty",
                    min_value=0.0, step=1.0, format="%.0f", width="small",
                    help="Number of units the foundry amortises the pattern cost over "
                         "(their minimum order / tooling split). Typically 5–20 off.",
                ),
                "notes": st.column_config.TextColumn(
                    "Notes / RFQ ref", width="large",
                    help="e.g. RFQ ref, material spec, certifications required, delivery terms",
                ),
            },
            hide_index=True,
        )

        c1, c2 = st.columns([1, 4])
        if c1.button("💾 Save all quotes", type="primary", use_container_width=True):
            clean = edited.dropna(subset=["material_id"]).copy()
            clean = clean[clean["material_id"].str.strip() != ""]
            # Normalise preferred to 0/1 int
            clean["preferred"] = clean["preferred"].astype(bool).astype(int)
            # Format valid_until as string YYYY-MM-DD
            if "valid_until" in clean.columns:
                clean["valid_until"] = pd.to_datetime(
                    clean["valid_until"], errors="coerce"
                ).dt.strftime("%Y-%m-%d").fillna("")
            _save_quotes(clean)
            st.success(f"✅ Saved {len(clean)} quotes to cost_forge.xlsx")
            st.rerun()

        with c2:
            st.caption(
                "Add a new row with the ➕ at the bottom. Delete a row by selecting it and pressing Delete. "
                "**Preferred = ✓** means the cost engine will always use this supplier for that material, "
                "even if a cheaper one exists."
            )

        st.divider()
        st.subheader("Quick-refresh a quote")
        st.markdown(
            "Use this to bump the validity date on existing quotes "
            "without touching the price or lead time."
        )
        if not q.empty:
            mat_opts = sorted(q["material_id"].dropna().unique().tolist())
            col_m, col_s, col_d, col_btn = st.columns([2, 2, 2, 1])
            sel_mat  = col_m.selectbox("Material", mat_opts, key="qr_mat")
            mat_rows = q[q["material_id"] == sel_mat]
            sup_opts = sorted(mat_rows["supplier"].dropna().unique().tolist())
            sel_sup  = col_s.selectbox("Supplier", sup_opts, key="qr_sup")
            new_date = col_d.date_input(
                "New validity date",
                value=(today + pd.DateOffset(months=6)).date(),
                key="qr_date",
            )
            if col_btn.button("↻ Refresh", use_container_width=True):
                mask = (q["material_id"] == sel_mat) & (q["supplier"] == sel_sup)
                q.loc[mask, "valid_until"] = str(new_date)
                _save_quotes(q)
                st.success(f"Refreshed quote: {sel_sup} / {sel_mat} → valid until {new_date}")
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — CASTING PATTERNS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_castings:
        st.markdown("""
### How supplier casting charges work

When a foundry supplies a casting (sand cast, investment cast, die cast) they typically charge:

| Charge | When | How it flows into cost |
|---|---|---|
| **Pattern / tooling cost** | One-time per part number (or per order) | Amortised over `pattern_amort_qty` units → `pattern_cost` column in BOM |
| **Piece price** | Per casting supplied | Entered as `subcontract_price_eur` in BOM + foundry markup from Processes |
| **Material spec** | Included in piece price | No separate material cost for bought-out castings |

The cost engine:
- Sets `process_cost` = piece price × (1 + subcontract markup%)
- Adds `pattern_cost` = pattern_cost_eur ÷ amort_qty (per unit in the BOM)
- Applies 2% handling overhead on the total bought value
- Zero machining cost (machine/labour rates are zeroed for `make_buy = B`)
- Margin comes from the process route (e.g. SAND_CAST) as usual
""")

        st.subheader("Casting BOM lines")
        cast_mask = bom["process_route"].str.contains("CAST", case=False, na=False) \
                    if "process_route" in bom.columns else pd.Series(False, index=bom.index)
        buy_mask  = (bom["make_buy"].str.upper() == "B") if "make_buy" in bom.columns \
                    else pd.Series(False, index=bom.index)
        cast_bom  = bom[cast_mask | buy_mask].copy()

        if cast_bom.empty:
            st.info("No casting or Buy lines in BOM yet. Mark a BOM line `make_buy = B` in the Buy Items tab.")
        else:
            # Ensure columns exist
            for _cc in ["subcontract_price_eur", "pattern_cost_eur", "pattern_amort_qty"]:
                if _cc not in cast_bom.columns:
                    cast_bom[_cc] = 0.0
                cast_bom[_cc] = pd.to_numeric(cast_bom[_cc], errors="coerce").fillna(0.0)

            show_cast_cols = [c for c in
                              ["line_id", "part_name", "material_id", "qty", "mass_kg",
                               "make_buy", "process_route", "subcontract_price_eur",
                               "pattern_cost_eur", "pattern_amort_qty"]
                              if c in cast_bom.columns]

            cast_edited = st.data_editor(
                cast_bom[show_cast_cols],
                num_rows="fixed",
                use_container_width=True,
                key="cast_bom_editor",
                column_config={
                    "line_id":   st.column_config.TextColumn("Line ID", disabled=True, width="small"),
                    "part_name": st.column_config.TextColumn("Part name", disabled=True, width="large"),
                    "material_id": st.column_config.TextColumn("Material", disabled=True, width="small"),
                    "qty":       st.column_config.NumberColumn("Qty", disabled=True, width="small"),
                    "mass_kg":   st.column_config.NumberColumn("Mass kg", disabled=True, format="%.1f", width="small"),
                    "make_buy":  st.column_config.SelectboxColumn("Make/Buy", options=["M", "B"], width="small"),
                    "process_route": st.column_config.TextColumn(
                        "Process route", width="small",
                        help="Keep SAND_CAST or INVEST_CAST so overhead% and margin% are inherited. "
                             "Make/Buy=B means hourly cost is zero — only subcontract price applies.",
                    ),
                    "subcontract_price_eur": st.column_config.NumberColumn(
                        "Foundry piece price EUR",
                        min_value=0.0, format="€ %.0f", width="medium",
                        help="The foundry's quoted price per casting, per unit. "
                             "A subcontract markup (from the process route) is added on top.",
                    ),
                    "pattern_cost_eur": st.column_config.NumberColumn(
                        "Pattern cost EUR (total)",
                        min_value=0.0, format="€ %.0f", width="medium",
                        help="One-time cost to make the sand casting pattern or investment casting die. "
                             "Quoted by the foundry. Amortised over pattern_amort_qty units.",
                    ),
                    "pattern_amort_qty": st.column_config.NumberColumn(
                        "Amort. qty",
                        min_value=0.0, step=1.0, format="%.0f", width="small",
                        help="Number of units over which the pattern cost is spread. "
                             "Often the foundry's MOQ (e.g. 5 off). "
                             "If you order 1, you still pay 1/5 of the pattern.",
                    ),
                },
                hide_index=True,
            )

            # Live preview of pattern cost per unit
            st.markdown("**Pattern cost per unit (preview)**")
            preview_rows = []
            for _, r in cast_edited.iterrows():
                pc = float(r.get("pattern_cost_eur", 0) or 0)
                aq = float(r.get("pattern_amort_qty", 0) or 0)
                sp = float(r.get("subcontract_price_eur", 0) or 0)
                qty_val = int(r.get("qty", 1) or 1)
                pc_per_unit = pc / aq if aq > 0 else pc
                handling = (sp + pc_per_unit) * 0.02
                preview_rows.append({
                    "Line": r.get("line_id", ""),
                    "Part": r.get("part_name", "")[:35],
                    "Piece price": f"€ {sp:,.0f}",
                    "Pattern (total)": f"€ {pc:,.0f}",
                    "Amort qty": f"{int(aq) if aq else '—'}",
                    "Pattern / unit": f"€ {pc_per_unit:,.0f}",
                    "2% handling": f"€ {handling:,.0f}",
                    "Base / unit": f"€ {sp + pc_per_unit + handling:,.0f}",
                })
            if preview_rows:
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

            if st.button("💾 Save casting BOM changes", type="primary"):
                updated = bom.copy()
                for _cc in ["subcontract_price_eur", "pattern_cost_eur", "pattern_amort_qty", "make_buy"]:
                    if _cc in cast_edited.columns and _cc in updated.columns:
                        idx_map = cast_edited.set_index("line_id")[_cc]
                        updated.set_index("line_id", inplace=True)
                        updated.update(idx_map)
                        updated.reset_index(inplace=True)
                _save_bom(updated)
                st.success("✅ Casting BOM changes saved.")
                st.rerun()

        st.divider()
        st.subheader("Foundry quotes for castings")
        st.caption(
            "Record foundry quotes below for reference. "
            "The pattern cost and piece price are entered per BOM line (above). "
            "This section tracks which foundry gave which quote for your records."
        )

        if not quotes.empty:
            cast_quotes = quotes[
                quotes["material_id"].str.contains("CAST", case=False, na=False)
            ].copy()
            if cast_quotes.empty:
                st.info("No casting-specific quotes found (material IDs containing 'CAST').")
            else:
                display_cols = [c for c in
                                ["supplier", "material_id", "lead_time_days", "valid_until",
                                 "pattern_cost_eur", "pattern_amort_qty", "notes"]
                                if c in cast_quotes.columns]
                st.dataframe(cast_quotes[display_cols].rename(columns={
                    "supplier": "Foundry",
                    "material_id": "Material",
                    "lead_time_days": "Lead time (d)",
                    "valid_until": "Valid until",
                    "pattern_cost_eur": "Pattern cost EUR",
                    "pattern_amort_qty": "Amort. qty",
                }), use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — BUY ITEMS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_buy:
        st.markdown("""
**Buy (purchased) items** are components you source fully built — bearings, seals, sensors, valves,
bought-out assemblies, or any item where there is no in-house machining or fabrication.

### How the cost engine handles them

| `make_buy` | `subcontract_price_eur` | How cost is calculated |
|---|---|---|
| **M** (Make) | — | material (kg × €/kg) + full process cost + overhead |
| **B** (Buy) – priced by weight | blank / 0 | material (kg × supplier €/kg) + 2% handling overhead, **no process cost** |
| **B** (Buy) – fixed unit price | Set this field | fixed price × (1 + markup%) + 2% handling, **no material or process cost** |

### Setting a BOM line as Buy

Edit the table below. Set `make_buy = B` and optionally set `subcontract_price_eur` for a fixed
unit price (e.g. a valve quoted at €850 each regardless of weight).

Leave `subcontract_price_eur` blank to price by weight from the Quotes sheet.
""")

        bom_edit = bom.copy() if not bom.empty else pd.DataFrame(columns=BOM_COLUMNS)
        buy_cols_avail = [c for c in BOM_COLUMNS if c in bom_edit.columns]
        # Ensure make_buy column exists
        if "make_buy" not in bom_edit.columns:
            bom_edit["make_buy"] = "M"
        if "subcontract_price_eur" not in bom_edit.columns:
            bom_edit["subcontract_price_eur"] = 0.0

        # Show only the relevant columns
        show_cols = ["line_id", "part_name", "material_id", "qty", "mass_kg",
                     "process_route", "make_buy", "subcontract_price_eur"]
        show_cols = [c for c in show_cols if c in bom_edit.columns]

        # Filter helper
        buy_filter = st.checkbox("Show only Buy items (make_buy = B)", value=False)
        bom_show = bom_edit[bom_edit["make_buy"].str.upper() == "B"] if buy_filter else bom_edit

        st.info(
            f"BOM has **{len(bom_edit)} lines** — "
            f"**{(bom_edit['make_buy'].str.upper() == 'B').sum()} Buy** "
            f"and **{(bom_edit['make_buy'].str.upper() == 'M').sum()} Make**."
        )

        edited_bom = st.data_editor(
            bom_show[show_cols],
            num_rows="fixed",
            use_container_width=True,
            key="bom_buy_editor",
            column_config={
                "line_id":  st.column_config.TextColumn("Line ID", disabled=True, width="small"),
                "part_name": st.column_config.TextColumn("Part", disabled=True, width="large"),
                "material_id": st.column_config.TextColumn("Material", disabled=True, width="small"),
                "qty":      st.column_config.NumberColumn("Qty", disabled=True, width="small"),
                "mass_kg":  st.column_config.NumberColumn("Mass kg", disabled=True, format="%.3f", width="small"),
                "process_route": st.column_config.TextColumn("Process route", disabled=True, width="medium"),
                "make_buy": st.column_config.SelectboxColumn(
                    "Make/Buy",
                    options=["M", "B"],
                    width="small",
                    help="M = manufacture in-house, B = buy/purchase externally",
                ),
                "subcontract_price_eur": st.column_config.NumberColumn(
                    "Fixed price EUR/unit",
                    min_value=0.0,
                    format="€ %.2f",
                    width="medium",
                    help="Leave 0 to price by weight from Quotes sheet. "
                         "Set a value for fixed-price purchased items (e.g. a valve at €850 each).",
                ),
            },
            hide_index=True,
        )

        col_sv, col_info = st.columns([1, 3])
        if col_sv.button("💾 Save BOM changes", type="primary", use_container_width=True):
            # Merge edits back into full bom
            updated = bom_edit.copy()
            if buy_filter:
                # Only edited the buy rows — merge back by line_id
                idx_map = edited_bom.set_index("line_id")[["make_buy", "subcontract_price_eur"]]
                updated.set_index("line_id", inplace=True)
                updated.update(idx_map)
                updated.reset_index(inplace=True)
            else:
                # Edited all rows
                updated = bom_edit.copy()
                updated["make_buy"] = edited_bom["make_buy"].values
                updated["subcontract_price_eur"] = edited_bom["subcontract_price_eur"].values
            _save_bom(updated)
            st.success("✅ BOM saved. Cost calculations will now reflect Buy item pricing.")
            st.rerun()

        with col_info:
            st.caption(
                "🔑 **Make (M):** full process cost applies. "
                "**Buy (B) with no fixed price:** cost = qty × kg × supplier €/kg + 2% handling. "
                "**Buy (B) with fixed price:** cost = fixed EUR × qty + 2% handling."
            )

        # Quick-add buy item helper
        with st.expander("➕ Add a new Buy item (purchased part not yet in BOM)"):
            st.caption(
                "Use this to add a line item for a purchased item like a bought-out seal kit, "
                "sensor, hydraulic unit, or sub-assembly."
            )
            nc1, nc2, nc3, nc4, nc5, nc6 = st.columns(6)
            new_line_id = nc1.text_input("Line ID", placeholder="e.g. HY_VALVE_01")
            new_part    = nc2.text_input("Part name", placeholder="e.g. Relief valve 250 bar")
            new_mat_id  = nc3.selectbox("Material ID", [""] + all_mat_ids, key="new_mat")
            new_qty     = nc4.number_input("Qty", min_value=1, value=1, step=1)
            new_mass    = nc5.number_input("Mass kg", min_value=0.0, value=1.0, format="%.3f")
            new_price   = nc6.number_input("Fixed price EUR/unit", min_value=0.0, value=0.0,
                                            format="%.2f",
                                            help="0 = price from quotes by weight")
            if st.button("➕ Add to BOM", use_container_width=False):
                if not new_line_id.strip() or not new_part.strip():
                    st.error("Line ID and Part name are required.")
                else:
                    new_row = {c: "" for c in bom_edit.columns}
                    new_row.update({
                        "line_id": new_line_id.strip(),
                        "part_name": new_part.strip(),
                        "material_id": new_mat_id if new_mat_id else "",
                        "qty": int(new_qty),
                        "mass_kg": float(new_mass),
                        "process_route": "",
                        "runtime_h": 0.0,
                        "setup_h": 0.0,
                        "make_buy": "B",
                        "cost_type": "UNIT",
                        "subcontract_price_eur": float(new_price) if new_price else 0.0,
                        "scale_exp": 0.0,
                        "yield_factor": 1.0,
                    })
                    updated_bom = pd.concat(
                        [bom_edit, pd.DataFrame([new_row])], ignore_index=True
                    )
                    _save_bom(updated_bom)
                    st.success(f"✅ Added {new_line_id} to BOM as Buy item.")
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — COVERAGE & GAPS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_coverage:
        st.subheader("Quote coverage — what's priced, what's missing")

        today_ts = pd.Timestamp.today().normalize()
        quoted_valid = set()
        if not quotes.empty and "valid_until" in quotes.columns:
            valid_q = quotes[
                pd.to_datetime(quotes["valid_until"], errors="coerce") >= today_ts
            ]
            quoted_valid = set(valid_q["material_id"].dropna().unique())

        quoted_any = set(quotes["material_id"].dropna().unique()) if not quotes.empty else set()
        all_mat_set = set(mats["material_id"].unique()) if not mats.empty else set()

        # BOM materials needed
        bom_mat_needed = set(bom["material_id"].dropna().unique()) if not bom.empty else set()
        # Buy items that have fixed price don't need a material quote
        buy_fixed = set()
        if not bom.empty and "make_buy" in bom.columns and "subcontract_price_eur" in bom.columns:
            buy_fixed = set(
                bom[
                    (bom["make_buy"].str.upper() == "B") &
                    (pd.to_numeric(bom["subcontract_price_eur"], errors="coerce").fillna(0) > 0)
                ]["material_id"].dropna().unique()
            )
        bom_mat_needed -= buy_fixed

        no_quote_at_all  = bom_mat_needed - quoted_any
        expired_only     = bom_mat_needed & (quoted_any - quoted_valid)
        valid_covered    = bom_mat_needed & quoted_valid

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Valid quotes", len(valid_covered))
        c2.metric("🔴 Expired only", len(expired_only),
                  delta="renew!" if expired_only else "✓",
                  delta_color="inverse" if expired_only else "off")
        c3.metric("⬜ No quote at all", len(no_quote_at_all),
                  delta="get quotes" if no_quote_at_all else "✓ covered",
                  delta_color="inverse" if no_quote_at_all else "off")

        if no_quote_at_all:
            st.error(
                f"**{len(no_quote_at_all)} material(s) in BOM have no supplier quote.** "
                "Cost is using the catalogue base price — may not reflect actual purchase cost."
            )
            gap_mats = mats[mats["material_id"].isin(no_quote_at_all)].copy()
            gap_mats["used_in_lines"] = gap_mats["material_id"].map(
                lambda m: ", ".join(
                    bom[bom["material_id"] == m]["line_id"].tolist()
                ) if not bom.empty else ""
            )
            st.dataframe(
                gap_mats[[c for c in ["material_id", "commodity", "price_eur_per_kg", "used_in_lines"]
                           if c in gap_mats.columns]].rename(columns={
                    "material_id": "Material", "commodity": "Commodity",
                    "price_eur_per_kg": "Base price €/kg (fallback)", "used_in_lines": "Used in BOM lines",
                }),
                use_container_width=True, hide_index=True,
            )

        if expired_only:
            st.warning(f"{len(expired_only)} material(s) have expired quotes. "
                       "Use the Quote Refresh tool in the Supplier Quotes tab.")
            exp_df = quotes[quotes["material_id"].isin(expired_only)].copy()
            exp_df["valid_until"] = pd.to_datetime(exp_df["valid_until"], errors="coerce").dt.strftime("%Y-%m-%d")
            st.dataframe(exp_df, use_container_width=True, hide_index=True)

        if not no_quote_at_all and not expired_only:
            st.success("✅ All BOM materials are covered by at least one valid supplier quote.")

        # Buy item summary
        st.divider()
        st.subheader("Buy item pricing summary")
        if not bom.empty and "make_buy" in bom.columns:
            buy_items = bom[bom["make_buy"].str.upper() == "B"].copy()
            if buy_items.empty:
                st.info("No Buy items in BOM. All lines are Make.")
            else:
                buy_items["Pricing method"] = buy_items.apply(
                    lambda r: "Fixed price" if pd.to_numeric(r.get("subcontract_price_eur", 0), errors="coerce") > 0
                    else "By weight (from Quotes)",
                    axis=1,
                )
                buy_items["Coverage"] = buy_items.apply(
                    lambda r: "✅ priced"
                    if (pd.to_numeric(r.get("subcontract_price_eur", 0), errors="coerce") > 0
                        or r.get("material_id", "") in quoted_valid)
                    else "⚠️ missing quote",
                    axis=1,
                )
                show = [c for c in ["line_id", "part_name", "material_id", "qty",
                                    "subcontract_price_eur", "Pricing method", "Coverage"]
                        if c in buy_items.columns or c in ("Pricing method", "Coverage")]
                st.dataframe(
                    buy_items[show].rename(columns={
                        "line_id": "Line ID", "part_name": "Part", "material_id": "Material",
                        "subcontract_price_eur": "Fixed price EUR",
                    }),
                    use_container_width=True, hide_index=True,
                )
        else:
            st.info("No make_buy column found in BOM.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — COST IMPACT
    # ══════════════════════════════════════════════════════════════════════════
    with tab_history:
        st.subheader("Cost impact — what the quotes are worth")
        st.caption(
            "Compare base catalogue cost vs. supplier-quoted cost, and see the "
            "financial impact of unquoted or expired materials."
        )

        try:
            mats_base   = mats.copy()  # no quote overrides
            mats_quoted = apply_best_quotes(mats, quotes)

            df_base   = compute_costs(mats_base, procs, bom)
            df_quoted = compute_costs(mats_quoted, procs, bom)

            base_mat_cost   = df_base["material_cost"].sum()
            quoted_mat_cost = df_quoted["material_cost"].sum()
            saving = base_mat_cost - quoted_mat_cost

            s1, s2, s3 = st.columns(3)
            s1.metric("Catalogue material cost", f"€ {base_mat_cost:,.2f}")
            s2.metric("Supplier-quoted material cost", f"€ {quoted_mat_cost:,.2f}")
            s3.metric(
                "Quote saving vs. catalogue",
                f"€ {abs(saving):,.2f}",
                delta=f"{'lower' if saving > 0 else 'higher'} than catalogue",
                delta_color="normal" if saving > 0 else "inverse",
            )

            # Per-material comparison
            comp_base   = df_base.groupby("material_id")["material_cost"].sum().rename("Base (catalogue)")
            comp_quoted = df_quoted.groupby("material_id")["material_cost"].sum().rename("Quoted (supplier)")
            comp = pd.concat([comp_base, comp_quoted], axis=1).reset_index()
            comp["Saving"] = comp["Base (catalogue)"] - comp["Quoted (supplier)"]
            comp["Saving %"] = (comp["Saving"] / comp["Base (catalogue)"] * 100).fillna(0)
            comp = comp.sort_values("Saving", ascending=False)

            # Format
            for c in ["Base (catalogue)", "Quoted (supplier)", "Saving"]:
                comp[c] = comp[c].map(lambda v: f"€ {v:,.2f}")
            comp["Saving %"] = comp["Saving %"].map(lambda v: f"{v:.1f}%")

            st.dataframe(comp.rename(columns={"material_id": "Material"}),
                         use_container_width=True, hide_index=True)

            # Show total cost comparison
            st.divider()
            base_sell   = df_base["total_cost"].sum()
            quoted_sell = df_quoted["total_cost"].sum()
            t1, t2, t3 = st.columns(3)
            t1.metric("Total sell price (catalogue)", f"€ {base_sell:,.2f}")
            t2.metric("Total sell price (quoted)", f"€ {quoted_sell:,.2f}")
            sell_delta = base_sell - quoted_sell
            t3.metric(
                "Impact on sell price",
                f"€ {abs(sell_delta):,.2f}",
                delta=f"{'reduced' if sell_delta > 0 else 'increased'} by quotes",
                delta_color="normal" if sell_delta > 0 else "inverse",
            )

        except Exception as e:
            st.warning(f"Could not compute cost comparison: {e}")


guard(main)
