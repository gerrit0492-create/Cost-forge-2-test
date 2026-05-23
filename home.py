from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.style import inject_css

st.set_page_config(page_title="Cost Forge 2", layout="wide", page_icon="🛠️")
inject_css()

# ── All pages ─────────────────────────────────────────────────────────────────────────────────
_P = {
    "bom":        st.Page("pages/15_Bom_Import.py",            title="BOM Import",          icon="📥"),
    "quick":      st.Page("pages/01_Quick_Cost.py",             title="Quick Cost",          icon="⚡"),
    "calc":       st.Page("pages/01_Calculatie.py",             title="Calculation",         icon="💸"),
    "routing":    st.Page("pages/16_Routing_Kosten.py",         title="Routing Costs",       icon="🛠️"),
    "scenario":   st.Page("pages/06_Scenario_Planner.py",       title="Scenario Planner",    icon="🦭"),
    "rapport":    st.Page("pages/12_Rapport.py",                title="Report",              icon="📑"),
    "export":     st.Page("pages/17_Offerte_Export.py",         title="Quote Export",        icon="📦"),
    "docx":       st.Page("pages/18_Offerte_DOCX.py",           title="Quote DOCX",          icon="📝"),
    "pdf":        st.Page("pages/19_Offerte_PDF.py",            title="Quote PDF",           icon="🖨️"),
    "download":   st.Page("pages/20_Download_Center.py",        title="Download Center",     icon="⬇️"),
    "mats":       st.Page("pages/04_Materiaalbronnen.py",       title="Materials",           icon="🧱"),
    "quotes":     st.Page("pages/07_Supplier_Quotes.py",        title="Supplier Quotes",     icon="🏭"),
    "presets":    st.Page("pages/03_Presets.py",                title="Presets",             icon="⚙️"),
    "quality":    st.Page("pages/05_Data_Quality.py",           title="Data Quality",        icon="✅"),
    "csv":        st.Page("pages/99_Update_from_Public_CSV.py", title="CSV Import",          icon="🔗"),
    "market":     st.Page("pages/13_Marktdata.py",              title="Market Data",         icon="📊"),
    "history":    st.Page("pages/22_Materiaal_Historie.py",     title="Material History",    icon="📉"),
    "anomalie":   st.Page("pages/26_anomalie_overview.py",      title="Anomalies",           icon="🚨"),
    "setup":      st.Page("pages/24_market_setup.py",           title="Market Setup",        icon="🧩"),
    "restore":    st.Page("pages/25_Restore_Hulp.py",           title="Restore",             icon="♻️"),
    "mgmt":       st.Page("pages/27_Management_Dashboard.py",   title="Management",          icon="📊"),
    "linedet":    st.Page("pages/28_Line_Cost_Detail.py",       title="Line Cost Detail",    icon="🔍"),
    "quotesheet": st.Page("pages/29_Quote_Sheet.py",            title="Quote Sheet",         icon="🧾"),
    "borescale":  st.Page("pages/30_Bore_Scale.py",             title="Waterjet Size Scale", icon="📐"),
    "prepost":    st.Page("pages/31_Pre_Post.py",               title="Pre / Post",          icon="📊"),
    "itemcost":   st.Page("pages/32_Item_Costing.py",           title="Item Costing",        icon="🔢"),
    "stakeholder":st.Page("pages/33_Stakeholder_Report.py",    title="Stakeholder Report",  icon="📋"),
    "actions":    st.Page("pages/34_Action_Centre.py",          title="Action Centre",       icon="🔧"),
    # ── Senior cost engineer toolbox ────────────────────────────────────────────────────
    "transport":  st.Page("pages/35_Transport_Logistics.py",   title="Transport & Logistics", icon="🚢"),
    "nre":        st.Page("pages/36_Engineering_NRE.py",       title="Engineering & NRE",     icon="🔬"),
    "volume":     st.Page("pages/37_Volume_Analysis.py",       title="Volume Analysis",       icon="📈"),
    "escalation": st.Page("pages/38_Escalation_Risk.py",       title="Escalation & Risk",     icon="📉"),
    "waterfall":  st.Page("pages/39_Full_Cost_Summary.py",     title="Full Cost Summary",     icon="🌊"),
    # ── Contract & project lifecycle ────────────────────────────────────────────────────
    "contract":   st.Page("pages/40_Contract_Cashflow.py",     title="Contract & Cash Flow",  icon="💰"),
    "changeorders":st.Page("pages/41_Change_Orders.py",        title="Change Orders",         icon="🔄"),
    "closeout":   st.Page("pages/42_Project_Closeout.py",      title="Project Close-out",     icon="🗂️"),
    "spareparts": st.Page("pages/43_Spare_Parts.py",           title="Spare Parts",           icon="🔩"),
    "revisions":  st.Page("pages/44_Quote_Revisions.py",       title="Quote Revisions",       icon="📜"),
    "cockpit":    st.Page("pages/45_Command_Centre.py",          title="Command Centre",      icon="🎯"),
    "india_lc":   st.Page("pages/46_India_Local_Content.py",    title="India Local Content", icon="🇮🇳"),
    "carbon":     st.Page("pages/47_Carbon_Energy.py",          title="Carbon & Energy",     icon="🌱"),
    "stakeholder":st.Page("pages/48_Stakeholder_Package.py",   title="Stakeholder Package", icon="📊"),
    "quarterly":  st.Page("pages/50_Quarterly_Update.py",       title="Quarterly Update",    icon="🔄"),
    "debug":      st.Page("pages/00_Debug.py",                  title="Debug",               icon="🐛"),
    "diagnose":   st.Page("pages/0_Diagnose.py",                title="Diagnose",            icon="🔍"),
}

