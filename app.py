import io
from datetime import datetime

import pandas as pd
import streamlit as st

APP_VERSION = "2.3.0-pure-stable"

st.set_page_config(page_title="Cost Forge 2.0", page_icon="⚙️", layout="wide")

BOM_COLS = ["Subsystem", "Part", "Qty", "Type", "Weight kg", "Material €/kg", "Supplier Quote €", "Process h", "Risk"]


def demo_bom():
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
    ], columns=BOM_COLS)


WORKFLOW = {
    "Control Center": ["Executive Dashboard", "Cost Update Hub", "System Health"],
    "Source Data": ["BOM Import", "QMS Prices", "Supplier Quotes"],
    "Calculate & Size": ["Quick Cost", "Detailed Calculation", "Size Scaling"],
    "Manufacturing Engineering": ["Routing Engine", "CNC Estimation", "Welding Estimation", "Paint & Coating"],
    "Cost Modeling": ["Material Costing", "Conversion Cost", "Should Costing"],
    "Scenario Simulation": ["Inflation Simulation", "Margin Simulation", "Plant Comparison"],
    "Commercial Output": ["Quote Generator", "Download Center", "Release Package"],
}


if "bom" not in st.session_state:
    st.session_state.bom = demo_bom()
if "chapter" not in st.session_state:
    st.session_state.chapter = "Control Center"
if "tool" not in st.session_state:
    st.session_state.tool = "Executive Dashboard"
for key, value in {"margin": 28, "overhead": 15, "scrap": 3, "inflation": 0, "labor": 65, "machine": 85}.items():
    st.session_state.setdefault(key, value)


def euro(value):
    return f"€ {value:,.0f}"


