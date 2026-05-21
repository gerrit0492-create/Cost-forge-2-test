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
ORIGIN_OPTIONS = ["Indian", "Imported", "Partially Indian"]
DECL_STATUS    = ["Pending", "Yes", "No", "Not required"]

# ── HS code keyword → code mapping (marine / industrial components) ───────────
# Each entry: (tuple-of-keywords,  hs_code,  short description)
_HS_KEYWORD_MAP: list[tuple[tuple[str, ...], str, str]] = [
    (("impeller", "runner", "wheel"),                       "8413.91", "Parts for pumps"),
    (("nozzle", "deflector", "jet tube", "steering nozzle"),"8481.80", "Taps/cocks/valves"),
    (("shaft",),                                            "8483.10", "Transmission shafts"),
    (("ball bearing", "roller bearing", "taper bearing"),   "8482.10", "Bearings"),
    (("bearing",),                                          "8482.80", "Bearings — other"),
    (("mechanical seal", "lip seal", "face seal"),          "8484.10", "Gaskets & seals"),
    (("o-ring", "o ring", "oring"),                         "4016.93", "Rubber gaskets"),
    (("gasket", "rubber", "elastomer"),                     "4016.93", "Vulcanised rubber"),
    (("wear ring", "liner", "wear liner"),                  "8413.91", "Parts for pumps"),
    (("casing", "housing", "volute", "bowl", "scroll"),     "8413.91", "Parts for pumps"),
    (("cover", "end cover", "bearing housing"),             "8413.91", "Parts for pumps"),
    (("valve", "check valve", "gate valve", "butterfly"),   "8481.80", "Valves"),
    (("bolt", "stud", "cap screw", "hex bolt"),             "7318.15", "Screws & bolts"),
    (("nut", "lock nut", "hex nut"),                        "7318.16", "Nuts"),
    (("washer", "spring washer"),                           "7318.21", "Washers"),
    (("flange",),                                           "7307.91", "Flanges — steel"),
    (("pipe", "tube", "hose"),                              "7304.49", "Seamless pipes/tubes"),
    (("casting", "cast bronze", "cast nab"),                "7419.99", "Copper alloy articles"),
    (("nab", "aluminium bronze", "nickel aluminium"),       "8413.91", "Parts for pumps"),
    (("bronze", "gunmetal"),                                "7419.99", "Copper alloy articles"),
    (("sensor", "transducer", "transmitter", "pressure sensor"), "9026.80", "Measuring instruments"),
    (("motor", "servo motor", "electric motor"),            "8501.10", "Electric motors"),
    (("pump",),                                             "8413.50", "Centrifugal pumps"),
    (("hydraulic", "cylinder", "ram"),                      "8412.21", "Hydraulic actuators"),
    (("cable", "wire", "wiring harness"),                   "8544.49", "Electric conductors"),
    (("gearbox", "gear", "pinion", "bevel gear"),           "8483.40", "Gears & gearing"),
    (("coupling", "flexible coupling", "rigid coupling"),   "8483.60", "Couplings"),
    (("bracket", "frame", "weldment", "fabrication"),       "7326.90", "Other steel articles"),
    (("stainless", "ss316", "ss304", "duplex"),             "7326.90", "Other steel articles"),
    (("paint", "coating", "primer", "epoxy"),               "3208.90", "Paints & varnishes"),
    (("key", "keyway", "dowel"),                            "7318.29", "Other threaded articles"),
    (("grease", "lubricant", "oil"),                        "2710.19", "Lubricating oils"),
    (("nameplate", "label", "plate"),                       "8310.00", "Sign-plates & nameplates"),
]


def _suggest_hs_code(part_name: str) -> str:
    """Return a likely HS code based on keywords in the component name.
    Returns empty string when no match — user fills it in."""
    name_lower = str(part_name or "").lower()
    for keywords, hs_code, _ in _HS_KEYWORD_MAP:
        if any(kw in name_lower for kw in keywords):
            return hs_code
    return ""


