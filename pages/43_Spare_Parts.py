"""
Spare Parts Catalog.
Generate a customer-facing spare parts price list from BOM wear items.
Separate revenue stream — typically 30–50% markup over manufacturing cost.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import (df_to_excel_bytes, load_bom, load_materials,
                      load_processes, load_quotes, save_sheet)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_name
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

WEAR_CATEGORIES = [
    "Impeller / runner",
    "Wear ring / liner",
    "Shaft & bearings",
    "Shaft seal",
    "Nozzle / deflector",
    "Fasteners & seals",
    "Hydraulic components",
    "Electrical / sensors",
    "Other consumable",
    "Structural (non-wearing)",
]

SPARE_RECOMMENDATION = {
    "Impeller / runner":      ("1×", "12–18 months"),
    "Wear ring / liner":      ("2×", "6–12 months"),
    "Shaft & bearings":       ("1 set", "24 months"),
    "Shaft seal":             ("2×", "6–12 months"),
    "Nozzle / deflector":     ("1×", "24 months"),
    "Fasteners & seals":      ("1 set", "Annual service"),
    "Hydraulic components":   ("Per system", "On condition"),
    "Electrical / sensors":   ("1×", "On condition"),
    "Other consumable":       ("As required", "On condition"),
    "Structural (non-wearing)": ("On demand", "On condition"),
}


def main() -> None:
    st.set_page_config(page_title="Spare Parts Catalog", layout="wide", page_icon="🔩")
    inject_css()
    home_button()
    project = load_project_name()
    page_header(
        title="Spare Parts Catalog",
        icon="🔩",
        caption="Generate customer spare parts list with recommended quantities and prices.",
        project=project or "",
    )

    # ── Load cost data ────────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM: {exc}")
        st.stop()

    # ── Sidebar — markup controls ─────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Spare parts pricing")

    default_markup = st.sidebar.slider(
        "Default spare parts markup %", 10, 100, 40, 5,
        help="% above manufacturing cost for all spare parts. "
             "Typically 30–50% for marine capital equipment.",
    )
    currency_sym = st.sidebar.text_input("Currency symbol", value="€")
    show_cost    = st.sidebar.toggle("Show manufacturing cost to user", value=False)

    st.sidebar.divider()
    st.sidebar.subheader("Catalog settings")
    company_name = st.sidebar.text_input("Supplier / OEM name", value="")
    catalog_note = st.sidebar.text_area(
        "Catalog footer note",
        value="Prices valid for 30 days. Lead times subject to stock availability. "
              "Please quote part number when ordering.",
        height=80,
    )

    # ── Step 1: Mark wear items ───────────────────────────────────────────────
    st.subheader("Step 1 — Mark wear / spare parts in BOM")
    st.caption(
        "Tag BOM lines that are customer-replaceable or recommended as spares. "
        "Set the wear category and individual markup per line."
    )

    # Build editable spare parts selection table
    spare_cols = ["line_id", "part_name", "material_id", "qty", "total_cost"]
    spare_seed = df[[c for c in spare_cols if c in df.columns]].copy()
    spare_seed["is_spare"]       = False
    spare_seed["wear_category"]  = "Other consumable"
    spare_seed["spare_markup_pct"] = float(default_markup)
    spare_seed["part_number"]    = spare_seed["line_id"].astype(str)
    spare_seed["notes"]          = ""

    edited_spares = st.data_editor(
        spare_seed,
        column_config={
            "line_id":          st.column_config.TextColumn("Line ID", width="small", disabled=True),
            "part_name":        st.column_config.TextColumn("Component", disabled=True),
            "material_id":      st.column_config.TextColumn("Material", width="small", disabled=True),
            "qty":              st.column_config.NumberColumn("Qty", disabled=True),
            "total_cost":       st.column_config.NumberColumn("Mfg cost €", disabled=True, format="%.2f"),
            "is_spare":         st.column_config.CheckboxColumn("Include as spare?"),
            "wear_category":    st.column_config.SelectboxColumn("Wear category", options=WEAR_CATEGORIES),
            "spare_markup_pct": st.column_config.NumberColumn("Markup %", min_value=0.0, max_value=200.0,
                                                               format="%.0f"),
            "part_number":      st.column_config.TextColumn("Part number"),
            "notes":            st.column_config.TextColumn("Notes"),
        },
        use_container_width=True,
        hide_index=True,
        key="spare_editor",
    )

    selected = edited_spares[edited_spares["is_spare"] == True].copy()

    if selected.empty:
        st.info("Check the **Include as spare?** box on lines you want in the catalog.")
        return

    # ── Step 2: Compute spare parts prices ────────────────────────────────────
    st.divider()
    st.subheader("Step 2 — Spare parts price list")

    selected["spare_price"] = selected["total_cost"] * (1 + selected["spare_markup_pct"] / 100)
    selected["margin_eur"]  = selected["spare_price"] - selected["total_cost"]

    # Add recommendation
    selected["rec_qty"]      = selected["wear_category"].map(
        lambda c: SPARE_RECOMMENDATION.get(c, ("TBD", "On condition"))[0])
    selected["rec_interval"] = selected["wear_category"].map(
        lambda c: SPARE_RECOMMENDATION.get(c, ("TBD", "On condition"))[1])

    # ── KPI row ───────────────────────────────────────────────────────────────
    total_spare_rev  = selected["spare_price"].sum()
    total_spare_cost = selected["total_cost"].sum()
    total_spare_mar  = selected["margin_eur"].sum()
    avg_markup       = (total_spare_mar / total_spare_cost * 100) if total_spare_cost > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Spare parts revenue",   fmt(total_spare_rev, 0))
    k2.metric("Manufacturing cost",    fmt(total_spare_cost, 0))
    k3.metric("Spare parts margin",    fmt(total_spare_mar, 0))
    k4.metric("Average markup",        f"{avg_markup:.0f}%")

    # ── Catalog preview ───────────────────────────────────────────────────────
    tab_cat, tab_analytics = st.tabs(["📄 Catalog preview", "📊 Analytics"])

    with tab_cat:
        if company_name:
            st.markdown(f"### {company_name} — Spare Parts Catalog")
        st.markdown(f"**Project:** {project or '—'}  |  **Valid 30 days from issue**")
        st.divider()

        for cat in WEAR_CATEGORIES:
            cat_items = selected[selected["wear_category"] == cat]
            if cat_items.empty:
                continue
            st.markdown(f"**{cat}**")
            disp = cat_items[["part_number", "part_name", "rec_qty",
                               "rec_interval", "spare_price", "notes"]].copy()
            if show_cost:
                disp["total_cost"] = cat_items["total_cost"].map(lambda x: fmt(x, 2))
            disp["spare_price"] = disp["spare_price"].map(
                lambda x: f"{currency_sym} {x:,.2f}")
            st.dataframe(
                disp.rename(columns={
                    "part_number":   "Part No.",
                    "part_name":     "Description",
                    "rec_qty":       "Rec. Qty",
                    "rec_interval":  "Replace interval",
                    "spare_price":   f"Unit price ({currency_sym})",
                    "notes":         "Notes",
                }),
                use_container_width=True, hide_index=True,
            )

        if catalog_note:
            st.caption(catalog_note)

        # Downloads
        st.divider()
        col_dl1, col_dl2 = st.columns(2)

        def _catalog_excel() -> bytes:
            buf = io.BytesIO()
            out = selected[["part_number", "part_name", "wear_category",
                             "rec_qty", "rec_interval", "spare_price", "notes"]].copy()
            out.rename(columns={
                "part_number":   "Part No.",
                "part_name":     "Description",
                "wear_category": "Category",
                "rec_qty":       "Rec. Qty",
                "rec_interval":  "Replace interval",
                "spare_price":   f"Unit price ({currency_sym})",
                "notes":         "Notes",
            }, inplace=True)
            out[f"Unit price ({currency_sym})"] = out[f"Unit price ({currency_sym})"].round(2)
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                out.to_excel(w, sheet_name="Spare Parts", index=False)
                if show_cost:
                    selected[["part_number", "part_name", "total_cost",
                               "spare_price", "margin_eur", "spare_markup_pct"]].to_excel(
                        w, sheet_name="Internal (cost)", index=False)
            return buf.getvalue()

        col_dl1.download_button(
            "⬇️ Download catalog (Excel)",
            data=_catalog_excel(),
            file_name="spare_parts_catalog.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        # CSV for simple sharing
        csv_out = selected[["part_number", "part_name", "wear_category",
                             "rec_qty", "rec_interval", "spare_price", "notes"]].copy()
        csv_out["spare_price"] = csv_out["spare_price"].round(2)
        col_dl2.download_button(
            "⬇️ Download CSV",
            data=csv_out.to_csv(index=False),
            file_name="spare_parts_catalog.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with tab_analytics:
        st.subheader("Spare parts revenue analytics")

        by_cat = (
            selected.groupby("wear_category")
            .agg(revenue=("spare_price", "sum"), cost=("total_cost", "sum"),
                 items=("part_number", "count"))
            .reset_index()
            .sort_values("revenue", ascending=False)
        )
        by_cat["margin_eur"] = by_cat["revenue"] - by_cat["cost"]
        by_cat["markup_pct"] = ((by_cat["revenue"] / by_cat["cost"] - 1) * 100).round(1)

        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(by_cat.set_index("wear_category")[["revenue", "cost"]].rename(
                columns={"revenue": "Spare price €", "cost": "Mfg cost €"}
            ), color=["#4CAF50", "#2196F3"])
        with c2:
            disp_cat = by_cat.copy()
            disp_cat["revenue"] = disp_cat["revenue"].map(lambda x: fmt(x, 0))
            disp_cat["margin_eur"] = disp_cat["margin_eur"].map(lambda x: fmt(x, 0))
            disp_cat["markup_pct"] = disp_cat["markup_pct"].map(lambda x: f"{x:.0f}%")
            st.dataframe(disp_cat.rename(columns={
                "wear_category": "Category", "revenue": "Revenue €",
                "margin_eur": "Margin €", "markup_pct": "Markup %", "items": "Items",
            }).drop(columns=["cost"], errors="ignore"),
                use_container_width=True, hide_index=True)

        st.metric("Spare parts revenue as % of system price",
                  f"{total_spare_rev / df['total_cost'].sum() * 100:.1f}%"
                  if df["total_cost"].sum() > 0 else "—",
                  delta="typical target: 20–35% of system price",
                  delta_color="off")


guard(main)
