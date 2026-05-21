"""
India Local Content (IC%) Manager.

Indian government and defence contracts (DAP 2020, DPP, DPIIT GeM, Shipbuilding
Financial Assistance Policy) require a declared Indigenous Content percentage,
verified by third-party surveying agencies (DGQA, BV, DNV, etc.).

KEY PRINCIPLE: Surveyors verify *manufacturing origin*, not *supplier price*.
You do NOT need to submit your full quote book. Three accepted methods:
  1. CA Certificate — CA certifies IC% from your books. Quotes stay internal.
  2. Manufacturer's Origin Declaration — supplier signs 1-page origin form (no price).
  3. Bill of Entry / HS Code — customs import records confirm what was imported.
"""
from __future__ import annotations

import io
import textwrap
from datetime import date

import pandas as pd
import streamlit as st

from utils.completeness import WATERJET_SUBSYSTEMS
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

IC_THRESHOLDS = {
    "Buy (Indian-IDDM)":                0.50,
    "Buy (Indian)":                     0.40,
    "Buy & Make (Indian)":              0.50,
    "Buy & Make":                       0.30,
    "Make (Indian)":                    0.50,
    "Strategic Partnership Model":      0.50,
    "GeM — Class I Local Supplier":     0.50,
    "GeM — Class II Local Supplier":    0.20,
    "Shipbuilding Financial Assistance":0.30,
    "Custom / contractual":             0.0,
}

# ── HS code keyword → code mapping ────────────────────────────────────────────
_HS_KEYWORD_MAP: list[tuple[tuple[str, ...], str]] = [
    (("impeller", "runner", "wheel"),                        "8413.91"),
    (("nozzle", "deflector", "jet tube", "steering nozzle"), "8481.80"),
    (("shaft",),                                             "8483.10"),
    (("ball bearing", "roller bearing", "taper bearing"),    "8482.10"),
    (("bearing",),                                           "8482.80"),
    (("mechanical seal", "lip seal", "face seal"),           "8484.10"),
    (("o-ring", "o ring", "oring"),                          "4016.93"),
    (("gasket", "rubber", "elastomer"),                      "4016.93"),
    (("wear ring", "liner", "wear liner"),                   "8413.91"),
    (("casing", "housing", "volute", "bowl", "scroll"),      "8413.91"),
    (("cover", "end cover", "bearing housing"),              "8413.91"),
    (("valve", "check valve", "gate valve", "butterfly"),    "8481.80"),
    (("bolt", "stud", "cap screw", "hex bolt"),              "7318.15"),
    (("nut", "lock nut", "hex nut"),                         "7318.16"),
    (("washer", "spring washer"),                            "7318.21"),
    (("flange",),                                            "7307.91"),
    (("pipe", "tube", "hose"),                               "7304.49"),
    (("casting", "cast bronze", "cast nab"),                 "7419.99"),
    (("nab", "aluminium bronze", "nickel aluminium"),        "8413.91"),
    (("bronze", "gunmetal"),                                 "7419.99"),
    (("sensor", "transducer", "transmitter"),                "9026.80"),
    (("motor", "servo motor"),                               "8501.10"),
    (("pump",),                                              "8413.50"),
    (("hydraulic", "cylinder", "ram"),                       "8412.21"),
    (("cable", "wire", "wiring harness"),                    "8544.49"),
    (("gearbox", "gear", "pinion"),                          "8483.40"),
    (("coupling",),                                          "8483.60"),
    (("bracket", "frame", "weldment", "fabrication"),        "7326.90"),
    (("stainless", "ss316", "ss304", "duplex"),              "7326.90"),
    (("paint", "coating", "primer", "epoxy"),                "3208.90"),
    (("grease", "lubricant"),                                "2710.19"),
]

def _suggest_hs_code(name: str) -> str:
    nl = str(name or "").lower()
    for kws, code in _HS_KEYWORD_MAP:
        if any(k in nl for k in kws):
            return code
    return ""

