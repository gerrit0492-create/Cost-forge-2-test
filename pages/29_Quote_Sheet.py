from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.completeness import WATERJET_SUBSYSTEMS
from utils.io import load_bom, load_materials, load_processes, load_quotes, df_to_excel_bytes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_name
from utils.quotes import apply_best_quotes, expired_quote_materials
from utils.style import inject_css, page_header

st.set_page_config(page_title="Quote Sheet", layout="wide", page_icon="🧾")
inject_css()
home_button()
page_header(
    title="Quote Sheet",
    icon="🧾",
    caption="Internal cost analysis · customer-facing quote preview · data quality checks.",
)

_, hdr2 = st.columns([6, 1])
if hdr2.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

# ── Company profile (sidebar) ─────────────────────────────────────────────────
with st.sidebar.expander("🏢 Company profile", expanded=False):
    company_name    = st.text_input("Company name",   key="cp_name",    value=st.session_state.get("cp_name",    ""))
    company_address = st.text_area( "Address",        key="cp_addr",    value=st.session_state.get("cp_addr",    ""), height=70)
    company_vat     = st.text_input("VAT / CoC no.",  key="cp_vat",     value=st.session_state.get("cp_vat",     ""))
    company_contact = st.text_input("Contact person", key="cp_contact", value=st.session_state.get("cp_contact", ""))
    company_email   = st.text_input("E-mail",         key="cp_email",   value=st.session_state.get("cp_email",   ""))
    company_phone   = st.text_input("Phone",          key="cp_phone",   value=st.session_state.get("cp_phone",   ""))

# ── Quote header ──────────────────────────────────────────────────────────────
st.subheader("1 · Quote header")
h1, h2, h3, h4, h5 = st.columns(5)
quote_number  = h1.text_input("Quote number", value="QT-2026-001")
quote_rev     = h2.text_input("Revision",     value="A")
quote_date    = h3.date_input("Issue date",   value=datetime.date.today())
validity_days = h4.number_input("Valid (days)", min_value=1, max_value=365, value=60)
valid_until   = quote_date + datetime.timedelta(days=int(validity_days))
h5.metric("Valid until", valid_until.strftime("%d %b %Y"))

c1, c2, c3, c4 = st.columns(4)
customer_name    = c1.text_input("Customer company",  value="")
customer_contact = c2.text_input("Customer contact",  value="")
customer_email   = c3.text_input("Customer e-mail",   value="")
customer_po      = c4.text_input("Customer PO / Ref", value="")
project_label    = st.text_input("Project / description", value=load_project_name())

# ── Commercial terms ──────────────────────────────────────────────────────────
st.subheader("2 · Commercial terms")
t1, t2, t3, t4 = st.columns(4)
payment_terms = t1.selectbox("Payment terms", [
    "Net 30 days", "Net 60 days", "Net 90 days",
    "50% advance, 50% on delivery", "100% advance",
    "Letter of credit (LC at sight)",
])
incoterms = t2.selectbox("Incoterms 2020", [
    "EXW — Ex Works", "FCA — Free Carrier", "CPT — Carriage Paid To",
    "CIF — Cost, Insurance & Freight", "DAP — Delivered at Place", "DDP — Delivered Duty Paid",
])
delivery_weeks  = t3.number_input("Delivery (weeks)",  min_value=1,  max_value=104, value=20, step=1)
warranty_months = t4.number_input("Warranty (months)", min_value=0,  max_value=36,  value=12, step=1)
scope_notes = st.text_area(
    "Scope notes / exclusions", height=55,
    placeholder="e.g. Excludes installation, commissioning and sea trials. Capital spares not included.",
)

st.divider()

