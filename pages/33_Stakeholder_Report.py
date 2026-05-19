from __future__ import annotations

import datetime
import io

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.completeness import WATERJET_SUBSYSTEMS, completeness_score, detect_subsystems, missing_subsystems
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_meta
from utils.quotes import apply_best_quotes, best_quotes, expired_quote_materials

st.set_page_config(page_title="Stakeholder Report", layout="wide", page_icon="📋")
home_button()

_, btn = st.columns([6, 1])
if btn.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

# ── Load everything ───────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _load():
    mats   = load_materials()
    quotes = load_quotes()
    bom    = load_bom()
    procs  = load_processes()
    df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    return mats, quotes, bom, procs, df

try:
    mats, quotes, bom, procs, df = _load()
except Exception as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()

meta   = load_project_meta()
today  = datetime.date.today()
todayp = pd.Timestamp.today().normalize()

MATURITY_COLOUR = {
    "RoM (±30%)":       "#f0a500",
    "Budget (±15%)":    "#ff7043",
    "Definitive (±5%)": "#42a5f5",
    "Firm":             "#66bb6a",
}

# ── Pre-compute all metrics ───────────────────────────────────────────────────
qty_s      = pd.to_numeric(bom["qty"],    errors="coerce").fillna(1)
total_mass = (qty_s * bom["mass_kg"].fillna(0)).sum()

total_sell = df["total_cost"].sum()
total_mat  = df["material_cost"].sum()
total_proc = df.get("process_cost",  pd.Series([0]*len(df))).sum() if "process_cost"  in df.columns else 0.0
total_mach = df["machine_cost"].sum() if "machine_cost" in df.columns else 0.0
total_lab  = df["labour_cost"].sum()  if "labour_cost"  in df.columns else 0.0
total_oh   = df["overhead"].sum()
total_base = df["base_cost"].sum()    if "base_cost"    in df.columns else (total_mat + total_proc + total_oh)
total_marg = df["margin"].sum()

margin_pct  = total_marg / total_base * 100  if total_base  else 0
mat_share   = total_mat  / total_base * 100  if total_base  else 0
eur_per_kg  = total_sell / total_mass        if total_mass  else 0
target_cost = float(meta.get("target_cost", 0))
maturity    = meta.get("maturity", "Budget (±15%)")
mat_colour  = MATURITY_COLOUR.get(maturity, "#42a5f5")

# Subsystem aggregation
def _sub(lid):
    u = str(lid).upper()
    return next((p for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True)
                 if u.startswith(p)), "?")

df["_sub"]       = df["line_id"].apply(_sub)
df["_line_mass"] = qty_s.values * df["mass_kg"].fillna(0).values
sub_agg = df.groupby("_sub").agg(
    mat=("material_cost", "sum"),
    proc=("process_cost", "sum") if "process_cost" in df.columns else ("total_cost", "first"),
    oh=("overhead", "sum"),
    marg=("margin", "sum"),
    sell=("total_cost", "sum"),
    mass=("_line_mass", "sum"),
    lines=("line_id", "count"),
).reset_index()
sub_agg["label"]  = sub_agg["_sub"].map(lambda p: f"{WATERJET_SUBSYSTEMS.get(p,{}).get('icon','❓')} {WATERJET_SUBSYSTEMS.get(p,{}).get('name', p)}")
sub_agg["epkg"]   = (sub_agg["sell"] / sub_agg["mass"].replace(0, float("nan"))).round(0)
sub_agg["share"]  = sub_agg["sell"] / total_sell * 100 if total_sell else 0.0

# Quote metrics
today_q = pd.Timestamp.today().normalize()
q = quotes.copy()
if "valid_until" in q.columns:
    q["valid_until"] = pd.to_datetime(q["valid_until"], errors="coerce")
    q["expired"]     = q["valid_until"] < today_q
else:
    q["expired"] = False
expired_list  = expired_quote_materials(quotes)
quoted_ids    = set(q[~q["expired"]]["material_id"].unique())
all_mat_ids   = set(mats["material_id"].unique())
unquoted      = sorted(all_mat_ids - quoted_ids)
n_suppliers   = q["supplier"].nunique() if "supplier" in q.columns else 0
max_lt        = int(q["lead_time_days"].max()) if "lead_time_days" in q.columns and not q.empty else 0

