import pandas as pd
import streamlit as st

from cf_core import (
    REQUIRED_BOM_COLUMNS,
    calculate_costs,
    default_assumptions,
    default_bom,
    excel_bytes,
    normalize_bom_file,
    pdf_bytes,
    quote_text,
    scenario_matrix,
    subsystem_summary,
    system_health,
)

APP_VERSION = "3.0.0-new-core"

st.set_page_config(page_title="Cost Forge 2.0", page_icon="⚙️", layout="wide")

WORKFLOW = {
    "Control Center": ["Executive Dashboard", "Cost Update Hub", "System Health"],
    "Source Data": ["BOM Import", "QMS Prices", "Supplier Quotes"],
    "Calculate & Size": ["Quick Cost", "Detailed Calculation", "Size Scaling"],
    "Manufacturing Engineering": ["Routing Engine", "CNC Estimation", "Welding Estimation", "Paint & Coating"],
    "Cost Modeling": ["Material Costing", "Conversion Cost", "Should Costing"],
    "Scenario Simulation": ["Scenario Planner", "Margin Simulation", "Plant Comparison"],
    "Commercial Output": ["Quote Generator", "Download Center", "Release Package"],
}

if "bom_df" not in st.session_state:
    st.session_state.bom_df = default_bom()
if "assumptions" not in st.session_state:
    st.session_state.assumptions = default_assumptions()
if "chapter" not in st.session_state:
    st.session_state.chapter = "Control Center"
if "tool" not in st.session_state:
    st.session_state.tool = "Executive Dashboard"


def euro(value: float) -> str:
    return f"€ {value:,.0f}"


def update_assumptions() -> None:
    a = st.session_state.assumptions
    st.session_state.assumptions = {
        "plant": st.session_state.get("plant", a["plant"]),
        "estimate_maturity": st.session_state.get("estimate_maturity", a["estimate_maturity"]),
        "target_margin_pct": float(st.session_state.get("target_margin_pct", a["target_margin_pct"])),
        "overhead_pct": float(st.session_state.get("overhead_pct", a["overhead_pct"])),
        "scrap_pct": float(st.session_state.get("scrap_pct", a["scrap_pct"])),
        "inflation_pct": float(st.session_state.get("inflation_pct", a["inflation_pct"])),
        "labor_rate_eur_h": float(st.session_state.get("labor_rate_eur_h", a["labor_rate_eur_h"])),
        "machine_rate_eur_h": float(st.session_state.get("machine_rate_eur_h", a["machine_rate_eur_h"])),
        "currency": st.session_state.get("currency", a["currency"]),
    }


st.title("⚙️ Cost Forge 2.0")
st.caption(f"Manufacturing Cost Engineering Suite | clean rebuild | {APP_VERSION}")

update_assumptions()
costed, summary = calculate_costs(st.session_state.bom_df, st.session_state.assumptions)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("TOTAL PROJECT COST", euro(summary["total_cost"]), "live")
k2.metric("TOTAL WEIGHT", f"{summary['total_weight']:,.0f} kg", "live")
k3.metric("EST. COST / KG", f"€ {summary['cost_per_kg']:,.0f}", "live")
k4.metric("BOM LINES", str(summary["bom_lines"]), "active")
k5.metric("QUOTE COVERAGE", f"{summary['quote_coverage']} / {summary['bom_lines']}", f"{summary['quote_coverage_pct']:.0f}%")
k6.metric("SALES PRICE", euro(summary["sales_price"]), "target")

nav, main, settings = st.columns([2.2, 5.8, 2.4], gap="large")

with nav:
    st.header("Control Center")
    chapter = st.radio("Workflow chapter", list(WORKFLOW), index=list(WORKFLOW).index(st.session_state.chapter), key="chapter_selector")
    if chapter != st.session_state.chapter:
        st.session_state.chapter = chapter
        st.session_state.tool = WORKFLOW[chapter][0]
        st.rerun()
    st.subheader("Tools")
    for tool_name in WORKFLOW[st.session_state.chapter]:
        if st.button(tool_name, key=f"tool_{st.session_state.chapter}_{tool_name}", use_container_width=True):
            st.session_state.tool = tool_name
            st.rerun()
    st.success("Control Center clickable")

with settings:
    a = st.session_state.assumptions
    st.header("Assumptions")
    st.selectbox("Plant", ["Eindhoven", "Hamburg", "Gdansk", "Prototype Shop"], index=["Eindhoven", "Hamburg", "Gdansk", "Prototype Shop"].index(str(a["plant"])), key="plant")
    st.selectbox("Estimate maturity", ["Budget (±15%)", "Proposal (±8%)", "Production (±3%)"], index=["Budget (±15%)", "Proposal (±8%)", "Production (±3%)"].index(str(a["estimate_maturity"])), key="estimate_maturity")
    st.slider("Target margin %", 0, 60, int(a["target_margin_pct"]), key="target_margin_pct")
    st.slider("Overhead %", 0, 60, int(a["overhead_pct"]), key="overhead_pct")
    st.slider("Scrap factor %", 0, 25, int(a["scrap_pct"]), key="scrap_pct")
    st.slider("Material inflation %", -20, 80, int(a["inflation_pct"]), key="inflation_pct")
    st.number_input("Labor rate €/h", min_value=0.0, value=float(a["labor_rate_eur_h"]), step=5.0, key="labor_rate_eur_h")
    st.number_input("Machine rate €/h", min_value=0.0, value=float(a["machine_rate_eur_h"]), step=5.0, key="machine_rate_eur_h")