# ── Known Indian manufacturers (marine / industrial) ─────────────────────────
INDIAN_SUPPLIERS: list[str] = [
    "",                                         # blank — for non-Indian lines
    # Castings & forgings
    "Bharat Forge Ltd",
    "Bhoruka Aluminium Ltd",
    "Electrosteel Castings Ltd",
    "Hinduja Foundries Ltd",
    "Kirloskar Ferrous Industries",
    "Nelcast Ltd",
    "Sundaram Clayton Ltd",
    "WFD Metalcast India",
    # Machined / fabricated components
    "BEML Ltd",
    "Godrej & Boyce Mfg Co Ltd",
    "HMT Ltd (Machine Tools)",
    "L&T Precision Engineering",
    "Larsen & Toubro Ltd",
    "Tata Advanced Systems Ltd",
    # Bearings
    "FAG Bearings India (Schaeffler India)",
    "NBC Bearings (National Engineering Industries)",
    "SKF India Ltd",
    "Timken India Ltd",
    # Seals & gaskets
    "Freudenberg Sealing Technologies India",
    "Parker Hannifin India Pvt Ltd",
    "Trelleborg Sealing Solutions India",
    # Fasteners
    "Bulten India Pvt Ltd",
    "Sundaram Fasteners Ltd",
    "Vikrant Screw Factory",
    # Hydraulics & pneumatics
    "Bosch Rexroth India Ltd",
    "Eaton Fluid Power Ltd (India)",
    "Parker Hannifin India Pvt Ltd",
    # Electrical & instrumentation
    "ABB India Ltd",
    "Bharat Heavy Electricals Ltd (BHEL)",
    "Emerson Electric India",
    "Honeywell Automation India",
    "Schneider Electric India",
    "Siemens Ltd India",
    # Valves
    "Alfa Laval India Pvt Ltd",
    "Audco India Ltd (Flowserve)",
    "KSB Pumps Ltd",
    "L&T Valves Ltd",
    # Stainless / structural steel
    "Bhushan Steel Ltd",
    "Jindal Stainless Ltd",
    "Kalyani Steels Ltd",
    "Mukand Ltd",
    # Pumps & fluid equipment
    "Flowserve India Controls Pvt Ltd",
    "Kirloskar Brothers Ltd",
    "KSB Pumps Ltd",
    "Sulzer India Ltd",
    # Marine & defence
    "Cochin Shipyard Ltd",
    "Garden Reach Shipbuilders & Engineers Ltd",
    "Goa Shipyard Ltd",
    "Hindustan Shipyard Ltd",
    "Mazagon Dock Shipbuilders Ltd",
    # Rubber & sealing
    "Fenner India Ltd",
    "Gates India Pvt Ltd",
    "Premier Rubber Works",
    # Other
    "Other Indian manufacturer",
]