# BOM completeness
comp_score   = completeness_score(bom)
present_subs = detect_subsystems(bom)
missing_subs = missing_subsystems(bom)
crit_missing = [(p, i) for p, i in missing_subs if i["critical"]]

# Risk findings — each entry: (severity, title, detail, why_it_matters, fix_steps, page_links)
# page_links = list of (label, path) tuples
risks = []
if expired_list:
    risks.append((
        "🔴 High",
        "Expired supplier quotes",
        f"{len(expired_list)} material(s): {', '.join(expired_list[:5])}{'…' if len(expired_list)>5 else ''}",
        "Costs are calculated using stale or base prices — the quoted price to the customer may not be achievable.",
        [
            "Open **Supplier Quotes** and go to the *Quote status* tab.",
            "Identify all rows marked 🔴 Expired.",
            "Contact each supplier and request an updated price and validity date.",
            "Enter the new quote via **CSV Import** or directly in `cost_forge.xlsx → Quotes`.",
            "Click 🔄 Refresh and verify all quotes show 🟢 Valid before releasing the quotation.",
        ],
        [("→ Supplier Quotes", "pages/07_Supplier_Quotes.py"),
         ("→ CSV Import",      "pages/99_Update_from_Public_CSV.py")],
    ))
if crit_missing:
    risks.append((
        "🔴 High",
        "Critical subsystems missing from BOM",
        ", ".join(i["name"] for _, i in crit_missing),
        "The cost estimate is incomplete — the total sell price is understated because critical parts are absent.",
        [
            "Open your BOM source file (ERP export or Excel).",
            f"Ensure the missing subsystem(s) have line IDs starting with the correct prefix: "
            f"{', '.join('`'+p+'`' for p,_ in crit_missing)}.",
            "Re-upload the complete BOM via **BOM Import**.",
            "Check the BOM completeness grid in this report — all critical rows should show 🟢.",
        ],
        [("→ BOM Import", "pages/15_Bom_Import.py"),
         ("→ Data Quality", "pages/05_Data_Quality.py")],
    ))
if len(unquoted) > 0:
    risks.append((
        "🟠 Medium",
        "Materials without a valid supplier quote",
        f"{len(unquoted)} of {len(mats)} materials have no confirmed quote",
        "Those materials fall back to the base catalogue price — cost accuracy is reduced and the price is not commercially confirmed.",
        [
            "Open **Supplier Quotes → Coverage Gaps** to see the exact list of unquoted materials.",
            "Contact suppliers for each unquoted material.",
            "Enter the received quotes via **CSV Import** or `cost_forge.xlsx → Quotes`.",
            "Re-check coverage in **Material Library → Quote coverage** tab.",
        ],
        [("→ Supplier Quotes — Coverage Gaps", "pages/07_Supplier_Quotes.py"),
         ("→ CSV Import", "pages/99_Update_from_Public_CSV.py"),
         ("→ Material Library", "pages/04_Materiaalbronnen.py")],
    ))
if mat_share > 75:
    risks.append((
        "🟠 Medium",
        "High material cost exposure",
        f"Material is {mat_share:.0f}% of the cost base (threshold: 75%)",
        "Commodity price movements directly affect margin. A 5 % material price increase could eliminate all profit.",
        [
            "Open **Supplier Quotes → Spend & Concentration** and identify the top 3 spend materials.",
            "Negotiate fixed-price supply contracts or price-escalation clauses for those materials.",
            "Use **Scenario Planner** to simulate the margin impact of price swings before quoting.",
            "Consider back-to-back supply agreements for the highest-exposure items.",
        ],
        [("→ Supplier Quotes — Spend", "pages/07_Supplier_Quotes.py"),
         ("→ Scenario Planner", "pages/06_Scenario_Planner.py")],
    ))