with main:
    update_assumptions()
    costed, summary = calculate_costs(st.session_state.bom_df, st.session_state.assumptions)

    st.header("Executive Dashboard")
    chart_col, ready_col = st.columns([1.2, 1])
    with chart_col:
        st.subheader("Cost Breakdown by Subsystem")
        st.bar_chart(costed.groupby("Subsystem")["Total Cost €"].sum().sort_values(ascending=False))
    with ready_col:
        st.subheader("Readiness")
        st.dataframe(system_health(costed, summary), use_container_width=True, hide_index=True)
        st.success("Dashboard persistent")

    st.divider()
    st.header(f"Active Tool: {st.session_state.tool}")
    tool = st.session_state.tool

    if tool == "BOM Import":
        upload = st.file_uploader("Upload BOM CSV or Excel", type=["csv", "xlsx"], key="bom_upload")
        if upload is not None:
            try:
                st.session_state.bom_df = normalize_bom_file(upload)
                st.success("BOM uploaded and normalized.")
                st.rerun()
            except Exception as exc:
                st.error(f"BOM import failed: {exc}")
        edited = st.data_editor(st.session_state.bom_df, use_container_width=True, hide_index=True, num_rows="dynamic", key="bom_editor")
        b1, b2 = st.columns(2)
        if b1.button("Apply BOM edits", use_container_width=True):
            st.session_state.bom_df = edited[REQUIRED_BOM_COLUMNS]
            st.rerun()
        if b2.button("Reset demo BOM", use_container_width=True):
            st.session_state.bom_df = default_bom()
            st.rerun()

    elif tool in ["Quick Cost", "Detailed Calculation", "Material Costing", "Conversion Cost", "Should Costing", "Size Scaling"]:
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Total Cost", euro(summary["total_cost"]))
        a2.metric("Sales Price", euro(summary["sales_price"]))
        a3.metric("Margin Value", euro(summary["margin_value"]))
        a4.metric("Cost / kg", f"€ {summary['cost_per_kg']:,.0f}")
        st.dataframe(costed, use_container_width=True, hide_index=True)

    elif tool in ["Scenario Planner", "Margin Simulation", "Plant Comparison"]:
        scenarios = scenario_matrix(st.session_state.bom_df, st.session_state.assumptions)
        st.dataframe(scenarios, use_container_width=True, hide_index=True)
        st.line_chart(scenarios.set_index("Scenario")[["Total Cost €", "Sales Price €"]])

    elif tool in ["Routing Engine", "CNC Estimation", "Welding Estimation", "Paint & Coating"]:
        r1, r2, r3 = st.columns(3)
        r1.metric("Labor Rate", f"€ {st.session_state.assumptions['labor_rate_eur_h']:,.0f}/h")
        r2.metric("Machine Rate", f"€ {st.session_state.assumptions['machine_rate_eur_h']:,.0f}/h")
        r3.metric("Process Hours", f"{costed['Process h'].sum():,.1f} h")
        st.dataframe(costed[["Subsystem", "Part", "Type", "Process h", "Conversion Cost €"]], use_container_width=True, hide_index=True)

    elif tool in ["Quote Generator", "Download Center", "Release Package"]:
        text = quote_text(summary, st.session_state.assumptions)
        st.text_area("Quote summary", text, height=180)
        st.download_button("Download quote TXT", text, "cost_forge_quote_summary.txt", "text/plain", use_container_width=True)
        st.download_button("Download costed BOM CSV", costed.to_csv(index=False), "costed_bom.csv", "text/csv", use_container_width=True)
        st.download_button("Download costed BOM Excel", excel_bytes(costed, summary, st.session_state.assumptions), "costed_bom.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        st.download_button("Download quote PDF", pdf_bytes(summary, st.session_state.assumptions), "cost_forge_quote_summary.pdf", "application/pdf", use_container_width=True)

    elif tool == "System Health":
        st.dataframe(system_health(costed, summary), use_container_width=True, hide_index=True)
        st.success(f"System healthy — {APP_VERSION}")

    else:
        st.dataframe(subsystem_summary(costed), use_container_width=True, hide_index=True)
        st.success(f"BOM completeness: {summary['quote_coverage']} / {summary['bom_lines']} lines with supplier quote")

st.divider()
st.caption("Cost Forge 2.0 — Enterprise Manufacturing Cost Engineering Suite")
