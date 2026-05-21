from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.style import inject_css

st.set_page_config(page_title="Cost Forge 2", layout="wide", page_icon="🛠️")
inject_css()

# ── All pages (unique keys) ────────────────────────────────────────────────────
_P = {
    # Prepare
    "bom":          st.Page("pages/15_Bom_Import.py",            title="BOM Import",           icon="📥"),
    "mats":         st.Page("pages/04_Materiaalbronnen.py",       title="Materials",            icon="🧱"),
    "quotemgmt":    st.Page("pages/49_Quote_Management.py",       title="Quote Management",     icon="🛒"),
    "quotes":       st.Page("pages/07_Supplier_Quotes.py",        title="Supplier Intelligence",icon="🏭"),
    "presets":      st.Page("pages/03_Presets.py",                title="Presets",              icon="⚙️"),
    "csv":          st.Page("pages/99_Update_from_Public_CSV.py", title="CSV Import",           icon="🔗"),
    # Calculate
    "quick":        st.Page("pages/01_Quick_Cost.py",             title="Quick Cost",           icon="⚡"),
    "calc":         st.Page("pages/01_Calculatie.py",             title="Calculation",          icon="💸"),
    "routing":      st.Page("pages/16_Routing_Kosten.py",         title="Routing Costs",        icon="🛠️"),
    "itemcost":     st.Page("pages/32_Item_Costing.py",           title="Item Costing",         icon="🔢"),
    "borescale":    st.Page("pages/30_Bore_Scale.py",             title="Size Scale",           icon="📐"),
    # Analyse
    "mgmt":         st.Page("pages/27_Management_Dashboard.py",   title="Management Dashboard", icon="📊"),
    "scenario":     st.Page("pages/06_Scenario_Planner.py",       title="Scenario Planner",     icon="🧭"),
    "linedet":      st.Page("pages/28_Line_Cost_Detail.py",       title="Line Cost Detail",     icon="🔍"),
    "prepost":      st.Page("pages/31_Pre_Post.py",               title="Pre / Post",           icon="📊"),
    "quality":      st.Page("pages/05_Data_Quality.py",           title="Data Quality",         icon="✅"),
    "volume":       st.Page("pages/37_Volume_Analysis.py",        title="Volume Analysis",      icon="📈"),
    # Quote & export
    "quotesheet":   st.Page("pages/29_Quote_Sheet.py",            title="Quote Sheet",          icon="🧾"),
    "rapport":      st.Page("pages/12_Rapport.py",                title="Report",               icon="📑"),
    "export":       st.Page("pages/17_Offerte_Export.py",         title="Quote Export",         icon="📦"),
    "docx":         st.Page("pages/18_Offerte_DOCX.py",           title="Quote DOCX",           icon="📝"),
    "pdf":          st.Page("pages/19_Offerte_PDF.py",            title="Quote PDF",            icon="🖨️"),
    "download":     st.Page("pages/20_Download_Center.py",        title="Download Centre",      icon="⬇️"),
    "stakeholder_pkg": st.Page("pages/48_Stakeholder_Package.py", title="Stakeholder Package",  icon="📦"),
    # Cost engineering
    "waterfall":    st.Page("pages/39_Full_Cost_Summary.py",      title="Full Cost Summary",    icon="🌊"),
    "transport":    st.Page("pages/35_Transport_Logistics.py",    title="Transport & Logistics",icon="🚢"),
    "nre":          st.Page("pages/36_Engineering_NRE.py",        title="Engineering & NRE",    icon="🔬"),
    "escalation":   st.Page("pages/38_Escalation_Risk.py",        title="Escalation & Risk",    icon="📉"),
    # Contract & lifecycle
    "contract":     st.Page("pages/40_Contract_Cashflow.py",      title="Contract & Cash Flow", icon="💰"),
    "changeorders": st.Page("pages/41_Change_Orders.py",          title="Change Orders",        icon="🔄"),
    "closeout":     st.Page("pages/42_Project_Closeout.py",       title="Project Close-out",    icon="📁"),
    "spareparts":   st.Page("pages/43_Spare_Parts.py",            title="Spare Parts",          icon="🔩"),
    "revisions":    st.Page("pages/44_Quote_Revisions.py",        title="Quote Revisions",      icon="📜"),
    # Compliance & sustainability
    "india_lc":     st.Page("pages/46_India_Local_Content.py",    title="India Local Content",  icon="🇮🇳"),
    "carbon":       st.Page("pages/47_Carbon_Energy.py",          title="Carbon & Energy",      icon="🌱"),
    # Market intelligence
    "market":       st.Page("pages/13_Marktdata.py",              title="Market Data",          icon="📊"),
    "history":      st.Page("pages/22_Materiaal_Historie.py",     title="Material History",     icon="📉"),
    "anomalie":     st.Page("pages/26_anomalie_overview.py",      title="Anomalies",            icon="🚨"),
    "setup":        st.Page("pages/24_market_setup.py",           title="Market Setup",         icon="🧩"),
    # System / tools
    "actions":      st.Page("pages/34_Action_Centre.py",          title="Action Centre",        icon="🔧"),
    "cockpit":      st.Page("pages/45_Command_Centre.py",         title="Command Centre",       icon="🎯"),
    "stakeholder_rpt": st.Page("pages/33_Stakeholder_Report.py", title="Stakeholder Report",   icon="📋"),
    "restore":      st.Page("pages/25_Restore_Hulp.py",           title="Restore",              icon="♻️"),
    "debug":        st.Page("pages/00_Debug.py",                  title="Debug",                icon="🐛"),
    "diagnose":     st.Page("pages/0_Diagnose.py",                title="Diagnose",             icon="🔍"),
}

