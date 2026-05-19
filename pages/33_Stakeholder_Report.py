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

# ── Additional pre-computations for live status in risk cards ─────────────────
from utils.validators import all_rules_ok, business_rules, check_missing, check_positive, material_lines

_m_miss    = check_missing(mats,  ["material_id", "price_eur_per_kg"])
_m_pos     = check_positive(mats, ["price_eur_per_kg"])
_p_miss    = check_missing(procs, ["process_id", "machine_rate_eur_h", "labor_rate_eur_h",
                                    "overhead_pct", "margin_pct"])
_p_pos     = check_positive(procs, ["machine_rate_eur_h", "labor_rate_eur_h"])
_b_miss    = check_missing(bom,   ["line_id", "material_id", "qty", "mass_kg",
                                    "process_route", "runtime_h"])
_b_pos     = check_positive(material_lines(bom), ["qty", "mass_kg"])
_b_no_rt   = (bom[~bom["process_route"].isin(procs["process_id"])]["line_id"].tolist()
              if "process_route" in bom.columns and "process_id" in procs.columns else [])
_b_no_mat  = (bom[~bom["material_id"].isin(mats["material_id"])]["line_id"].tolist()
              if "material_id" in bom.columns else [])
_q_exp_ids = (quotes[pd.to_datetime(quotes["valid_until"], errors="coerce") < today_q
                     ]["material_id"].unique().tolist()
              if "valid_until" in quotes.columns and not quotes.empty else [])
_rules     = business_rules(mats, procs, bom)
_rules_ok  = all_rules_ok(_rules)
_dq_checks = [not _m_miss, not _m_pos, not _p_miss, not _p_pos,
               not _b_miss, not _b_pos, not _b_no_rt, not _b_no_mat,
               not _q_exp_ids, _rules_ok]
dq_score   = sum(_dq_checks)   # out of 10
dq_total   = len(_dq_checks)

zero_runtime = int(
    (pd.to_numeric(bom["runtime_h"], errors="coerce").fillna(0) == 0).sum()
) if "runtime_h" in bom.columns else len(bom)

cov_pct = len(quoted_ids) / len(mats) * 100 if len(mats) else 0

_oh_val   = procs["overhead_pct"].iloc[0] * 100  if (not procs.empty and "overhead_pct"  in procs.columns) else None
_marg_val = procs["margin_pct"].iloc[0]   * 100  if (not procs.empty and "margin_pct"     in procs.columns) else None
oh_display   = f"{_oh_val:.0f}%"   if _oh_val   is not None else "not set"
marg_display = f"{_marg_val:.0f}%" if _marg_val is not None else "not set"

# ── Risk findings ──────────────────────────────────────────────────────────────
# Each risk: dict with keys sev, title, detail, impact, steps
# Each step: dict with keys action, look, status, ok (True/False/None), page, btn
risks = []

if expired_list:
    risks.append(dict(
        sev="🔴 High", title="Expired supplier quotes",
        detail=f"{len(expired_list)} material(s): {', '.join(expired_list[:5])}{'…' if len(expired_list)>5 else ''}",
        impact="Costs are calculated using stale prices — the sell price may not be achievable with current suppliers.",
        steps=[
            dict(action="See which quotes have expired",
                 look="Supplier Quotes → Quote status tab → look for 🔴 Expired rows",
                 status=f"{len(expired_list)} expired", ok=False,
                 page="pages/07_Supplier_Quotes.py", btn="Open Supplier Quotes →"),
            dict(action="Contact each supplier and request a new price + validity date",
                 look="Use the material names listed in the Detail above",
                 status=None, ok=None, page=None, btn=None),
            dict(action="Enter the new quote price and valid-until date",
                 look="CSV Import → paste supplier name, material_id, price_eur_per_kg, valid_until",
                 status=None, ok=None,
                 page="pages/99_Update_from_Public_CSV.py", btn="Open CSV Import →"),
            dict(action="Verify: all quotes must show 🟢 Valid",
                 look="Supplier Quotes → Quote status tab → Expired count must be 0",
                 status=f"{len(expired_list)} still expired", ok=False,
                 page="pages/07_Supplier_Quotes.py", btn="Re-check here →"),
        ],
    ))

