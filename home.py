from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Cost Forge 2", layout="wide", page_icon="🛠️")


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


def _card(page: str, icon: str, title: str, caption: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(caption)
        st.page_link(page, label="Open →", use_container_width=True)


def dashboard() -> None:
    st.title("🛠️ Cost Forge 2")
    st.caption("Klik op een kaart om naar de pagina te gaan.")

    kpi = _kpis()
    if kpi:
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        k1.metric("Totaal",     f"€ {kpi['total']:,.0f}")
        k2.metric("Materiaal",  f"€ {kpi['mat']:,.0f}")
        k3.metric("Bewerking",  f"€ {kpi['proc']:,.0f}")
        k4.metric("Overhead",   f"€ {kpi['overhead']:,.0f}")
        k5.metric("Marge",      f"€ {kpi['margin']:,.0f}")
        k6.metric("BOM regels", kpi["lines"])
        k7.metric("Materialen", kpi["materials"])
    else:
        st.info("Nog geen BOM geladen — gebruik BOM Import om te starten.")

    st.divider()

    # ── Berekening ────────────────────────────────────────────────────────────
    st.subheader("💶 Berekening")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _card("pages/15_Bom_Import.py",      "📥", "BOM Import",
              "Upload een BOM CSV en bereken direct alle kosten.")
    with c2:
        _card("pages/01_Quick_Cost.py",      "⚡", "Quick Cost",
              "Snelle kostenoverzicht van de actieve BOM met beste quotes.")
    with c3:
        _card("pages/16_Routing_Kosten.py",  "🛠️", "Routing Kosten",
              "Bewerkingstijd en kosten via een routing CSV.")
    with c4:
        _card("pages/06_Scenario_Planner.py","🧭", "Scenario Planner",
              "Simuleer prijswijzigingen met sliders en zie het effect.")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("📄 Export")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card("pages/12_Rapport.py",         "📑", "Rapport",
              "Genereer en download een Markdown offerterapport.")
    with c2:
        _card("pages/17_Offerte_Export.py",  "📦", "Offerte Export",
              "Download DOCX én PDF offerte in één klik.")
    with c3:
        _card("pages/18_Offerte_DOCX.py",   "📝", "Offerte DOCX",
              "Word-document met regeldetail en totaalprijs.")
    with c4:
        _card("pages/19_Offerte_PDF.py",    "🖨️", "Offerte PDF",
              "PDF-offerte klaar voor verzending.")
    with c5:
        _card("pages/20_Download_Center.py","⬇️", "Download Center",
              "Download alle bronbestanden als CSV.")

    st.divider()

    # ── Data & Beheer ─────────────────────────────────────────────────────────
    st.subheader("📋 Data & Beheer")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card("pages/04_Materiaalbronnen.py",       "🧱", "Materialen",
              "Materialen en beste leveranciersprijzen bekijken.")
    with c2:
        _card("pages/07_Supplier_Quotes.py",        "🏭", "Leveranciersquotes",
              "Offertes vergelijken per leverancier.")
    with c3:
        _card("pages/03_Presets.py",                "⚙️", "Presets",
              "Overhead- en margepercentages opslaan als preset.")
    with c4:
        _card("pages/05_Data_Quality.py",           "✅", "Data Kwaliteit",
              "Valideer de consistentie van materialen en BOM.")
    with c5:
        _card("pages/99_Update_from_Public_CSV.py", "🔗", "CSV Import",
              "Importeer data vanuit een publieke Google Sheet.")

    st.divider()

    # ── Markt & Analyse ───────────────────────────────────────────────────────
    st.subheader("📈 Markt & Analyse")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card("pages/13_Marktdata.py",           "📊", "Marktdata",
              "Grondstofprijsreeksen en jaar-op-jaar wijzigingen.")
    with c2:
        _card("pages/22_Materiaal_Historie.py",  "📉", "Materiaal Historie",
              "Prijsgrafieken en snapshots per materiaal.")
    with c3:
        _card("pages/26_anomalie_overview.py",   "🚨", "Anomalieën",
              "Overzicht van grote prijsafwijkingen.")
    with c4:
        _card("pages/24_market_setup.py",        "🧩", "Market Setup",
              "Koppel een Google Sheet als marktfactorbron.")
    with c5:
        _card("pages/25_Restore_Hulp.py",        "♻️", "Restore",
              "Herstel de database vanuit een historische snapshot.")


# ── Navigation — sidebar hidden, all routing via dashboard cards ──────────────
pg = st.navigation(
    [
        st.Page(dashboard,                              title="Home",               icon="🏠", default=True),
        st.Page("pages/15_Bom_Import.py",              title="BOM Import",         icon="📥"),
        st.Page("pages/01_Quick_Cost.py",              title="Quick Cost",         icon="⚡"),
        st.Page("pages/01_Calculatie.py",              title="Calculatie",         icon="💸"),
        st.Page("pages/16_Routing_Kosten.py",          title="Routing Kosten",     icon="🛠️"),
        st.Page("pages/06_Scenario_Planner.py",        title="Scenario Planner",   icon="🧭"),
        st.Page("pages/12_Rapport.py",                 title="Rapport",            icon="📑"),
        st.Page("pages/17_Offerte_Export.py",          title="Offerte Export",     icon="📦"),
        st.Page("pages/18_Offerte_DOCX.py",            title="Offerte DOCX",       icon="📝"),
        st.Page("pages/19_Offerte_PDF.py",             title="Offerte PDF",        icon="🖨️"),
        st.Page("pages/20_Download_Center.py",         title="Download Center",    icon="⬇️"),
        st.Page("pages/04_Materiaalbronnen.py",        title="Materialen",         icon="🧱"),
        st.Page("pages/07_Supplier_Quotes.py",         title="Leveranciersquotes", icon="🏭"),
        st.Page("pages/03_Presets.py",                 title="Presets",            icon="⚙️"),
        st.Page("pages/05_Data_Quality.py",            title="Data Kwaliteit",     icon="✅"),
        st.Page("pages/99_Update_from_Public_CSV.py",  title="CSV Import",         icon="🔗"),
        st.Page("pages/13_Marktdata.py",               title="Marktdata",          icon="📊"),
        st.Page("pages/22_Materiaal_Historie.py",      title="Materiaal Historie", icon="📉"),
        st.Page("pages/26_anomalie_overview.py",       title="Anomalieën",         icon="🚨"),
        st.Page("pages/24_market_setup.py",            title="Market Setup",       icon="🧩"),
        st.Page("pages/25_Restore_Hulp.py",            title="Restore",            icon="♻️"),
        st.Page("pages/00_Debug.py",                   title="Debug",              icon="🐛"),
        st.Page("pages/0_Diagnose.py",                 title="Diagnose",           icon="🔍"),
    ],
    position="hidden",
)
pg.run()