MATURITY_OPTIONS = {
    "RoM (±30%)":        ("🟡", "Rough Order of Magnitude"),
    "Budget (±15%)":     ("🟠", "Budget estimate"),
    "Definitive (±5%)":  ("🔵", "Definitive estimate"),
    "Firm":              ("🟢", "Firm price"),
}


# ── Cached loaders ────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _kpis() -> dict | None:
    try:
        from utils.completeness import WATERJET_SUBSYSTEMS
        from utils.io import WORKBOOK, load_bom, load_materials, load_processes, load_quotes
        from utils.pricing import compute_costs
        from utils.quotes import apply_best_quotes, expired_quote_materials

        mats   = load_materials()
        quotes = load_quotes()
        bom    = load_bom()
        procs  = load_processes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)

        qty_s      = pd.to_numeric(bom["qty"], errors="coerce").fillna(1)
        total_mass = (qty_s * bom["mass_kg"].fillna(0)).sum()
        total_sell = df["total_cost"].sum()
        mat_cost   = df["material_cost"].sum()
        proc_cost  = df["process_cost"].sum()
        moq_cost   = df["moq_excess_cost"].sum() if "moq_excess_cost" in df.columns else 0.0
        pattern_cost = df["pattern_cost"].sum() if "pattern_cost" in df.columns else 0.0
        overhead   = df["overhead"].sum()
        margin     = df["margin"].sum()
        base_cost  = df["base_cost"].sum()

        expired     = expired_quote_materials(quotes)
        total_mats  = len(mats)
        quoted_mats = quotes["material_id"].nunique() if not quotes.empty else 0
        wb_mtime    = WORKBOOK.stat().st_mtime if WORKBOOK.exists() else None

        df["_sub"] = df["line_id"].apply(
            lambda lid: next(
                (p for p in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True)
                 if str(lid).upper().startswith(p)), "_other"
            )
        )
        sub_costs = (
            df.groupby("_sub")["total_cost"].sum()
            .rename(index=lambda p: (
                f"{WATERJET_SUBSYSTEMS[p]['icon']} {WATERJET_SUBSYSTEMS[p]['name']}"
                if p in WATERJET_SUBSYSTEMS else "❓ Other"
            ))
            .sort_values(ascending=False)
        )

        return {
            "total": total_sell, "mat": mat_cost, "proc": proc_cost,
            "moq": moq_cost, "pattern": pattern_cost,
            "overhead": overhead, "margin": margin, "base_cost": base_cost,
            "margin_pct": margin / base_cost if base_cost else 0,
            "mat_share": mat_cost / base_cost if base_cost else 0,
            "eur_per_kg": total_sell / total_mass if total_mass else 0,
            "mass_kg": total_mass, "lines": len(df),
            "materials": df["material_id"].nunique(),
            "expired": expired, "total_mats": total_mats, "quoted_mats": quoted_mats,
            "wb_mtime": wb_mtime, "sub_costs": sub_costs,
        }
    except Exception:
        return None


@st.cache_data(ttl=30)
def _completeness() -> dict | None:
    try:
        from utils.completeness import completeness_score, detect_subsystems, missing_subsystems
        from utils.io import load_bom
        bom = load_bom()
        return {
            "score": completeness_score(bom),
            "present": detect_subsystems(bom),
            "missing": missing_subsystems(bom),
        }
    except Exception:
        return None