# ── Indian manufacturer list ──────────────────────────────────────────────────
INDIAN_SUPPLIERS: list[str] = [
    "",
    # ── Seals & PTC (propeller / shaft seals) ─────────────────────────────
    "Amruta PTC Pvt Ltd",
    "Vulcan Engineering Co",
    "Trelleborg Sealing Solutions India",
    "Freudenberg Sealing Technologies India",
    "Parker Hannifin India Pvt Ltd",
    "Dynamic Sealing Technologies India",
    "Precision Seals Mfg Ltd",
    # ── Castings & forgings ────────────────────────────────────────────────
    "Bharat Forge Ltd",
    "Bhoruka Aluminium Ltd",
    "Electrosteel Castings Ltd",
    "Hinduja Foundries Ltd",
    "Kirloskar Ferrous Industries",
    "Mahindra Hinoday Industries",
    "Nelcast Ltd",
    "Sundaram Clayton Ltd",
    "WFD Metalcast India",
    "Amtek Auto Ltd",
    "Ennore Foundries Ltd",
    "Perfect Castings Pvt Ltd",
    # ── Machined & fabricated components ──────────────────────────────────
    "BEML Ltd",
    "Godrej & Boyce Mfg Co Ltd",
    "HMT Ltd",
    "L&T Precision Engineering",
    "Larsen & Toubro Ltd",
    "Tata Advanced Systems Ltd",
    "Precision Camshafts Ltd",
    "Bhart Heavy Plate & Vessels Ltd",
    "Walchandnagar Industries Ltd",
    # ── Bearings ──────────────────────────────────────────────────────────
    "FAG Bearings India (Schaeffler India)",
    "NBC Bearings (National Engineering Industries)",
    "SKF India Ltd",
    "Timken India Ltd",
    "NRB Bearings Ltd",
    # ── Fasteners ─────────────────────────────────────────────────────────
    "Bulten India Pvt Ltd",
    "Sundaram Fasteners Ltd",
    "Vikrant Screw Factory",
    "Mangal Fasteners Pvt Ltd",
    "Lisi Aerospace India",
    "Infastech India",
    # ── Hydraulics & pneumatics ────────────────────────────────────────────
    "Bosch Rexroth India Ltd",
    "Eaton Fluid Power Ltd India",
    "Parker Hannifin India Pvt Ltd",
    "Yuken India Ltd",
    "Hydraulics & Pneumatics Ltd",
    "Enerpac India",
    # ── Valves ────────────────────────────────────────────────────────────
    "Audco India Ltd (Flowserve)",
    "KSB Pumps Ltd",
    "L&T Valves Ltd",
    "Advance Valves Pvt Ltd",
    "Forbes Marshall Pvt Ltd",
    "Intervalve India Ltd",
    # ── Pumps ─────────────────────────────────────────────────────────────
    "Flowserve India Controls Pvt Ltd",
    "Kirloskar Brothers Ltd",
    "KSB Pumps Ltd",
    "Sulzer India Ltd",
    "Worthington India Pvt Ltd",
    "WPIL Ltd",
    # ── Electrical & instrumentation ──────────────────────────────────────
    "ABB India Ltd",
    "Bharat Heavy Electricals Ltd (BHEL)",
    "Emerson Electric India",
    "Honeywell Automation India",
    "Schneider Electric India",
    "Siemens Ltd India",
    "Yokogawa India Ltd",
    "Endress+Hauser India",
    # ── Stainless / structural steel ──────────────────────────────────────
    "Bhushan Steel Ltd",
    "Jindal Stainless Ltd",
    "Kalyani Steels Ltd",
    "Mukand Ltd",
    "Kalyani Group",
    "ISMT Ltd",
    # ── Cables ────────────────────────────────────────────────────────────
    "Apar Industries Ltd",
    "Finolex Cables Ltd",
    "Polycab India Ltd",
    "KEI Industries Ltd",
    # ── Rubber & gaskets ──────────────────────────────────────────────────
    "Fenner India Ltd",
    "Gates India Pvt Ltd",
    "Premier Rubber Works",
    "Supreme Industries Ltd",
    # ── Marine & defence ──────────────────────────────────────────────────
    "Cochin Shipyard Ltd",
    "Garden Reach Shipbuilders & Engineers Ltd",
    "Goa Shipyard Ltd",
    "Hindustan Shipyard Ltd",
    "Mazagon Dock Shipbuilders Ltd",
    "Pipavav Defence & Offshore Engineering",
    # ── Surface finishing ─────────────────────────────────────────────────
    "Metalcolour Surface Coatings Pvt Ltd",
    "Berger Paints India Ltd",
    "Jotun India Pvt Ltd",
    "Asian Paints Ltd",
    # ── Other ─────────────────────────────────────────────────────────────
    "Other Indian manufacturer",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _traffic(val: float, threshold: float) -> str:
    if val >= threshold:        return "🟢"
    if val >= threshold * 0.85: return "🟠"
    return "🔴"

def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"

def _safe_col(df: pd.DataFrame, name: str, default="") -> pd.Series:
    return df[name] if name in df.columns else pd.Series([default] * len(df), index=df.index)


# ── Scope detection from BOM line_ids ─────────────────────────────────────────
def _build_scope_table(df_costs: pd.DataFrame) -> pd.DataFrame:
    """
    Group BOM cost rows by waterjet subsystem prefix → one row per scope.
    Unmatched lines go into 'Other'.
    Returns DataFrame with: scope_id, scope_name, icon, lines, cost_eur
    """
    # Sort prefixes longest-first so 'SB' matches before 'S'
    prefix_order = sorted(WATERJET_SUBSYSTEMS.keys(), key=len, reverse=True)

    rows = []
    for _, r in df_costs.iterrows():
        lid = str(r.get("line_id", "")).upper()
        matched = "_OTHER"
        for p in prefix_order:
            if lid.startswith(p):
                matched = p
                break
        rows.append(matched)

    df_costs = df_costs.copy()
    df_costs["_scope"] = rows

    agg = (
        df_costs.groupby("_scope")
        .agg(lines=("line_id", "count"),
             cost_eur=("total_cost", "sum"))
        .reset_index()
        .rename(columns={"_scope": "scope_id"})
    )

    def _scope_name(sid):
        if sid in WATERJET_SUBSYSTEMS:
            info = WATERJET_SUBSYSTEMS[sid]
            return f"{info['icon']} {info['name']}"
        return "❓ Other / Miscellaneous"

    agg["scope_name"] = agg["scope_id"].map(_scope_name)
    # Sort: known subsystems first (in definition order), then Other
    order = {k: i for i, k in enumerate(WATERJET_SUBSYSTEMS.keys())}
    agg["_order"] = agg["scope_id"].map(lambda s: order.get(s, 999))
    agg = agg.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
    return agg


# ── Document builders ─────────────────────────────────────────────────────────
def _build_submission_excel(scope_ic: pd.DataFrame, meta: dict,
                             contract_value: float, ic_pct: float) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame([
            ["Project",            meta.get("name", "")],
            ["Customer",           meta.get("customer", "")],
            ["Contract value (€)", f"{contract_value:,.0f}"],
            ["Declared IC%",       f"{ic_pct * 100:.2f}%"],
            ["Date",               str(date.today())],
            ["Method",             "Value-based (IC% = Indian value / Total value × 100)"],
            ["Basis",              "Internal cost records; available for CA certification on request"],
        ], columns=["Field", "Value"]).to_excel(w, sheet_name="IC Summary", index=False)

        clean = pd.DataFrame({
            "Scope / Subsystem":          scope_ic["scope_name"],
            "Manufacturing origin":       _safe_col(scope_ic, "origin", "Imported"),
            "Indian manufacturer":        _safe_col(scope_ic, "indian_supplier"),
            "IC fraction claimed":        _safe_col(scope_ic, "ic_value_pct", 0.0).map(
                                              lambda x: f"{float(x or 0)*100:.0f}%"),
            "Origin declaration received":_safe_col(scope_ic, "declaration_rxd", "Pending"),
            "Declaration ref / date":     _safe_col(scope_ic, "declaration_ref"),
            "HS Code (representative)":   _safe_col(scope_ic, "hs_code"),
            "Notes":                      _safe_col(scope_ic, "notes"),
        })
        clean.to_excel(w, sheet_name="Scope Origin Register", index=False)

        decl = scope_ic[_safe_col(scope_ic, "origin", "Imported").isin(
            ["Indian", "Partially Indian"])].copy()
        pd.DataFrame({
            "Scope":                 _safe_col(decl, "scope_name"),
            "Indian manufacturer":   _safe_col(decl, "indian_supplier"),
            "Declaration received?": _safe_col(decl, "declaration_rxd", "Pending"),
            "Reference / date":      _safe_col(decl, "declaration_ref"),
        }).to_excel(w, sheet_name="Declaration Tracker", index=False)

    return buf.getvalue()


def _ca_cert_text(meta: dict, contract_value: float, ic_pct: float,
                  indian_val: float, imported_val: float) -> str:
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

    The Indigenous Content (IC) is calculated as follows, in accordance with
    the value-based methodology prescribed under the applicable procurement policy:

        Total assessed value:     EUR {contract_value:,.0f}
        Value of imported inputs: EUR {imported_val:,.0f}
        Value of Indian inputs:   EUR {indian_val:,.0f}
        Indigenous Content (IC):  {ic_pct * 100:.2f}%

    IC% = (Indian input value / Total contract value) × 100

    Individual supplier prices and purchase records are available for inspection
    by the competent authority upon written request, maintained per statutory requirements.

    Authorised signatory:

    Name:           _______________________________
    Firm:           _______________________________  [CA Firm, Reg No.]
    Membership No.: _______________________________
    Date:           _______________________________
    Seal:
    """)


def _manufacturer_decl_text(supplier_name: str, scope: str,
                              hs_code: str, project: str) -> str:
    today = date.today().strftime("%d %B %Y")
    return textwrap.dedent(f"""\
    MANUFACTURER'S DECLARATION OF DOMESTIC ORIGIN

    Date: {today}

    To: [Buyer / Authorised Representative]

    We, {supplier_name or "[SUPPLIER NAME]"}, hereby declare that the goods /
    assemblies described below are manufactured in India and qualify as
    Domestically Manufactured Goods under applicable Indian procurement policy:

        Scope / assembly:  {scope}
        HS Code:           {hs_code or "[HS Code]"}
        Project reference: {project}

    We confirm that:
    1. The manufacturing facility is located in India.
    2. The goods are not imported and re-labelled.
    3. The IC value fraction claimed reflects actual manufacturing performed in India.
    4. Records supporting this declaration are maintained for not less than 7 years.

    This declaration is made without disclosing commercial pricing, which is
    proprietary, and is provided solely to support the buyer's IC compliance filing.

    Authorised signatory:

    Name:        _______________________________
    Designation: _______________________________
    Company:     {supplier_name or "[SUPPLIER NAME]"}
    Date:        _______________________________
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
            "CA certificate · manufacturer origin declarations · Bill of Entry method."
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

    # Back-fill BOM columns that compute_costs may not carry through
    for col in ("line_id", "part_name", "material_id"):
        if col not in df.columns and col in bom.columns:
            df = df.merge(
                bom[["line_id", col]].drop_duplicates("line_id"),
                on="line_id", how="left", suffixes=("", "_bom"),
            )

    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0.0)
    total_bom_value  = float(df["total_cost"].sum())

    # ── Sidebar ───────────────────────────────────────────────────────────────
    st.sidebar.divider()
    st.sidebar.subheader("Contract settings")

    procurement_cat = st.sidebar.selectbox(
        "Procurement category", list(IC_THRESHOLDS.keys()), index=0,
    )
    threshold_pct = st.sidebar.number_input(
        "IC% threshold (override)",
        min_value=0.0, max_value=100.0,
        value=float(IC_THRESHOLDS[procurement_cat] * 100), step=1.0,
    )
    threshold = threshold_pct / 100.0

    contract_value = float(st.sidebar.number_input(
        "Contract value (€)",
        min_value=0.0, value=float(total_bom_value), step=10_000.0, format="%.0f",
        help="Defaults to BOM sell price. Override with signed contract value.",
    ))
    if contract_value == 0:
        contract_value = total_bom_value

    st.sidebar.text_input("Your company name (for declarations)")
    st.sidebar.text_input("Surveying / certifying agency",
                          placeholder="e.g. DGQA / BV / DNV")
    st.sidebar.divider()
    st.sidebar.info(
        "**No quote book needed. Three methods:**\n\n"
        "1️⃣ **CA Certificate** — CA certifies IC% from books.\n\n"
        "2️⃣ **Origin Declaration** — supplier signs 1-page form, no price.\n\n"
        "3️⃣ **Bill of Entry** — customs records confirm imports; rest is Indian."
    )

    # ── Build scope table from BOM ────────────────────────────────────────────
    scope_tbl = _build_scope_table(df)   # scope_id, scope_name, lines, cost_eur

    # ── Load previously saved scope IC data ───────────────────────────────────
    lc_df = load_india_lc()
    # Saved rows use scope_id as their line_id (prefixed "SCOPE_")
    saved_scope = pd.DataFrame()
    if not lc_df.empty and "line_id" in lc_df.columns:
        saved_scope = lc_df[lc_df["line_id"].str.startswith("SCOPE_", na=False)].copy()
        saved_scope["scope_id"] = saved_scope["line_id"].str.replace("SCOPE_", "", regex=False)

    today_iso = date.today().isoformat()

    # Merge saved scope settings into the scope table
    if not saved_scope.empty:
        merge_cols = ["scope_id"] + [
            c for c in ["origin", "ic_value_pct", "indian_supplier",
                         "declaration_rxd", "declaration_ref", "hs_code", "notes"]
            if c in saved_scope.columns
        ]
        scope_tbl = scope_tbl.merge(saved_scope[merge_cols], on="scope_id", how="left")

    # Fill defaults for any missing columns (new scopes not yet in saved data)
    if "origin"          not in scope_tbl.columns: scope_tbl["origin"]          = "Imported"
    if "ic_value_pct"    not in scope_tbl.columns: scope_tbl["ic_value_pct"]    = 0.0
    if "indian_supplier" not in scope_tbl.columns: scope_tbl["indian_supplier"] = ""
    if "declaration_rxd" not in scope_tbl.columns: scope_tbl["declaration_rxd"] = "Pending"
    if "declaration_ref" not in scope_tbl.columns: scope_tbl["declaration_ref"] = today_iso
    if "hs_code"         not in scope_tbl.columns: scope_tbl["hs_code"]         = ""
    if "notes"           not in scope_tbl.columns: scope_tbl["notes"]           = ""

    scope_tbl["origin"]          = scope_tbl["origin"].fillna("Imported")
    scope_tbl["ic_value_pct"]    = pd.to_numeric(scope_tbl["ic_value_pct"], errors="coerce").fillna(0.0)
    scope_tbl["indian_supplier"] = scope_tbl["indian_supplier"].fillna("")
    scope_tbl["declaration_rxd"] = scope_tbl["declaration_rxd"].fillna("Pending")
    scope_tbl["declaration_ref"] = scope_tbl["declaration_ref"].fillna(today_iso).replace("", today_iso)
    scope_tbl["hs_code"]         = scope_tbl["hs_code"].fillna("")
    scope_tbl["notes"]           = scope_tbl["notes"].fillna("")

    # Auto-suggest HS codes for blank rows using scope name
    blank_hs = scope_tbl["hs_code"].str.strip() == ""
    scope_tbl.loc[blank_hs, "hs_code"] = scope_tbl.loc[blank_hs, "scope_name"].map(_suggest_hs_code)

    scope_tbl["cost_eur"] = pd.to_numeric(scope_tbl["cost_eur"], errors="coerce").fillna(0.0)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📋 IC Register (scope level)",
        "📊 IC% Dashboard",
        "📝 Submission Documents",
        "🏭 Strategy Adviser",
        "🔍 BOM Line Detail",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — IC REGISTER (SCOPE LEVEL)
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[0]:
        st.subheader("IC register — one row per scope / subsystem")
        st.caption(
            "Set origin and IC fraction at the **scope level** — one row per waterjet subsystem. "
            "Indian = 1.0 · Imported = 0.0 · Partially Indian = enter the fraction (e.g. 0.60). "
            "🤖 HS codes auto-suggested · 🏭 Manufacturer is a searchable dropdown · "
            "📅 Declaration date defaults to today."
        )

        editor_df = scope_tbl[[
            "scope_name", "lines", "cost_eur",
            "origin", "ic_value_pct", "indian_supplier",
            "declaration_rxd", "declaration_ref", "hs_code", "notes",
        ]].copy()

        edited = st.data_editor(
            editor_df,
            column_config={
                "scope_name":      st.column_config.TextColumn(
                    "Scope / subsystem", disabled=True, width="medium"),
                "lines":           st.column_config.NumberColumn(
                    "BOM lines", disabled=True, width="small"),
                "cost_eur":        st.column_config.NumberColumn(
                    "Cost (€)", disabled=True, format="%.0f"),
                "origin":          st.column_config.SelectboxColumn(
                    "Origin", options=ORIGIN_OPTIONS, width="medium",
                    help="Indian=100% local · Imported=0% · Partially Indian=enter fraction"),
                "ic_value_pct":    st.column_config.NumberColumn(
                    "IC fraction", min_value=0.0, max_value=1.0, format="%.2f",
                    help="1.00 = fully Indian · 0.00 = fully imported · "
                         "0.60 = 60% of this scope's cost is Indian. "
                         "Enter your value — it will NOT be reset."),
                "indian_supplier": st.column_config.SelectboxColumn(
                    "Indian manufacturer", options=INDIAN_SUPPLIERS, width="large",
                    help="Type to filter. Supplier name only — no price."),
                "declaration_rxd": st.column_config.SelectboxColumn(
                    "Declaration rxd?", options=DECL_STATUS, width="small"),
                "declaration_ref": st.column_config.TextColumn(
                    "Declaration ref / date",
                    help="Defaults to today. Update when signed declaration received."),
                "hs_code":         st.column_config.TextColumn(
                    "HS Code", width="small",
                    help="Auto-suggested from scope name. Verify and correct."),
                "notes":           st.column_config.TextColumn("Notes"),
            },
            use_container_width=True,
            hide_index=True,
            key="scope_ic_editor",
            num_rows="fixed",
        )

        # ── Coerce types but DO NOT auto-reset user-entered ic_value_pct ─────
        edited = edited.copy()
        edited["ic_value_pct"] = pd.to_numeric(
            edited["ic_value_pct"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
        edited["cost_eur"] = scope_tbl["cost_eur"].values   # always from live BOM

        c_save, c_tip = st.columns([1, 6])
        if c_save.button("💾 Save IC register", type="primary", use_container_width=True):
            save_rows = edited.copy()
            save_rows["line_id"]   = "SCOPE_" + scope_tbl["scope_id"].values
            save_rows["part_name"] = save_rows["scope_name"]
            save_sheet(
                save_rows[["line_id", "part_name", "hs_code", "origin",
                            "indian_supplier", "declaration_rxd", "declaration_ref",
                            "ic_value_pct", "notes"]],
                "india_lc",
            )
            st.success("✅ IC register saved.")
            st.rerun()

        c_tip.caption(
            "💡 Enter IC fraction directly (e.g. **0.65** = 65% Indian). "
            "Your value is kept as-is — it is not auto-reset. "
            "The surveying agency needs manufacturer name + HS code, not your price."
        )

    # ── Shared IC calculation (used by all remaining tabs) ────────────────────
    edited["_ic_eur"]  = edited["cost_eur"] * edited["ic_value_pct"]
    edited["_imp_eur"] = edited["cost_eur"] * (1 - edited["ic_value_pct"])
    indian_val   = float(edited["_ic_eur"].sum())
    imported_val = float(edited["_imp_eur"].sum())
    ic_pct_calc  = indian_val / contract_value if contract_value > 0 else 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — IC% DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        st.subheader("IC% summary")

        k1, k2, k3, k4, k5 = st.columns(5)
        sig = _traffic(ic_pct_calc, threshold)
        k1.metric("Declared IC%",        _pct(ic_pct_calc),
                  delta=f"{sig} {'Meets' if ic_pct_calc >= threshold else 'Below'} "
                        f"{_pct(threshold)} threshold")
        k2.metric("Indian content (€)",  fmt(indian_val, 0))
        k3.metric("Imported content (€)",fmt(imported_val, 0))
        k4.metric("Contract value (€)",  fmt(contract_value, 0))
        k5.metric("IC threshold",        _pct(threshold),
                  delta=procurement_cat, delta_color="off")

        if ic_pct_calc < threshold:
            shortfall_eur = (threshold - ic_pct_calc) * contract_value
            st.error(
                f"⚠️ IC% shortfall: **{_pct(threshold - ic_pct_calc)}** — "
                f"need **{fmt(shortfall_eur, 0)}** more Indian content. "
                "See **Strategy Adviser** tab."
            )
        else:
            st.success(
                f"✅ IC% exceeds threshold by **{_pct(ic_pct_calc - threshold)}** "
                f"({fmt((ic_pct_calc - threshold) * contract_value, 0)} buffer)."
            )

        st.divider()
        st.subheader("Origin declaration status")

        indian_scopes = edited[edited["origin"].isin(["Indian", "Partially Indian"])]
        d_yes     = int((indian_scopes["declaration_rxd"] == "Yes").sum())
        d_pending = int((indian_scopes["declaration_rxd"] == "Pending").sum())
        d_no      = int((indian_scopes["declaration_rxd"] == "No").sum())

        dc1, dc2, dc3, dc4 = st.columns(4)
        dc1.metric("Scopes needing declaration", len(indian_scopes))
        dc2.metric("✅ Received",   d_yes)
        dc3.metric("⏳ Pending",    d_pending,
                   delta="chase" if d_pending else None,
                   delta_color="inverse" if d_pending else "off")
        dc4.metric("❌ Not obtained", d_no,
                   delta="risk" if d_no else None,
                   delta_color="inverse" if d_no else "off")

        if d_pending:
            pend_rows = indian_scopes[indian_scopes["declaration_rxd"] == "Pending"]
            labels = [
                r["indian_supplier"] if str(r.get("indian_supplier", "")).strip()
                else r["scope_name"]
                for _, r in pend_rows.iterrows()
            ]
            st.warning("Chase declarations from: " + ", ".join(f"**{l}**" for l in labels))

        st.divider()

        # Scope breakdown chart
        by_origin = (
            edited.groupby("origin")["cost_eur"]
            .sum().reset_index()
            .rename(columns={"cost_eur": "Cost (€)", "origin": "Origin"})
        )
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(by_origin.set_index("Origin")[["Cost (€)"]], color="#2196F3", height=220)
        with c2:
            disp = by_origin.copy()
            disp["Cost (€)"] = disp["Cost (€)"].map(lambda x: fmt(x, 0))
            st.dataframe(disp, use_container_width=True, hide_index=True)

        # Per-scope IC breakdown
        st.subheader("IC contribution by scope")
        scope_disp = pd.DataFrame({
            "Scope":         edited["scope_name"],
            "Cost (€)":      edited["cost_eur"].map(lambda x: fmt(x, 0)),
            "Origin":        edited["origin"],
            "IC fraction":   edited["ic_value_pct"].map(lambda x: f"{x*100:.0f}%"),
            "IC value (€)":  edited["_ic_eur"].map(lambda x: fmt(x, 0)),
            "Contribution":  edited["_ic_eur"].map(
                lambda x: _pct(x / contract_value) if contract_value > 0 else "—"),
        })
        st.dataframe(scope_disp, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — SUBMISSION DOCUMENTS
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[2]:
        st.subheader("Submission documents — no prices revealed")
        st.info(
            "None of these documents contain individual supplier prices. "
            "Your quote book stays internal — only your CA firm sees it.",
            icon="🔒",
        )

        doc_col1, doc_col2 = st.columns(2)

        with doc_col1:
            with st.container(border=True):
                st.markdown("**📄 Document A — Scope Origin Register**")
                st.caption(
                    "Excel: IC Summary, Scope Origin Register (no prices), "
                    "Declaration Tracker. Hand to the surveying company."
                )
                try:
                    excel_bytes = _build_submission_excel(
                        edited, meta, contract_value, ic_pct_calc)
                    st.download_button(
                        "⬇️ Download Scope Origin Register (Excel)",
                        data=excel_bytes,
                        file_name="india_ic_submission_package.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, type="primary",
                    )
                except Exception as e:
                    st.error(f"Could not generate: {e}")

        with doc_col2:
            with st.container(border=True):
                st.markdown("**📜 Document B — CA Certificate Draft**")
                st.caption(
                    "Template for your CA to adapt and sign. "
                    "CA certifies IC% from your books; quotes stay with you."
                )
                st.download_button(
                    "⬇️ Download CA Certificate Template (TXT)",
                    data=_ca_cert_text(meta, contract_value, ic_pct_calc,
                                       indian_val, imported_val),
                    file_name="ca_certificate_draft.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

        st.divider()
        st.markdown("**🏭 Document C — Manufacturer's Origin Declarations**")
        st.caption(
            "One declaration per Indian supplier — they sign and stamp it. "
            "No price. Accepted by DGQA and classification societies."
        )

        indian_rows = edited[edited["origin"].isin(["Indian", "Partially Indian"])].copy()
        if indian_rows.empty:
            st.info("No scopes tagged as Indian yet — update the IC Register tab first.")
        else:
            suppliers_with_name = sorted(set(
                s for s in indian_rows["indian_supplier"].fillna("").tolist() if s.strip()
            ))
            if not suppliers_with_name:
                st.warning("Fill in **Indian manufacturer** names in the IC Register to generate declarations.")
            else:
                sel_supplier = st.selectbox(
                    "Select supplier to generate declaration for",
                    options=suppliers_with_name,
                )
                sup_rows = indian_rows[
                    indian_rows["indian_supplier"].fillna("") == sel_supplier
                ]
                scope_list = "; ".join(sup_rows["scope_name"].fillna("").tolist())
                hs_list    = "; ".join(sup_rows["hs_code"].fillna("").tolist())
                decl_text  = _manufacturer_decl_text(sel_supplier, scope_list,
                                                      hs_list, project)
                with st.expander("Preview declaration text"):
                    st.text(decl_text)
                st.download_button(
                    f"⬇️ Download declaration — {sel_supplier}",
                    data=decl_text,
                    file_name=f"origin_declaration_{sel_supplier.replace(' ', '_')}.txt",
                    mime="text/plain",
                )

        st.divider()
        st.markdown("**🔐 Document D — Internal IC Workbook (CA eyes only — CONFIDENTIAL)**")
        st.caption("Full cost detail — give ONLY to your CA firm, never to the surveyor.")

        def _internal_excel() -> bytes:
            buf = io.BytesIO()
            out = edited.copy()
            out["IC%"] = out["ic_value_pct"].map(lambda x: f"{float(x or 0)*100:.0f}%")
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                out[[
                    "scope_name", "cost_eur", "origin", "IC%",
                    "_ic_eur", "_imp_eur", "indian_supplier", "hs_code",
                    "declaration_rxd", "declaration_ref", "notes",
                ]].rename(columns={
                    "scope_name": "Scope", "cost_eur": "BOM cost (€)",
                    "origin": "Origin", "_ic_eur": "IC value (€)",
                    "_imp_eur": "Import value (€)",
                    "indian_supplier": "Indian manufacturer", "hs_code": "HS Code",
                    "declaration_rxd": "Declaration rxd?",
                    "declaration_ref": "Declaration ref",
                }).to_excel(w, sheet_name="IC Detail", index=False)

                pd.DataFrame([
                    ["Contract value (€)",   f"{contract_value:,.0f}"],
                    ["Indian content (€)",   f"{indian_val:,.0f}"],
                    ["Imported content (€)", f"{imported_val:,.0f}"],
                    ["Declared IC%",         f"{ic_pct_calc*100:.2f}%"],
                    ["Required IC%",         f"{threshold*100:.1f}%"],
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
            st.error(f"Could not generate: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — STRATEGY ADVISER
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        st.subheader("Strategy adviser")

        shortfall = max(threshold - ic_pct_calc, 0.0)
        if shortfall == 0:
            st.success(
                f"✅ You meet the IC% requirement ({_pct(ic_pct_calc)} ≥ {_pct(threshold)}). "
                "Focus on documentation."
            )
        else:
            st.error(
                f"Shortfall: **{_pct(shortfall)}** = **{fmt(shortfall * contract_value, 0)}** "
                f"of additional Indian content needed to reach {_pct(threshold)}."
            )

        st.divider()
        st.markdown("### 🎯 Mitigation options — ranked by effort")

        with st.container(border=True):
            st.markdown("#### 1️⃣ Partially Indian scopes — review claimed fraction")
            partial = edited[edited["origin"] == "Partially Indian"].copy()
            if partial.empty:
                st.caption("No Partially Indian scopes tagged yet.")
            else:
                partial["Upside if 100% (€)"] = (
                    partial["cost_eur"] * (1 - partial["ic_value_pct"])
                ).map(lambda x: fmt(x, 0))
                partial["ic_value_pct"] = partial["ic_value_pct"].map(
                    lambda x: f"{float(x)*100:.0f}%")
                st.dataframe(
                    partial[["scope_name", "indian_supplier",
                              "ic_value_pct", "Upside if 100% (€)"]].rename(columns={
                        "scope_name": "Scope", "indian_supplier": "Indian manufacturer",
                        "ic_value_pct": "Current IC%",
                    }), use_container_width=True, hide_index=True,
                )

        with st.container(border=True):
            st.markdown("#### 2️⃣ NRE & Engineering — 100% Indian if performed in India")
            try:
                from utils.io import load_nre
                from utils.nre import nre_total
                nre_df = load_nre()
                if not nre_df.empty:
                    nre_eur = float(nre_total(nre_df))
                    nre_contrib = nre_eur / contract_value if contract_value > 0 else 0
                    st.metric("NRE total", fmt(nre_eur, 0),
                              delta="Full IC contribution if performed in India",
                              delta_color="normal")
                    st.caption(
                        f"With all NRE as Indian: IC% = {_pct(ic_pct_calc + nre_contrib)} "
                        f"(currently {_pct(ic_pct_calc)})"
                    )
                else:
                    st.caption("Enter NRE data in Engineering & NRE page.")
            except Exception:
                st.caption("Load NRE data to see this contribution.")

        with st.container(border=True):
            st.markdown("#### 3️⃣ Top imported scopes — candidate for Indian alternative")
            top_imp = (
                edited[edited["origin"] == "Imported"]
                .nlargest(6, "cost_eur")
                [["scope_name", "cost_eur", "hs_code"]]
                .copy()
            )
            if top_imp.empty:
                st.caption("No imported scopes.")
            else:
                top_imp["IC uplift if Indian"] = top_imp["cost_eur"].map(
                    lambda v: _pct(v / contract_value) if contract_value > 0 else "—")
                top_imp["cost_eur"] = top_imp["cost_eur"].map(lambda x: fmt(x, 0))
                st.dataframe(top_imp.rename(columns={
                    "scope_name": "Scope", "cost_eur": "Value (€)", "hs_code": "HS Code",
                }), use_container_width=True, hide_index=True)

        with st.container(border=True):
            st.markdown("#### 4️⃣ Contract structuring — advanced methods")
            st.markdown("""
**Bill of Entry (BoE):** File a BoE for every imported item. Customs-cleared import
value is documented; everything else is deemed Indian. Irrefutable.

**Free Issue Material (FIM):** Customer supplies high-value imports themselves —
excluded from the IC% denominator entirely. Negotiate this for NAB castings,
impeller blanks, or imported shaft material.

**Offset credits:** DAP 2020 allows Offset credits for work placed with Indian entities.
If your parent company has an offset obligation, sub-placing machining/assembly is dual-purpose.

**Letter of Intent:** At tender stage, an LoI from an Indian supplier (no price) is accepted
as evidence of active local sourcing for Partially Indian items.
            """)

        st.info(
            "**Bottom line:** Submit (A) Scope Origin Register, (B) CA Certificate, "
            "(C) Supplier Origin Declarations. Surveyor gets origin data only — "
            "no prices, no quotes.",
            icon="🔒",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — BOM LINE DETAIL (read-only, how scope IC applies per line)
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[4]:
        st.subheader("BOM line detail — scope IC applied per line")
        st.caption(
            "Read-only view. IC fraction from the scope register is applied to every "
            "BOM line within that scope. Use this to spot any lines that need a scope override."
        )

        # Build per-line view
        prefix_order = sorted(WATERJET_SUBSYSTEMS.keys(), key=len, reverse=True)

        def _match_scope(lid: str) -> str:
            lid_up = str(lid).upper()
            for p in prefix_order:
                if lid_up.startswith(p):
                    return p
            return "_OTHER"

        df_detail = df[["line_id", "part_name", "material_id", "total_cost"]].copy()
        df_detail["scope_id"] = df_detail["line_id"].map(_match_scope)

        # Attach scope IC settings
        scope_ic_map = edited.copy()
        scope_ic_map["scope_id"] = scope_tbl["scope_id"].values
        scope_ic_map = scope_ic_map[["scope_id", "origin", "ic_value_pct",
                                      "indian_supplier"]].drop_duplicates("scope_id")

        df_detail = df_detail.merge(scope_ic_map, on="scope_id", how="left")
        df_detail["ic_value_pct"] = pd.to_numeric(
            df_detail["ic_value_pct"], errors="coerce").fillna(0.0)
        df_detail["IC value (€)"] = df_detail["total_cost"] * df_detail["ic_value_pct"]

        df_detail["total_cost"]  = df_detail["total_cost"].map(lambda x: fmt(x, 0))
        df_detail["IC value (€)"]= df_detail["IC value (€)"].map(lambda x: fmt(x, 0))
        df_detail["ic_value_pct"]= df_detail["ic_value_pct"].map(lambda x: f"{x*100:.0f}%")

        st.dataframe(df_detail.rename(columns={
            "line_id": "Line ID", "part_name": "Component",
            "material_id": "Material", "total_cost": "Cost (€)",
            "scope_id": "Scope", "origin": "Origin",
            "ic_value_pct": "IC fraction", "IC value (€)": "IC value (€)",
            "indian_supplier": "Indian manufacturer",
        }).drop(columns=["scope_id"], errors="ignore"),
        use_container_width=True, hide_index=True)


guard(main)