if crit_missing:
    prefix_list = ", ".join(f"`{p}`" for p, _ in crit_missing)
    risks.append(dict(
        sev="🔴 High", title="Critical subsystems missing from BOM",
        detail=", ".join(i["name"] for _, i in crit_missing),
        impact="Total sell price is understated — critical assemblies are not included in the cost calculation.",
        steps=[
            dict(action="Check which subsystems are missing",
                 look="BOM Completeness grid at the bottom of this page — 🔴 Missing rows are the gaps",
                 status=f"{len(crit_missing)} critical missing", ok=False,
                 page=None, btn=None),
            dict(action=f"Add missing lines to your BOM source file",
                 look=f"Line IDs must start with the correct prefix: {prefix_list}. "
                      f"Check ERP / Excel BOM export — each subsystem needs at least one line.",
                 status=None, ok=None, page=None, btn=None),
            dict(action="Re-upload the complete BOM",
                 look="BOM Import → drag & drop the updated file → click Import",
                 status=None, ok=None,
                 page="pages/15_Bom_Import.py", btn="Open BOM Import →"),
            dict(action="Confirm all critical subsystems show 🟢",
                 look="Scroll down to BOM Completeness grid — every Critical = Yes row must show 🟢",
                 status=f"{len(crit_missing)} still missing", ok=False,
                 page=None, btn=None),
        ],
    ))

if len(unquoted) > 0:
    risks.append(dict(
        sev="🟠 Medium", title="Materials without a valid supplier quote",
        detail=f"{len(unquoted)} of {len(mats)} materials ({100-cov_pct:.0f}% gap)",
        impact="Those materials use the base catalogue price, not a confirmed supplier price — cost accuracy is reduced.",
        steps=[
            dict(action="See exactly which materials have no quote",
                 look="Supplier Quotes → Coverage Gaps tab → all 🔴 No quote rows",
                 status=f"{len(unquoted)} unquoted", ok=False,
                 page="pages/07_Supplier_Quotes.py", btn="Open Coverage Gaps →"),
            dict(action="Request quotes from suppliers for each unquoted material",
                 look="Use material IDs from the Coverage Gaps table as reference",
                 status=None, ok=None, page=None, btn=None),
            dict(action="Enter confirmed quotes",
                 look="CSV Import → columns: material_id, supplier, price_eur_per_kg, valid_until",
                 status=None, ok=None,
                 page="pages/99_Update_from_Public_CSV.py", btn="Open CSV Import →"),
            dict(action="Verify coverage is ≥ 80%",
                 look="Material Library → Quote coverage tab → coverage metric at top",
                 status=f"Currently {cov_pct:.0f}% — need ≥ 80%", ok=cov_pct >= 80,
                 page="pages/04_Materiaalbronnen.py", btn="Check coverage →"),
        ],
    ))

if mat_share > 75:
    risks.append(dict(
        sev="🟠 Medium", title="High material cost exposure",
        detail=f"Material is {mat_share:.0f}% of cost base — threshold is 75%",
        impact="A 5% commodity price increase directly erodes margin. No process buffer exists to absorb it.",
        steps=[
            dict(action="Identify the top 3 highest-spend materials",
                 look="Supplier Quotes → Spend & Concentration tab → bar chart and table sorted by spend",
                 status=f"{mat_share:.0f}% material share", ok=False,
                 page="pages/07_Supplier_Quotes.py", btn="Open Spend analysis →"),
            dict(action="Model the margin impact of a price increase",
                 look="Scenario Planner → move commodity sliders to +5% and +10% → check margin column",
                 status=None, ok=None,
                 page="pages/06_Scenario_Planner.py", btn="Open Scenario Planner →"),
            dict(action="Negotiate fixed-price or escalation-clause contracts",
                 look="Target the top 3 materials by spend — agree price-lock period with suppliers",
                 status=None, ok=None, page=None, btn=None),
        ],
    ))

if margin_pct < 10:
    risks.append(dict(
        sev="🔴 High", title="Overall margin below minimum threshold",
        detail=f"Margin is {margin_pct:.1f}% — minimum recommended 10%",
        impact="Any cost overrun (rework, delays, material price rise) will result in a commercial loss.",
        steps=[
            dict(action="Find the lowest-margin lines",
                 look="Line Cost Detail → sort by Margin % column ascending → focus on top 5 lowest",
                 status=f"Overall margin: {margin_pct:.1f}%", ok=False,
                 page="pages/28_Line_Cost_Detail.py", btn="Open Line Cost Detail →"),
            dict(action="Check overhead % and margin % are set correctly",
                 look="Presets → verify overhead_pct and margin_pct match the approved project rates",
                 status=f"OH: {oh_display} | Margin: {marg_display}", ok=None,
                 page="pages/03_Presets.py", btn="Open Presets →"),
            dict(action="Check whether process times can be reduced",
                 look="Routing Costs → look for lines with high runtime_h — confirm with manufacturing",
                 status=None, ok=None,
                 page="pages/16_Routing_Kosten.py", btn="Open Routing Costs →"),
            dict(action="Review sell price with commercial team",
                 look="Quote Sheet → Internal tab → margin KPI — adjust if sell price needs to increase",
                 status=None, ok=None,
                 page="pages/29_Quote_Sheet.py", btn="Open Quote Sheet →"),
        ],
    ))