# ── Card helper ───────────────────────────────────────────────────────────────
def _card(page, icon: str, title: str, caption: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(caption)
        st.page_link(page, label="Open →", use_container_width=True)


# ── Home dashboard ────────────────────────────────────────────────────────────
def dashboard() -> None:
    from utils.currency import currency_selector
    from utils.project import load_project_meta, save_project_meta
    from utils.style import page_header

    # ── Sidebar: project settings ─────────────────────────────────────────────
    currency_selector()
    meta = load_project_meta()

    st.sidebar.divider()
    st.sidebar.subheader("Estimate settings")

    maturity_default = meta.get("maturity", "Budget (±15%)")
    maturity_idx = list(MATURITY_OPTIONS).index(maturity_default) \
                   if maturity_default in MATURITY_OPTIONS else 1
    maturity = st.sidebar.selectbox(
        "Estimate maturity", list(MATURITY_OPTIONS.keys()), index=maturity_idx,
    )
    target_cost = st.sidebar.number_input(
        "Budget / target cost (€)",
        min_value=0.0, value=float(meta.get("target_cost", 0.0)),
        step=10_000.0, format="%.0f",
    )
    if maturity != meta.get("maturity") or target_cost != meta.get("target_cost", 0.0):
        save_project_meta(maturity=maturity, target_cost=target_cost)

    # ── Header ────────────────────────────────────────────────────────────────
    badge_icon, badge_tip = MATURITY_OPTIONS[maturity]
    page_header(
        title="Cost Forge 2",
        icon="🛠️",
        caption="Marine waterjet cost engineering platform",
        project=meta.get("name", ""),
        maturity=maturity,
        right_html=f"<b>{badge_icon} {maturity}</b><br><small>{badge_tip}</small>",
    )

    col_refresh, _ = st.columns([1, 8])
    if col_refresh.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

    # ── KPI block ─────────────────────────────────────────────────────────────
    kpi = _kpis()
    if kpi:
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        k1.metric("Sell price",     fmt(kpi["total"]))
        k2.metric("Base cost",      fmt(kpi["base_cost"]))
        k3.metric("Process",        fmt(kpi["proc"]))
        k4.metric("Material",       fmt(kpi["mat"]))
        k5.metric("MOQ excess",     fmt(kpi["moq"]))
        k6.metric("Margin",         fmt(kpi["margin"]),
                  delta=f"{kpi['margin_pct']*100:.1f}%")
        k7.metric("€ / kg",         f"{kpi['eur_per_kg']:,.0f}",
                  delta=f"{kpi['mass_kg']:,.0f} kg", delta_color="off")

        # Coverage / alerts row
        exp_count  = len(kpi["expired"])
        quote_cov  = kpi["quoted_mats"] / kpi["total_mats"] * 100 if kpi["total_mats"] else 0

        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("BOM lines",       kpi["lines"])
        r2.metric("Unique materials", kpi["materials"])
        r3.metric("Quote coverage",  f"{kpi['quoted_mats']}/{kpi['total_mats']}",
                  delta=f"{quote_cov:.0f}%", delta_color="off")
        r4.metric("Expired quotes",  exp_count,
                  delta="⚠️ renew" if exp_count else "✅ ok",
                  delta_color="inverse" if exp_count else "off")
        if kpi["wb_mtime"]:
            age_s = time.time() - kpi["wb_mtime"]
            age_str = (f"{int(age_s/60)} min ago" if age_s < 3600
                       else f"{int(age_s/3600)}h ago" if age_s < 86400
                       else f"{int(age_s/86400)}d ago")
            r5.metric("Data updated", age_str)

        if target_cost > 0:
            gap = kpi["total"] - target_cost
            t1, t2, t3, _ = st.columns([1, 1, 1, 4])
            t1.metric("Target",         fmt(target_cost))
            t2.metric("Gap to target",  fmt(gap),
                      delta=f"{gap/target_cost*100:+.1f}%",
                      delta_color="inverse")
            t3.metric("Cost vs budget", f"{kpi['total']/target_cost*100:.1f}%")

        # Alerts
        alerts = []
        if exp_count:
            alerts.append(f"⚠️ **{exp_count} expired quote(s):** "
                          f"{', '.join(kpi['expired'][:4])}{'…' if exp_count > 4 else ''}")
        if quote_cov < 80:
            alerts.append(f"⚠️ **Quote coverage {quote_cov:.0f}%** — "
                          f"{kpi['total_mats'] - kpi['quoted_mats']} material(s) unquoted.")
        if maturity in ("RoM (±30%)", "Budget (±15%)"):
            alerts.append(f"ℹ️ Maturity **{maturity}** — confirm figures before issuing a firm quotation.")
        for a in alerts:
            st.warning(a)

    else:
        st.info("No BOM loaded yet — open **BOM Import** from the sidebar to get started.")

    st.divider()

    # ── Two-column layout: subsystem chart + completeness ────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        if kpi:
            st.subheader("Subsystem cost split")
            chart_df = pd.DataFrame({"Sell price (€)": kpi["sub_costs"]})
            st.bar_chart(chart_df, color="#2196F3")

    with col_right:
        comp = _completeness()
        if comp:
            from utils.completeness import WATERJET_SUBSYSTEMS
            score   = comp["score"]
            missing = comp["missing"]
            pct     = int(score * 100)
            crit    = [(p, i) for p, i in missing if i["critical"]]
            label   = f"{'✅' if pct == 100 else '⚠️'} BOM — {pct}%"

            with st.expander(label, expanded=bool(crit)):
                st.progress(score)
                cols2 = st.columns(4)
                for i, (prefix, info) in enumerate(WATERJET_SUBSYSTEMS.items()):
                    present = prefix in comp["present"]
                    count   = comp["present"].get(prefix, 0)
                    badge   = f"`{count}`" if present else "❌"
                    cols2[i % 4].markdown(f"{info['icon']} **{info['name']}** {badge}")
                if crit:
                    st.warning("Critical missing: " +
                               ", ".join(f"{i['icon']} {i['name']}" for _, i in crit))
                    st.page_link(_P["bom"], label="→ BOM Import")

        if kpi:
            st.subheader("Cost structure")
            cost_items = [
                ("Material",   kpi["mat"]),
                ("MOQ excess", kpi["moq"]),
                ("Process",    kpi["proc"]),
                ("Overhead",   kpi["overhead"]),
                ("Margin",     kpi["margin"]),
            ]
            for label, val in cost_items:
                share = val / kpi["base_cost"] * 100 if kpi.get("base_cost") else 0
                st.markdown(
                    f"**{label}** &ensp; {fmt(val)} &ensp; "
                    f"<small style='color:#888'>{share:.1f}%</small>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Workflow quick-launch ─────────────────────────────────────────────────
    st.subheader("Workflow")

    with st.expander("1️⃣ Prepare — BOM, materials, quotes", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["bom"],      "📥", "BOM Import",
                  "Upload or paste a BOM — costs calculate immediately.")
        with c2:
            _card(_P["mats"],     "🧱", "Materials",
                  "Review materials and best supplier prices.")
        with c3:
            _card(_P["quotemgmt"],"🛒", "Quote Management",
                  "Add/edit quotes · buy items · casting patterns · validity.")
        with c4:
            _card(_P["presets"],  "⚙️", "Presets",
                  "Set overhead %, margin % and labour rates.")

    with st.expander("2️⃣ Calculate — cost engine & sizing"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["quick"],    "⚡", "Quick Cost",
                  "Instant cost summary with best quotes applied.")
        with c2:
            _card(_P["calc"],     "💸", "Calculation",
                  "Detailed breakdown per BOM line.")
        with c3:
            _card(_P["routing"],  "🛠️", "Routing Costs",
                  "Process time and cost via routing data.")
        with c4:
            _card(_P["borescale"],"📐", "Size Scale",
                  "Scale cost to any waterjet bore MWJ-410 → MWJ-2120.")

    with st.expander("3️⃣ Analyse — drivers, scenarios, quality"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["mgmt"],     "📊", "Management Dashboard",
                  "Cost by subsystem — material, process, overhead, margin.")
        with c2:
            _card(_P["scenario"], "🧭", "Scenario Planner",
                  "Simulate commodity price shifts with sliders.")
        with c3:
            _card(_P["linedet"],  "🔍", "Line Cost Detail",
                  "Full cost stack per BOM line.")
        with c4:
            _card(_P["quality"],  "✅", "Data Quality",
                  "Flag missing prices, expired quotes, anomalies.")

    with st.expander("4️⃣ Quote & export — documents & packages"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["stakeholder_pkg"], "📦", "Stakeholder Package",
                  "9-tab Excel + 6-section PDF covering full workflow.")
        with c2:
            _card(_P["quotesheet"],      "🧾", "Quote Sheet",
                  "Internal cost analysis + customer quote preview.")
        with c3:
            _card(_P["docx"],            "📝", "Quote DOCX / PDF",
                  "Word and PDF documents ready to send.")
        with c4:
            _card(_P["download"],        "⬇️", "Download Centre",
                  "Full workbook and individual data sheets.")

    with st.expander("5️⃣ Cost engineering — transport, NRE, escalation"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["waterfall"],  "🌊", "Full Cost Summary",
                  "Complete waterfall: BOM to delivery.")
        with c2:
            _card(_P["transport"],  "🚢", "Transport & Logistics",
                  "Freight, packaging, duties and shipping.")
        with c3:
            _card(_P["nre"],        "🔬", "Engineering & NRE",
                  "Design, testing, tooling, commissioning.")
        with c4:
            _card(_P["escalation"], "📉", "Escalation & Risk",
                  "Price indices, risk register, contingency.")

    with st.expander("6️⃣ Contract & lifecycle — from award to close-out"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["contract"],     "💰", "Contract & Cash Flow",
                  "Milestone payments, LD, APG, retention.")
        with c2:
            _card(_P["changeorders"], "🔄", "Change Orders",
                  "Scope variations and margin impact.")
        with c3:
            _card(_P["closeout"],     "📁", "Project Close-out",
                  "Final P&L, budget vs actuals, lessons.")
        with c4:
            _card(_P["spareparts"],   "🔩", "Spare Parts",
                  "Customer catalogue with prices and quantities.")

    with st.expander("7️⃣ Compliance & sustainability"):
        c1, c2, _, _ = st.columns(4)
        with c1:
            _card(_P["india_lc"], "🇮🇳", "India Local Content",
                  "IC% register, declarations, DAP 2020 compliance.")
        with c2:
            _card(_P["carbon"],   "🌱", "Carbon & Energy",
                  "kWh and CO₂e from manufacturing. Reduction levers.")

    with st.expander("📈 Market intelligence"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card(_P["market"],   "📊", "Market Data",
                  "Raw material price series.")
        with c2:
            _card(_P["history"],  "📉", "Material History",
                  "Price charts per material.")
        with c3:
            _card(_P["anomalie"], "🚨", "Anomalies",
                  "Large price deviations across the library.")
        with c4:
            _card(_P["setup"],    "🧩", "Market Setup",
                  "Link a live Google Sheet as a price source.")

    st.divider()
    # ── Bottom shortcuts ──────────────────────────────────────────────────────
    b1, b2 = st.columns(2)
    with b1:
        st.info("**🔧 Issues to fix?** Action Centre resolves expired quotes, "
                "missing runtimes, overhead gaps — all in one place.")
        st.page_link(_P["actions"], label="→ Open Action Centre")
    with b2:
        st.info("**🎯 Want everything in one screen?** Command Centre shows live metrics, "
                "signals and workflow shortcuts.")
        st.page_link(_P["cockpit"], label="→ Open Command Centre")


# ── Navigation (grouped sidebar) ─────────────────────────────────────────────
_home = st.Page(dashboard, title="Home", icon="🏠", default=True)

pg = st.navigation(
    {
        "Home":                      [_home],
        "1 · Prepare":               [_P["bom"], _P["mats"], _P["quotemgmt"],
                                      _P["quotes"], _P["presets"], _P["csv"]],
        "2 · Calculate":             [_P["quick"], _P["calc"], _P["routing"],
                                      _P["itemcost"], _P["borescale"]],
        "3 · Analyse":               [_P["mgmt"], _P["scenario"], _P["linedet"],
                                      _P["prepost"], _P["quality"], _P["volume"]],
        "4 · Quote & Export":        [_P["stakeholder_pkg"], _P["quotesheet"],
                                      _P["rapport"], _P["export"],
                                      _P["docx"], _P["pdf"], _P["download"]],
        "5 · Cost Engineering":      [_P["waterfall"], _P["transport"], _P["nre"],
                                      _P["escalation"]],
        "6 · Contract & Lifecycle":  [_P["contract"], _P["changeorders"],
                                      _P["closeout"], _P["spareparts"], _P["revisions"]],
        "7 · Compliance":            [_P["india_lc"], _P["carbon"]],
        "Market Intelligence":       [_P["market"], _P["history"],
                                      _P["anomalie"], _P["setup"]],
        "Tools":                     [_P["actions"], _P["cockpit"],
                                      _P["stakeholder_rpt"], _P["restore"],
                                      _P["debug"], _P["diagnose"]],
    },
    position="sidebar",
)
pg.run()
