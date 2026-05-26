import streamlit as st

from cf_core import (
    REQUIRED_BOM_COLUMNS,
    calculate_costs,
    default_assumptions,
    default_bom,
    excel_bytes,
    normalize_bom_dataframe,
    normalize_bom_file,
    pdf_bytes,
    quote_text,
    scenario_matrix,
    subsystem_summary,
    system_health,
)

APP_VERSION = "4.2-control-tower"

st.set_page_config(page_title="Cost Forge Control Tower", page_icon="⚙️", layout="wide")

if "bom_df" not in st.session_state:
    st.session_state.bom_df = default_bom()
if "page" not in st.session_state:
    st.session_state.page = "Control Tower"

for key, value in default_assumptions().items():
    st.session_state.setdefault(key, value)


def euro(value):
    return f"€ {value:,.0f}"


def assumptions():
    return {
        "plant": st.session_state.plant,
        "estimate_maturity": st.session_state.estimate_maturity,
        "target_margin_pct": float(st.session_state.target_margin_pct),
        "overhead_pct": float(st.session_state.overhead_pct),
        "scrap_pct": float(st.session_state.scrap_pct),
        "inflation_pct": float(st.session_state.inflation_pct),
        "labor_rate_eur_h": float(st.session_state.labor_rate_eur_h),
        "machine_rate_eur_h": float(st.session_state.machine_rate_eur_h),
        "currency": st.session_state.currency,
    }


def go(page):
    st.session_state.page = page


def top_gap_table(costed):
    cols = ["Subsystem", "Part", "Supplier Quote €", "Internal Should Cost €", "Quote vs Should Gap €", "Risk"]
    return costed[cols].sort_values("Quote vs Should Gap €", ascending=False).head(10)


def render_kpi_strip(summary):
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Project Cost", euro(summary["total_cost"]))
    c2.metric("Sales Price", euro(summary["sales_price"]))
    c3.metric("Margin Value", euro(summary["margin_value"]))
    c4.metric("Cost / kg", f"€ {summary['cost_per_kg']:,.0f}")
    c5.metric("Quote Coverage", f"{summary['quote_coverage_pct']:.0f}%")
    c6.metric("High Risk Items", str(summary["high_risk_items"]))


def render_navigation():
    pages = [
        "Control Tower",
        "BOM Factory",
        "Cost Engine",
        "Manufacturing Model",
        "Scenario Lab",
        "Supplier Radar",
        "Quote Room",
        "System Health",
    ]
    st.subheader("Cost Engineering Flow")
    for page in pages:
        if st.button(page, key=f"nav_{page}", use_container_width=True):
            go(page)
            st.rerun()


def render_assumptions():
    st.subheader("Live Assumptions")
    st.selectbox("Plant", ["Eindhoven", "Hamburg", "Gdansk", "Prototype Shop"], key="plant")
    st.selectbox("Estimate maturity", ["Budget (±15%)", "Proposal (±8%)", "Production (±3%)"], key="estimate_maturity")
    st.slider("Target margin %", 0, 60, key="target_margin_pct")
    st.slider("Overhead %", 0, 60, key="overhead_pct")
    st.slider("Scrap factor %", 0, 25, key="scrap_pct")
    st.slider("Material inflation %", -20, 80, key="inflation_pct")
    st.number_input("Labor rate €/h", min_value=0.0, step=5.0, key="labor_rate_eur_h")
    st.number_input("Machine rate €/h", min_value=0.0, step=5.0, key="machine_rate_eur_h")


def render_dashboard(costed, summary):
    st.header("Cost Engineer Dashboard")
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Cost Pareto by Subsystem")
        st.bar_chart(costed.groupby("Subsystem")["Total Cost €"].sum().sort_values(ascending=False))
    with right:
        st.subheader("Decision Readiness")
        st.dataframe(system_health(costed, summary), use_container_width=True, hide_index=True)
        st.info(
            f"BOM lines: {summary['bom_lines']} | Coverage: {summary['quote_coverage_pct']:.0f}% | "
            f"Weight: {summary['total_weight']:,.0f} kg | Plant: {st.session_state.plant}"
        )
    m1, m2, m3 = st.columns(3)
    m1.metric("Material Cost", euro(summary["material_cost"]))
    m2.metric("Conversion Cost", euro(summary["conversion_cost"]))
    m3.metric("Overhead Cost", euro(summary["overhead_cost"]))


