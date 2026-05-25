import pandas as pd
import streamlit as st


def money(value):
    return f"EUR {value:,.2f}"


def render_scenario_planner():
    st.title("Scenario Planner")
    st.caption("Live cost and margin simulation with persistent Streamlit widget keys.")

    defaults = {
        "scenario_material_cost": 1000.0,
        "scenario_routing_cost": 500.0,
        "scenario_overhead_pct": 15.0,
        "scenario_sales_price": 2500.0,
        "scenario_material_delta": 0,
        "scenario_routing_delta": 0,
        "scenario_overhead_delta": 0,
        "scenario_sales_delta": 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    st.subheader("Baseline")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        material_cost = st.number_input("Material cost", min_value=0.0, step=50.0, key="scenario_material_cost")
    with col2:
        routing_cost = st.number_input("Routing cost", min_value=0.0, step=25.0, key="scenario_routing_cost")
    with col3:
        overhead_pct = st.number_input("Overhead percent", min_value=0.0, max_value=100.0, step=1.0, key="scenario_overhead_pct")
    with col4:
        sales_price = st.number_input("Sales price", min_value=0.0, step=50.0, key="scenario_sales_price")

    st.subheader("Scenario sliders")
    left, right = st.columns(2)

    with left:
        material_delta = st.slider("Material price change percent", -50, 100, key="scenario_material_delta")
        routing_delta = st.slider("Routing cost change percent", -50, 100, key="scenario_routing_delta")

    with right:
        overhead_delta = st.slider("Overhead change percent", -50, 100, key="scenario_overhead_delta")
        sales_delta = st.slider("Sales price change percent", -50, 100, key="scenario_sales_delta")

    base_subtotal = material_cost + routing_cost
    base_total = base_subtotal * (1 + overhead_pct / 100)
    base_margin = sales_price - base_total
    base_margin_pct = (base_margin / sales_price * 100) if sales_price else 0.0

    scenario_material = material_cost * (1 + material_delta / 100)
    scenario_routing = routing_cost * (1 + routing_delta / 100)
    scenario_overhead_pct = max(0.0, overhead_pct * (1 + overhead_delta / 100))
    scenario_sales = sales_price * (1 + sales_delta / 100)

    scenario_total = (scenario_material + scenario_routing) * (1 + scenario_overhead_pct / 100)
    scenario_margin = scenario_sales - scenario_total
    scenario_margin_pct = (scenario_margin / scenario_sales * 100) if scenario_sales else 0.0

    st.subheader("Live result")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total cost", money(scenario_total), money(scenario_total - base_total))
    m2.metric("Margin value", money(scenario_margin), money(scenario_margin - base_margin))
    m3.metric("Margin percent", f"{scenario_margin_pct:.1f}%", f"{scenario_margin_pct - base_margin_pct:.1f}%")
    m4.metric("Sales price", money(scenario_sales), f"{sales_delta}%")

    table = pd.DataFrame([
        ["Material", material_cost, scenario_material, scenario_material - material_cost],
        ["Routing", routing_cost, scenario_routing, scenario_routing - routing_cost],
        ["Overhead percent", overhead_pct, scenario_overhead_pct, scenario_overhead_pct - overhead_pct],
        ["Total cost", base_total, scenario_total, scenario_total - base_total],
        ["Sales price", sales_price, scenario_sales, scenario_sales - sales_price],
        ["Margin", base_margin, scenario_margin, scenario_margin - base_margin],
    ], columns=["Item", "Baseline", "Scenario", "Delta"])

    st.dataframe(table, use_container_width=True, hide_index=True)
    st.bar_chart(pd.DataFrame({"Baseline": [base_total, base_margin], "Scenario": [scenario_total, scenario_margin]}, index=["Total cost", "Margin"]))

    st.session_state.scenario_values = {
        "total_cost": scenario_total,
        "margin": scenario_margin,
        "margin_percent": scenario_margin_pct,
        "sales_price": scenario_sales,
    }
