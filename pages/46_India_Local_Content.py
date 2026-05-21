"""
India Local Content (IC%) Manager.

Indian government and defence contracts (DAP 2020, DPP, DPIIT GeM, Shipbuilding
Financial Assistance Policy) require a declared Indigenous Content percentage,
verified by third-party surveying agencies (DGQA, BV, DNV, etc.).

KEY PRINCIPLE: Surveyors verify *manufacturing origin*, not *supplier price*.
You do NOT need to submit your full quote book. Three accepted methods let you
prove IC% without exposing commercial pricing:

  1. Chartered Accountant Certificate — CA certifies IC% from your books.
     Surveyor accepts the certificate; individual quotes stay internal.
  2. Manufacturer's Origin Declaration — Indian supplier signs a declaration
     of domestic manufacture. One page, no price, fully accepted.
  3. HS Code + DGFT licensing route — import data (Bill of Entry) confirms
     what was imported; everything else is deemed domestic.

This page manages all three methods and generates the required outputs.
"""
from __future__ import annotations

import io
import textwrap
from datetime import date

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import (
    load_bom, load_materials, load_processes, load_quotes,
    load_india_lc, save_sheet,
)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_meta
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

# ── Constants ─────────────────────────────────────────────────────────────────
ORIGIN_OPTIONS  = ["Indian", "Imported", "Partially Indian"]
DECL_STATUS     = ["Pending", "Yes", "No", "Not required"]

# IC thresholds per procurement category (DAP 2020 / Make in India for Defence)
IC_THRESHOLDS = {
    "Buy (Indian-IDDM)":          0.50,   # Min 50% IC, design owned by Indian entity
    "Buy (Indian)":               0.40,   # Min 40% IC
    "Buy & Make (Indian)":        0.50,   # 50% IC on make portion
    "Buy & Make":                 0.30,   # 30% IC
    "Make (Indian)":              0.50,
    "Strategic Partnership Model": 0.50,
    "GeM — Class I Local Supplier": 0.50,  # DPIIT GeM portal
    "GeM — Class II Local Supplier": 0.20,
    "Shipbuilding Financial Assistance": 0.30,
    "Custom / contractual":        0.0,   # Enter manually below
}

# Colour coding
def _traffic(val: float, threshold: float) -> str:
    if val >= threshold:
        return "🟢"
    if val >= threshold * 0.85:
        return "🟠"
    return "🔴"


def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"