# ── Production parameters ─────────────────────────────────────────────────────
st.subheader("3 · Production parameters")
p1, p2 = st.columns(2)
num_units = p1.number_input(
    "Production run (units)", min_value=1, max_value=20, value=1,
    help="Setup time is amortised across the run.",
)
CERT_CLASSES = {
    "None (commercial)":       {"ndt_mult": 1.00, "test_mult": 1.00, "fee_eur": 0},
    "DNV / GL":                {"ndt_mult": 1.50, "test_mult": 1.30, "fee_eur": 3_500},
    "Lloyd's Register (LRS)":  {"ndt_mult": 1.50, "test_mult": 1.30, "fee_eur": 3_500},
    "Bureau Veritas (BV)":     {"ndt_mult": 1.40, "test_mult": 1.25, "fee_eur": 3_000},
    "ABS":                     {"ndt_mult": 1.40, "test_mult": 1.25, "fee_eur": 3_000},
}
cert_class = p2.selectbox("Classification society", list(CERT_CLASSES.keys()),
                          help="Adds surcharge to NDT and pressure-test costs.")
cert_cfg = CERT_CLASSES[cert_class]

st.divider()

# ── Load & compute ────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load(n_units: int) -> pd.DataFrame:
    mats = apply_best_quotes(load_materials(), load_quotes())
    return compute_costs(mats, load_processes(), load_bom(), num_units=n_units)

try:
    df = _load(int(num_units))
except Exception as exc:
    st.error(f"Could not load cost data: {exc}")
    st.stop()

try:
    expired = expired_quote_materials(load_quotes())
    if expired:
        st.warning(f"⚠️ Expired supplier quotes ignored for: {', '.join(expired)}")
except Exception:
    pass

# Subsystem tagging
df["subsystem"] = df["line_id"].apply(
    lambda lid: next(
        (p for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True)
         if str(lid).upper().startswith(p)), "?"
    )
)
subsys_label = {p: f"{i['icon']} {i['name']}" for p, i in WATERJET_SUBSYSTEMS.items()}

# ── Margin override ───────────────────────────────────────────────────────────
st.subheader("4 · Margin settings")
m1, m2 = st.columns([1, 3])
use_override = m1.toggle("Global margin override")
global_margin_pct: float | None = None
if use_override:
    global_margin_pct = m2.slider("Global margin %", 0, 50, 18, 1) / 100.0
    st.info(f"All lines will use **{global_margin_pct*100:.0f}%** margin for this quote.")

work = df.copy()
if global_margin_pct is not None:
    work["margin_pct"] = global_margin_pct
    work["margin"]     = work["base_cost"] * global_margin_pct
    work["total_cost"] = work["base_cost"] + work["margin"]

# Certification surcharge
ndt_cost  = work.loc[work["process_route"] == "NDT_INSPECT",   "process_cost"].sum() \
            if "process_route" in work.columns else 0.0
test_cost = work.loc[work["process_route"] == "PRESSURE_TEST", "process_cost"].sum() \
            if "process_route" in work.columns else 0.0
cert_surcharge = (
    ndt_cost  * (cert_cfg["ndt_mult"]  - 1.0) +
    test_cost * (cert_cfg["test_mult"] - 1.0) +
    cert_cfg["fee_eur"]
)

# ── Aggregate totals (shared across tabs) ─────────────────────────────────────
qty_s = pd.to_numeric(work["qty"], errors="coerce").fillna(1)
work["_line_mass"] = qty_s * work["mass_kg"].fillna(0)

def _safe(col: str) -> pd.Series:
    return work[col] if col in work.columns else pd.Series([0.0] * len(work), index=work.index)

total_mass = work["_line_mass"].sum()
total_mat  = work["material_cost"].sum()
total_mach = _safe("machine_cost").sum()
total_lab  = _safe("labour_cost").sum()
total_oh   = work["overhead"].sum()
total_base = work["base_cost"].sum()
total_marg = work["margin"].sum()
total_sell = work["total_cost"].sum() + cert_surcharge

agg_cols = [c for c in ["material_cost", "machine_cost", "labour_cost",
                         "overhead", "base_cost", "margin", "total_cost", "_line_mass"]
            if c in work.columns]