MATURITY_OPTIONS = {
    "RoM (±30%)":        ("🟡", "Rough Order of Magnitude — early concept estimate"),
    "Budget (±15%)":     ("🟠", "Budget estimate — project planning / pre-FEED"),
    "Definitive (±5%)":  ("🔵", "Definitive estimate — detailed design complete"),
    "Firm":              ("🟢", "Firm price — locked BOM, confirmed supplier quotes"),
}


# ── Cached data loaders ─────────────────────────────────────────────────────────────────────────────────
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
        overhead   = df["overhead"].sum()
        margin     = df["margin"].sum()
        base_cost  = df["base_cost"].sum() if "base_cost" in df.columns else (mat_cost + proc_cost + overhead)

        expired    = expired_quote_materials(quotes)
        total_mats = len(mats)
        quoted_mats = quotes["material_id"].nunique() if not quotes.empty else 0

        wb_mtime = WORKBOOK.stat().st_mtime if WORKBOOK.exists() else None

        # Subsystem cost split
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
            "total":       total_sell,
            "mat":         mat_cost,
            "proc":        proc_cost,
            "overhead":    overhead,
            "margin":      margin,
            "base_cost":   base_cost,
            "margin_pct":  margin / base_cost if base_cost else 0,
            "mat_share":   mat_cost / base_cost if base_cost else 0,
            "eur_per_kg":  total_sell / total_mass if total_mass else 0,
            "mass_kg":     total_mass,
            "lines":       len(df),
            "materials":   df["material_id"].nunique(),
            "expired":     expired,
            "total_mats":  total_mats,
            "quoted_mats": quoted_mats,
            "wb_mtime":    wb_mtime,
            "sub_costs":   sub_costs,
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
            "score":   completeness_score(bom),
            "present": detect_subsystems(bom),
            "missing": missing_subsystems(bom),
        }
    except Exception:
        return None