# ── Excel builders ─────────────────────────────────────────────────────────────
def _build_submission_excel(df_lc: pd.DataFrame, meta: dict,
                             contract_value: float, ic_pct: float) -> bytes:
    """
    Clean submission package — BOM with origin data ONLY (no prices).
    Suitable to hand to the surveying company.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        # Sheet 1: IC Calculation Summary (no individual prices)
        summary = pd.DataFrame([
            ["Project",               meta.get("name", "")],
            ["Customer",              meta.get("customer", "")],
            ["Contract value (€)",    f"{contract_value:,.0f}"],
            ["Declared IC%",          f"{ic_pct * 100:.2f}%"],
            ["Date",                  str(date.today())],
            ["Calculation method",    "Value-based (IC% = Indian value / Total value × 100)"],
            ["Basis",                 "Internal cost records, available for CA certification on request"],
        ], columns=["Field", "Value"])
        summary.to_excel(w, sheet_name="IC Summary", index=False)

        # Sheet 2: BOM origin register (no prices)
        clean = df_lc[["line_id", "part_name", "hs_code", "origin",
                        "indian_supplier", "declaration_rxd", "declaration_ref",
                        "ic_value_pct", "notes"]].copy()
        clean["ic_value_pct"] = clean["ic_value_pct"].map(
            lambda x: f"{float(x or 0) * 100:.0f}%" if pd.notna(x) else "0%")
        clean.rename(columns={
            "line_id":         "Line ID",
            "part_name":       "Component / part",
            "hs_code":         "HS Code",
            "origin":          "Manufacturing origin",
            "indian_supplier": "Indian manufacturer",
            "declaration_rxd": "Origin declaration received",
            "declaration_ref": "Declaration reference",
            "ic_value_pct":    "IC value claimed (%)",
            "notes":           "Notes",
        }, inplace=True)
        clean.to_excel(w, sheet_name="BOM Origin Register", index=False)

        # Sheet 3: Declaration tracker
        decl_needed = df_lc[df_lc["origin"].isin(["Indian", "Partially Indian"])].copy()
        decl_needed = decl_needed[["line_id", "part_name", "indian_supplier",
                                    "declaration_rxd", "declaration_ref"]].copy()
        decl_needed.rename(columns={
            "line_id": "Line ID", "part_name": "Component",
            "indian_supplier": "Indian manufacturer",
            "declaration_rxd": "Declaration received?",
            "declaration_ref": "Reference / date",
        }, inplace=True)
        decl_needed.to_excel(w, sheet_name="Declaration Tracker", index=False)

    return buf.getvalue()


def _ca_cert_text(meta: dict, contract_value: float, ic_pct: float,
                  indian_value: float, imported_value: float) -> str:
    """Draft CA certificate covering letter text."""
    company = meta.get("name", "[PROJECT NAME]")
    customer = meta.get("customer", "[CUSTOMER NAME]")
    today = date.today().strftime("%d %B %Y")
    return textwrap.dedent(f"""\
    CERTIFICATE OF INDIGENOUS CONTENT

    Date: {today}

    To Whom It May Concern,

    This is to certify that we have examined the books of accounts, invoices,
    purchase orders and internal cost records of the above-referenced project:

        Project:              {company}
        Customer / end user:  {customer}
        Total contract value: EUR {contract_value:,.0f}

    Based on our examination, the Indigenous Content (IC) for this supply is
    calculated as follows in accordance with the value-based methodology
    prescribed under the applicable procurement policy:

        Total assessed value:     EUR {contract_value:,.0f}
        Value of imported inputs: EUR {imported_value:,.0f}
        Value of Indian inputs:   EUR {indian_value:,.0f}
        Indigenous Content (IC):  {ic_pct * 100:.2f}%

    IC% = (Indian input value / Total contract value) × 100

    The individual supplier prices and purchase records on which this
    calculation is based are available for inspection by the competent
    authority upon written request and are maintained in accordance with
    applicable statutory requirements.

    This certificate is issued in good faith and to the best of our knowledge
    based on records made available to us.

    Authorised signatory:

    Name:     _______________________________
    Firm:     _______________________________  [CA Firm, Reg No.]
    Membership No.:  _______________________________
    Date:     _______________________________
    Seal:
    """)


def _manufacturer_decl_text(supplier_name: str, component: str,
                              hs_code: str, project: str) -> str:
    """Manufacturer's Declaration of Domestic Origin template."""
    today = date.today().strftime("%d %B %Y")
    return textwrap.dedent(f"""\
    MANUFACTURER'S DECLARATION OF DOMESTIC ORIGIN

    Date: {today}

    To: [Buyer / Authorised Representative]

    We, {supplier_name or '[SUPPLIER NAME]'}, hereby declare that the
    goods described below are manufactured in India and qualify as
    Domestically Manufactured Goods under applicable Indian procurement
    policy:

        Component description:  {component}
        HS Code:                {hs_code or '[HS Code]'}
        Project reference:      {project}

    We further confirm that:
    1. The manufacturing facility is located in India.
    2. The goods are not imported and re-labelled.
    3. The IC value fraction claimed is based on actual manufacturing
       operations performed in India.
    4. We undertake to maintain records to support this declaration for
       a period of not less than 7 years.

    This declaration is made without disclosing commercial pricing, which
    is proprietary information, and is provided solely for the purpose of
    supporting the buyer's Indigenous Content compliance filing.

    Authorised signatory:

    Name:     _______________________________
    Designation: _______________________________
    Company:  {supplier_name or '[SUPPLIER NAME]'}
    Date:     _______________________________
    Seal:
    """)