if margin_pct < 10:
    risks.append((
        "🔴 High",
        "Overall margin below minimum threshold",
        f"Margin is {margin_pct:.1f}% — minimum recommended is 10%",
        "Any cost increase (materials, rework, delays) will result in a commercial loss on this order.",
        [
            "Open **Line Cost Detail** and sort by margin % ascending to find the lowest-margin lines.",
            "Check whether process routing hours can be reduced — review in **Routing Costs**.",
            "Verify overhead % and margin % settings are correct in **Presets**.",
            "Review the sell price with the commercial team in **Quote Sheet**.",
            "Consider value-engineering the top 3 cost-driver lines (see Section 2 above).",
        ],
        [("→ Line Cost Detail", "pages/28_Line_Cost_Detail.py"),
         ("→ Presets",          "pages/03_Presets.py"),
         ("→ Quote Sheet",      "pages/29_Quote_Sheet.py"),
         ("→ Routing Costs",    "pages/16_Routing_Kosten.py")],
    ))
if maturity in ("RoM (±30%)", "Budget (±15%)"):
    _next = "Budget (±15%)" if maturity == "RoM (±30%)" else "Definitive (±5%)"
    _steps_by_maturity = {
        "RoM (±30%)": [
            "**BOM scope**: Verify all major subsystems are represented — open the BOM completeness grid below and confirm no *critical* subsystem is missing.",
            "**Material prices**: Every material must have a non-zero base price. Check → **Data Quality → Materials** tab, *Zero / negative prices* metric must be 0.",
            "**Process routes assigned**: All BOM lines must have a process route. Check → **Data Quality → BOM** tab, *Unmatched process routes* must be 0.",
            "**Weight basis**: Confirm mass_kg is filled for every BOM line (not 0 or blank). Check → **Data Quality → BOM** tab.",
            f"**Advance maturity**: Once all 4 points above are ✅, open the dashboard sidebar and change maturity to *{_next}*.",
        ],
        "Budget (±15%)": [
            "**Data Quality score ≥ 8/10**: Open **Data Quality** — the overall health bar must show at least 8/10 checks passed.",
            "**Quote coverage ≥ 80%**: At least 80 % of materials must have a valid, non-expired supplier quote. Check → **Supplier Quotes → Coverage Gaps** — the coverage metric must show ≥ 80 %.",
            "**No expired quotes**: **Supplier Quotes → Quote status** must show zero 🔴 Expired rows. Renew any outstanding quotes first.",
            "**Process hours reviewed**: Open **Routing Costs** and confirm runtime_h values are based on actual routing data, not placeholders.",
            "**Overhead % and margin % approved**: Open **Presets** and verify the rates are signed off by project management — not default values.",
            "**Surcharges and classification**: If a classification society applies, confirm the correct society and surcharge % is set in **Quote Sheet → Production** settings.",
            f"**Advance maturity**: Once all 6 points above are ✅, open the dashboard sidebar and change maturity to *{_next}*. For *Firm*, also confirm a customer PO or LOI is in hand and back-to-back supply contracts cover the top 5 spend materials.",
        ],
    }
    risks.append((
        "🟡 Low",
        "Estimate maturity is not firm",
        f"Current: {maturity} — target next level: {_next}",
        f"At {maturity} the sell price could vary by the stated tolerance. Issuing this as a firm quotation exposes the company to potential loss if actual costs land at the high end of the range.",
        _steps_by_maturity[maturity],
        [("→ Data Quality",   "pages/05_Data_Quality.py"),
         ("→ Supplier Quotes","pages/07_Supplier_Quotes.py"),
         ("→ Routing Costs",  "pages/16_Routing_Kosten.py"),
         ("→ Presets",        "pages/03_Presets.py")],
    ))
if target_cost > 0 and total_sell > target_cost * 1.05:
    gap_pct = (total_sell - target_cost) / target_cost * 100
    risks.append((
        "🟠 Medium",
        "Sell price exceeds budget target",
        f"Sell price {fmt(total_sell)} vs target {fmt(target_cost)} (+{gap_pct:.1f}%)",
        "The commercial target is not met — risk of contract loss or unacceptable margin reduction.",
        [
            "Review the subsystem breakdown in Section 2 and target the largest cost subsystem for value engineering.",
            "Use **Scenario Planner** to model which commodity savings would close the gap.",
            "Check whether process times can be reduced in **Routing Costs**.",
            "Review overhead % and margin settings in **Presets** — verify they reflect the actual project.",
            "Escalate to the commercial and engineering team with the Section 2 subsystem table as evidence.",
        ],
        [("→ Scenario Planner", "pages/06_Scenario_Planner.py"),
         ("→ Routing Costs",    "pages/16_Routing_Kosten.py"),
         ("→ Presets",          "pages/03_Presets.py")],
    ))