def render_workbench(costed, summary, ass):
    page = st.session_state.page
    st.divider()
    st.header(page)

    if page == "Control Tower":
        a, b = st.columns(2)
        with a:
            st.subheader("Top Cost Drivers")
            st.dataframe(subsystem_summary(costed), use_container_width=True, hide_index=True)
        with b:
            st.subheader("Quote Gap / Risk Watchlist")
            st.dataframe(top_gap_table(costed), use_container_width=True, hide_index=True)
        st.success("Start here: review the biggest subsystem, supplier gap and high-risk lines before quoting.")
        return

    if page == "BOM Factory":
        file = st.file_uploader("Upload BOM CSV or Excel", type=["csv", "xlsx"])
        if file is not None:
            try:
                st.session_state.bom_df = normalize_bom_file(file)
                st.success("BOM uploaded and normalized.")
                st.rerun()
            except Exception as exc:
                st.error(f"BOM import failed: {exc}")
        edited = st.data_editor(st.session_state.bom_df, use_container_width=True, hide_index=True, num_rows="dynamic")
        c1, c2 = st.columns(2)
        if c1.button("Apply BOM edits", use_container_width=True):
            st.session_state.bom_df = normalize_bom_dataframe(edited[REQUIRED_BOM_COLUMNS])
            st.rerun()
        if c2.button("Reset demo BOM", use_container_width=True):
            st.session_state.bom_df = default_bom()
            st.rerun()
        return

    if page == "Cost Engine":
        st.dataframe(costed, use_container_width=True, hide_index=True)
        return

    if page == "Manufacturing Model":
        c1, c2, c3 = st.columns(3)
        c1.metric("Labor Rate", f"€ {ass['labor_rate_eur_h']:,.0f}/h")
        c2.metric("Machine Rate", f"€ {ass['machine_rate_eur_h']:,.0f}/h")
        c3.metric("Process Hours", f"{costed['Process h'].sum():,.1f} h")
        st.dataframe(costed[["Subsystem", "Part", "Type", "Process h", "Conversion Cost €"]], use_container_width=True, hide_index=True)
        return

    if page == "Scenario Lab":
        scenarios = scenario_matrix(st.session_state.bom_df, ass)
        st.dataframe(scenarios, use_container_width=True, hide_index=True)
        st.line_chart(scenarios.set_index("Scenario")[["Total Cost €", "Sales Price €", "Margin Value €"]])
        return

    if page == "Supplier Radar":
        st.dataframe(top_gap_table(costed), use_container_width=True, hide_index=True)
        st.bar_chart(costed.set_index("Part")["Quote vs Should Gap €"].sort_values(ascending=False).head(10))
        return

    if page == "Quote Room":
        text = quote_text(summary, ass)
        st.text_area("Quote summary", text, height=180)
        st.download_button("Download TXT", text, "cost_forge_quote_summary.txt", "text/plain", use_container_width=True)
        st.download_button("Download CSV", costed.to_csv(index=False), "costed_bom.csv", "text/csv", use_container_width=True)
        st.download_button("Download Excel", excel_bytes(costed, summary, ass), "costed_bom.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        st.download_button("Download PDF", pdf_bytes(summary, ass), "cost_forge_quote_summary.pdf", "application/pdf", use_container_width=True)
        return

    if page == "System Health":
        st.dataframe(system_health(costed, summary), use_container_width=True, hide_index=True)
        st.success(f"Running {APP_VERSION}. home.py is the active Cost Forge entrypoint.")


ass = assumptions()
costed, summary = calculate_costs(st.session_state.bom_df, ass)

st.title("⚙️ Cost Forge Control Tower")
st.caption(f"Manufacturing Cost Engineering Dashboard | {APP_VERSION}")
render_kpi_strip(summary)

nav, main, side = st.columns([2.2, 5.8, 2.4], gap="large")
with nav:
    render_navigation()
with side:
    render_assumptions()
with main:
    ass = assumptions()
    costed, summary = calculate_costs(st.session_state.bom_df, ass)
    render_dashboard(costed, summary)
    render_workbench(costed, summary, ass)

st.caption("Cost Forge Control Tower — production cost engineering cockpit")