# ═════════════════════════════════════════════════════════════════════════════
def main() -> None:
    st.set_page_config(page_title="India Local Content", layout="wide", page_icon="🇮🇳")
    inject_css()
    home_button()

    meta    = load_project_meta()
    project = meta.get("name", "")

    page_header(
        title="India Local Content (IC%) Manager",
        icon="🇮🇳",
        caption=(
            "Prove IC% compliance without submitting your full quote book. "
            "Uses CA certificate, manufacturer origin declarations and HS code methods."
        ),
        project=project,
    )

    # ── Load BOM costs ────────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM: {exc}")
        st.stop()

    total_contract_value = float(df["total_cost"].sum())
    lc_df = load_india_lc()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Contract settings")

    procurement_cat = st.sidebar.selectbox(
        "Procurement category",
        list(IC_THRESHOLDS.keys()),
        index=0,
        help="Select the applicable Indian procurement category to set the IC threshold.",
    )
    auto_threshold = IC_THRESHOLDS[procurement_cat]
    custom_threshold_pct = st.sidebar.number_input(
        "IC% threshold (override)",
        min_value=0.0, max_value=100.0,
        value=float(auto_threshold * 100),
        step=1.0,
        help="Auto-filled from category above. Override if your contract specifies a different figure.",
    )
    threshold = custom_threshold_pct / 100.0

    contract_override = st.sidebar.number_input(
        "Contract value (€) — override",
        min_value=0.0,
        value=total_contract_value,
        step=10_000.0,
        format="%.0f",
        help="Defaults to current BOM sell price. Override for the actual signed contract value.",
    )
    contract_value = contract_override if contract_override > 0 else total_contract_value

    company_name     = st.sidebar.text_input("Your company name (for declarations)")
    surveying_agency = st.sidebar.text_input("Surveying / certifying agency", placeholder="e.g. DGQA / BV / DNV")

    st.sidebar.divider()
    st.sidebar.info(
        "**Three accepted methods — no quotes needed:**\n\n"
        "1️⃣ **CA Certificate** — CA certifies IC% from your books. "
        "Quotes stay internal.\n\n"
        "2️⃣ **Origin Declaration** — Indian supplier signs 1-page origin declaration "
        "(no price). Fully accepted by DGQA & classification societies.\n\n"
        "3️⃣ **Bill of Entry method** — import customs records confirm what was imported; "
        "balance is deemed domestic.\n\n"
        "Use all three in parallel for maximum defensibility."
    )

    tabs = st.tabs([
        "📋 IC Register",
        "📊 IC% Dashboard",
        "📝 Submission Documents",
        "🏭 Strategy Adviser",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — IC REGISTER
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[0]:
        st.subheader("Indigenous Content register — tag each BOM line")
        st.caption(
            "Set the manufacturing origin for every line. "
            "For **Partially Indian** lines, set the IC fraction (e.g. 0.60 = 60% of that line's "
            "value is Indian). You do **not** need a supplier price quote — only an origin declaration."
        )

        # Merge BOM cost data with existing LC data
        bom_base = df[["line_id", "part_name", "material_id", "total_cost"]].copy()
        bom_base["hs_code"] = bom_base["material_id"].map(
            mats.set_index("material_id")["hs_code"].to_dict()
        ).fillna("")

        if lc_df.empty:
            # Seed from BOM — default all to Imported (conservative)
            seed = bom_base.copy()
            seed["origin"]          = "Imported"
            seed["indian_supplier"] = ""
            seed["declaration_rxd"] = "Pending"
            seed["declaration_ref"] = ""
            seed["ic_value_pct"]    = 0.0
            seed["notes"]           = ""
        else:
            # Merge saved data with current BOM
            seed = bom_base.merge(
                lc_df[["line_id", "origin", "indian_supplier", "declaration_rxd",
                        "declaration_ref", "ic_value_pct", "notes"]],
                on="line_id", how="left"
            )
            seed["origin"]          = seed["origin"].fillna("Imported")
            seed["indian_supplier"] = seed["indian_supplier"].fillna("")
            seed["declaration_rxd"] = seed["declaration_rxd"].fillna("Pending")
            seed["declaration_ref"] = seed["declaration_ref"].fillna("")
            seed["ic_value_pct"]    = pd.to_numeric(seed["ic_value_pct"], errors="coerce").fillna(0.0)
            seed["notes"]           = seed["notes"].fillna("")

        edited = st.data_editor(
            seed[["line_id", "part_name", "material_id", "hs_code", "total_cost",
                  "origin", "ic_value_pct", "indian_supplier",
                  "declaration_rxd", "declaration_ref", "notes"]],
            column_config={
                "line_id":         st.column_config.TextColumn("Line ID", width="small", disabled=True),
                "part_name":       st.column_config.TextColumn("Component", disabled=True),
                "material_id":     st.column_config.TextColumn("Material", width="small", disabled=True),
                "hs_code":         st.column_config.TextColumn("HS Code", width="small"),
                "total_cost":      st.column_config.NumberColumn("Cost (€)", disabled=True, format="%.0f"),
                "origin":          st.column_config.SelectboxColumn(
                    "Origin", options=ORIGIN_OPTIONS,
                    help="Indian = manufactured in India. Imported = sourced outside India. "
                         "Partially Indian = split."),
                "ic_value_pct":    st.column_config.NumberColumn(
                    "IC fraction (0–1)",
                    min_value=0.0, max_value=1.0, format="%.2f",
                    help="1.0 = 100% Indian. 0.0 = fully imported. "
                         "Auto-set: Indian→1.0, Imported→0.0, Partially Indian→enter manually."),
                "indian_supplier": st.column_config.TextColumn(
                    "Indian manufacturer",
                    help="Name of Indian manufacturing company. No price needed."),
                "declaration_rxd": st.column_config.SelectboxColumn(
                    "Declaration rxd?", options=DECL_STATUS),
                "declaration_ref": st.column_config.TextColumn("Declaration ref / date"),
                "notes":           st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            hide_index=True,
            key="lc_editor",
        )

        # Auto-correct ic_value_pct for pure Indian / Imported
        edited.loc[edited["origin"] == "Indian",   "ic_value_pct"] = 1.0
        edited.loc[edited["origin"] == "Imported",  "ic_value_pct"] = 0.0
        # Partially Indian: keep whatever the user entered

        c_save, c_tip = st.columns([1, 5])
        if c_save.button("💾 Save register", type="primary", use_container_width=True):
            save_df = edited[["line_id", "part_name", "hs_code", "origin",
                               "indian_supplier", "declaration_rxd", "declaration_ref",
                               "ic_value_pct", "notes"]].copy()
            save_sheet(save_df, "india_lc")
            st.success("IC register saved.")
        c_tip.caption(
            "💡 **Tip:** You only need to fill in **Indian manufacturer** names for Indian/Partially Indian lines. "
            "The surveying agency needs the manufacturer name and HS code — NOT your purchase price."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — IC% DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        st.subheader("IC% summary")

        # Calculate IC values
        edited["_ic_eur"] = (
            pd.to_numeric(edited["total_cost"], errors="coerce").fillna(0)
            * pd.to_numeric(edited["ic_value_pct"], errors="coerce").fillna(0)
        )
        edited["_imp_eur"] = (
            pd.to_numeric(edited["total_cost"], errors="coerce").fillna(0)
            * (1 - pd.to_numeric(edited["ic_value_pct"], errors="coerce").fillna(0))
        )

        indian_value   = float(edited["_ic_eur"].sum())
        imported_value = float(edited["_imp_eur"].sum())
        ic_pct         = indian_value / contract_value if contract_value > 0 else 0.0

        # KPIs
        k1, k2, k3, k4, k5 = st.columns(5)
        sig = _traffic(ic_pct, threshold)
        k1.metric("Declared IC%", _pct(ic_pct),
                  delta=f"{sig} {'Meets' if ic_pct >= threshold else 'Below'} {_pct(threshold)} threshold")
        k2.metric("Indian content (€)", fmt(indian_value, 0))
        k3.metric("Imported content (€)", fmt(imported_value, 0))
        k4.metric("Contract value (€)", fmt(contract_value, 0))
        k5.metric("IC threshold", _pct(threshold),
                  delta=procurement_cat, delta_color="off")

        # Gap analysis
        if ic_pct < threshold:
            shortfall_eur = (threshold - ic_pct) * contract_value
            st.error(
                f"⚠️ IC% shortfall: **{_pct(threshold - ic_pct)}** — "
                f"need **{fmt(shortfall_eur, 0)}** more Indian content. "
                f"See Strategy Adviser tab for options."
            )
        else:
            surplus_pct = ic_pct - threshold
            st.success(
                f"✅ IC% exceeds threshold by **{_pct(surplus_pct)}** "
                f"({fmt(surplus_pct * contract_value, 0)} buffer). "
                f"Comfortable position — document and file."
            )

        st.divider()

        # ── Declaration tracker status ──────────────────────────────────────
        st.subheader("Origin declaration status")
        indian_lines = edited[edited["origin"].isin(["Indian", "Partially Indian"])].copy()

        d_yes     = (indian_lines["declaration_rxd"] == "Yes").sum()
        d_pending = (indian_lines["declaration_rxd"] == "Pending").sum()
        d_no      = (indian_lines["declaration_rxd"] == "No").sum()

        dc1, dc2, dc3, dc4 = st.columns(4)
        dc1.metric("Lines needing declaration", len(indian_lines))
        dc2.metric("✅ Received", d_yes,
                   delta="good" if d_pending == 0 else None, delta_color="normal")
        dc3.metric("⏳ Pending", d_pending,
                   delta="chase suppliers" if d_pending > 0 else None,
                   delta_color="inverse" if d_pending > 0 else "off")
        dc4.metric("❌ Not obtained", d_no,
                   delta="risk" if d_no > 0 else None,
                   delta_color="inverse" if d_no > 0 else "off")

        if d_pending > 0:
            pending_suppliers = indian_lines[indian_lines["declaration_rxd"] == "Pending"][
                ["line_id", "part_name", "indian_supplier"]
            ]
            st.warning(
                f"Chase declarations from: "
                + ", ".join(
                    f"**{r['indian_supplier'] or r['line_id']}**"
                    for _, r in pending_suppliers.iterrows()
                )
            )

        st.divider()

        # ── Origin breakdown chart ──────────────────────────────────────────
        by_origin = (
            edited.groupby("origin")["total_cost"]
            .sum()
            .reset_index()
            .rename(columns={"total_cost": "Cost (€)", "origin": "Origin"})
        )
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(by_origin.set_index("Origin"), color="#2196F3", height=200)
        with c2:
            by_origin["IC €"] = by_origin.apply(
                lambda r: r["Cost (€)"] if r["Origin"] == "Indian"
                else (r["Cost (€)"] * edited.loc[
                    edited["origin"] == r["Origin"], "ic_value_pct"
                ].mean() if not edited.loc[edited["origin"] == r["Origin"]].empty else 0),
                axis=1
            )
            by_origin["Cost (€)"] = by_origin["Cost (€)"].map(lambda x: fmt(x, 0))
            st.dataframe(by_origin[["Origin", "Cost (€)"]], use_container_width=True, hide_index=True)

        # ── Largest imported items ──────────────────────────────────────────
        top_imported = edited[edited["origin"] == "Imported"].nlargest(8, "total_cost")[
            ["line_id", "part_name", "material_id", "total_cost"]
        ].copy()
        if not top_imported.empty:
            with st.expander("🔍 Top imported items — consider Indian alternatives"):
                top_imported["total_cost"] = top_imported["total_cost"].map(lambda x: fmt(x, 0))
                st.dataframe(top_imported.rename(columns={
                    "line_id": "Line", "part_name": "Component",
                    "material_id": "Material", "total_cost": "Value (€)"
                }), use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — SUBMISSION DOCUMENTS
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[2]:
        st.subheader("Submission documents — no prices revealed")
        st.info(
            "All documents below are designed for **surveyor / authority submission**. "
            "None contain individual supplier prices. "
            "Your full quote book remains internal — only the CA sees it.",
            icon="🔒",
        )

        ic_pct_calc = (
            (pd.to_numeric(edited["total_cost"], errors="coerce").fillna(0)
             * pd.to_numeric(edited["ic_value_pct"], errors="coerce").fillna(0)).sum()
            / contract_value
        ) if contract_value > 0 else 0.0
        indian_val  = ic_pct_calc * contract_value
        imported_val = contract_value - indian_val

        doc_col1, doc_col2 = st.columns(2)

        # ── Document A: BOM Origin Register (Excel) ─────────────────────────
        with doc_col1:
            with st.container(border=True):
                st.markdown("**📄 Document A — BOM Origin Register**")
                st.caption(
                    "Excel workbook with three sheets: IC Calculation Summary, "
                    "BOM Origin Register (line-by-line, no prices), "
                    "and Declaration Tracker. Hand this to the surveying company."
                )
                save_df = edited[["line_id", "part_name", "hs_code", "origin",
                                   "indian_supplier", "declaration_rxd",
                                   "declaration_ref", "ic_value_pct", "notes"]].copy()
                st.download_button(
                    "⬇️ Download BOM Origin Register (Excel)",
                    data=_build_submission_excel(save_df, meta, contract_value, ic_pct_calc),
                    file_name="india_ic_submission_package.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary",
                )

        # ── Document B: Draft CA Certificate ───────────────────────────────
        with doc_col2:
            with st.container(border=True):
                st.markdown("**📜 Document B — Draft CA Certificate**")
                st.caption(
                    "Text template for your Chartered Accountant to adapt and sign. "
                    "CA certifies IC% from your books; individual quotes stay with you."
                )
                ca_text = _ca_cert_text(meta, contract_value, ic_pct_calc,
                                        indian_val, imported_val)
                st.download_button(
                    "⬇️ Download CA Certificate Template (TXT)",
                    data=ca_text,
                    file_name="ca_certificate_draft.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

        st.divider()

        # ── Document C: Manufacturer Origin Declarations ─────────────────
        st.markdown("**🏭 Document C — Manufacturer's Origin Declarations**")
        st.caption(
            "Generate one declaration per Indian supplier. The supplier signs and stamps it. "
            "No price appears. This is legally accepted as origin proof by DGQA and classification societies."
        )

        indian_lines2 = edited[edited["origin"].isin(["Indian", "Partially Indian"])].copy()

        if indian_lines2.empty:
            st.info("No lines tagged as Indian yet — update the IC Register tab first.")
        else:
            # Group by supplier
            suppliers_in_bom = indian_lines2["indian_supplier"].fillna("").unique()
            suppliers_in_bom = [s for s in suppliers_in_bom if s.strip()]

            if not suppliers_in_bom:
                st.warning("Fill in **Indian manufacturer** names in the IC Register to generate declarations.")
            else:
                sel_supplier = st.selectbox("Select supplier to generate declaration for",
                                             options=suppliers_in_bom)
                sup_lines = indian_lines2[
                    indian_lines2["indian_supplier"].fillna("") == sel_supplier
                ]
                # Use first component for the template; list all in notes
                component_list = "; ".join(sup_lines["part_name"].fillna("").tolist())
                hs_list = "; ".join(sup_lines["hs_code"].fillna("").tolist())

                decl_text = _manufacturer_decl_text(
                    supplier_name=sel_supplier,
                    component=component_list,
                    hs_code=hs_list,
                    project=project,
                )
                with st.expander("Preview declaration text"):
                    st.text(decl_text)

                st.download_button(
                    f"⬇️ Download declaration — {sel_supplier}",
                    data=decl_text,
                    file_name=f"origin_declaration_{sel_supplier.replace(' ', '_')}.txt",
                    mime="text/plain",
                    use_container_width=False,
                )

        st.divider()

        # ── Document D: Internal IC workbook (WITH prices, for CA) ────────
        st.markdown("**🔐 Document D — Internal IC Workbook (for CA only — CONFIDENTIAL)**")
        st.caption(
            "Full detail with costs — give ONLY to your CA firm, not to the surveyor. "
            "CA uses this to certify the IC% calculation."
        )

        def _internal_excel() -> bytes:
            buf = io.BytesIO()
            out = edited.copy()
            out["_ic_eur"] = (
                pd.to_numeric(out["total_cost"], errors="coerce").fillna(0)
                * pd.to_numeric(out["ic_value_pct"], errors="coerce").fillna(0)
            )
            out["_imp_eur"] = out["total_cost"].fillna(0) - out["_ic_eur"]
            out["ic_value_pct_fmt"] = out["ic_value_pct"].map(
                lambda x: f"{float(x or 0)*100:.0f}%")
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                out[["line_id", "part_name", "material_id", "total_cost",
                     "origin", "ic_value_pct_fmt", "_ic_eur", "_imp_eur",
                     "indian_supplier", "hs_code", "declaration_rxd",
                     "declaration_ref", "notes"]].rename(columns={
                    "line_id": "Line ID", "part_name": "Component",
                    "material_id": "Material", "total_cost": "BOM cost (€)",
                    "origin": "Origin", "ic_value_pct_fmt": "IC%",
                    "_ic_eur": "IC value (€)", "_imp_eur": "Import value (€)",
                    "indian_supplier": "Indian manufacturer",
                    "hs_code": "HS Code",
                    "declaration_rxd": "Declaration rxd?",
                    "declaration_ref": "Declaration ref",
                }).to_excel(w, sheet_name="IC Detail", index=False)

                pd.DataFrame([
                    ["Contract value (€)",   f"{contract_value:,.0f}"],
                    ["Indian content (€)",   f"{indian_val:,.0f}"],
                    ["Imported content (€)", f"{imported_val:,.0f}"],
                    ["Declared IC%",         f"{ic_pct_calc * 100:.2f}%"],
                    ["Required IC%",         f"{threshold * 100:.1f}%"],
                    ["Category",             procurement_cat],
                    ["Date",                 str(date.today())],
                ], columns=["Field", "Value"]).to_excel(w, sheet_name="Summary", index=False)
            return buf.getvalue()

        st.download_button(
            "⬇️ Download internal IC workbook (CONFIDENTIAL — CA eyes only)",
            data=_internal_excel(),
            file_name="india_ic_internal_CONFIDENTIAL.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — STRATEGY ADVISER
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        st.subheader("Strategy adviser — how to reach your IC% target")

        ic_pct_now = ic_pct_calc
        shortfall  = max(threshold - ic_pct_now, 0.0)

        if shortfall == 0:
            st.success(
                f"✅ You currently meet the IC% requirement ({_pct(ic_pct_now)} ≥ {_pct(threshold)}). "
                "Focus on documentation (declarations, CA cert) rather than sourcing changes."
            )

        else:
            shortfall_eur = shortfall * contract_value
            st.error(
                f"Shortfall: **{_pct(shortfall)}** = **{fmt(shortfall_eur, 0)}** of additional "
                f"Indian content needed to reach {_pct(threshold)}."
            )

        st.divider()
        st.markdown("### 🎯 Mitigation options — ranked by effort")

        with st.container(border=True):
            st.markdown("#### 1️⃣ Partially Indian items — maximise claimed fraction (fastest, zero cost)")
            st.markdown(
                "Any item tagged **Partially Indian** where the IC fraction is set conservatively "
                "can be reassessed with better data. If an Indian foundry casts the blank and an "
                "imported CNC finishes it, the casting portion IS Indian content. "
                "Get a cost breakdown from the Indian supplier confirming the split."
            )
            partial_lines = edited[edited["origin"] == "Partially Indian"].copy()
            if partial_lines.empty:
                st.caption("No Partially Indian lines tagged yet.")
            else:
                partial_lines["_upside_eur"] = (
                    partial_lines["total_cost"].fillna(0)
                    * (1 - partial_lines["ic_value_pct"].fillna(0))
                )
                partial_lines["ic_value_pct"] = partial_lines["ic_value_pct"].map(
                    lambda x: f"{float(x)*100:.0f}%")
                partial_lines["_upside_eur"] = partial_lines["_upside_eur"].map(
                    lambda x: fmt(x, 0))
                st.dataframe(
                    partial_lines[["line_id", "part_name", "indian_supplier",
                                   "ic_value_pct", "_upside_eur"]].rename(columns={
                        "line_id": "Line", "part_name": "Component",
                        "indian_supplier": "Indian manufacturer",
                        "ic_value_pct": "Current IC%",
                        "_upside_eur": "Max upside (€) if 100%",
                    }),
                    use_container_width=True, hide_index=True,
                )

        with st.container(border=True):
            st.markdown("#### 2️⃣ NRE & Engineering services — 100% Indian by default")
            st.markdown(
                "Engineering, commissioning, site supervision, documentation, training and "
                "after-sales support performed **in India by Indian personnel** count as 100% IC. "
                "If you have Indian subcontractors or agents doing any of this, tag it. "
                "This is the easiest Indian content to add — it's already there."
            )
            nre_ic_eur = 0.0
            try:
                from utils.io import load_nre
                from utils.nre import nre_total
                nre_df = load_nre()
                if not nre_df.empty:
                    nre_ic_eur = float(nre_total(nre_df))
                    st.metric(
                        "NRE / engineering cost",
                        fmt(nre_ic_eur, 0),
                        delta="Add to IC% if performed in India",
                        delta_color="normal",
                    )
                    nre_contribution = nre_ic_eur / contract_value if contract_value > 0 else 0
                    st.caption(
                        f"If all NRE is Indian: IC% = {_pct(ic_pct_now + nre_contribution)} "
                        f"(currently {_pct(ic_pct_now)})"
                    )
            except Exception:
                st.caption("Load NRE data in Engineering & NRE page to see NRE IC contribution.")

        with st.container(border=True):
            st.markdown("#### 3️⃣ Indian alternative suppliers — top candidates")
            st.markdown(
                "The items below are currently **Imported** and have the highest value. "
                "Consider whether an Indian foundry, fabricator or distributor can supply "
                "a compliant alternative — even if at a modest premium, the IC% uplift may "
                "be commercially beneficial."
            )
            top_imp = edited[edited["origin"] == "Imported"].nlargest(6, "total_cost")[
                ["line_id", "part_name", "material_id", "total_cost", "hs_code"]
            ].copy()
            if top_imp.empty:
                st.caption("No imported lines.")
            else:
                top_imp["total_cost"] = top_imp["total_cost"].map(lambda x: fmt(x, 0))
                top_imp["IC uplift if Indian"] = top_imp.apply(
                    lambda r: _pct(
                        pd.to_numeric(
                            edited.loc[edited["line_id"] == r["line_id"], "total_cost"],
                            errors="coerce"
                        ).fillna(0).sum() / contract_value
                    ) if contract_value > 0 else "—",
                    axis=1,
                )
                st.dataframe(
                    top_imp.rename(columns={
                        "line_id": "Line", "part_name": "Component",
                        "material_id": "Material", "total_cost": "Value (€)",
                        "hs_code": "HS Code",
                    }),
                    use_container_width=True, hide_index=True,
                )

        with st.container(border=True):
            st.markdown("#### 4️⃣ Structuring the contract — advanced methods")
            st.markdown(
                """
**Bill of Entry (BoE) method:**
File a Bill of Entry for every imported item. The customs-cleared import value is officially
documented. Everything in the contract value not covered by a BoE is deemed Indian. Simple,
irrefutable, and requires zero supplier cooperation beyond standard import paperwork.

**Free Issue Material (FIM):**
If the Indian customer is purchasing certain imported items themselves and providing them free
of charge to you, those items may be excluded from the IC% denominator entirely, boosting your
effective IC%. Requires contract clause — worth negotiating for high-value imports.

**Offset arrangements:**
Under DAP 2020, foreign OEMs with large Indian defence contracts can generate Offset
credits by placing work with Indian entities. If your parent company has an offset obligation
in India, sub-placing machining/assembly work is dual-purpose.

**Letter of Comfort vs. full quotes:**
For Partially Indian items where you are getting a competitive domestic quote, you can
present a Letter of Intent from the Indian supplier (not the actual price quote) as evidence
you are actively pursuing Indian sourcing. Accepted at tender stage by most authorities.
                """
            )

        st.divider()
        st.info(
            "**Bottom line:** Do not submit your full quote book. "
            "Submit: (A) BOM Origin Register, (B) CA Certificate, (C) Supplier Origin Declarations. "
            "Your CA sees the internal workbook; the surveyor sees only origin data.",
            icon="🔒",
        )


guard(main)
