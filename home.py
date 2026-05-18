from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Cost Forge 2", layout="wide", page_icon="🛠️")

# ── All pages defined once ───────────────────────────────────────────────────
_P = {
    "bom":      st.Page("pages/15_Bom_Import.py",             title="BOM Import",       icon="📥"),
    "quick":    st.Page("pages/01_Quick_Cost.py",              title="Quick Cost",       icon="⚡"),
    "calc":     st.Page("pages/01_Calculatie.py",              title="Calculation",      icon="💸"),
    "routing":  st.Page("pages/16_Routing_Kosten.py",          title="Routing Costs",    icon="🛠️"),
    "scenario": st.Page("pages/06_Scenario_Planner.py",        title="Scenario Planner", icon="🧭"),
    "rapport":  st.Page("pages/12_Rapport.py",                 title="Report",           icon="📑"),
    "export":   st.Page("pages/17_Offerte_Export.py",          title="Quote Export",     icon="📦"),
    "docx":     st.Page("pages/18_Offerte_DOCX.py",            title="Quote DOCX",       icon="📝"),
    "pdf":      st.Page("pages/19_Offerte_PDF.py",             title="Quote PDF",        icon="🖨️"),
    "download": st.Page("pages/20_Download_Center.py",         title="Download Center",  icon="⬇️"),
    "mats":     st.Page("pages/04_Materiaalbronnen.py",        title="Materials",        icon="🧱"),
    "quotes":   st.Page("pages/07_Supplier_Quotes.py",         title="Supplier Quotes",  icon="🏭"),
    "presets":  st.Page("pages/03_Presets.py",                 title="Presets",          icon="⚙️"),
    "quality":  st.Page("pages/05_Data_Quality.py",            title="Data Quality",     icon="✅"),
    "csv":      st.Page("pages/99_Update_from_Public_CSV.py",  title="CSV Import",       icon="🔗"),
    "market":   st.Page("pages/13_Marktdata.py",               title="Market Data",      icon="📊"),
    "history":  st.Page("pages/22_Materiaal_Historie.py",      title="Material History", icon="📉"),
    "anomalie": st.Page("pages/26_anomalie_overview.py",       title="Anomalies",        icon="🚨"),
    "setup":    st.Page("pages/24_market_setup.py",            title="Market Setup",     icon="🧩"),
    "restore":  st.Page("pages/25_Restore_Hulp.py",            title="Restore",          icon="♻️"),
    "mgmt":     st.Page("pages/27_Management_Dashboard.py",    title="Management",       icon="📊"),
    "linedet":  st.Page("pages/28_Line_Cost_Detail.py",        title="Line Cost Detail", icon="🔍"),
    "quotesheet": st.Page("pages/29_Quote_Sheet.py",           title="Quote Sheet",      icon="🧾"),
    "debug":    st.Page("pages/00_Debug.py",                   title="Debug",            icon="🐛"),
    "diagnose": st.Page("pages/0_Diagnose.py",                 title="Diagnose",         icon="🔍"),
}


@st.cache_data(ttl=30)
def _kpis():
    try:
        from utils.io import load_bom, load_materials, load_processes, load_quotes
        from utils.pricing import compute_costs
        from utils.quotes import apply_best_quotes

        mats = load_materials()
        df = compute_costs(apply_best_quotes(mats, load_quotes()), load_processes(), load_bom())
        return {
            "total":     df["total_cost"].sum(),
            "mat":       df["material_cost"].sum(),
            "proc":      df["process_cost"].sum(),
            "overhead":  df["overhead"].sum(),
            "margin":    df["margin"].sum(),
            "lines":     len(df),
            "materials": df["material_id"].nunique(),
        }
    except Exception:
        return None


@st.cache_data(ttl=30)
def _completeness():
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