# ── Card helper ─────────────────────────────────────────────────────────────────────────────────
def _card(page, icon: str, title: str, caption: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(caption)
        st.page_link(page, label="Open →", use_container_width=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────────────────────
def dashboard() -> None:
    from utils.currency import currency_selector
    from utils.project import load_project_meta, save_project_meta

    # ── Sidebar controls ──────────────────────────────────────────────────────────────────────────
    currency_selector()

    meta = load_project_meta()

    st.sidebar.divider()
    st.sidebar.subheader("Estimate settings")

    maturity_default = meta.get("maturity", "Budget (±15%)")
    maturity_idx = list(MATURITY_OPTIONS).index(maturity_default) \
                   if maturity_default in MATURITY_OPTIONS else 1
    maturity = st.sidebar.selectbox(
        "Estimate maturity",
        list(MATURITY_OPTIONS.keys()),
        index=maturity_idx,
        help="Confidence level of the current cost estimate.",
    )

    target_default = float(meta.get("target_cost", 0.0))
    target_cost = st.sidebar.number_input(
        "Budget / target cost (€)",
        min_value=0.0, value=target_default, step=10_000.0, format="%.0f",
        help="Set a budget reference to track gap-to-target on the dashboard.",
    )

    if maturity != meta.get("maturity") or target_cost != meta.get("target_cost", 0.0):
        save_project_meta(maturity=maturity, target_cost=target_cost)

    # ── Header ────────────────────────────────────────────────────────────────────────────────
    name = meta.get("name", "")
    badge_icon, badge_tip = MATURITY_OPTIONS[maturity]

    from utils.style import page_header
    page_header(
        title="Cost Forge 2",
        icon="🛠️",
        caption="Marine waterjet cost engineering platform",
        project=name,
        maturity=maturity,
        right_html=f"<b>{badge_icon} {maturity}</b><br><small>{badge_tip}</small>",
    )
    if st.button("🔄 Refresh", help="Clear all cached data"):
        st.cache_data.clear()
        st.rerun()

    # ── KPI block ────────────────────────────────────────────────────────────────────────────────
    kpi = _kpis()
    if kpi:
        # Row 1 — primary cost stack
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        k1.metric("Sell price",      fmt(kpi["total"]))
        k2.metric("Material",        fmt(kpi["mat"]))
        k3.metric("Process",         fmt(kpi["proc"]))
        k4.metric("Overhead",        fmt(kpi["overhead"]))
        k5.metric("Margin",          fmt(kpi["margin"]),
                  delta=f"{kpi['margin_pct']*100:.1f}%")
        k6.metric("Material share",  f"{kpi['mat_share']*100:.0f}%",
                  delta="of cost",
                  delta_color="off")
        k7.metric("€ / kg",          f"{kpi['eur_per_kg']:,.0f}",
                  delta=f"{kpi['mass_kg']:,.0f} kg total",
                  delta_color="off")

        # Row 2 — coverage & structure
        r1, r2, r3, r4, r5, r6 = st.columns(6)
        r1.metric("BOM lines",       kpi["lines"])
        r2.metric("Unique materials", kpi["materials"])
        r3.metric("Dry weight",      f"{kpi['mass_kg']:,.0f} kg")

        quote_cov = kpi["quoted_mats"] / kpi["total_mats"] * 100 if kpi["total_mats"] else 0
        r4.metric("Quote coverage",
                  f"{kpi['quoted_mats']} / {kpi['total_mats']}",
                  delta=f"{quote_cov:.0f}%",
                  delta_color="off")

        exp_count = len(kpi["expired"])
        r5.metric("Expired quotes",  exp_count,
                  delta="⚠️ action needed" if exp_count else "✅ all valid",
                  delta_color="inverse" if exp_count else "off")

        if kpi["wb_mtime"]:
            age_s = time.time() - kpi["wb_mtime"]
            if age_s < 3600:
                age_str = f"{int(age_s/60)} min ago"
            elif age_s < 86400:
                age_str = f"{int(age_s/3600)}h ago"
            else:
                age_str = f"{int(age_s/86400)}d ago"
            r6.metric("Data last updated", age_str)

        # ── Target cost gap ──────────────────────────────────────────────────────────────────────────
        if target_cost > 0:
            gap      = kpi["total"] - target_cost
            gap_pct  = gap / target_cost * 100
            t1, t2, t3, _ = st.columns([1, 1, 1, 4])
            t1.metric("Target cost",   fmt(target_cost))
            t2.metric("Gap to target", fmt(gap),
                      delta=f"{gap_pct:+.1f}%",
                      delta_color="inverse")
            t3.metric("Cost vs budget", f"{kpi['total']/target_cost*100:.1f}%",
                      delta="over" if gap > 0 else "under",
                      delta_color="inverse" if gap > 0 else "normal")

        # ── Data quality alerts ─────────────────────────────────────────────────────────────────────────
        alerts = []
        if exp_count:
            alerts.append(f"⚠️ **{exp_count} expired supplier quote(s)** — prices may be stale: "
                          f"{', '.join(kpi['expired'][:5])}{'…' if len(kpi['expired']) > 5 else ''}")
        if kpi["mat_share"] > 0.75:
            alerts.append(f"⚠️ **Material share {kpi['mat_share']*100:.0f}%** — high commodity exposure. "
                          "Consider escalation clauses or back-to-back supply contracts.")
        if quote_cov < 80:
            alerts.append(f"⚠️ **Quote coverage {quote_cov:.0f}%** — {kpi['total_mats'] - kpi['quoted_mats']} "
                          "material(s) have no supplier quote.")
        if maturity in ("RoM (±30%)", "Budget (±15%)"):
            alerts.append(f"ℹ️ Estimate maturity: **{maturity}** — numbers carry inherent uncertainty. "
                          "Confirm before issuing a firm quotation.")
        for a in alerts:
            st.warning(a)

        st.divider()

        # ── Subsystem cost breakdown ───────────────────────────────────────────────────────────────────
        st.subheader("Subsystem cost split")
        sc_col, sc_tbl = st.columns([3, 1])
        with sc_col:
            chart_df = pd.DataFrame({"Sell price (€)": kpi["sub_costs"]})
            st.bar_chart(chart_df, color="#2196F3")
        with sc_tbl:
            tbl_df = pd.DataFrame({
                "Subsystem":  kpi["sub_costs"].index,
                "€":          kpi["sub_costs"].values,
                "Share":      (kpi["sub_costs"].values / kpi["total"] * 100),
            })
            tbl_df["€"]     = tbl_df["€"].map(lambda x: fmt(x))
            tbl_df["Share"] = tbl_df["Share"].map(lambda x: f"{x:.1f}%")
            st.dataframe(tbl_df, use_container_width=True, hide_index=True)

    else:
        st.info("No BOM loaded yet — start with **BOM Import** in section 1 below.")

    # ── BOM completeness ─────────────────────────────────────────────────────────────────────────────
    comp = _completeness()
    if comp:
        from utils.completeness import WATERJET_SUBSYSTEMS
        score    = comp["score"]
        missing  = comp["missing"]
        crit     = [(p, i) for p, i in missing if i["critical"]]
        pct      = int(score * 100)

        with st.expander(
            f"{'✅' if pct == 100 else '⚠️'} BOM Completeness — {pct}%  "
            f"({'Complete' if not missing else f'{len(missing)} subsystem(s) missing'})",
            expanded=bool(crit),
        ):
            st.progress(score)
            cols = st.columns(7)
            for i, (prefix, info) in enumerate(WATERJET_SUBSYSTEMS.items()):
                present = prefix in comp["present"]
                count   = comp["present"].get(prefix, 0)
                badge   = f"`{count} lines`" if present else "❌ missing"
                cols[i % 7].markdown(f"{info['icon']} **{info['name']}**  \n{badge}")
            if crit:
                st.warning(
                    "**Critical subsystems missing:** "
                    + ", ".join(f"{i['icon']} {i['name']}" for _, i in crit)
                    + "  \nOpen **BOM Import** to upload a complete BOM."
                )
                st.page_link(_P["bom"], label="→ BOM Import", use_container_width=False)
            elif missing:
                st.info("Optional subsystems not found: "
                        + ", ".join(i["name"] for _, i in missing))

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════════
    #  NUMBERED WORKFLOW SECTIONS
    # ══════════════════════════════════════════════════════════════════════════════

    # ── 1 · Prepare data ──────────────────────────────────────────────────────────────────────────
    st.subheader("1️⃣ Prepare data")
    st.caption("Start here — upload your BOM, verify materials, enter supplier prices and set overhead/margin presets.")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["bom"],       "📥", "BOM Import",
              "Upload or paste a BOM — costs are calculated immediately.")
    with c2:
        _card(_P["mats"],      "🧱", "Materials",
              "Review all materials and their best current supplier prices.")
    with c3:
        _card(_P["quotes"],    "🏭", "Supplier Quotes",
              "Enter, compare and validate quotes per supplier.")
    with c4:
        _card(_P["presets"],   "⚙️", "Presets",
              "Set default overhead %, margin % and labour rates.")
    with c5:
        _card(_P["quarterly"], "🔄", "Quarterly Update",
              "Generate the quarterly price-update workbook, import it back, and track update history.")
    c1, c2, _, _, _ = st.columns(5)
    with c1:
        _card(_P["csv"],       "🔗", "CSV Import",
              "Pull materials and prices from a public Google Sheet.")

    st.divider()

    # ── 2 · Calculate & size ─────────────────────────────────────────────────────────────────────────
    st.subheader("2️⃣ Calculate & size")
    st.caption("Run the cost engine — full BOM or a single item, and scale to any waterjet bore size.")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["quick"],    "⚡", "Quick Cost",
              "Instant cost summary of the active BOM with best quotes.")
    with c2:
        _card(_P["calc"],     "💸", "Calculation",
              "Detailed cost breakdown per BOM line.")
    with c3:
        _card(_P["routing"],  "🛠️", "Routing Costs",
              "Process time and cost per line via routing data.")
    with c4:
        _card(_P["itemcost"], "🔢", "Item Costing",
              "Price a single part with full routing, yield, surcharges and volume breaks.")
    with c5:
        _card(_P["borescale"],"📐", "Waterjet Size Scale",
              "Scale MWJ-720 cost and mass to any size MWJ-410 → MWJ-2120.")

    st.divider()

    # ── 3 · Analyse ──────────────────────────────────────────────────────────────────────────────────
    st.subheader("3️⃣ Analyse")
    st.caption("Understand cost drivers, run what-if scenarios and check data integrity before quoting.")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["mgmt"],     "📊", "Management Dashboard",
              "Cost by group and subsystem — material, process, overhead, margin.")
    with c2:
        _card(_P["scenario"], "🦭", "Scenario Planner",
              "Simulate commodity price shifts and labour rate changes with sliders.")
    with c3:
        _card(_P["linedet"],  "🔍", "Line Cost Detail",
              "Full cost stack per line — purchase, machine, labour, overhead, margin.")
    with c4:
        _card(_P["prepost"],  "📊", "Pre / Post",
              "Compare budget estimate against SAP or uploaded actuals — variance per line.")
    with c5:
        _card(_P["quality"],  "✅", "Data Quality",
              "Validate BOM and material data — flags missing prices, expired quotes, anomalies.")

    st.divider()

    # ── 4 · Quote ─────────────────────────────────────────────────────────────────────────────────
    st.subheader("4️⃣ Quote")
    st.caption("Build a professional customer quotation with commercial terms, classification and margin control.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _card(_P["quotesheet"], "🧾", "Quote Sheet",
              "Full internal cost analysis + styled customer quote preview + quality checks.")
    with c2:
        _card(_P["export"],     "📦", "Quote Export",
              "One-click DOCX + PDF generation from active BOM.")
    with c3:
        _card(_P["rapport"],    "📑", "Report",
              "Generate a structured Markdown cost report.")
    with c4:
        _card(_P["stakeholder"],"📋", "Stakeholder Report",
              "Conclusive multi-section report — executive summary, cost, procurement and risk register.")

    st.info(
        "**🔧 Issues to resolve?** Use the Action Centre to fix expired quotes, "
        "missing runtime values, overhead rates and estimate maturity — all in one place.",
        icon="🔧",
    )
    st.page_link(_P["actions"], label="→ Open Action Centre", use_container_width=False)

    st.divider()

    # ── 5 · Export & deliver ────────────────────────────────────────────────────────────────────────
    st.subheader("5️⃣ Export & deliver")
    st.caption("Download documents and source data.")

    # Stakeholder Package — prominent call-out
    with st.container(border=True):
        sc1, sc2 = st.columns([3, 1])
        sc1.markdown(
            "**📊 Stakeholder Package** — one click generates a **9-tab Excel workbook** "
            "and a **6-section PDF** covering the full workflow: "
            "cost waterfall · subsystem breakdown · procurement · energy & carbon · "
            "India local content · risk register. Ready to email."
        )
        sc2.page_link(_P["stakeholder"], label="Open →", use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _card(_P["docx"],     "📝", "Quote DOCX",
              "Word document with full BOM cost table.")
    with c2:
        _card(_P["pdf"],      "🖨️", "Quote PDF",
              "PDF ready for e-mail or printing.")
    with c3:
        _card(_P["download"], "⬇️", "Download Center",
              "Download full workbook and individual data sheets.")
    with c4:
        _card(_P["prepost"],  "📊", "Pre / Post Export",
              "SAP actuals import and pre/post variance report.")

    st.divider()

    # ── 6 · Senior cost engineer toolbox ─────────────────────────────────────────────────────
    st.subheader("6️⃣ Senior Cost Engineer Toolbox")
    st.caption(
        "Complete cost engineering: transport, NRE, volume curves, escalation, "
        "risk and the full P&L waterfall."
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["transport"],  "🚢", "Transport & Logistics",
              "Inbound freight, packaging, import duties and outbound shipping.")
    with c2:
        _card(_P["nre"],        "🔬", "Engineering & NRE",
              "Design hours, PM, testing, tooling and commissioning costs.")
    with c3:
        _card(_P["volume"],     "📈", "Volume Analysis",
              "Learning curve, batch pricing and break-even across production volumes.")
    with c4:
        _card(_P["escalation"], "📉", "Escalation & Risk",
              "Commodity price indices, risk register and contingency allowance.")
    with c5:
        _card(_P["waterfall"],  "🌊", "Full Cost Summary",
              "Complete waterfall: all cost elements from BOM to delivery.")

    st.divider()

    # ── Command Centre call-out ────────────────────────────────────────────────────────────────────────
    st.info(
        "**🎯 Want everything in one screen?** "
        "Open the **Command Centre** for a live cockpit view of all key metrics, "
        "signals and workflow shortcuts.",
        icon="🎯",
    )
    st.page_link(_P["cockpit"], label="→ Open Command Centre", use_container_width=False)
    st.divider()

    # ── 7 · Contract & project lifecycle ──────────────────────────────────────────────────────
    st.subheader("7️⃣ Contract & Project Lifecycle")
    st.caption(
        "From contract signature through delivery and close-out — "
        "cash flow, change orders, final P&L, spare parts and quote audit trail."
    )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        _card(_P["contract"],    "💰", "Contract & Cash Flow",
              "Milestone payments, cash flow timeline, LD, APG, retention and bond costs.")
    with c2:
        _card(_P["changeorders"],"🔄", "Change Orders",
              "Scope variation register — track approved and pending changes and their margin impact.")
    with c3:
        _card(_P["closeout"],    "🗂️", "Project Close-out",
              "Final P&L, budget vs actuals variance and lessons learned register.")
    with c4:
        _card(_P["spareparts"],  "🔩", "Spare Parts",
              "Generate customer spare parts catalog with recommended quantities and prices.")
    with c5:
        _card(_P["revisions"],   "📜", "Quote Revisions",
              "Snapshot and compare quote revisions — full audit trail for contracts.")
    with c6:
        _card(_P["india_lc"],    "🇮🇳", "India Local Content",
              "IC% register, CA certificate, origin declarations — prove compliance without submitting quote book.")

    st.divider()

    # ── 8 · Sustainability ──────────────────────────────────────────────────────────────────────────────
    st.subheader("8️⃣ Sustainability")
    st.caption(
        "Scope 2 electricity consumption and carbon footprint from manufacturing operations. "
        "Reduction levers, grid emission factors and Scope 3 context."
    )
    s1, s2 = st.columns([1, 5])
    with s1:
        _card(_P["carbon"], "🌱", "Carbon & Energy",
              "kWh and kg CO2e from BOM manufacturing ops. By scope, process and BOM line. "
              "Reduction levers and Scope 3 / CBAM guidance.")

    st.divider()

    # ── Market intelligence ────────────────────────────────────────────────────────────────────────────
    st.subheader("📈 Market intelligence")
    st.caption("Track raw material price trends, spot anomalies and link live market data sources.")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["market"],   "📊", "Market Data",
              "Raw material price series — year-on-year movements.")
    with c2:
        _card(_P["history"],  "📉", "Material History",
              "Price charts and historical snapshots per material.")
    with c3:
        _card(_P["anomalie"], "🚨", "Anomalies",
              "Overview of large price deviations across the material library.")
    with c4:
        _card(_P["setup"],    "🧩", "Market Setup",
              "Link a Google Sheet as a live market factor source.")
    with c5:
        _card(_P["restore"],  "♻️", "Restore",
              "Roll back the database to a historical snapshot.")


pg = st.navigation(
    [st.Page(dashboard, title="Home", icon="🏠", default=True)] + list(_P.values()),
    position="hidden",
)
pg.run()