if maturity in ("RoM (±30%)", "Budget (±15%)"):
    _next = "Budget (±15%)" if maturity == "RoM (±30%)" else "Definitive (±5%)"
    _maturity_steps = {
        "RoM (±30%)": [
            dict(action="No critical subsystems missing from BOM",
                 look="BOM Completeness grid below — every Critical = Yes row must show 🟢",
                 status=f"{len(crit_missing)} critical missing" if crit_missing else "✅ all present",
                 ok=not crit_missing,
                 page=None, btn=None),
            dict(action="All material prices are non-zero",
                 look="Data Quality → Materials tab → 'Zero / negative prices' metric must be 0",
                 status=f"{len(_m_pos)} columns with bad prices" if _m_pos else "✅ all positive",
                 ok=not _m_pos,
                 page="pages/05_Data_Quality.py", btn="Open Data Quality →"),
            dict(action="All BOM lines have a process route assigned",
                 look="Data Quality → BOM tab → 'Unmatched process routes' must be 0",
                 status=f"{len(_b_no_rt)} unmatched" if _b_no_rt else "✅ all matched",
                 ok=not _b_no_rt,
                 page="pages/05_Data_Quality.py", btn="Open Data Quality →"),
            dict(action="All BOM lines have a mass_kg value > 0",
                 look="Data Quality → BOM tab → 'Zero or negative qty/mass' must be 0",
                 status=f"issues found" if _b_pos else "✅ all positive",
                 ok=not _b_pos,
                 page="pages/05_Data_Quality.py", btn="Open Data Quality →"),
            dict(action=f"Change estimate maturity to {_next}",
                 look="Home dashboard → sidebar → 'Estimate maturity' dropdown — only after all above are ✅",
                 status=f"Currently: {maturity}", ok=False,
                 page=None, btn=None),
        ],
        "Budget (±15%)": [
            dict(action="Data Quality score ≥ 8/10",
                 look="Data Quality → header shows 'X/10 checks passed' — must be 8 or higher",
                 status=f"Currently {dq_score}/{dq_total} — {'✅ ok' if dq_score >= 8 else 'need ' + str(8 - dq_score) + ' more'}",
                 ok=dq_score >= 8,
                 page="pages/05_Data_Quality.py", btn="Open Data Quality →"),
            dict(action="Quote coverage ≥ 80%",
                 look="Supplier Quotes → Coverage Gaps tab → coverage metric at top must show ≥ 80%",
                 status=f"Currently {cov_pct:.0f}% — {'✅ ok' if cov_pct >= 80 else f'need {80 - cov_pct:.0f}% more'}",
                 ok=cov_pct >= 80,
                 page="pages/07_Supplier_Quotes.py", btn="Open Supplier Quotes →"),
            dict(action="No expired quotes",
                 look="Supplier Quotes → Quote status tab → Expired count must be 0",
                 status=f"{len(expired_list)} expired — renew with suppliers" if expired_list else "✅ none expired",
                 ok=not expired_list,
                 page="pages/07_Supplier_Quotes.py", btn="Open Supplier Quotes →"),
            dict(action="Process runtime hours are not zero",
                 look="Routing Costs → runtime_h column — a value of 0 means the line was not costed for process time",
                 status=f"{zero_runtime} lines with 0 h — check with manufacturing" if zero_runtime else "✅ all non-zero",
                 ok=zero_runtime == 0,
                 page="pages/16_Routing_Kosten.py", btn="Open Routing Costs →"),
            dict(action="Overhead % and margin % are management-approved values",
                 look="Presets → overhead_pct and margin_pct columns — confirm these match the project approval",
                 status=f"OH: {oh_display} | Margin: {marg_display} — verify these are correct",
                 ok=None,
                 page="pages/03_Presets.py", btn="Open Presets →"),
            dict(action="Classification surcharges set (if applicable)",
                 look="Quote Sheet → Production section → Classification society dropdown and surcharge %",
                 status=None, ok=None,
                 page="pages/29_Quote_Sheet.py", btn="Open Quote Sheet →"),
            dict(action=f"Change estimate maturity to {_next}",
                 look="Home dashboard → sidebar → 'Estimate maturity' dropdown — only after all above are ✅",
                 status=f"Currently: {maturity}", ok=False,
                 page=None, btn=None),
        ],
    }
    risks.append(dict(
        sev="🟡 Low", title="Estimate maturity is not firm",
        detail=f"Current: {maturity} → next level: {_next}",
        impact=f"At {maturity} the sell price can vary by the stated tolerance. "
               f"Do not issue as a firm commercial quotation until the checklist below is complete.",
        steps=_maturity_steps[maturity],
    ))

