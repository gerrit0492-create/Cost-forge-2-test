from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Cost Forge 2", layout="wide", page_icon="🛠️")

# Hide the default sidebar page list — navigation is via the dashboard cards
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none}</style>",
    unsafe_allow_html=True,
)

# ── Live KPIs from current BOM ────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _kpis():
    try:
        from utils.io import load_bom, load_materials, load_processes, load_quotes
        from utils.pricing import compute_costs
        from utils.quotes import apply_best_quotes
        mats = load_materials()
        df = compute_costs(apply_best_quotes(mats, load_quotes()), load_processes(), load_bom())
        return {
            "total":    df["total_cost"].sum(),
            "mat":      df["material_cost"].sum(),
            "proc":     df["process_cost"].sum(),
            "overhead": df["overhead"].sum(),
            "margin":   df["margin"].sum(),
            "lines":    len(df),
            "materials": df["material_id"].nunique(),
        }
    except Exception:
        return None

st.title("🛠️ Cost Forge 2")
st.caption("Klik op een kaart om naar de pagina te gaan.")

kpi = _kpis()
if kpi:
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("Totaal",          f"€ {kpi['total']:,.0f}")
    k2.metric("Materiaal",       f"€ {kpi['mat']:,.0f}")
    k3.metric("Bewerking",       f"€ {kpi['proc']:,.0f}")
    k4.metric("Overhead",        f"€ {kpi['overhead']:,.0f}")
    k5.metric("Marge",           f"€ {kpi['margin']:,.0f}")
    k6.metric("BOM regels",      kpi["lines"])
    k7.metric("Materialen",      kpi["materials"])
else:
    st.info("Nog geen BOM geladen — gebruik BOM Import om te starten.")

st.divider()


# ── Helper: one card ──────────────────────────────────────────────────────────
def card(page: str, icon: str, title: str, caption: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(caption)
        st.page_link(page, label="Open →", use_container_width=True)


# ── Section 1: Berekening ─────────────────────────────────────────────────────
st.subheader("💶 Berekening")
c1, c2, c3, c4 = st.columns(4)
with c1:
    card("pages/15_Bom_Import.py",  "📥", "BOM Import",
         "Upload een BOM CSV en bereken direct alle kosten.")
with c2:
    card("pages/01_Quick_Cost.py",  "⚡", "Quick Cost",
         "Snelle kostenoverzicht van de actieve BOM met beste quotes.")
with c3:
    card("pages/16_Routing_Kosten.py", "🛠️", "Routing Kosten",
         "Bereken bewerkingstijd en kosten via een routing CSV.")
with c4:
    card("pages/06_Scenario_Planner.py", "🧭", "Scenario Planner",
         "Simuleer prijswijzigingen met sliders en zie het effect direct.")

st.divider()

# ── Section 2: Export ─────────────────────────────────────────────────────────
st.subheader("📄 Export")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    card("pages/12_Rapport.py",       "📑", "Rapport",
         "Genereer en download een Markdown offerterapport.")
with c2:
    card("pages/17_Offerte_Export.py","📦", "Offerte Export",
         "Download DOCX en PDF offerte in één klik.")
with c3:
    card("pages/18_Offerte_DOCX.py",  "📝", "Offerte DOCX",
         "Word-document met regeldetail en totaalprijs.")
with c4:
    card("pages/19_Offerte_PDF.py",   "🖨️", "Offerte PDF",
         "PDF-offerte klaar voor verzending.")
with c5:
    card("pages/20_Download_Center.py","📥", "Download Center",
         "Download alle bronbestanden (materialen, processen, BOM, quotes).")

st.divider()

# ── Section 3: Data & Beheer ─────────────────────────────────────────────────
st.subheader("📋 Data & Beheer")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    card("pages/04_Materiaalbronnen.py", "🧱", "Materiaalbronnen",
         "Bekijk materialen en beste leveranciersprijzen.")
with c2:
    card("pages/07_Supplier_Quotes.py",  "🏭", "Leveranciersquotes",
         "Beheer en vergelijk offertes per leverancier.")
with c3:
    card("pages/03_Presets.py",          "⚙️", "Presets",
         "Sla overhead- en margepercentages op als herbruikbare presets.")
with c4:
    card("pages/05_Data_Quality.py",     "✅", "Data Kwaliteit",
         "Valideer de consistentie van materialen, processen en BOM.")
with c5:
    card("pages/99_Update_from_Public_CSV.py", "🔗", "CSV via Google Sheet",
         "Importeer materialen of processen vanuit een publieke Google Sheet.")

st.divider()

# ── Section 4: Markt & Analyse ────────────────────────────────────────────────
st.subheader("📈 Markt & Analyse")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    card("pages/13_Marktdata.py",        "📊", "Marktdata",
         "Bekijk grondstofprijsreeksen en jaar-op-jaar wijzigingen.")
with c2:
    card("pages/22_Materiaal_Historie.py","📉", "Materiaal Historie",
         "Prijsgrafieken en snapshots voor elk materiaal.")
with c3:
    card("pages/26_anomalie_overview.py", "🚨", "Anomalieën",
         "Overzicht van grote prijsafwijkingen in de geschiedenis.")
with c4:
    card("pages/24_market_setup.py",      "🧩", "Market Setup",
         "Koppel een Google Sheet als bron voor marktfactoren.")
with c5:
    card("pages/25_Restore_Hulp.py",      "♻️", "Restore",
         "Herstel de materiaaldatabase vanuit een historische snapshot.")
