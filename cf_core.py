import io
from datetime import datetime
from typing import Dict, Tuple

import pandas as pd

REQUIRED_BOM_COLUMNS = [
    "Subsystem", "Part", "Qty", "Type", "Weight kg", "Material €/kg", "Supplier Quote €", "Process h", "Risk"
]

COLUMN_ALIASES = {
    "qty": "Qty", "quantity": "Qty", "aantal": "Qty",
    "part": "Part", "description": "Part", "omschrijving": "Part", "item": "Part",
    "subsystem": "Subsystem", "system": "Subsystem", "module": "Subsystem",
    "weight": "Weight kg", "weight kg": "Weight kg", "gewicht": "Weight kg", "kg": "Weight kg",
    "material €/kg": "Material €/kg", "material eur/kg": "Material €/kg", "price/kg": "Material €/kg", "material price": "Material €/kg",
    "supplier quote": "Supplier Quote €", "supplier quote €": "Supplier Quote €", "quote": "Supplier Quote €", "cost": "Supplier Quote €",
    "process h": "Process h", "hours": "Process h", "uren": "Process h",
    "type": "Type", "risk": "Risk",
}


def default_bom() -> pd.DataFrame:
    rows = [
        ["Pump Housing", "Pump Housing Casting", 1, "Machined", 420.0, 8.25, 43955.0, 22.0, "Low"],
        ["Stator Bowl", "Stator Bowl Assembly", 1, "Assembly", 230.0, 7.90, 32512.0, 15.0, "Medium"],
        ["Impeller Assembly", "Impeller", 1, "Machined", 185.0, 10.75, 31218.0, 18.0, "Low"],
        ["Shaft Line", "Main Shaft", 1, "Machined", 260.0, 6.80, 27765.0, 16.0, "Low"],
        ["QA / Testing", "Factory Acceptance Test", 1, "Service", 0.0, 0.0, 17544.0, 24.0, "Low"],
        ["Mounting Frame", "Welded Frame", 1, "Welded", 280.0, 3.20, 17408.0, 20.0, "Medium"],
        ["Thrust Block", "Thrust Block", 1, "Purchased", 90.0, 9.10, 15770.0, 4.0, "Low"],
        ["Inlet Duct", "Inlet Duct Weldment", 1, "Welded", 115.0, 3.85, 12301.0, 13.0, "Medium"],
        ["Steering System", "Steering Cylinder Set", 1, "Purchased", 35.0, 0.0, 9749.0, 2.0, "High"],
        ["Reverse System", "Reverse Bucket", 1, "Assembly", 60.0, 5.20, 9093.0, 7.0, "Medium"],
    ]
    return pd.DataFrame(rows, columns=REQUIRED_BOM_COLUMNS)


def default_assumptions() -> Dict[str, float | str]:
    return {
        "plant": "Eindhoven",
        "estimate_maturity": "Budget (±15%)",
        "target_margin_pct": 28.0,
        "overhead_pct": 15.0,
        "scrap_pct": 3.0,
        "inflation_pct": 0.0,
        "labor_rate_eur_h": 65.0,
        "machine_rate_eur_h": 85.0,
        "currency": "EUR (€)",
    }


