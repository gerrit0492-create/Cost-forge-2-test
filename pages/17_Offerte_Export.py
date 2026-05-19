from __future__ import annotations

import datetime

import streamlit as st

from utils.currency import fmt
from utils.docx_export import make_offer_docx
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pdf_export import make_offer_pdf
from utils.pricing import compute_costs
from utils.project import load_project_name
from utils.quotes import apply_best_quotes
from utils.safe import guard


def main():
    st.set_page_config(page_title="Quote Export", layout="wide", page_icon="📦")
    home_button()
    st.title("📦 Quote Export")
    st.caption("Generate a DOCX and PDF quotation document from the active BOM in one click.")

    # ── Quote meta ────────────────────────────────────────────────────────────
    st.subheader("Quote details")
    c1, c2, c3, c4 = st.columns(4)
    quote_number  = c1.text_input("Quote number", value="QT-2026-001")
    customer_name = c2.text_input("Customer",     value="")
    quote_date    = c3.date_input("Date",          value=datetime.date.today())
    project_label = c4.text_input("Project",       value=load_project_name())

    st.divider()

    # ── Load & compute ────────────────────────────────────────────────────────
    mats   = load_materials()
    procs  = load_processes()
    bom    = load_bom()
    quotes = load_quotes()
    df = compute_costs(apply_best_quotes(mats, quotes), procs, bom)

    total_sell = df["total_cost"].sum()
    total_mat  = df["material_cost"].sum() if "material_cost" in df.columns else 0.0
    total_proc = df["process_cost"].sum()  if "process_cost"  in df.columns else 0.0
    total_marg = df["margin"].sum()        if "margin"        in df.columns else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Material",   fmt(total_mat))
    k2.metric("Process",    fmt(total_proc))
    k3.metric("Margin",     fmt(total_marg),
              delta=f"{total_marg/total_sell*100:.1f}% of sell" if total_sell else None)
    k4.metric("Sell price", fmt(total_sell))

    st.divider()

    # ── Preview table ─────────────────────────────────────────────────────────
    show_cols = [c for c in ["line_id", "part_name", "material_id", "qty",
                              "material_cost", "process_cost", "overhead",
                              "margin", "total_cost"] if c in df.columns]
    st.dataframe(df[show_cols].head(30), use_container_width=True, hide_index=True)

    st.divider()

    # ── Downloads ─────────────────────────────────────────────────────────────
    title = f"Quotation {quote_number} — {customer_name or project_label}"
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "⬇️ Download DOCX",
            data=make_offer_docx(df, title=title),
            file_name=f"{quote_number}_quote.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "⬇️ Download PDF",
            data=make_offer_pdf(df, title=title),
            file_name=f"{quote_number}_quote.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


guard(main)
