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
    "transport":  st.Page("pages/35_Transport_Logistics.py",   title="Transport & Logistics", icon="🚢"),
    "nre":        st.Page("pages/36_Engineering_NRE.py",       title="Engineering & NRE",     icon="🔬"),
    "volume":     st.Page("pages/37_Volume_Analysis.py",       title="Volume Analysis",       icon="📈"),
    "escalation": st.Page("pages/38_Escalation_Risk.py",       title="Escalation & Risk",     icon="📉"),
    "waterfall":  st.Page("pages/39_Full_Cost_Summary.py",     title="Full Cost Summary",     icon="🌊"),
    "contract":   st.Page("pages/40_Contract_Cashflow.py",     title="Contract & Cash Flow",  icon="💰"),
    "changeorders":st.Page("pages/41_Change_Orders.py",        title="Change Orders",         icon="🔄"),
    "closeout":   st.Page("pages/42_Project_Closeout.py",      title="Project Close-out",     icon="📁"),
    "spareparts": st.Page("pages/43_Spare_Parts.py",           title="Spare Parts",           icon="🔩"),
    "revisions":  st.Page("pages/44_Quote_Revisions.py",       title="Quote Revisions",       icon="📜"),
    "cockpit":    st.Page("pages/45_Command_Centre.py",        title="Command Centre",      icon="🎯"),
    "debug":      st.Page("pages/00_Debug.py",                 title="Debug",               icon="🐛"),
    "diagnose":   st.Page("pages/0_Diagnose.py",               title="Diagnose",            icon="🔍"),
}

st.title('Cost Forge 2')
st.caption('Enterprise Cost Engineering Platform')

st.success('✅ Restored full dashboard navigation and System Health integration.')

pg = st.navigation(
    [st.Page("home.py", title="Home", icon="🏠", default=True)] + list(_P.values()),
    position="hidden",
)
pg.run()
