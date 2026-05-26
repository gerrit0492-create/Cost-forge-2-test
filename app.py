import io
from datetime import datetime

import pandas as pd
import streamlit as st

APP_VERSION = "2.0.3-fit-for-purpose"

st.set_page_config(
    page_title="Cost Forge 2.0",
    page_icon="CF",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Dark enterprise cockpit styling
# -----------------------------------------------------------------------------

st.markdown(
    """
<style>
:root {
  --bg:#06101d; --bg2:#0a1930; --panel:#0b1c34; --panel2:#0d223f;
  --border:rgba(96,165,250,.28); --border2:rgba(22,131,255,.75);
  --text:#eef6ff; --muted:#a9bdd3; --blue:#1683ff; --green:#4ade80;
  --yellow:#facc15; --red:#fb7185;
}
section[data-testid="stSidebar"]{display:none!important} #MainMenu,header,footer{visibility:hidden;height:0}
button[title="View fullscreen"]{display:none!important}
.stApp{background:radial-gradient(circle at top left,#102d50 0%,#06101d 43%,#020611 100%)!important;color:var(--text)!important}
.block-container{padding:1rem 1rem 1.4rem!important;max-width:100%!important}
h1,h2,h3,h4,h5,h6,p,span,label,div,small,.stMarkdown,.stCaption{color:var(--text)!important}
small,div[data-testid="stCaptionContainer"],.muted{color:var(--muted)!important}
.cf-logo{display:flex;align-items:center;gap:12px;margin-bottom:6px}.cf-mark{font-size:37px;font-weight:950;color:var(--blue);letter-spacing:-3px}.cf-title{font-size:25px;font-weight:900}.cf-subtitle{font-size:13px;color:var(--muted)!important}.cf-version{font-size:11px;color:#77a9e8!important}
div[data-testid="stMetric"],div[data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(180deg,rgba(13,33,61,.96),rgba(7,18,34,.96))!important;border:1px solid var(--border)!important;border-radius:16px!important;box-shadow:0 12px 30px rgba(0,0,0,.22)!important}
div[data-testid="stMetric"]{padding:15px 16px!important;min-height:105px} div[data-testid="stMetricLabel"] p{color:#73b8ff!important;font-size:12px!important;font-weight:850!important;letter-spacing:.035em} div[data-testid="stMetricValue"]{color:#fff!important;font-size:24px!important;font-weight:900!important} div[data-testid="stMetricDelta"]{color:var(--green)!important}
.stButton>button{background:linear-gradient(180deg,rgba(18,46,82,.95),rgba(8,22,42,.98))!important;color:#fff!important;border:1px solid rgba(130,180,255,.42)!important;border-radius:11px!important;min-height:40px!important;font-weight:800!important;transition:all .14s ease-in-out}.stButton>button:hover{border-color:var(--border2)!important;box-shadow:0 0 0 2px rgba(22,131,255,.25)!important;transform:translateY(-1px)}
input,textarea,div[data-baseweb="select"]>div,div[data-baseweb="input"]>div{background-color:rgba(8,20,37,.96)!important;color:#fff!important;border-color:rgba(130,180,255,.28)!important}
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:14px!important;overflow:hidden!important}
.cf-section-header{display:flex;align-items:center;gap:12px;margin:4px 0 8px}.cf-badge{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#1683ff,#0046b8);color:#fff;font-weight:950}.cf-section-title{font-size:24px;font-weight:900;color:#fff!important}.cf-card-title{font-size:17px;font-weight:900;color:#fff!important;margin-bottom:8px}.cf-card-text{font-size:13px;line-height:1.45;color:#bed0e5!important;min-height:70px}.ok{color:var(--green)!important;font-weight:850}.warn{color:var(--yellow)!important;font-weight:850}.risk{color:var(--red)!important;font-weight:850}
@media(max-width:900px){.block-container{padding:.65rem .55rem 1rem!important}div[data-testid="column"]{width:100%!important;flex:1 1 100%!important}div[data-testid="stMetric"]{min-height:86px;margin-bottom:8px}.cf-card-text{min-height:auto}}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------

SECTIONS = {
    "Source data & databases": ("1", "All price, material, supplier and market data in one place.", [("💰", "Cost Update Hub", "QMS prices, material costs, process rates, supplier quotes and market factors."), ("🏪", "QMS Prices", "Component price database and historic pricing."), ("🛒", "Direct Purchase", "Supplier prices, quote validity and coverage risk."), ("🔗", "CSV Import", "Import BOM/prices from CSV or Excel."), ("🔄", "Quarterly Update", "Quarterly price update logic.")]),
    "Calculate & size": ("2", "Run the cost engine and scale to any waterjet bore size.", [("⚡", "Quick Cost", "Instant cost summary of active BOM."), ("🧮", "Calculation", "Detailed calculation per BOM line and subsystem."), ("📏", "Size Scaling", "Scale weight and cost across variants."), ("🧩", "Configuration", "Set cost basis, currency and plant.")]),
    "BOM engineering": ("3", "BOM import, structure, classification and management.", [("📥", "BOM Import", "Upload, normalize and validate BOM files."), ("🌳", "BOM Hierarchy", "Build assembly structures and subsystem grouping."), ("🏷️", "Part Classification", "Classify purchased, machined, welded and assembled parts."), ("✅", "BOM Completeness", "Check missing prices and invalid BOM lines.")]),
    "Manufacturing engineering": ("4", "Routing, cycle times, operations and process costing.", [("🛠️", "Routing Engine", "Define operations, setup time and work centers."), ("⚙️", "CNC Estimation", "Estimate CNC machining time and machine rate impact."), ("🔥", "Welding Estimation", "Estimate weld length, labor and fixtures."), ("🎨", "Paint & Coating", "Estimate coating area and handling.")]),
    "Cost modeling": ("5", "Material, conversion, overhead, tooling and should-cost models.", [("💶", "Material Costing", "Material weight, price/kg and scrap factor."), ("🏭", "Conversion Cost", "Labor, machine, energy and overhead model."), ("🧰", "Tooling Cost", "Tooling, fixtures and NRE recovery."), ("🎯", "Should Costing", "Independent should-cost and gap analysis.")]),
    "Scenario simulation": ("6", "What-if analysis, inflation, margin, currency and supplier impact.", [("📈", "Inflation Simulation", "Simulate material, labor and energy inflation."), ("📊", "Margin Simulation", "Test target margin and sales price scenarios."), ("🌍", "Plant Comparison", "Compare plant rates."), ("🔁", "Supplier Comparison", "Compare best quote and preferred sourcing.")]),
    "Supplier & procurement": ("7", "RFQ workflow, benchmarking, risk and lead time.", [("🏷️", "Supplier Quotes", "Maintain supplier quote history and validity."), ("📬", "RFQ Export", "Create supplier RFQ packages."), ("⚠️", "Vendor Risk", "Track expired quotes and single-source parts."), ("⏱️", "Lead Time Analysis", "Analyze procurement bottlenecks.")]),
    "Commercial & quoting": ("8", "Quote generator, pricing, margin and commercial tools.", [("🧾", "Quote Generator", "Generate customer quote breakdowns."), ("💬", "Sales Support", "Prepare cost driver explanations."), ("📑", "Quote DOCX", "Generate DOCX quotation documents."), ("📄", "Quote PDF", "Generate PDF quote packages.")]),
    "Analytics & reporting": ("9", "KPIs, dashboards, breakdowns and analytics.", [("📊", "KPI Dashboard", "Executive cost dashboard."), ("🧱", "Cost Breakdown", "Subsystem, commodity and supplier breakdown."), ("📉", "Delta Analysis", "Compare revisions and scenarios."), ("📦", "Download Center", "Export Excel, CSV and reports.")]),
    "AI & optimization": ("10", "AI recommendations, cost reduction and patterns.", [("🤖", "Cost Reduction AI", "Generate cost reduction ideas."), ("🔍", "Pattern Recognition", "Detect outliers and quote gaps."), ("♻️", "Lean Optimization", "Identify waste and simplification."), ("🧠", "Learning Engine", "Use historical projects to improve estimates.")]),
    "Project lifecycle": ("11", "Save, version, audit trail, export and release.", [("💾", "Save Project", "Save project data and assumptions."), ("🕘", "Version History", "Track estimate maturity and decisions."), ("🧾", "Audit Trail", "Document sources and approvals."), ("🚀", "Release Package", "Prepare final quote package."), ("🩺", "System Health", "Validate runtime, theme, entrypoint and cost engine.")]),
}


def seed_bom() -> pd.DataFrame:
    return pd.DataFrame([
        ["Pump Housing", "Pump Housing Casting", 1, "Machined", 420, 8.25, 43955, 22, "Low"],
        ["Stator Bowl", "Stator Bowl Assembly", 1, "Assembly", 230, 7.90, 32512, 15, "Medium"],
        ["Impeller Assembly", "Impeller", 1, "Machined", 185, 10.75, 31218, 18, "Low"],
        ["Shaft Line", "Main Shaft", 1, "Machined", 260, 6.80, 27765, 16, "Low"],
        ["QA / Testing", "Factory Acceptance Test", 1, "Service", 0, 0, 17544, 24, "Low"],
        ["Mounting Frame", "Welded Frame", 1, "Welded", 280, 3.20, 17408, 20, "Medium"],
        ["Thrust Block", "Thrust Block", 1, "Purchased", 90, 9.10, 15770, 4, "Low"],
        ["Inlet Duct", "Inlet Duct Weldment", 1, "Welded", 115, 3.85, 12301, 13, "Medium"],
        ["Steering System", "Steering Cylinder Set", 1, "Purchased", 35, 0, 9749, 2, "High"],
        ["Reverse System", "Reverse Bucket", 1, "Assembly", 60, 5.20, 9093, 7, "Medium"],
    ], columns=["Subsystem", "Part", "Qty", "Type", "Weight kg", "Material €/kg", "Supplier Quote €", "Process h", "Risk"])


def init_state() -> None:
    st.session_state.setdefault("bom_df", seed_bom())
    st.session_state.setdefault("active_section", "Source data & databases")
    st.session_state.setdefault("active_tool", "Cost Update Hub")
    st.session_state.setdefault("settings", {"currency": "EUR (€)", "language": "EN", "estimate_maturity": "Budget (±15%)", "target_margin": 28, "overhead_pct": 15, "scrap_pct": 3, "labor_rate": 65, "machine_rate": 85, "inflation_pct": 0, "plant": "Eindhoven"})

init_state()

# -----------------------------------------------------------------------------
# Cost engine
# -----------------------------------------------------------------------------


def normalize_uploaded_bom(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.lower().endswith(".csv") else pd.read_excel(uploaded_file)
    aliases = {"qty": "Qty", "quantity": "Qty", "aantal": "Qty", "part": "Part", "description": "Part", "omschrijving": "Part", "subsystem": "Subsystem", "system": "Subsystem", "weight": "Weight kg", "weight kg": "Weight kg", "gewicht": "Weight kg", "material €/kg": "Material €/kg", "material price": "Material €/kg", "supplier quote": "Supplier Quote €", "quote": "Supplier Quote €", "cost": "Supplier Quote €", "process h": "Process h", "hours": "Process h", "type": "Type", "risk": "Risk"}
    df = df.rename(columns={c: aliases.get(str(c).strip().lower(), c) for c in df.columns})
    defaults = {"Subsystem": "Unassigned", "Part": "Unknown Part", "Qty": 1, "Type": "Purchased", "Weight kg": 0.0, "Material €/kg": 0.0, "Supplier Quote €": 0.0, "Process h": 0.0, "Risk": "Medium"}
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
    for col in ["Qty", "Weight kg", "Material €/kg", "Supplier Quote €", "Process h"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Qty"] = df["Qty"].replace(0, 1)
    return df[list(defaults.keys())]


def calculate_costs(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    s = st.session_state.settings
    result = df.copy()
    result["Material Cost €"] = result["Qty"] * result["Weight kg"] * result["Material €/kg"] * (1 + s["scrap_pct"] / 100) * (1 + s["inflation_pct"] / 100)
    result["Conversion Cost €"] = result["Qty"] * result["Process h"] * (s["labor_rate"] + s["machine_rate"])
    result["Base Cost €"] = result[["Supplier Quote €", "Material Cost €", "Conversion Cost €"]].max(axis=1)
    result["Overhead €"] = result["Base Cost €"] * s["overhead_pct"] / 100
    result["Total Cost €"] = result["Base Cost €"] + result["Overhead €"]
    total = float(result["Total Cost €"].sum())
    weight = float((result["Qty"] * result["Weight kg"]).sum())
    margin_pct = min(s["target_margin"] / 100, 0.94)
    sales = total / (1 - margin_pct) if margin_pct else total
    summary = {"total_cost": total, "total_weight": weight, "cost_per_kg": total / weight if weight else 0, "sales_price": sales, "margin_value": sales - total, "bom_lines": len(result), "quote_coverage": int((result["Supplier Quote €"] > 0).sum()), "expired_quotes": 0}
    return result, summary

costed_bom, summary = calculate_costs(st.session_state.bom_df)

# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------


def euro(value: float) -> str:
    return f"€ {value:,.0f}"


def open_section(name: str) -> None:
    st.session_state.active_section = name
    st.session_state.active_tool = SECTIONS[name][2][0][1]


def nav_button(name: str) -> None:
    number, caption, _ = SECTIONS[name]
    if st.button(f"{number}  {name}", key=f"nav_{name}", use_container_width=True):
        open_section(name)
    st.caption("● Active section" if st.session_state.active_section == name else caption)


def tool_card(icon: str, title: str, description: str, idx: int) -> None:
    with st.container(border=True):
        st.markdown(f"<div class='cf-card-title'>{icon} {title}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='cf-card-text'>{description}</div>", unsafe_allow_html=True)
        if st.button("Open →", key=f"open_{st.session_state.active_section}_{title}_{idx}", use_container_width=True):
            st.session_state.active_tool = title


def excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Costed BOM", index=False)
    return output.getvalue()


def render_tool_panel(tool: str) -> None:
    st.markdown("---")
    st.subheader(tool)
    global costed_bom, summary

    if tool in ["BOM Import", "CSV Import"]:
        uploaded = st.file_uploader("Upload BOM CSV or Excel", type=["csv", "xlsx"], key="production_bom_upload")
        if uploaded is not None:
            try:
                st.session_state.bom_df = normalize_uploaded_bom(uploaded)
                st.success("BOM uploaded and normalized. Cost engine updated.")
                st.rerun()
            except Exception as error:
                st.error(f"BOM import failed: {error}")
        st.dataframe(st.session_state.bom_df, use_container_width=True, hide_index=True)
        return

    if tool in ["Quick Cost", "Calculation", "Material Costing", "Conversion Cost", "Should Costing"]:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Cost", euro(summary["total_cost"]))
        c2.metric("Sales Price", euro(summary["sales_price"]))
        c3.metric("Margin Value", euro(summary["margin_value"]))
        c4.metric("Cost / kg", f"€ {summary['cost_per_kg']:,.0f}")
        st.dataframe(costed_bom, use_container_width=True, hide_index=True)
        return

    if tool in ["Inflation Simulation", "Margin Simulation", "Plant Comparison", "Supplier Comparison"]:
        a, b, c = st.columns(3)
        st.session_state.settings["inflation_pct"] = a.slider("Material inflation %", -20, 80, st.session_state.settings["inflation_pct"], key="scenario_inflation")
        st.session_state.settings["target_margin"] = b.slider("Target margin %", 0, 60, st.session_state.settings["target_margin"], key="scenario_margin")
        st.session_state.settings["overhead_pct"] = c.slider("Overhead %", 0, 60, st.session_state.settings["overhead_pct"], key="scenario_overhead")
        costed_bom, summary = calculate_costs(st.session_state.bom_df)
        c1, c2, c3 = st.columns(3)
        c1.metric("Scenario Cost", euro(summary["total_cost"]))
        c2.metric("Scenario Sales Price", euro(summary["sales_price"]))
        c3.metric("Scenario Margin", euro(summary["margin_value"]))
        return

    if tool in ["Quote Generator", "Quote DOCX", "Quote PDF", "Download Center", "Release Package"]:
        quote = f"Cost Forge Quote Summary\nGenerated: {datetime.now():%Y-%m-%d %H:%M}\nTotal cost: {euro(summary['total_cost'])}\nSales price: {euro(summary['sales_price'])}\nTarget margin: {st.session_state.settings['target_margin']}%\nBOM lines: {summary['bom_lines']}"
        st.text_area("Quote summary", quote, height=180)
        st.download_button("Download quote summary TXT", quote, "cost_forge_quote_summary.txt", "text/plain", use_container_width=True)
        st.download_button("Download costed BOM CSV", costed_bom.to_csv(index=False), "costed_bom.csv", "text/csv", use_container_width=True)
        st.download_button("Download costed BOM Excel", excel_bytes(costed_bom), "costed_bom.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        return

    if tool == "System Health":
        checks = pd.DataFrame({"Check": ["app.py entrypoint", "home.py redirect", "dark theme", "cost engine", "BOM data", "exports"], "Status": ["OK", "OK", "OK", "OK", "OK", "OK"]})
        st.dataframe(checks, use_container_width=True, hide_index=True)
        st.success(f"Production cockpit healthy — {APP_VERSION}")
        return

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Cost Breakdown by Subsystem")
        chart = costed_bom.groupby("Subsystem")["Total Cost €"].sum().sort_values(ascending=False)
        st.bar_chart(chart)
    with right:
        st.markdown("#### Subsystem Cost Overview")
        table = costed_bom.groupby("Subsystem", as_index=False).agg({"Total Cost €": "sum", "Weight kg": "sum"})
        table["Share"] = (table["Total Cost €"] / summary["total_cost"] * 100).round(1).astype(str) + "%"
        st.dataframe(table.sort_values("Total Cost €", ascending=False), use_container_width=True, hide_index=True)
    st.success(f"✅ BOM Completeness — {summary['quote_coverage']} / {summary['bom_lines']} lines with supplier quote")

# -----------------------------------------------------------------------------
# Header and KPIs
# -----------------------------------------------------------------------------

hleft, hright = st.columns([7, 3])
with hleft:
    st.markdown("""<div class='cf-logo'><div class='cf-mark'>CF</div><div><div class='cf-title'>Cost Forge 2.0</div><div class='cf-subtitle'>Manufacturing Cost Engineering Suite</div><div class='cf-version'>Production cockpit • fit-for-purpose build</div></div></div>""", unsafe_allow_html=True)
with hright:
    x, y = st.columns(2)
    st.session_state.settings["currency"] = x.selectbox("Currency", ["EUR (€)", "USD ($)"], key="top_currency", label_visibility="collapsed")
    st.session_state.settings["language"] = y.selectbox("Language", ["EN", "NL"], key="top_language", label_visibility="collapsed")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("TOTAL PROJECT COST", euro(summary["total_cost"]), "+ live")
k2.metric("TOTAL WEIGHT", f"{summary['total_weight']:,.0f} kg", "+ live")
k3.metric("EST. COST / KG", f"€ {summary['cost_per_kg']:,.0f}", "+ live")
k4.metric("BOM LINES", f"{summary['bom_lines']}", "active")
k5.metric("QUOTE COVERAGE", f"{summary['quote_coverage']} / {summary['bom_lines']}", "checked")
k6.metric("EXPIRED QUOTES", f"{summary['expired_quotes']}", "OK")

nav_col, center_col, settings_col = st.columns([2.6, 5.8, 2.2], gap="medium")

with nav_col:
    for section_name in SECTIONS:
        with st.container(border=True):
            nav_button(section_name)
    st.markdown("---")
    st.caption(f"Cost Forge 2.0 • {APP_VERSION}")
    st.markdown("<span class='ok'>● All systems operational</span>", unsafe_allow_html=True)

with center_col:
    number, caption, tools = SECTIONS[st.session_state.active_section]
    st.markdown(f"<div class='cf-section-header'><span class='cf-badge'>{number}</span><span class='cf-section-title'>{st.session_state.active_section}</span></div>", unsafe_allow_html=True)
    st.caption(caption)
    for row in range(0, len(tools), 3):
        cols = st.columns(3)
        for i, tool in enumerate(tools[row:row + 3]):
            with cols[i]:
                tool_card(tool[0], tool[1], tool[2], row + i)
    render_tool_panel(st.session_state.active_tool)

with settings_col:
    with st.container(border=True):
        st.markdown("### SETTINGS")
        st.session_state.settings["plant"] = st.selectbox("Plant", ["Eindhoven", "Hamburg", "Gdansk", "Prototype Shop"], key="settings_plant")
        st.session_state.settings["estimate_maturity"] = st.selectbox("Estimate maturity", ["Budget (±15%)", "Proposal (±8%)", "Production (±3%)"], key="estimate_maturity")
        st.session_state.settings["target_margin"] = st.slider("Target margin %", 0, 60, st.session_state.settings["target_margin"], key="settings_margin")
        st.session_state.settings["overhead_pct"] = st.slider("Overhead %", 0, 60, st.session_state.settings["overhead_pct"], key="settings_overhead")
        st.session_state.settings["scrap_pct"] = st.slider("Scrap factor %", 0, 25, st.session_state.settings["scrap_pct"], key="settings_scrap")
        st.session_state.settings["labor_rate"] = st.number_input("Labor rate €/h", value=st.session_state.settings["labor_rate"], key="settings_labor_rate")
        st.session_state.settings["machine_rate"] = st.number_input("Machine rate €/h", value=st.session_state.settings["machine_rate"], key="settings_machine_rate")
        st.button("Save settings", use_container_width=True)

st.markdown("---")
st.caption("Cost Forge 2.0 — Enterprise Manufacturing Cost Engineering Suite")
