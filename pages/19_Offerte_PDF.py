from __future__ import annotations

import datetime

import streamlit as st

from utils.currency import fmt
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pdf_export import make_offer_pdf
from utils.pricing import compute_costs
from utils.project import load_project_name
from utils.quotes import apply_best_quotes
from utils.safe import guard


def main():
    st.set_page_config(page_title="Quote PDF", layout="wide", page_icon="🖨️")
    home_button()
    st.title("🖨️ Quote PDF")
    st.caption("PDF quotation document ready for e-mail or printing.")

    c1, c2, c3 = st.columns(3)
    quote_number  = c1.text_input("Quote number", value="QT-2026-001")
    customer_name = c2.text_input("Customer",     value="")
    project_label = c3.text_input("Project",       value=load_project_name())

    st.divider()

    mats  = load_materials()
    procs = load_processes()
    bom   = load_bom()
    df    = compute_costs(apply_best_quotes(mats, load_quotes()), procs, bom)

    total_sell = df["total_cost"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Material",   fmt(df["material_cost"].sum() if "material_cost" in df.columns else 0))
    k2.metric("Process",    fmt(df["process_cost"].sum()  if "process_cost"  in df.columns else 0))
    k3.metric("Sell price", fmt(total_sell))

    show_cols = [c for c in ["line_id", "part_name", "material_id", "qty",
                              "material_cost", "process_cost", "overhead",
                              "margin", "total_cost"] if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)

    title = f"Quotation {quote_number} — {customer_name or project_label}"
    st.download_button(
        "⬇️ Download Quote PDF",
        data=make_offer_pdf(df, title=title),
        file_name=f"{quote_number}_quote.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


guard(main)