IC_THRESHOLDS = {
    "Buy (Indian-IDDM)":             0.50,
    "Buy (Indian)":                  0.40,
    "Buy & Make (Indian)":           0.50,
    "Buy & Make":                    0.30,
    "Make (Indian)":                 0.50,
    "Strategic Partnership Model":   0.50,
    "GeM — Class I Local Supplier":  0.50,
    "GeM — Class II Local Supplier": 0.20,
    "Shipbuilding Financial Assistance": 0.30,
    "Custom / contractual":          0.0,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _traffic(val: float, threshold: float) -> str:
    if val >= threshold:        return "🟢"
    if val >= threshold * 0.85: return "🟠"
    return "🔴"

def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"

def _col(df: pd.DataFrame, name: str, default="") -> pd.Series:
    """Return column if it exists, else a series of default values."""
    return df[name] if name in df.columns else pd.Series([default] * len(df), index=df.index)


# ── Document builders ─────────────────────────────────────────────────────────
def _build_submission_excel(df_lc: pd.DataFrame, meta: dict,
                             contract_value: float, ic_pct: float) -> bytes:
    """Clean submission package — BOM with origin data ONLY (no prices)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        # Sheet 1: IC Summary
        pd.DataFrame([
            ["Project",            meta.get("name", "")],
            ["Customer",           meta.get("customer", "")],
            ["Contract value (€)", f"{contract_value:,.0f}"],
            ["Declared IC%",       f"{ic_pct * 100:.2f}%"],
            ["Date",               str(date.today())],
            ["Calculation method", "Value-based (IC% = Indian value / Total value × 100)"],
            ["Basis",              "Internal cost records, available for CA certification on request"],
        ], columns=["Field", "Value"]).to_excel(w, sheet_name="IC Summary", index=False)

        # Sheet 2: BOM origin register (no prices)
        clean = pd.DataFrame({
            "Line ID":                    _col(df_lc, "line_id"),
            "Component / part":           _col(df_lc, "part_name"),
            "HS Code":                    _col(df_lc, "hs_code"),
            "Manufacturing origin":       _col(df_lc, "origin", "Imported"),
            "Indian manufacturer":        _col(df_lc, "indian_supplier"),
            "Origin declaration received":_col(df_lc, "declaration_rxd", "Pending"),
            "Declaration reference":      _col(df_lc, "declaration_ref"),
            "IC value claimed (%)":       _col(df_lc, "ic_value_pct", 0.0).map(
                                              lambda x: f"{float(x or 0) * 100:.0f}%"),
            "Notes":                      _col(df_lc, "notes"),
        })
        clean.to_excel(w, sheet_name="BOM Origin Register", index=False)

        # Sheet 3: Declaration tracker
        mask = _col(df_lc, "origin", "Imported").isin(["Indian", "Partially Indian"])
        pd.DataFrame({
            "Line ID":               _col(df_lc, "line_id")[mask].values,
            "Component":             _col(df_lc, "part_name")[mask].values,
            "Indian manufacturer":   _col(df_lc, "indian_supplier")[mask].values,
            "Declaration received?": _col(df_lc, "declaration_rxd", "Pending")[mask].values,
            "Reference / date":      _col(df_lc, "declaration_ref")[mask].values,
        }).to_excel(w, sheet_name="Declaration Tracker", index=False)

    return buf.getvalue()


def _ca_cert_text(meta: dict, contract_value: float, ic_pct: float,
                  indian_value: float, imported_value: float) -> str:
    today = date.today().strftime("%d %B %Y")
    return textwrap.dedent(f"""\
    CERTIFICATE OF INDIGENOUS CONTENT

    Date: {today}

    To Whom It May Concern,

    This is to certify that we have examined the books of accounts, invoices,
    purchase orders and internal cost records of the above-referenced project:

        Project:              {meta.get("name", "[PROJECT NAME]")}
        Customer / end user:  {meta.get("customer", "[CUSTOMER NAME]")}
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
    today = date.today().strftime("%d %B %Y")
    return textwrap.dedent(f"""\
    MANUFACTURER'S DECLARATION OF DOMESTIC ORIGIN

    Date: {today}

    To: [Buyer / Authorised Representative]

    We, {supplier_name or "[SUPPLIER NAME]"}, hereby declare that the goods
    described below are manufactured in India and qualify as Domestically
    Manufactured Goods under applicable Indian procurement policy:

        Component description:  {component}
        HS Code:                {hs_code or "[HS Code]"}
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
    Company:  {supplier_name or "[SUPPLIER NAME]"}
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

    # Ensure required columns exist in cost df (compute_costs may not pass all BOM cols through)
    for _col_name in ("line_id", "part_name", "material_id", "total_cost"):
        if _col_name not in df.columns:
            # Try to pull from BOM directly
            if _col_name in bom.columns:
                df = df.merge(bom[["line_id", _col_name]].drop_duplicates("line_id"),
                              on="line_id", how="left", suffixes=("", "_bom"))
            else:
                df[_col_name] = ""

    total_contract_value = float(df["total_cost"].fillna(0).sum())
    lc_df = load_india_lc()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Contract settings")

    procurement_cat = st.sidebar.selectbox(
        "Procurement category",
        list(IC_THRESHOLDS.keys()),
        index=0,
        help="Selects the IC% threshold for the applicable Indian procurement category.",
    )
    auto_threshold = IC_THRESHOLDS[procurement_cat]
    custom_threshold_pct = st.sidebar.number_input(
        "IC% threshold (override)",
        min_value=0.0, max_value=100.0,
        value=float(auto_threshold * 100),
        step=1.0,
        help="Auto-filled from category. Override if your contract specifies a different figure.",
    )
    threshold = custom_threshold_pct / 100.0

    contract_override = st.sidebar.number_input(
        "Contract value (€) — override",
        min_value=0.0,
        value=float(total_contract_value),
        step=10_000.0,
        format="%.0f",
        help="Defaults to BOM sell price. Override with actual signed contract value.",
    )
    contract_value = float(contract_override) if contract_override > 0 else float(total_contract_value)

    st.sidebar.text_input("Your company name (for declarations)")
    st.sidebar.text_input("Surveying / certifying agency", placeholder="e.g. DGQA / BV / DNV")

    st.sidebar.divider()
    st.sidebar.info(
        "**Three accepted methods — no quotes needed:**\n\n"
        "1️⃣ **CA Certificate** — CA certifies IC% from your books. Quotes stay internal.\n\n"
        "2️⃣ **Origin Declaration** — Indian supplier signs 1-page form (no price). "
        "Accepted by DGQA & classification societies.\n\n"
        "3️⃣ **Bill of Entry method** — customs import records confirm what was imported; "
        "balance is deemed domestic.\n\n"
        "Use all three in parallel for maximum defensibility."
    )

    # ── Build seed table BEFORE tabs (used by all four tabs) ─────────────────
    # Safe hs_code lookup — column may not exist in materials sheet yet
    if "hs_code" in mats.columns and "material_id" in mats.columns:
        hs_map = mats.dropna(subset=["material_id"]).set_index("material_id")["hs_code"].to_dict()
    else:
        hs_map = {}

    bom_base = df[["line_id", "part_name", "material_id", "total_cost"]].copy()
    bom_base["hs_code"] = bom_base["material_id"].map(hs_map).fillna("").astype(str)

    today_iso = date.today().isoformat()   # e.g. "2026-05-21"

    if lc_df.empty:
        seed = bom_base.copy()
        seed["origin"]          = "Imported"
        seed["indian_supplier"] = ""
        seed["declaration_rxd"] = "Pending"
        seed["declaration_ref"] = today_iso   # default to today for new rows
        seed["ic_value_pct"]    = 0.0
        seed["notes"]           = ""
    else:
        # Only pull columns that actually exist in lc_df
        lc_merge_cols = ["line_id"] + [
            c for c in ["origin", "indian_supplier", "declaration_rxd",
                         "declaration_ref", "ic_value_pct", "notes"]
            if c in lc_df.columns
        ]
        seed = bom_base.merge(lc_df[lc_merge_cols], on="line_id", how="left")

        seed["origin"]          = seed.get("origin",         pd.Series(dtype=str)).fillna("Imported")
        seed["indian_supplier"] = seed.get("indian_supplier", pd.Series(dtype=str)).fillna("")
        seed["declaration_rxd"] = seed.get("declaration_rxd", pd.Series(dtype=str)).fillna("Pending")
        # Default blank declaration_ref to today so new rows have a sensible starting date
        seed["declaration_ref"] = seed.get("declaration_ref", pd.Series(dtype=str)).fillna(today_iso)
        seed["declaration_ref"] = seed["declaration_ref"].replace("", today_iso)
        seed["ic_value_pct"]    = pd.to_numeric(
            seed.get("ic_value_pct", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        seed["notes"]           = seed.get("notes", pd.Series(dtype=str)).fillna("")

    # Guarantee hs_code column exists (loaded lc_df might overwrite via merge)
    if "hs_code" not in seed.columns:
        seed["hs_code"] = ""

    # Auto-suggest HS codes for lines where it is still blank
    mask_blank_hs = seed["hs_code"].fillna("").str.strip() == ""
    seed.loc[mask_blank_hs, "hs_code"] = seed.loc[mask_blank_hs, "part_name"].map(_suggest_hs_code)

    # Ensure total_cost is numeric
    seed["total_cost"] = pd.to_numeric(seed["total_cost"], errors="coerce").fillna(0.0)

    # ── Tabs ──────────────────────────────────────────────────────────────────
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
        st.info(
            "🤖 **HS codes** are auto-suggested from the component name — verify and correct where needed.  "
            "🏭 **Indian manufacturer** is a searchable dropdown of known Indian suppliers — "
            "type to filter or scroll.  "
            "📅 **Declaration ref** defaults to today's date; update it when the signed declaration arrives.",
            icon="ℹ️",
        )

        edited = st.data_editor(
            seed[["line_id", "part_name", "material_id", "hs_code", "total_cost",
                  "origin", "ic_value_pct", "indian_supplier",
                  "declaration_rxd", "declaration_ref", "notes"]],
            column_config={
                "line_id":         st.column_config.TextColumn("Line ID", width="small", disabled=True),
                "part_name":       st.column_config.TextColumn("Component", disabled=True),
                "material_id":     st.column_config.TextColumn("Material", width="small", disabled=True),
                "hs_code":         st.column_config.TextColumn("HS Code", width="small",
                                       help="Fill in if blank — needed for Bill of Entry method."),
                "total_cost":      st.column_config.NumberColumn("Cost (€)", disabled=True, format="%.0f"),
                "origin":          st.column_config.SelectboxColumn(
                                       "Origin", options=ORIGIN_OPTIONS,
                                       help="Indian = manufactured in India. "
                                            "Imported = sourced outside India. "
                                            "Partially Indian = split (set IC fraction)."),
                "ic_value_pct":    st.column_config.NumberColumn(
                                       "IC fraction (0–1)", min_value=0.0, max_value=1.0, format="%.2f",
                                       help="Auto-set: Indian→1.0, Imported→0.0. "
                                            "For Partially Indian enter the fraction manually."),
                "indian_supplier": st.column_config.SelectboxColumn(
                                       "Indian manufacturer",
                                       options=INDIAN_SUPPLIERS,
                                       help="Select known Indian manufacturer, or type to filter. "
                                            "Name only — no price needed."),
                "declaration_rxd": st.column_config.SelectboxColumn(
                                       "Declaration rxd?", options=DECL_STATUS),
                "declaration_ref": st.column_config.TextColumn(
                                       "Declaration ref / date",
                                       help="Free text — defaults to today's date. "
                                            "Update when declaration is actually received."),
                "notes":           st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            hide_index=True,
            key="lc_editor",
        )

        # Auto-correct ic_value_pct for pure Indian / Imported
        edited = edited.copy()
        edited["ic_value_pct"] = pd.to_numeric(edited["ic_value_pct"], errors="coerce").fillna(0.0)
        edited.loc[edited["origin"] == "Indian",   "ic_value_pct"] = 1.0
        edited.loc[edited["origin"] == "Imported", "ic_value_pct"] = 0.0
        edited["total_cost"] = pd.to_numeric(edited["total_cost"], errors="coerce").fillna(0.0)

        c_save, c_tip = st.columns([1, 5])
        if c_save.button("💾 Save register", type="primary", use_container_width=True):
            save_df = edited[["line_id", "part_name", "hs_code", "origin",
                               "indian_supplier", "declaration_rxd", "declaration_ref",
                               "ic_value_pct", "notes"]].copy()
            save_sheet(save_df, "india_lc")
            st.success("✅ IC register saved.")
        c_tip.caption(
            "💡 Fill in **Indian manufacturer** names for Indian/Partially Indian lines. "
            "The surveying agency needs the manufacturer name and HS code — NOT your purchase price."
        )

    # Pre-compute IC values used by all remaining tabs
    ic_eur     = edited["total_cost"] * edited["ic_value_pct"]
    imp_eur    = edited["total_cost"] * (1 - edited["ic_value_pct"])
    indian_val = float(ic_eur.sum())
    ic_pct_calc = indian_val / contract_value if contract_value > 0 else 0.0
    imported_val = contract_value - indian_val

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — IC% DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        st.subheader("IC% summary")

        k1, k2, k3, k4, k5 = st.columns(5)
        sig = _traffic(ic_pct_calc, threshold)
        k1.metric("Declared IC%", _pct(ic_pct_calc),
                  delta=f"{sig} {'Meets' if ic_pct_calc >= threshold else 'Below'} "
                        f"{_pct(threshold)} threshold")
        k2.metric("Indian content (€)",   fmt(indian_val, 0))
        k3.metric("Imported content (€)", fmt(imported_val, 0))
        k4.metric("Contract value (€)",   fmt(contract_value, 0))
        k5.metric("IC threshold",         _pct(threshold),
                  delta=procurement_cat, delta_color="off")

        if ic_pct_calc < threshold:
            shortfall_eur = (threshold - ic_pct_calc) * contract_value
            st.error(
                f"⚠️ IC% shortfall: **{_pct(threshold - ic_pct_calc)}** — "
                f"need **{fmt(shortfall_eur, 0)}** more Indian content. "
                "See **Strategy Adviser** tab for options."
            )
        else:
            surplus = ic_pct_calc - threshold
            st.success(
                f"✅ IC% exceeds threshold by **{_pct(surplus)}** "
                f"({fmt(surplus * contract_value, 0)} buffer). "
                "Comfortable — focus on documentation."
            )

        st.divider()

        # ── Declaration tracker ───────────────────────────────────────────────
        st.subheader("Origin declaration status")
        indian_lines = edited[edited["origin"].isin(["Indian", "Partially Indian"])].copy()

        d_yes     = int((indian_lines["declaration_rxd"] == "Yes").sum())
        d_pending = int((indian_lines["declaration_rxd"] == "Pending").sum())
        d_no      = int((indian_lines["declaration_rxd"] == "No").sum())

        dc1, dc2, dc3, dc4 = st.columns(4)
        dc1.metric("Lines needing declaration", len(indian_lines))
        dc2.metric("✅ Received",   d_yes)
        dc3.metric("⏳ Pending",    d_pending,
                   delta="chase suppliers" if d_pending else None,
                   delta_color="inverse" if d_pending else "off")
        dc4.metric("❌ Not obtained", d_no,
                   delta="risk" if d_no else None,
                   delta_color="inverse" if d_no else "off")

        if d_pending > 0:
            names = indian_lines.loc[
                indian_lines["declaration_rxd"] == "Pending",
                "indian_supplier"
            ].fillna("").tolist()
            line_ids = indian_lines.loc[
                indian_lines["declaration_rxd"] == "Pending",
                "line_id"
            ].fillna("").tolist()
            labels = [n if n.strip() else lid for n, lid in zip(names, line_ids)]
            st.warning("Chase declarations from: " + ", ".join(f"**{l}**" for l in labels))

        st.divider()

        # ── Origin breakdown chart ─────────────────────────────────────────
        by_origin = (
            edited.groupby("origin")["total_cost"]
            .sum()
            .reset_index()
            .rename(columns={"total_cost": "Cost (€)", "origin": "Origin"})
        )
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(by_origin.set_index("Origin")[["Cost (€)"]], color="#2196F3", height=200)
        with c2:
            disp = by_origin.copy()
            disp["Cost (€)"] = disp["Cost (€)"].map(lambda x: fmt(x, 0))
            st.dataframe(disp, use_container_width=True, hide_index=True)

        # ── Top imported items ─────────────────────────────────────────────
        top_imported = (
            edited[edited["origin"] == "Imported"]
            .nlargest(8, "total_cost")
            [["line_id", "part_name", "material_id", "total_cost"]]
            .copy()
        )
        if not top_imported.empty:
            with st.expander("🔍 Top imported items — consider Indian alternatives"):
                top_imported["total_cost"] = top_imported["total_cost"].map(lambda x: fmt(x, 0))
                st.dataframe(top_imported.rename(columns={
                    "line_id": "Line", "part_name": "Component",
                    "material_id": "Material", "total_cost": "Value (€)",
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

        doc_col1, doc_col2 = st.columns(2)

        # ── Document A: BOM Origin Register (Excel) ──────────────────────────
        with doc_col1:
            with st.container(border=True):
                st.markdown("**📄 Document A — BOM Origin Register**")
                st.caption(
                    "Excel workbook: IC Calculation Summary, BOM Origin Register "
                    "(line-by-line, no prices), Declaration Tracker. "
                    "Hand this to the surveying company."
                )
                save_df = edited[["line_id", "part_name", "hs_code", "origin",
                                   "indian_supplier", "declaration_rxd",
                                   "declaration_ref", "ic_value_pct", "notes"]].copy()
                try:
                    excel_bytes = _build_submission_excel(
                        save_df, meta, contract_value, ic_pct_calc)
                    st.download_button(
                        "⬇️ Download BOM Origin Register (Excel)",
                        data=excel_bytes,
                        file_name="india_ic_submission_package.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary",
                    )
                except Exception as e:
                    st.error(f"Could not generate Excel: {e}")

        # ── Document B: Draft CA Certificate ─────────────────────────────────
        with doc_col2:
            with st.container(border=True):
                st.markdown("**📜 Document B — Draft CA Certificate**")
                st.caption(
                    "Text template for your Chartered Accountant to adapt and sign. "
                    "CA certifies IC% from your books; individual quotes stay with you."
                )
                ca_text = _ca_cert_text(
                    meta, contract_value, ic_pct_calc, indian_val, imported_val)
                st.download_button(
                    "⬇️ Download CA Certificate Template (TXT)",
                    data=ca_text,
                    file_name="ca_certificate_draft.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

        st.divider()

        # ── Document C: Manufacturer Origin Declarations ──────────────────────
        st.markdown("**🏭 Document C — Manufacturer's Origin Declarations**")
        st.caption(
            "Generate one declaration per Indian supplier. The supplier signs and stamps it. "
            "No price appears. Accepted by DGQA and classification societies."
        )

        indian_lines2 = edited[edited["origin"].isin(["Indian", "Partially Indian"])].copy()

        if indian_lines2.empty:
            st.info("No lines tagged as Indian yet — update the IC Register tab first.")
        else:
            suppliers_list = sorted(set(
                s for s in indian_lines2["indian_supplier"].fillna("").tolist()
                if s.strip()
            ))
            if not suppliers_list:
                st.warning(
                    "Fill in **Indian manufacturer** names in the IC Register "
                    "to generate declarations."
                )
            else:
                sel_supplier = st.selectbox(
                    "Select supplier to generate declaration for",
                    options=suppliers_list,
                )
                sup_lines = indian_lines2[
                    indian_lines2["indian_supplier"].fillna("") == sel_supplier
                ]
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
                )

        st.divider()

        # ── Document D: Internal IC workbook (for CA, with prices) ───────────
        st.markdown("**🔐 Document D — Internal IC Workbook (CA eyes only — CONFIDENTIAL)**")
        st.caption(
            "Full detail with costs — give ONLY to your CA firm, not to the surveyor. "
            "CA uses this to certify the IC% calculation."
        )

        def _internal_excel() -> bytes:
            buf = io.BytesIO()
            out = edited.copy()
            out["IC value (€)"]     = out["total_cost"] * out["ic_value_pct"]
            out["Import value (€)"] = out["total_cost"] - out["IC value (€)"]
            out["IC%"]              = out["ic_value_pct"].map(
                lambda x: f"{float(x or 0) * 100:.0f}%")
            display_cols = {
                "line_id":          "Line ID",
                "part_name":        "Component",
                "material_id":      "Material",
                "total_cost":       "BOM cost (€)",
                "origin":           "Origin",
                "IC%":              "IC%",
                "IC value (€)":     "IC value (€)",
                "Import value (€)": "Import value (€)",
                "indian_supplier":  "Indian manufacturer",
                "hs_code":          "HS Code",
                "declaration_rxd":  "Declaration rxd?",
                "declaration_ref":  "Declaration ref",
                "notes":            "Notes",
            }
            # Only select columns that actually exist
            sel_cols = [c for c in display_cols if c in out.columns]
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                out[sel_cols].rename(columns=display_cols).to_excel(
                    w, sheet_name="IC Detail", index=False)
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

        try:
            st.download_button(
                "⬇️ Download internal IC workbook (CONFIDENTIAL — CA eyes only)",
                data=_internal_excel(),
                file_name="india_ic_internal_CONFIDENTIAL.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Could not generate internal workbook: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — STRATEGY ADVISER
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        st.subheader("Strategy adviser — how to reach your IC% target")

        shortfall = max(threshold - ic_pct_calc, 0.0)

        if shortfall == 0:
            st.success(
                f"✅ You currently meet the IC% requirement "
                f"({_pct(ic_pct_calc)} ≥ {_pct(threshold)}). "
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
                "can be reassessed. If an Indian foundry casts the blank and imported CNC "
                "finishes it, the casting portion IS Indian content. "
                "Get a cost breakdown from the Indian supplier confirming the split."
            )
            partial = edited[edited["origin"] == "Partially Indian"].copy()
            if partial.empty:
                st.caption("No Partially Indian lines tagged yet.")
            else:
                partial["Max upside (€) if 100%"] = (
                    partial["total_cost"] * (1 - partial["ic_value_pct"])
                ).map(lambda x: fmt(x, 0))
                partial["ic_value_pct"] = partial["ic_value_pct"].map(
                    lambda x: f"{float(x) * 100:.0f}%")
                st.dataframe(
                    partial[["line_id", "part_name", "indian_supplier",
                              "ic_value_pct", "Max upside (€) if 100%"]].rename(columns={
                        "line_id": "Line", "part_name": "Component",
                        "indian_supplier": "Indian manufacturer",
                        "ic_value_pct": "Current IC%",
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
            try:
                from utils.io import load_nre
                from utils.nre import nre_total
                nre_df = load_nre()
                if not nre_df.empty:
                    nre_ic_eur = float(nre_total(nre_df))
                    nre_contribution = nre_ic_eur / contract_value if contract_value > 0 else 0
                    st.metric(
                        "NRE / engineering cost", fmt(nre_ic_eur, 0),
                        delta="Add to IC% if performed in India", delta_color="normal",
                    )
                    st.caption(
                        f"If all NRE is Indian: IC% = "
                        f"{_pct(ic_pct_calc + nre_contribution)} "
                        f"(currently {_pct(ic_pct_calc)})"
                    )
                else:
                    st.caption("No NRE data loaded — enter it in Engineering & NRE page.")
            except Exception:
                st.caption("Load NRE data in Engineering & NRE page to see NRE IC contribution.")

        with st.container(border=True):
            st.markdown("#### 3️⃣ Indian alternative suppliers — top candidates")
            st.markdown(
                "The items below are currently **Imported** and have the highest value. "
                "Consider whether an Indian foundry, fabricator or distributor can supply "
                "a compliant alternative — even at a modest premium the IC% uplift may be "
                "commercially beneficial."
            )
            top_imp = (
                edited[edited["origin"] == "Imported"]
                .nlargest(6, "total_cost")
                [["line_id", "part_name", "material_id", "total_cost", "hs_code"]]
                .copy()
            )
            if top_imp.empty:
                st.caption("No imported lines.")
            else:
                top_imp["IC uplift if Indian"] = top_imp["total_cost"].map(
                    lambda v: _pct(v / contract_value) if contract_value > 0 else "—"
                )
                top_imp["total_cost"] = top_imp["total_cost"].map(lambda x: fmt(x, 0))
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
File a Bill of Entry for every imported item with Indian customs. The cleared import
value is officially documented. Everything in the contract value not covered by a BoE
is deemed Indian — simple, irrefutable, requires zero supplier cooperation beyond
standard import paperwork.

**Free Issue Material (FIM):**
If the Indian customer purchases certain imported items themselves and supplies them
free of charge to you, those items may be excluded from the IC% denominator entirely,
boosting your effective IC%. Requires a contract clause — worth negotiating for
high-value imports (e.g. NAB castings, impeller blanks).

**Offset arrangements:**
Under DAP 2020, foreign OEMs with large Indian defence contracts can generate Offset
credits by placing work with Indian entities. If your parent company has an offset
obligation in India, sub-placing machining/assembly work is dual-purpose.

**Letter of Intent vs. full quotes:**
For Partially Indian items where you are actively seeking a domestic quote, present
a Letter of Intent from the Indian supplier (not the actual price quote) as evidence
of active local sourcing. Accepted at tender stage by most procurement authorities.
                """
            )

        st.divider()
        st.info(
            "**Bottom line:** Do not submit your full quote book. "
            "Submit: (A) BOM Origin Register, (B) CA Certificate, "
            "(C) Supplier Origin Declarations. "
            "Your CA sees the internal workbook; the surveyor sees only origin data.",
            icon="🔒",
        )


guard(main)