if target_cost > 0 and total_sell > target_cost * 1.05:
    gap_pct = (total_sell - target_cost) / target_cost * 100
    top_sub = sub_agg.sort_values("sell", ascending=False).iloc[0]["label"] if not sub_agg.empty else "—"
    risks.append(dict(
        sev="🟠 Medium", title="Sell price exceeds budget target",
        detail=f"{fmt(total_sell)} vs target {fmt(target_cost)} (+{gap_pct:.1f}%)",
        impact="Commercial target not met — risk of losing the contract or absorbing an unacceptable margin reduction.",
        steps=[
            dict(action="Identify which subsystem drives the overrun",
                 look="Section 2 above — Subsystem table sorted by Sell price; largest subsystem is the primary target",
                 status=f"Largest: {top_sub}", ok=None,
                 page=None, btn=None),
            dict(action="Model commodity savings needed to close the gap",
                 look="Scenario Planner → move sliders for the highest-spend commodities — watch gap-to-target metric",
                 status=f"Gap: {fmt(total_sell - target_cost)} ({gap_pct:.1f}%)", ok=False,
                 page="pages/06_Scenario_Planner.py", btn="Open Scenario Planner →"),
            dict(action="Check whether process times can be reduced",
                 look="Routing Costs → runtime_h column — identify lines with long cycle times and verify with manufacturing",
                 status=None, ok=None,
                 page="pages/16_Routing_Kosten.py", btn="Open Routing Costs →"),
            dict(action="Verify overhead % and margin % are correct for this project",
                 look="Presets → confirm rates reflect the actual project approval, not generic defaults",
                 status=f"OH: {oh_display} | Margin: {marg_display}", ok=None,
                 page="pages/03_Presets.py", btn="Open Presets →"),
        ],
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
    for r in risks[:3]:
        st.warning(f"{r['sev']} &nbsp; **{r['title']}** — {r['detail']}")
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
st.page_link("pages/34_Action_Centre.py",
             label="🔧 Open Action Centre — fix all issues in one place →",
             use_container_width=False)

if not risks:
    st.success("✅ No significant risks identified — data is complete and consistent.")
else:
    st.caption(f"{len(risks)} finding(s). Each card shows current status per step and a button to open the exact page.")
    for risk in risks:
        sev = risk["sev"]
        sev_colour = {"🔴": "#f44336", "🟠": "#ff9800", "🟡": "#ffc107"}.get(sev[0], "#888")
        with st.container(border=True):
            # ── Header ───────────────────────────────────────────────────────
            h1, h2 = st.columns([5, 2])
            h1.markdown(
                f"<span style='color:{sev_colour}; font-weight:700; font-size:1.05em;'>{sev}</span>"
                f" &nbsp; <span style='font-weight:700; font-size:1.05em;'>{risk['title']}</span>",
                unsafe_allow_html=True,
            )
            h2.caption(risk["detail"])
            st.caption(f"**Why it matters:** {risk['impact']}")
            st.markdown("---")

            # ── Steps ─────────────────────────────────────────────────────────
            for i, step in enumerate(risk["steps"], 1):
                ok = step.get("ok")
                status_txt = step.get("status") or ""
                ok_icon = "✅" if ok is True else ("❌" if ok is False else "·")
                ok_color = "#4CAF50" if ok is True else ("#f44336" if ok is False else "#aaa")

                col_n, col_act, col_status, col_btn = st.columns([0.25, 4.5, 2.25, 1.75])
                col_n.markdown(f"**{i}**")
                col_act.markdown(
                    f"<span style='font-weight:600'>{step['action']}</span><br>"
                    f"<span style='color:#aaa; font-size:0.88em'>📍 {step['look']}</span>",
                    unsafe_allow_html=True,
                )
                if status_txt:
                    col_status.markdown(
                        f"<span style='color:{ok_color}; font-weight:600; font-size:0.9em'>"
                        f"{ok_icon} {status_txt}</span>",
                        unsafe_allow_html=True,
                    )
                if step.get("page"):
                    col_btn.page_link(step["page"], label=step["btn"], use_container_width=True)

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
            pd.DataFrame([{
                "Severity": r["sev"],
                "Finding":  r["title"],
                "Detail":   r["detail"],
                "Impact":   r["impact"],
                "Resolution steps": "\n".join(
                    f"{i+1}. {s['action']} — {s['look']}"
                    for i, s in enumerate(r["steps"])
                ),
            } for r in risks]).to_excel(w, sheet_name="Risk Register", index=False)

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