agg = work.groupby("subsystem")[agg_cols].sum().reset_index()
agg["label"] = agg["subsystem"].map(lambda p: subsys_label.get(p, p))
agg["_epkg"]  = (agg["total_cost"] / agg["_line_mass"].replace(0, float("nan"))).round(0)
agg["_share"] = agg["total_cost"] / total_sell * 100 if total_sell else 0.0

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
tab_int, tab_cust, tab_qa = st.tabs([
    "💼 Internal cost analysis",
    "📄 Customer quote preview",
    "⚠️ Quality & risk checks",
])

# ──────────────────────────────────────────────────────────────────────────────
with tab_int:
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Material",   fmt(total_mat))
    k2.metric("Processing", fmt(total_mach + total_lab))
    k3.metric("Overhead",   fmt(total_oh))
    k4.metric("Your cost",  fmt(total_base))
    k5.metric("Sell price", fmt(total_sell),
              delta=f"Margin {fmt(total_marg)} ({total_marg/total_base*100:.1f}%)" if total_base else None)
    k6.metric("Dry weight", f"{total_mass:,.0f} kg")

    if cert_surcharge > 0:
        st.info(
            f"**{cert_class}** surcharge **{fmt(cert_surcharge)}** included  \n"
            f"NDT ×{cert_cfg['ndt_mult']}, pressure test ×{cert_cfg['test_mult']}, "
            f"cert. fee {fmt(cert_cfg['fee_eur'])}"
        )
    if num_units > 1:
        st.caption(f"Setup amortised across **{int(num_units)} units** — all costs shown per unit.")

    st.divider()

    # Cost structure percentages
    st.subheader("Cost structure")
    cs1, cs2, cs3, cs4, cs5 = st.columns(5)
    cs1.metric("Material %",  f"{total_mat/total_base*100:.0f}%"              if total_base else "—")
    cs2.metric("Machine %",   f"{total_mach/total_base*100:.0f}%"             if total_base else "—")
    cs3.metric("Labour %",    f"{total_lab/total_base*100:.0f}%"              if total_base else "—")
    cs4.metric("Overhead %",  f"{total_oh/total_base*100:.0f}%"               if total_base else "—")
    cs5.metric("Margin %",    f"{total_marg/total_base*100:.1f}%"             if total_base else "—")

    st.divider()

    # Subsystem breakdown
    st.subheader("Subsystem breakdown")
    ch_col, tbl_col = st.columns([3, 2])

    with ch_col:
        chart_cols = [c for c in ["material_cost", "machine_cost", "labour_cost", "overhead", "margin"]
                      if c in agg.columns]
        rename_map = {"material_cost": "Material", "machine_cost": "Machine",
                      "labour_cost": "Labour", "overhead": "Overhead", "margin": "Margin"}
        chart_df = agg.set_index("label")[chart_cols].rename(columns=rename_map)
        st.bar_chart(chart_df,
                     color=["#2196F3", "#FF9800", "#F44336", "#9C27B0", "#4CAF50"][:len(chart_cols)])

    with tbl_col:
        tbl = agg[["label", "base_cost", "margin", "total_cost", "_line_mass", "_epkg", "_share"]].copy()
        tbl.columns = ["Subsystem", "Your cost", "Margin", "Sell price", "Mass kg", "€/kg", "Share %"]
        tbl["Your cost"]  = tbl["Your cost"].map(lambda x: fmt(x))
        tbl["Margin"]     = tbl["Margin"].map(lambda x: fmt(x))
        tbl["Sell price"] = tbl["Sell price"].map(lambda x: fmt(x))
        tbl["Mass kg"]    = tbl["Mass kg"].map(lambda x: f"{x:,.0f}")
        tbl["€/kg"]       = tbl["€/kg"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
        tbl["Share %"]    = tbl["Share %"].map(lambda x: f"{x:.1f}%")
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    st.divider()

    with st.expander("Full BOM line detail", expanded=False):
        line_map = {
            "line_id": "Line", "part_name": "Component", "material_id": "Material",
            "qty": "Qty", "mass_kg": "kg", "yield_factor": "Yield",
            "material_cost": "Mat €", "process_route": "Route",
            "runtime_h": "Run h", "setup_h": "Setup h",
            "machine_cost": "Mach €", "labour_cost": "Lab €",
            "overhead": "OH €", "base_cost": "Cost €",
            "margin": "Margin €", "total_cost": "Sell €",
        }
        lt = work[[c for c in line_map if c in work.columns]].copy()
        lt.rename(columns=line_map, inplace=True)
        for col in ["Mat €", "Mach €", "Lab €", "OH €", "Cost €", "Margin €", "Sell €"]:
            if col in lt.columns:
                lt[col] = lt[col].map(lambda x: fmt(x, 2))
        st.dataframe(lt, use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
with tab_cust:
    inco_code = incoterms.split("—")[0].strip()
    date_str  = quote_date.strftime("%d %B %Y")
    valid_str = valid_until.strftime("%d %B %Y")
    addr_html = company_address.replace("\n", "<br>") if company_address else ""

    st.markdown(f"""
<div style="border:1px solid #334; border-radius:10px; padding:32px 36px;
            max-width:860px; margin:0 auto; font-family:Arial,sans-serif; background:#111820;">

  <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:28px;">
    <div>
      <div style="font-size:2em; font-weight:700; color:#4da6ff; letter-spacing:1px;">QUOTATION</div>
      <div style="font-size:1.05em; font-weight:600; color:#ddd; margin-top:4px;">{company_name or "—"}</div>
      <div style="font-size:0.82em; color:#888; margin-top:2px; line-height:1.6;">{addr_html}</div>
      {f'<div style="font-size:0.82em;color:#888;">VAT: {company_vat}</div>' if company_vat else ""}
      {f'<div style="font-size:0.82em;color:#888;">{company_email}&nbsp;|&nbsp;{company_phone}</div>' if company_email else ""}
    </div>
    <div style="text-align:right; line-height:1.9;">
      <div style="font-size:1.1em; font-weight:600; color:#fff;">{quote_number}&nbsp; Rev&nbsp;{quote_rev}</div>
      <div style="color:#aaa; font-size:0.88em;">Date: {date_str}</div>
      <div style="color:#f0a500; font-size:0.88em; font-weight:600;">Valid until: {valid_str}</div>
    </div>
  </div>

  <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:8px;">
    <div style="background:#1a2535; border-radius:7px; padding:14px 18px;">
      <div style="color:#888; font-size:0.78em; text-transform:uppercase; letter-spacing:.5px; margin-bottom:6px;">Bill To</div>
      <div style="font-weight:600; color:#ddd;">{customer_name or "—"}</div>
      {f'<div style="color:#aaa;font-size:0.88em;">Attn: {customer_contact}</div>' if customer_contact else ""}
      {f'<div style="color:#aaa;font-size:0.88em;">{customer_email}</div>' if customer_email else ""}
      {f'<div style="color:#aaa;font-size:0.88em;">PO Ref: {customer_po}</div>' if customer_po else ""}
    </div>
    <div style="background:#1a2535; border-radius:7px; padding:14px 18px;">
      <div style="color:#888; font-size:0.78em; text-transform:uppercase; letter-spacing:.5px; margin-bottom:6px;">Project</div>
      <div style="font-weight:600; color:#ddd;">{project_label or "—"}</div>
      <div style="color:#aaa; font-size:0.88em; margin-top:6px; line-height:1.7;">
        Delivery: <strong style="color:#ccc;">{delivery_weeks} weeks</strong> after order confirmation<br>
        Warranty: <strong style="color:#ccc;">{warranty_months} months</strong><br>
        Classification: <strong style="color:#ccc;">{cert_class}</strong>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("")
    st.subheader("Scope of supply")

    scope_rows = agg[["label", "total_cost"]].copy()
    scope_rows.columns = ["Description", "_amt"]
    if cert_surcharge > 0:
        scope_rows = pd.concat([scope_rows, pd.DataFrame([{
            "Description": f"Classification surcharge — {cert_class}",
            "_amt": cert_surcharge,
        }])], ignore_index=True)
    scope_rows["Amount"] = scope_rows["_amt"].map(lambda x: fmt(float(x), 2))
    st.dataframe(scope_rows[["Description", "Amount"]], use_container_width=True, hide_index=True)

    st.markdown(f"""
<div style="display:flex; justify-content:flex-end; margin-top:12px; margin-bottom:20px;">
  <div style="background:#1a3050; border:1px solid #2a5090; border-radius:8px;
              padding:18px 28px; min-width:300px; text-align:right;">
    <div style="color:#888; font-size:0.78em; text-transform:uppercase; letter-spacing:.5px;">Total selling price</div>
    <div style="font-size:2em; font-weight:700; color:#4da6ff; margin:4px 0;">{fmt(total_sell)}</div>
    <div style="color:#aaa; font-size:0.82em;">{inco_code} &nbsp;·&nbsp; {payment_terms}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    if scope_notes:
        st.markdown("**Notes & Exclusions**")
        st.info(scope_notes)

    with st.expander("Commercial terms"):
        terms_df = pd.DataFrame([
            ("Payment terms",  payment_terms),
            ("Incoterms 2020", incoterms),
            ("Delivery",       f"{delivery_weeks} weeks from order confirmation"),
            ("Warranty",       f"{warranty_months} months on parts and workmanship"),
            ("Quote validity", f"Valid until {valid_str}"),
            ("Classification", cert_class),
        ], columns=["Term", "Condition"])
        st.dataframe(terms_df, use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
with tab_qa:
    st.subheader("Data quality & risk checks")
    issues = 0

    try:
        exp_list = expired_quote_materials(load_quotes())
        if exp_list:
            st.warning(f"⚠️ **{len(exp_list)} material(s) with expired quotes:** {', '.join(exp_list)}")
            issues += len(exp_list)
        else:
            st.success("✅ All supplier quotes are within their validity period.")
    except Exception:
        pass

    zero_lines = work[work["total_cost"] <= 0]
    if not zero_lines.empty:
        st.warning(f"⚠️ **{len(zero_lines)} BOM line(s) with zero or negative sell price** — check material prices and process rates.")
        cols = [c for c in ["line_id", "part_name", "material_id", "material_cost", "process_cost"] if c in zero_lines.columns]
        st.dataframe(zero_lines[cols].head(20), hide_index=True)
        issues += len(zero_lines)
    else:
        st.success("✅ All BOM lines have a positive sell price.")

    if "margin_pct" in work.columns:
        low = work[work["margin_pct"] < 0.10]
        if not low.empty:
            st.warning(f"⚠️ **{len(low)} line(s) carry less than 10% margin.**")
            display_low = low[["line_id", "part_name", "base_cost", "margin_pct", "total_cost"]].copy()
            display_low["margin_pct"] = display_low["margin_pct"].map(lambda x: f"{x*100:.1f}%")
            display_low["base_cost"]  = display_low["base_cost"].map(lambda x: fmt(x, 2))
            display_low["total_cost"] = display_low["total_cost"].map(lambda x: fmt(x, 2))
            st.dataframe(display_low.head(20), hide_index=True)
            issues += len(low)
        else:
            st.success("✅ All lines carry at least 10% margin.")

    mat_share = total_mat / total_base if total_base else 0
    if mat_share > 0.75:
        st.warning(
            f"⚠️ Material is **{mat_share*100:.0f}%** of cost — high commodity price exposure. "
            "Consider back-to-back supply contracts or price escalation clauses."
        )
        issues += 1
    else:
        st.success(f"✅ Material share is {mat_share*100:.0f}% of cost — within normal range.")

    overall_margin = total_marg / total_base * 100 if total_base else 0
    if overall_margin < 10:
        st.error(f"🚨 Overall quote margin is **{overall_margin:.1f}%** — below the 10% threshold.")
        issues += 1
    elif overall_margin < 15:
        st.warning(f"⚠️ Overall margin **{overall_margin:.1f}%** — consider whether this covers risk and overheads adequately.")
    else:
        st.success(f"✅ Overall quote margin: **{overall_margin:.1f}%**")

    st.divider()
    if issues == 0:
        st.success("✅ **No issues found** — quote data is complete and consistent.")
    else:
        st.error(f"**{issues} issue(s) found** — review before sending the quote to the customer.")

    st.subheader("Cost structure")
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Material share",  f"{total_mat/total_base*100:.0f}%"              if total_base else "—")
    r2.metric("Process share",   f"{(total_mach+total_lab)/total_base*100:.0f}%" if total_base else "—")
    r3.metric("Overhead share",  f"{total_oh/total_base*100:.0f}%"               if total_base else "—")
    r4.metric("Overall margin",  f"{total_marg/total_base*100:.1f}%"             if total_base else "—")
    r5.metric("€ per kg",        f"{total_sell/total_mass:,.0f}" if total_mass else "—")

# ── Downloads ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Downloads")

internal_cols = [
    "line_id", "part_name", "material_id", "qty", "mass_kg",
    "yield_factor", "price_eur_per_kg", "material_cost",
    "process_route", "runtime_h", "setup_h",
    "machine_cost", "labour_cost", "overhead_pct", "overhead",
    "base_cost", "margin_pct", "margin", "total_cost",
]
internal_df = work[[c for c in internal_cols if c in work.columns]].copy()

header_meta = pd.DataFrame([
    {"Description": k, "Selling price": v} for k, v in [
        ("Quote number",   quote_number),  ("Revision",      quote_rev),
        ("Date",           str(quote_date)),("Valid until",   str(valid_until)),
        ("Customer",       customer_name), ("Contact",        customer_contact),
        ("E-mail",         customer_email),("PO reference",   customer_po),
        ("Project",        project_label), ("Payment terms",  payment_terms),
        ("Incoterms 2020", incoterms),     ("Delivery",       f"{delivery_weeks} weeks"),
        ("Warranty",       f"{warranty_months} months"), ("Classification", cert_class),
        ("---",            "---"),
    ]
])
cust_lines = agg[["label", "total_cost"]].rename(
    columns={"label": "Description", "total_cost": "Selling price"}
).copy()
cust_lines["Selling price"] = cust_lines["Selling price"].round(2)
if cert_surcharge > 0:
    cust_lines = pd.concat([cust_lines, pd.DataFrame([{
        "Description": f"Classification surcharge ({cert_class})",
        "Selling price": round(cert_surcharge, 2),
    }])], ignore_index=True)
cust_lines = pd.concat([
    cust_lines,
    pd.DataFrame([{"Description": "TOTAL", "Selling price": round(total_sell, 2)}]),
], ignore_index=True)
customer_sheet = pd.concat([header_meta, cust_lines], ignore_index=True)

dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        "⬇️ Internal cost detail (Excel)",
        data=df_to_excel_bytes(internal_df, "Internal Cost"),
        file_name=f"{quote_number}_internal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Full cost breakdown including margins — keep confidential.",
    )
with dl2:
    st.download_button(
        "⬇️ Customer quote (Excel)",
        data=df_to_excel_bytes(customer_sheet, "Quote"),
        file_name=f"{quote_number}_quote.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Subsystem selling prices only — safe to share with customer.",
    )
