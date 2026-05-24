from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.style import inject_css

st.set_page_config(page_title="Cost Forge 2", layout="wide", page_icon="🛠️")
inject_css()

# ── All pages ─────────────────────────────────────────────────────────────────
_P = {
    "bom":        st.Page("pages/15_Bom_Import.py",            title="BOM Import",          icon="📥"),
    "quick":      st.Page("pages/01_Quick_Cost.py",             title="Quick Cost",          icon="⚡"),
    "calc":       st.Page("pages/01_Calculatie.py",             title="Calculation",         icon="💸"),
    "routing":    st.Page("pages/16_Routing_Kosten.py",         title="Routing Costs",       icon="🛠️"),
    "scenario":   st.Page("pages/06_Scenario_Planner.py",       title="Scenario Planner",    icon="🧭"),
    "rapport":    st.Page("pages/12_Rapport.py",                title="Report",              icon="📑"),
    "export":     st.Page("pages/17_Offerte_Export.py",         title="Quote Export",        icon="📦"),
    "docx":       st.Page("pages/18_Offerte_DOCX.py",           title="Quote DOCX",          icon="📝"),
    "pdf":        st.Page("pages/19_Offerte_PDF.py",            title="Quote PDF",           icon="🖨️"),
    "download":   st.Page("pages/20_Download_Center.py",        title="Download Center",     icon="⬇️"),
    "mats":       st.Page("pages/04_Materiaalbronnen.py",       title="Materials",           icon="🧱"),
    "quotes":     st.Page("pages/07_Supplier_Quotes.py",        title="Supplier Quotes",     icon="🏭"),
    "presets":    st.Page("pages/03_Presets.py",                title="Presets",             icon="⚙️"),
    "quality":    st.Page("pages/05_Data_Quality.py",           title="Data Quality",        icon="✅"),
    "systemhealth": st.Page("pages/05_System_Health.py",        title="System Health",       icon="🩺"),
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
}


def _card(page, icon: str, title: str, caption: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(caption)
        st.page_link(page, label="Open →", use_container_width=True)


st.title('Cost Forge 2')
st.caption('Enterprise Cost Engineering Platform')

st.subheader('1️⃣ Prepare data')

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    _card(_P['bom'], '📥', 'BOM Import', 'Import BOM structures and project data.')

with c2:
    _card(_P['mats'], '🧱', 'Materials', 'Manage material master data.')

with c3:
    _card(_P['quotes'], '🏭', 'Supplier Quotes', 'Manage supplier pricing.')

with c4:
    _card(_P['quality'], '✅', 'Data Quality', 'Validate workbook quality.')

with c5:
    _card(_P['systemhealth'], '🩺', 'System Health', 'Monitor workbook integrity and runtime stability.')