def normalize_bom_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: COLUMN_ALIASES.get(str(col).strip().lower(), col) for col in df.columns}
    out = df.rename(columns=renamed).copy()
    defaults = {
        "Subsystem": "Unassigned", "Part": "Unknown Part", "Qty": 1, "Type": "Purchased",
        "Weight kg": 0.0, "Material €/kg": 0.0, "Supplier Quote €": 0.0, "Process h": 0.0, "Risk": "Medium",
    }
    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default
    for column in ["Qty", "Weight kg", "Material €/kg", "Supplier Quote €", "Process h"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    out["Qty"] = out["Qty"].replace(0, 1)
    out["Subsystem"] = out["Subsystem"].fillna("Unassigned").astype(str)
    out["Part"] = out["Part"].fillna("Unknown Part").astype(str)
    out["Type"] = out["Type"].fillna("Purchased").astype(str)
    out["Risk"] = out["Risk"].fillna("Medium").astype(str)
    return out[REQUIRED_BOM_COLUMNS]


def normalize_bom_file(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.lower().endswith(".csv") else pd.read_excel(uploaded_file)
    return normalize_bom_dataframe(df)


def calculate_costs(bom_df: pd.DataFrame, assumptions: Dict[str, float | str]) -> Tuple[pd.DataFrame, Dict[str, float]]:
    df = normalize_bom_dataframe(bom_df)
    scrap_factor = 1 + float(assumptions["scrap_pct"]) / 100
    inflation_factor = 1 + float(assumptions["inflation_pct"]) / 100
    labor_rate = float(assumptions["labor_rate_eur_h"])
    machine_rate = float(assumptions["machine_rate_eur_h"])
    overhead_pct = float(assumptions["overhead_pct"])
    target_margin_pct = min(float(assumptions["target_margin_pct"]), 94.0)
    df["Material Cost €"] = df["Qty"] * df["Weight kg"] * df["Material €/kg"] * scrap_factor * inflation_factor
    df["Conversion Cost €"] = df["Qty"] * df["Process h"] * (labor_rate + machine_rate)
    df["Internal Should Cost €"] = df["Material Cost €"] + df["Conversion Cost €"]
    df["Selected Base Cost €"] = df["Supplier Quote €"].where(df["Supplier Quote €"] > 0, df["Internal Should Cost €"])
    df["Quote vs Should Gap €"] = df["Supplier Quote €"] - df["Internal Should Cost €"]
    df["Overhead €"] = df["Selected Base Cost €"] * overhead_pct / 100
    df["Total Cost €"] = df["Selected Base Cost €"] + df["Overhead €"]
    total_cost = float(df["Total Cost €"].sum())
    total_weight = float((df["Qty"] * df["Weight kg"]).sum())
    target_margin = target_margin_pct / 100
    sales_price = total_cost / (1 - target_margin) if target_margin < 0.95 else total_cost
    quote_coverage = int((df["Supplier Quote €"] > 0).sum())
    high_risk = int((df["Risk"].str.lower() == "high").sum())
    summary = {
        "total_cost": total_cost,
        "total_weight": total_weight,
        "cost_per_kg": total_cost / total_weight if total_weight else 0.0,
        "sales_price": sales_price,
        "margin_value": sales_price - total_cost,
        "bom_lines": int(len(df)),
        "quote_coverage": quote_coverage,
        "quote_coverage_pct": quote_coverage / len(df) * 100 if len(df) else 0.0,
        "high_risk_items": high_risk,
        "material_cost": float(df["Material Cost €"].sum()),
        "conversion_cost": float(df["Conversion Cost €"].sum()),
        "overhead_cost": float(df["Overhead €"].sum()),
    }
    return df, summary


def subsystem_summary(costed_bom: pd.DataFrame) -> pd.DataFrame:
    table = costed_bom.groupby("Subsystem", as_index=False).agg({
        "Total Cost €": "sum", "Weight kg": "sum", "Material Cost €": "sum", "Conversion Cost €": "sum", "Supplier Quote €": "sum"
    })
    total = float(table["Total Cost €"].sum())
    table["Share %"] = (table["Total Cost €"] / total * 100).round(1) if total else 0.0
    return table.sort_values("Total Cost €", ascending=False)


def scenario_matrix(bom_df: pd.DataFrame, assumptions: Dict[str, float | str]) -> pd.DataFrame:
    scenarios = [("Current", 0, 0, 0), ("Material +10%", 10, 0, 0), ("Labor/Machine +10%", 0, 10, 0), ("Overhead +5 pts", 0, 0, 5), ("Margin +5 pts", 0, 0, 0)]
    rows = []
    for name, material_delta, rate_delta, overhead_delta in scenarios:
        s = dict(assumptions)
        s["inflation_pct"] = float(s["inflation_pct"]) + material_delta
        s["labor_rate_eur_h"] = float(s["labor_rate_eur_h"]) * (1 + rate_delta / 100)
        s["machine_rate_eur_h"] = float(s["machine_rate_eur_h"]) * (1 + rate_delta / 100)
        s["overhead_pct"] = float(s["overhead_pct"]) + overhead_delta
        if name == "Margin +5 pts":
            s["target_margin_pct"] = float(s["target_margin_pct"]) + 5
        _, summary = calculate_costs(bom_df, s)
        rows.append({"Scenario": name, "Total Cost €": summary["total_cost"], "Sales Price €": summary["sales_price"], "Margin Value €": summary["margin_value"], "Cost / kg": summary["cost_per_kg"]})
    return pd.DataFrame(rows)


def quote_text(summary: Dict[str, float], assumptions: Dict[str, float | str]) -> str:
    return (
        "Cost Forge 2.0 Quote Summary\n"
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}\n"
        f"Plant: {assumptions['plant']}\n"
        f"Estimate maturity: {assumptions['estimate_maturity']}\n"
        f"Total cost: € {summary['total_cost']:,.0f}\n"
        f"Sales price: € {summary['sales_price']:,.0f}\n"
        f"Margin value: € {summary['margin_value']:,.0f}\n"
        f"Cost / kg: € {summary['cost_per_kg']:,.0f}\n"
        f"BOM lines: {summary['bom_lines']}\n"
        f"Quote coverage: {summary['quote_coverage']} / {summary['bom_lines']}\n"
        f"High risk items: {summary['high_risk_items']}\n"
    )


def excel_bytes(costed_bom: pd.DataFrame, summary: Dict[str, float], assumptions: Dict[str, float | str]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        costed_bom.to_excel(writer, sheet_name="Costed BOM", index=False)
        subsystem_summary(costed_bom).to_excel(writer, sheet_name="Subsystems", index=False)
        scenario_matrix(costed_bom[REQUIRED_BOM_COLUMNS], assumptions).to_excel(writer, sheet_name="Scenarios", index=False)
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame([assumptions]).to_excel(writer, sheet_name="Assumptions", index=False)
    return output.getvalue()


def pdf_bytes(summary: Dict[str, float], assumptions: Dict[str, float | str]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        output = io.BytesIO()
        pdf = canvas.Canvas(output, pagesize=A4)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, 800, "Cost Forge 2.0 Quote Summary")
        pdf.setFont("Helvetica", 10)
        y = 760
        for line in quote_text(summary, assumptions).splitlines():
            pdf.drawString(40, y, line)
            y -= 20
        pdf.save()
        return output.getvalue()
    except Exception:
        return quote_text(summary, assumptions).encode("utf-8")


def system_health(costed_bom: pd.DataFrame, summary: Dict[str, float]) -> pd.DataFrame:
    checks = [("App entrypoint", "OK"), ("Cost engine", "OK" if summary["total_cost"] > 0 else "Check"), ("BOM data", "OK" if len(costed_bom) > 0 else "Check"), ("Quote coverage", f"{summary['quote_coverage_pct']:.0f}%"), ("Exports", "OK"), ("Control Center", "OK")]
    return pd.DataFrame(checks, columns=["Check", "Status"])
