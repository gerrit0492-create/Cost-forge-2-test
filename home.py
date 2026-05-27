import streamlit as st
import pandas as pd

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

APP_VERSION = "5.0-marine-jet-selector"

JET_DATABASE = pd.DataFrame([
    [510,1700,1665,1400],
    [570,2100,1490,1750],
    [640,2700,1330,2400],
    [720,3400,1180,2850],
    [810,4300,1050,3600],
    [900,5200,980,4300],
    [1000,6200,920,5200],
    [1100,7300,860,6100],
    [1200,8600,800,7200],
    [1300,9800,760,8500],
    [1400,11200,710,9800],
    [1500,12800,670,11200],
    [1640,14500,620,12800],
    [1720,15800,590,14200],
    [1880,17500,540,16000],
], columns=["Jet Size","Max Power kW","Max RPM","Mass kg"])

st.set_page_config(page_title="Cost Forge Marine", page_icon="⚓", layout="wide")

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


def render_navigation():
    pages = [
        "Control Tower",
        "Marine Jet Selector",
        "BOM Factory",
        "Cost Engine",
        "Scenario Lab",
        "Supplier Radar",
        "Quote Room",
        "System Health",
    ]

    st.markdown("## ⚓ Marine Cost Suite")

    for page in pages:
        if st.button(page, use_container_width=True):
            go(page)
            st.rerun()


def render_assumptions():
    st.subheader("Commercial Assumptions")
    st.selectbox("Plant", ["Eindhoven", "Hamburg", "Gdansk", "Prototype Shop"], key="plant")
    st.slider("Target Margin %", 0, 60, key="target_margin_pct")
    st.slider("Overhead %", 0, 60, key="overhead_pct")
    st.number_input("Labor €/h", min_value=0.0, step=5.0, key="labor_rate_eur_h")
    st.number_input("Machine €/h", min_value=0.0, step=5.0, key="machine_rate_eur_h")


def render_dashboard(costed, summary):
    st.markdown("## Cost Engineering Command Center")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Project Cost", euro(summary["total_cost"]))
    c2.metric("Sales Price", euro(summary["sales_price"]))
    c3.metric("Margin", euro(summary["margin_value"]))
    c4.metric("High Risk", summary["high_risk_items"])

    left, right = st.columns([1.5,1])

    with left:
        st.markdown("### Cost Breakdown")
        st.bar_chart(costed.groupby("Subsystem")["Total Cost €"].sum())

    with right:
        st.markdown("### Health Status")
        st.dataframe(system_health(costed, summary), use_container_width=True, hide_index=True)


def render_jet_selector():
    st.markdown("## 🚤 Marine Waterjet Selector")

    a,b,c = st.columns(3)

    with a:
        power = st.number_input("Installed Power per Jet (kW)", value=2500)
    with b:
        speed = st.number_input("Design Speed (knots)", value=35)
    with c:
        vessel_length = st.number_input("Waterline Length (m)", value=50)

    correction_factor = round(1 + ((vessel_length - 20) / 100), 2)
    corrected_power = power * correction_factor

    recommended = JET_DATABASE[JET_DATABASE["Max Power kW"] >= corrected_power].head(1)

    if not recommended.empty:
        row = recommended.iloc[0]

        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Recommended Jet", f"{int(row['Jet Size'])}")
        m2.metric("Corrected Power", f"{corrected_power:,.0f} kW")
        m3.metric("Max RPM", f"{int(row['Max RPM'])}")
        m4.metric("Dry Mass", f"{int(row['Mass kg'])} kg")

        st.success(f"Recommended jet size based on Wärtsilä-style sizing logic: {int(row['Jet Size'])}")

    st.markdown("### Full Jet Selection Matrix")
    st.dataframe(JET_DATABASE, use_container_width=True, hide_index=True)

    st.markdown("### Power vs Jet Size")
    st.line_chart(JET_DATABASE.set_index("Jet Size")[["Max Power kW"]])


def render_workbench(costed, summary, ass):
    page = st.session_state.page

    if page == "Control Tower":
        st.markdown("### Top Cost Drivers")
        st.dataframe(subsystem_summary(costed), use_container_width=True, hide_index=True)
        return

    if page == "Marine Jet Selector":
        render_jet_selector()
        return

    if page == "BOM Factory":
        file = st.file_uploader("Upload BOM CSV or Excel", type=["csv", "xlsx"])

        if file is not None:
            st.session_state.bom_df = normalize_bom_file(file)
            st.success("Marine BOM uploaded")
            st.rerun()

        edited = st.data_editor(st.session_state.bom_df, use_container_width=True, hide_index=True, num_rows="dynamic")

        if st.button("Apply BOM"):
            st.session_state.bom_df = normalize_bom_dataframe(edited[REQUIRED_BOM_COLUMNS])
            st.rerun()

        st.dataframe(pd.read_csv("data/marine_waterjet_bom_seed.csv"), use_container_width=True)
        return

    if page == "Cost Engine":
        st.dataframe(costed, use_container_width=True, hide_index=True)
        return

    if page == "Scenario Lab":
        scenarios = scenario_matrix(st.session_state.bom_df, ass)
        st.dataframe(scenarios, use_container_width=True, hide_index=True)
        return

    if page == "Supplier Radar":
        gap_cols = ["Subsystem", "Part", "Supplier Quote €", "Internal Should Cost €", "Quote vs Should Gap €"]
        st.dataframe(costed[gap_cols], use_container_width=True, hide_index=True)
        return

    if page == "Quote Room":
        text = quote_text(summary, ass)
        st.text_area("Quote", text, height=180)

        st.download_button("Download Excel", excel_bytes(costed, summary, ass), "marine_cost_model.xlsx")
        st.download_button("Download PDF", pdf_bytes(summary, ass), "marine_quote.pdf")
        return

    if page == "System Health":
        st.dataframe(system_health(costed, summary), use_container_width=True, hide_index=True)
        st.success(APP_VERSION)


ass = assumptions()
costed, summary = calculate_costs(st.session_state.bom_df, ass)

st.title("⚓ Cost Forge Marine")
st.caption("Advanced Marine Waterjet Cost Engineering Platform")

render_dashboard(costed, summary)

nav, main, side = st.columns([1.5,5,2])

with nav:
    render_navigation()

with main:
    render_workbench(costed, summary, ass)

with side:
    render_assumptions()