# Low-margin lines
low_margin_lines = []
if "margin_pct" in df.columns:
    low_margin_lines = df[df["margin_pct"] < 0.10][["line_id", "part_name", "margin_pct", "total_cost"]].head(10).to_dict("records") if "part_name" in df.columns else []

report_ts = datetime.datetime.now().strftime("%d %b %Y  %H:%M")

# ══════════════════════════════════════════════════════════════════════════════
#  REPORT HEADER
# ══════════════════════════════════════════════════════════════════════════════
proj_name = meta.get("name", "—")
quote_num = meta.get("quote_number", "—")

st.markdown(f"""
<div style="border:1px solid #334; border-radius:10px; padding:28px 36px; margin-bottom:24px;
            background:#111820; font-family:Arial,sans-serif;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
    <div>
      <div style="font-size:1.8em; font-weight:700; color:#fff; letter-spacing:.5px;">
        📋 Cost Engineering Report
      </div>
      <div style="font-size:1.1em; color:#4da6ff; margin-top:4px;">{proj_name}</div>
      <div style="margin-top:10px;">
        <span style="background:{mat_colour}22; border:1px solid {mat_colour};
               border-radius:4px; padding:3px 12px; font-size:0.85em; color:{mat_colour};">
          {maturity}
        </span>
      </div>
    </div>
    <div style="text-align:right; color:#888; font-size:0.88em; line-height:1.9;">
      <div style="color:#ddd; font-size:1em;">Generated: {report_ts}</div>
      <div>BOM lines: {len(df)} &nbsp;|&nbsp; Materials: {df['material_id'].nunique()}</div>
      <div>Dry weight: {total_mass:,.0f} kg</div>
      {"<div style='color:#f0a500;'>Target: " + fmt(target_cost) + "</div>" if target_cost > 0 else ""}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 1 · Executive Summary")

e1, e2, e3, e4, e5 = st.columns(5)
e1.metric("Sell price",     fmt(total_sell))
e2.metric("Your cost",      fmt(total_base))
e3.metric("Margin",         fmt(total_marg), delta=f"{margin_pct:.1f}%")
e4.metric("€ per kg",       f"{eur_per_kg:,.0f}")
e5.metric("Dry weight",     f"{total_mass:,.0f} kg")

if target_cost > 0:
    gap = total_sell - target_cost
    t1, t2, t3, _ = st.columns([1,1,1,2])
    t1.metric("Budget target",  fmt(target_cost))
    t2.metric("Gap",            fmt(gap), delta=f"{gap/target_cost*100:+.1f}%", delta_color="inverse")
    t3.metric("vs budget",      f"{total_sell/target_cost*100:.1f}%",
              delta="over" if gap>0 else "under", delta_color="inverse" if gap>0 else "normal")

if risks:
    st.markdown(f"**{len(risks)} finding(s) require attention** — see Risk Register (Section 4) for step-by-step resolution.")
    for sev, title, detail, *_ in risks[:3]:
        st.warning(f"{sev} &nbsp; **{title}** — {detail}")
    if len(risks) > 3:
        st.caption(f"+ {len(risks)-3} more finding(s) in Section 4.")
else:
    st.success("✅ No significant risks identified.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — COST ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 2 · Cost Analysis")
st.caption("For: Cost Engineers · Management")

# Cost structure
cs1, cs2, cs3, cs4 = st.columns(4)
cs1.metric("Material share",  f"{mat_share:.0f}%")
cs2.metric("Process share",   f"{(total_mach+total_lab)/total_base*100:.0f}%" if total_base else "—")
cs3.metric("Overhead share",  f"{total_oh/total_base*100:.0f}%" if total_base else "—")
cs4.metric("Margin",          f"{margin_pct:.1f}%")

# Subsystem breakdown
st.subheader("Cost by subsystem")
ch_col, tbl_col = st.columns([3, 2])
with ch_col:
    chart_data = sub_agg.set_index("label")[["mat", "oh", "marg"]].rename(
        columns={"mat": "Material", "oh": "Overhead+Process", "marg": "Margin"}
    )
    if "machine_cost" in df.columns:
        extra = df.groupby("_sub")[["machine_cost","labour_cost"]].sum().reset_index()
        extra["label"] = extra["_sub"].map(lambda p: f"{WATERJET_SUBSYSTEMS.get(p,{}).get('icon','❓')} {WATERJET_SUBSYSTEMS.get(p,{}).get('name',p)}")
        m_data = extra.set_index("label")[["machine_cost","labour_cost"]].rename(
            columns={"machine_cost":"Machine","labour_cost":"Labour"})
        chart_data = sub_agg.set_index("label")[["mat","marg"]].rename(columns={"mat":"Material","marg":"Margin"})
        chart_data = chart_data.join(m_data, how="left")
    st.bar_chart(chart_data, color=["#2196F3","#FF9800","#F44336","#4CAF50"][:len(chart_data.columns)])

with tbl_col:
    sub_tbl = sub_agg[["label","sell","mass","epkg","share","lines"]].copy()
    sub_tbl.columns = ["Subsystem","Sell price","Mass kg","€/kg","Share %","Lines"]
    sub_tbl["Sell price"] = sub_tbl["Sell price"].map(lambda x: fmt(x))
    sub_tbl["Mass kg"]    = sub_tbl["Mass kg"].map(lambda x: f"{x:,.0f}")
    sub_tbl["€/kg"]       = sub_tbl["€/kg"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    sub_tbl["Share %"]    = sub_tbl["Share %"].map(lambda x: f"{x:.1f}%")
    st.dataframe(sub_tbl, use_container_width=True, hide_index=True)

# Top 10 most expensive lines
st.subheader("Top 10 cost drivers")
top10_cols = [c for c in ["line_id","part_name","material_id","material_cost","process_cost","overhead","margin","total_cost"] if c in df.columns]
top10 = df.nlargest(10, "total_cost")[top10_cols].copy()
for c in ["material_cost","process_cost","overhead","margin","total_cost"]:
    if c in top10.columns:
        top10[c] = top10[c].map(lambda x: fmt(x, 2))
st.dataframe(top10.rename(columns={
    "line_id":"Line","part_name":"Component","material_id":"Material",
    "material_cost":"Material €","process_cost":"Process €",
    "overhead":"Overhead €","margin":"Margin €","total_cost":"Sell €",
}), use_container_width=True, hide_index=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — PROCUREMENT STATUS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 3 · Procurement Status")
st.caption("For: Procurement · Supply Chain")

p1, p2, p3, p4, p5 = st.columns(5)
p1.metric("Suppliers",        n_suppliers if n_suppliers else "—")
p2.metric("Materials quoted",  f"{len(quoted_ids)} / {len(mats)}",
          delta=f"{len(quoted_ids)/len(mats)*100:.0f}%" if mats.shape[0] else "—",
          delta_color="off")
p3.metric("Expired quotes",   len(expired_list),
          delta="action needed" if expired_list else "all valid",
          delta_color="inverse" if expired_list else "off")
p4.metric("Not quoted",       len(unquoted),
          delta="gaps exist" if unquoted else "fully covered",
          delta_color="inverse" if unquoted else "off")
p5.metric("Max lead time",    f"{max_lt} days" if max_lt else "—")

# Quote status table
if not quotes.empty:
    best_q = best_quotes(quotes)
    q_status = best_q.copy()
    if "valid_until" in q_status.columns:
        q_status["valid_until"] = pd.to_datetime(q_status["valid_until"], errors="coerce")
        q_status["Status"] = q_status["valid_until"].apply(
            lambda d: ("🔴 Expired" if pd.notna(d) and d < today_q
                       else ("🟡 Expiring ≤30d" if pd.notna(d) and (d - today_q).days <= 30
                             else "🟢 Valid"))
        )
        q_status["Expires"] = q_status["valid_until"].dt.strftime("%d %b %Y")
    if "price_eur_per_kg" in q_status.columns:
        q_status["Price €/kg"] = q_status["price_eur_per_kg"].map(lambda x: fmt(x, 2))

    show_q = ["material_id"]
    if "supplier"      in q_status.columns: show_q.append("supplier")
    show_q.append("Price €/kg")
    if "Status"        in q_status.columns: show_q.append("Status")
    if "Expires"       in q_status.columns: show_q.append("Expires")
    if "lead_time_days" in q_status.columns: show_q.append("lead_time_days")

    with st.expander("Quote status — all materials", expanded=True):
        st.dataframe(
            q_status[[c for c in show_q if c in q_status.columns]].rename(columns={
                "material_id":"Material","supplier":"Supplier",
                "lead_time_days":"Lead time (d)",
            }),
            use_container_width=True, hide_index=True,
        )

# Supplier spend concentration
if "supplier" in quotes.columns:
    try:
        best_q_sup = best_quotes(quotes)
        spend_df   = df.merge(best_q_sup[["material_id","supplier"]], on="material_id", how="left")
        spend_by   = spend_df.groupby("supplier")["material_cost"].sum().sort_values(ascending=False)
        total_sp   = spend_by.sum()
        if total_sp > 0:
            st.subheader("Material spend by supplier")
            sp_tbl = pd.DataFrame({
                "Supplier": spend_by.index,
                "Spend":    spend_by.map(lambda x: fmt(x)).values,
                "Share %":  (spend_by / total_sp * 100).map(lambda x: f"{x:.1f}%").values,
                "Cumul. %": (spend_by / total_sp * 100).cumsum().map(lambda x: f"{x:.1f}%").values,
            })
            sc1, sc2 = st.columns([2, 1])
            sc1.bar_chart(spend_by.rename("Material spend (€)"), color="#2196F3")
            sc2.dataframe(sp_tbl, use_container_width=True, hide_index=True)
    except Exception:
        pass

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — RISK REGISTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 4 · Risk Register")
st.caption("For: Management · Quality · Cost Engineering")

if not risks:
    st.success("✅ No significant risks identified — data is complete and consistent.")
else:
    st.caption(f"{len(risks)} finding(s) detected. Each card below explains the issue, why it matters, and exactly how to resolve it.")
    for sev, title, detail, why, steps, pages in risks:
        sev_colour = {"🔴": "#f44336", "🟠": "#ff9800", "🟡": "#ffc107"}.get(sev[0], "#888")
        with st.container(border=True):
            h1, h2 = st.columns([6, 1])
            h1.markdown(
                f"<span style='color:{sev_colour}; font-weight:700; font-size:1.05em;'>{sev}</span>"
                f" &nbsp; <span style='font-weight:700; font-size:1.05em;'>{title}</span>",
                unsafe_allow_html=True,
            )
            h2.caption(detail)

            st.markdown(f"**Impact:** {why}")

            st.markdown("**How to resolve:**")
            for i, step in enumerate(steps, 1):
                st.markdown(f"{i}. {step}")

            if pages:
                link_cols = st.columns(len(pages))
                for col, (label, path) in zip(link_cols, pages):
                    col.page_link(path, label=label, use_container_width=True)

# BOM completeness
st.subheader("BOM completeness")
comp_pct = int(comp_score * 100)
comp_icon = "✅" if comp_pct == 100 else ("⚠️" if comp_pct >= 70 else "🚨")
st.progress(comp_score)
st.caption(f"{comp_icon} **{comp_pct}% complete** — "
           f"{len(WATERJET_SUBSYSTEMS) - len(missing_subs)} of {len(WATERJET_SUBSYSTEMS)} subsystems present.")

sub_status_rows = []
for prefix, info in WATERJET_SUBSYSTEMS.items():
    present = prefix in present_subs
    count   = present_subs.get(prefix, 0)
    sub_status_rows.append({
        "Subsystem":  f"{info['icon']} {info['name']}",
        "Critical":   "Yes" if info["critical"] else "—",
        "Status":     f"🟢 {count} lines" if present else "🔴 Missing",
        "Description": info["desc"],
    })
st.dataframe(pd.DataFrame(sub_status_rows), use_container_width=True, hide_index=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — FULL BOM SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("5 · Full BOM cost summary", expanded=False):
    st.caption("For: Cost Engineers — full line-level detail")
    bom_cols = {
        "line_id":"Line","part_name":"Component","material_id":"Material",
        "qty":"Qty","mass_kg":"kg","material_cost":"Mat €",
        "process_cost":"Process €","overhead":"OH €",
        "margin":"Margin €","total_cost":"Sell €",
    }
    bom_disp = df[[c for c in bom_cols if c in df.columns]].copy().rename(columns=bom_cols)
    for c in ["Mat €","Process €","OH €","Margin €","Sell €"]:
        if c in bom_disp.columns:
            bom_disp[c] = bom_disp[c].map(lambda x: fmt(x, 2))
    st.dataframe(bom_disp, use_container_width=True, hide_index=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  EXCEL EXPORT
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("⬇️ Download full report")

def _build_excel() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:

        # Sheet 1 — Executive Summary
        exec_rows = [
            ("Project",          proj_name),
            ("Report date",      report_ts),
            ("Estimate maturity",maturity),
            ("", ""),
            ("COST SUMMARY",     ""),
            ("Sell price",       round(total_sell, 2)),
            ("Your cost",        round(total_base, 2)),
            ("Margin €",         round(total_marg, 2)),
            ("Margin %",         f"{margin_pct:.1f}%"),
            ("€ per kg",         round(eur_per_kg, 0)),
            ("Dry weight (kg)",  round(total_mass, 0)),
            ("", ""),
            ("COST STRUCTURE",   ""),
            ("Material share %", f"{mat_share:.0f}%"),
            ("Process share %",  f"{(total_mach+total_lab)/total_base*100:.0f}%" if total_base else "—"),
            ("Overhead share %", f"{total_oh/total_base*100:.0f}%" if total_base else "—"),
        ]
        if target_cost > 0:
            exec_rows += [
                ("", ""),
                ("TARGET VS ACTUAL", ""),
                ("Budget target",    round(target_cost, 2)),
                ("Gap",              round(total_sell - target_cost, 2)),
                ("vs budget",        f"{total_sell/target_cost*100:.1f}%"),
            ]
        pd.DataFrame(exec_rows, columns=["Item","Value"]).to_excel(
            w, sheet_name="Executive Summary", index=False
        )

        # Sheet 2 — Subsystem Breakdown
        sub_export = sub_agg[["label","mat","oh","marg","sell","mass","epkg","share","lines"]].copy()
        sub_export.columns = ["Subsystem","Material €","Overhead €","Margin €",
                               "Sell price €","Mass kg","€/kg","Share %","Lines"]
        for c in ["Material €","Overhead €","Margin €","Sell price €"]:
            sub_export[c] = sub_export[c].round(2)
        sub_export["Share %"] = sub_export["Share %"].map(lambda x: f"{x:.1f}%")
        sub_export.to_excel(w, sheet_name="Subsystem Breakdown", index=False)

        # Sheet 3 — BOM Detail
        bom_exp_cols = [c for c in ["line_id","part_name","material_id","qty","mass_kg",
                                     "material_cost","process_cost","overhead","margin","total_cost"]
                        if c in df.columns]
        df[bom_exp_cols].round(2).to_excel(w, sheet_name="BOM Detail", index=False)

        # Sheet 4 — Procurement
        if not quotes.empty:
            best_q_exp = best_quotes(quotes)
            if "valid_until" in best_q_exp.columns:
                best_q_exp["valid_until"] = pd.to_datetime(
                    best_q_exp["valid_until"], errors="coerce"
                ).dt.strftime("%d %b %Y")
            best_q_exp.to_excel(w, sheet_name="Procurement", index=False)

        # Sheet 5 — Risk Register
        if risks:
            pd.DataFrame(
                [(sev, title, detail, why, "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)))
                 for sev, title, detail, why, steps, _ in risks],
                columns=["Severity", "Finding", "Detail", "Impact", "Resolution steps"],
            ).to_excel(w, sheet_name="Risk Register", index=False)

        # Sheet 6 — BOM Completeness
        pd.DataFrame(sub_status_rows).to_excel(w, sheet_name="BOM Completeness", index=False)

    return buf.getvalue()

filename = f"cost_report_{proj_name.replace(' ','_') or 'project'}_{today.strftime('%Y%m%d')}.xlsx"

st.download_button(
    "⬇️ Download stakeholder report (Excel — 6 sheets)",
    data=_build_excel(),
    file_name=filename,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
    help="Sheets: Executive Summary · Subsystem Breakdown · BOM Detail · Procurement · Risk Register · BOM Completeness",
)