def _card(page, icon: str, title: str, caption: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(caption)
        st.page_link(page, label="Open →", use_container_width=True)


def dashboard() -> None:
    from utils.project import load_project_name

    name = load_project_name()
    st.title("🛠️ Cost Forge 2")
    if name:
        st.subheader(f"📦 {name}")
    st.caption("Click a card to navigate to the page.")

    # ── KPI row ───────────────────────────────────────────────────────────────
    kpi = _kpis()
    if kpi:
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        k1.metric("Total",    f"€ {kpi['total']:,.0f}")
        k2.metric("Material", f"€ {kpi['mat']:,.0f}")
        k3.metric("Process",  f"€ {kpi['proc']:,.0f}")
        k4.metric("Overhead", f"€ {kpi['overhead']:,.0f}")
        k5.metric("Margin",   f"€ {kpi['margin']:,.0f}")
        k6.metric("BOM lines",  kpi["lines"])
        k7.metric("Materials",  kpi["materials"])
    else:
        st.info("No BOM loaded yet — use **BOM Import** to get started.")

    # ── Completeness panel ────────────────────────────────────────────────────
    comp = _completeness()
    if comp:
        score = comp["score"]
        missing = comp["missing"]
        critical_miss = [(p, info) for p, info in missing if info["critical"]]

        pct = int(score * 100)
        colour = "green" if pct == 100 else ("orange" if pct >= 70 else "red")

        with st.expander(
            f"{'✅' if pct == 100 else '⚠️'} BOM Completeness — {pct}%  "
            f"({'Complete' if not missing else f'{len(missing)} subsystem(s) missing'})",
            expanded=bool(critical_miss),
        ):
            st.progress(score)
            from utils.completeness import WATERJET_SUBSYSTEMS

            cols = st.columns(7)
            for i, (prefix, info) in enumerate(WATERJET_SUBSYSTEMS.items()):
                present = prefix in comp["present"]
                count = comp["present"].get(prefix, 0)
                label = f"{info['icon']} **{info['name']}**"
                badge = f"`{count} lines`" if present else "❌ missing"
                cols[i % 7].markdown(f"{label}  \n{badge}")

            if critical_miss:
                st.warning(
                    "**Critical subsystems missing:** "
                    + ", ".join(f"{info['icon']} {info['name']}" for _, info in critical_miss)
                    + "  \nOpen **BOM Import** to upload a complete BOM or use the template."
                )
                st.page_link(_P["bom"], label="→ Go to BOM Import", use_container_width=False)
            elif missing:
                names = ", ".join(info["name"] for _, info in missing)
                st.info(f"Optional subsystems not found: {names}")

    st.divider()

    # ── Management & Procurement ──────────────────────────────────────────────
    st.subheader("📊 Management & Procurement")
    c1, c2 = st.columns(2)
    with c1:
        _card(_P["mgmt"], "📊", "Management Dashboard",
              "Cost breakdown by group and line — material, process, overhead, margin.")
    with c2:
        _card(_P["scenario"], "🧭", "Scenario Planner",
              "Simulate material price or labour rate changes with sliders.")

    st.divider()

    # ── Calculation ───────────────────────────────────────────────────────────
    st.subheader("💶 Calculation")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _card(_P["bom"],     "📥", "BOM Import",
              "Upload a BOM CSV and calculate all costs immediately.")
    with c2:
        _card(_P["quick"],   "⚡", "Quick Cost",
              "Quick cost overview of the active BOM with best quotes.")
    with c3:
        _card(_P["routing"], "🛠️", "Routing Costs",
              "Process time and cost per BOM line via routing data.")
    with c4:
        _card(_P["calc"],    "💸", "Calculation",
              "Detailed calculation per BOM line.")

    c1, c2 = st.columns(2)
    with c1:
        _card(_P["linedet"],    "🔍", "Line Cost Detail",
              "Full cost breakdown per line — purchase, machine, labour, overhead, margin with error checks.")
    with c2:
        _card(_P["quotesheet"], "🧾", "Quote Sheet",
              "Internal cost vs selling price — generate a customer quote with optional margin override.")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("📄 Export")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["rapport"],  "📑", "Report",        "Generate a Markdown quote report.")
    with c2:
        _card(_P["export"],   "📦", "Quote Export",  "Download DOCX and PDF in one click.")
    with c3:
        _card(_P["docx"],     "📝", "Quote DOCX",    "Word document with line detail and total.")
    with c4:
        _card(_P["pdf"],      "🖨️", "Quote PDF",     "PDF quote ready for sending.")
    with c5:
        _card(_P["download"], "⬇️", "Download Center","Download all source files as CSV.")

    st.divider()

    # ── Data & Management ─────────────────────────────────────────────────────
    st.subheader("📋 Data & Management")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["mats"],    "🧱", "Materials",     "View materials and best supplier prices.")
    with c2:
        _card(_P["quotes"],  "🏭", "Supplier Quotes","Compare quotes per supplier.")
    with c3:
        _card(_P["presets"], "⚙️", "Presets",        "Save overhead and margin percentages.")
    with c4:
        _card(_P["quality"], "✅", "Data Quality",   "Validate materials and BOM consistency.")
    with c5:
        _card(_P["csv"],     "🔗", "CSV Import",     "Import data from a public Google Sheet.")

    st.divider()

    # ── Market & Analysis ─────────────────────────────────────────────────────
    st.subheader("📈 Market & Analysis")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card(_P["market"],   "📊", "Market Data",
              "Raw material price series and year-on-year changes.")
    with c2:
        _card(_P["history"],  "📉", "Material History",
              "Price charts and snapshots per material.")
    with c3:
        _card(_P["anomalie"], "🚨", "Anomalies",
              "Overview of large price deviations.")
    with c4:
        _card(_P["setup"],    "🧩", "Market Setup",
              "Link a Google Sheet as a market factor source.")
    with c5:
        _card(_P["restore"],  "♻️", "Restore",
              "Restore the database from a historical snapshot.")


pg = st.navigation(
    [st.Page(dashboard, title="Home", icon="🏠", default=True)] + list(_P.values()),
    position="hidden",
)
pg.run()