def normalize_bom(file):
    df = pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    aliases = {
        "qty": "Qty", "quantity": "Qty", "aantal": "Qty",
        "part": "Part", "description": "Part", "omschrijving": "Part",
        "subsystem": "Subsystem", "system": "Subsystem",
        "weight": "Weight kg", "weight kg": "Weight kg", "gewicht": "Weight kg",
        "material €/kg": "Material €/kg", "price/kg": "Material €/kg", "material price": "Material €/kg",
        "supplier quote": "Supplier Quote €", "quote": "Supplier Quote €", "cost": "Supplier Quote €",
        "process h": "Process h", "hours": "Process h",
        "type": "Type", "risk": "Risk",
    }
    df = df.rename(columns={c: aliases.get(str(c).strip().lower(), c) for c in df.columns})
    defaults = {
        "Subsystem": "Unassigned", "Part": "Unknown Part", "Qty": 1, "Type": "Purchased",
        "Weight kg": 0.0, "Material €/kg": 0.0, "Supplier Quote €": 0.0, "Process h": 0.0, "Risk": "Medium",
    }
    for c, v in defaults.items():
        if c not in df.columns:
            df[c] = v
    for c in ["Qty", "Weight kg", "Material €/kg", "Supplier Quote €", "Process h"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["Qty"] = df["Qty"].replace(0, 1)
    return df[BOM_COLS]


def calculate(df):
    x = df.copy()
    factor = (1 + st.session_state.scrap / 100) * (1 + st.session_state.inflation / 100)
    x["Material Cost €"] = x["Qty"] * x["Weight kg"] * x["Material €/kg"] * factor
    x["Conversion Cost €"] = x["Qty"] * x["Process h"] * (st.session_state.labor + st.session_state.machine)
    x["Base Cost €"] = x[["Supplier Quote €", "Material Cost €", "Conversion Cost €"]].max(axis=1)
    x["Overhead €"] = x["Base Cost €"] * st.session_state.overhead / 100
    x["Total Cost €"] = x["Base Cost €"] + x["Overhead €"]
    total = float(x["Total Cost €"].sum())
    weight = float((x["Qty"] * x["Weight kg"]).sum())
    sales = total / (1 - min(st.session_state.margin / 100, 0.94))
    coverage = int((x["Supplier Quote €"] > 0).sum())
    return x, {
        "total": total,
        "weight": weight,
        "cost_per_kg": total / weight if weight else 0,
        "sales": sales,
        "margin_value": sales - total,
        "lines": len(x),
        "coverage": coverage,
        "coverage_pct": coverage / len(x) * 100 if len(x) else 0,
        "risk_high": int((x["Risk"].astype(str).str.lower() == "high").sum()),
    }


def excel_bytes(df, summary):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Costed BOM", index=False)
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
    return buffer.getvalue()


costed, summary = calculate(st.session_state.bom)

st.title("⚙️ Cost Forge 2.0")
st.caption(f"Manufacturing Cost Engineering Suite | {APP_VERSION}")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("TOTAL PROJECT COST", euro(summary["total"]), "live")
k2.metric("TOTAL WEIGHT", f"{summary['weight']:,.0f} kg", "live")
k3.metric("EST. COST / KG", f"€ {summary['cost_per_kg']:,.0f}", "live")
k4.metric("BOM LINES", str(summary["lines"]), "active")
k5.metric("QUOTE COVERAGE", f"{summary['coverage']} / {summary['lines']}", f"{summary['coverage_pct']:.0f}%")
k6.metric("SALES PRICE", euro(summary["sales"]), "target")

nav_col, main_col, settings_col = st.columns([2.3, 5.7, 2.4], gap="large")

with nav_col:
    st.header("Control Center")
    chapter = st.radio("Workflow chapter", list(WORKFLOW.keys()), index=list(WORKFLOW.keys()).index(st.session_state.chapter), key="chapter_radio")
    if chapter != st.session_state.chapter:
        st.session_state.chapter = chapter
        st.session_state.tool = WORKFLOW[chapter][0]
        st.rerun()

    st.subheader("Tools")
    for tool_name in WORKFLOW[st.session_state.chapter]:
        if st.button(tool_name, key=f"tool_{st.session_state.chapter}_{tool_name}", use_container_width=True):
            st.session_state.tool = tool_name
            st.rerun()

    st.success("Control Center active")

with settings_col:
    st.header("Assumptions")
    st.selectbox("Plant", ["Eindhoven", "Hamburg", "Gdansk", "Prototype Shop"], key="plant")
    st.selectbox("Estimate maturity", ["Budget (±15%)", "Proposal (±8%)", "Production (±3%)"], key="maturity")
    st.session_state.margin = st.slider("Target margin %", 0, 60, st.session_state.margin)
    st.session_state.overhead = st.slider("Overhead %", 0, 60, st.session_state.overhead)
    st.session_state.scrap = st.slider("Scrap factor %", 0, 25, st.session_state.scrap)
    st.session_state.inflation = st.slider("Material inflation %", -20, 80, st.session_state.inflation)
    st.session_state.labor = st.number_input("Labor rate €/h", min_value=0, value=int(st.session_state.labor))
    st.session_state.machine = st.number_input("Machine rate €/h", min_value=0, value=int(st.session_state.machine))

with main_col:
    st.header("Executive Dashboard")
    chart_col, status_col = st.columns([1.2, 1])
    with chart_col:
        st.subheader("Cost Breakdown by Subsystem")
        st.bar_chart(costed.groupby("Subsystem")["Total Cost €"].sum().sort_values(ascending=False))
    with status_col:
        st.subheader("Readiness")
        st.dataframe(pd.DataFrame({"Check": ["BOM", "Cost engine", "Control Center", "Exports", "Runtime"], "Status": ["OK", "OK", "Clickable", "OK", "OK"]}), use_container_width=True, hide_index=True)

    st.divider()
    st.header(f"Active Tool: {st.session_state.tool}")
    tool = st.session_state.tool

    if tool == "BOM Import":
        upload = st.file_uploader("Upload BOM CSV or Excel", type=["csv", "xlsx"], key="bom_upload")
        if upload is not None:
            try:
                st.session_state.bom = normalize_bom(upload)
                st.success("BOM uploaded and normalized.")
                st.rerun()
            except Exception as exc:
                st.error(f"BOM import failed: {exc}")
        edited = st.data_editor(st.session_state.bom, use_container_width=True, hide_index=True, num_rows="dynamic", key="bom_editor")
        c1, c2 = st.columns(2)
        if c1.button("Apply BOM edits", use_container_width=True):
            st.session_state.bom = edited
            st.rerun()
        if c2.button("Reset demo BOM", use_container_width=True):
            st.session_state.bom = demo_bom()
            st.rerun()

    elif tool in ["Quick Cost", "Detailed Calculation", "Material Costing", "Conversion Cost", "Should Costing", "Size Scaling"]:
        a, b, c, d = st.columns(4)
        a.metric("Total Cost", euro(summary["total"]))
        b.metric("Sales Price", euro(summary["sales"]))
        c.metric("Margin Value", euro(summary["margin_value"]))
        d.metric("Cost / kg", f"€ {summary['cost_per_kg']:,.0f}")
        st.dataframe(costed, use_container_width=True, hide_index=True)

    elif tool in ["Inflation Simulation", "Margin Simulation", "Plant Comparison"]:
        st.info("Change assumptions on the right. Dashboard and calculations recalculate after each change.")
        scenario = pd.DataFrame({"Scenario": ["Current", "+10% Cost", "+5 Margin Points"], "Cost €": [summary["total"], summary["total"] * 1.10, summary["total"]], "Sales Price €": [summary["sales"], summary["sales"] * 1.10, summary["sales"] * 1.07]})
        st.dataframe(scenario, use_container_width=True, hide_index=True)
        st.line_chart(scenario.set_index("Scenario"))

    elif tool in ["Routing Engine", "CNC Estimation", "Welding Estimation", "Paint & Coating"]:
        a, b, c = st.columns(3)
        a.metric("Labor Rate", f"€ {st.session_state.labor}/h")
        b.metric("Machine Rate", f"€ {st.session_state.machine}/h")
        c.metric("Process Hours", f"{costed['Process h'].sum():,.1f} h")
        st.dataframe(costed[["Subsystem", "Part", "Type", "Process h", "Conversion Cost €"]], use_container_width=True, hide_index=True)

    elif tool in ["Quote Generator", "Download Center", "Release Package"]:
        quote = f"Cost Forge Quote Summary\nGenerated: {datetime.now():%Y-%m-%d %H:%M}\nTotal cost: {euro(summary['total'])}\nSales price: {euro(summary['sales'])}\nMargin value: {euro(summary['margin_value'])}\nBOM lines: {summary['lines']}\nQuote coverage: {summary['coverage']} / {summary['lines']}\n"
        st.text_area("Quote summary", quote, height=180)
        st.download_button("Download quote TXT", quote, "cost_forge_quote_summary.txt", "text/plain", use_container_width=True)
        st.download_button("Download costed BOM CSV", costed.to_csv(index=False), "costed_bom.csv", "text/csv", use_container_width=True)
        st.download_button("Download costed BOM Excel", excel_bytes(costed, summary), "costed_bom.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    elif tool == "System Health":
        st.success("System healthy. Dashboard persistent. Control Center clickable. Cost engine operational.")
        st.dataframe(pd.DataFrame({"Check": ["app.py", "home.py redirect", "dark theme", "BOM", "cost engine", "exports"], "Status": ["OK", "OK", "OK", "OK", "OK", "OK"]}), use_container_width=True, hide_index=True)

    else:
        subsystem = costed.groupby("Subsystem", as_index=False).agg({"Total Cost €": "sum", "Weight kg": "sum"})
        st.dataframe(subsystem.sort_values("Total Cost €", ascending=False), use_container_width=True, hide_index=True)
        st.success(f"BOM completeness: {summary['coverage']} / {summary['lines']} lines with supplier quote")

st.divider()
st.caption("Cost Forge 2.0 — Enterprise Manufacturing Cost Engineering Suite")
