from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

WORKBOOK = Path("data") / "cost_forge.xlsx"

SHEET_MAP = {
    "bom":        "BOM",
    "materials":  "Materials",
    "processes":  "Processes",
    "quotes":     "Quotes",
    "actuals":    "Actuals",
    "transport":  "Transport",
    "nre":        "NRE",
    "risk":       "Risk",
    "escalation":    "Escalation",
    "outbound":      "Outbound",
    "milestones":    "Milestones",
    "cost_timeline": "CostTimeline",
    "change_orders": "ChangeOrders",
}

SCHEMA_MATERIALS = {
    "material_id":       "string",
    "description":       "string",
    "commodity":         "string",
    "price_eur_per_kg":  "float64",
    "moq_kg":            "float64",   # minimum order quantity (kg)
    "hs_code":           "string",    # harmonised tariff code e.g. "8413.50"
    "lead_supplier":     "string",    # Primary / Sole source / Approved / Conditional
    "supplier":          "string",    # preferred supplier name (info only)
}
SCHEMA_PROCESSES = {
    "process_id":                "string",
    "machine_rate_eur_h":        "float64",
    "labor_rate_eur_h":          "float64",
    "overhead_pct":              "float64",
    "margin_pct":                "float64",
    "tooling_consumable_eur_h":  "float64",  # cutting tools / inserts per runtime hour
    "rework_pct":                "float64",  # rework provision as fraction of process cost
    "energy_kw":                 "float64",  # machine power draw (kW)
    "subcontract_markup_pct":    "float64",  # markup on subcontracted work
    "labour_grade":              "string",   # e.g. "Senior machinist", "Apprentice"
}
SCHEMA_BOM = {
    "line_id":               "string",
    "part_name":             "string",
    "material_id":           "string",
    "qty":                   "Int64",
    "mass_kg":               "float64",
    "process_route":         "string",
    "runtime_h":             "float64",
    "setup_h":               "float64",
    "yield_factor":          "float64",
    "make_buy":              "string",
    "cost_type":             "string",
    "subcontract_price_eur": "float64",
    "scale_exp":             "float64",
}
SCHEMA_QUOTES = {
    "supplier": "string",
    "material_id": "string",
    "price_eur_per_kg": "float64",
    "lead_time_days": "Int64",
    "valid_until": "string",
    "preferred": "Int64",
}
SCHEMA_ACTUALS = {
    "line_id":                "string",
    "actual_material_cost":   "float64",
    "actual_process_cost":    "float64",
    "actual_total_cost":      "float64",
    "notes":                  "string",
    "status":                 "string",
}


def _apply_schema(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        if dtype == "Int64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif dtype == "float64":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = df[col].astype(dtype)
    return df


def _read(sheet_key: str, schema: dict) -> pd.DataFrame:
    if WORKBOOK.exists():
        df = pd.read_excel(WORKBOOK, sheet_name=SHEET_MAP[sheet_key])
    else:
        csv = Path("data") / f"{sheet_key}.csv"
        if not csv.exists():
            raise FileNotFoundError(f"Neither {WORKBOOK} nor {csv} found")
        df = pd.read_csv(csv)
    return _apply_schema(df, schema)


def save_sheet(df: pd.DataFrame, sheet_key: str) -> None:
    """Write df to the named sheet in cost_forge.xlsx, preserving other sheets."""
    sheet = SHEET_MAP[sheet_key]
    if WORKBOOK.exists():
        with pd.ExcelWriter(WORKBOOK, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
            df.to_excel(w, sheet_name=sheet, index=False)
    else:
        with pd.ExcelWriter(WORKBOOK, engine="openpyxl") as w:
            df.to_excel(w, sheet_name=sheet, index=False)


def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    """Serialise a single DataFrame to Excel bytes for st.download_button."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def workbook_bytes() -> bytes:
    """Return the full workbook as bytes for download."""
    return WORKBOOK.read_bytes()


# ── Public loaders ────────────────────────────────────────────────────────────

def load_materials() -> pd.DataFrame:
    return _read("materials", SCHEMA_MATERIALS)


def load_processes() -> pd.DataFrame:
    return _read("processes", SCHEMA_PROCESSES)


def load_bom() -> pd.DataFrame:
    return _read("bom", SCHEMA_BOM)


def load_quotes() -> pd.DataFrame:
    return _read("quotes", SCHEMA_QUOTES)


def load_actuals() -> pd.DataFrame:
    try:
        return _read("actuals", SCHEMA_ACTUALS)
    except Exception:
        return pd.DataFrame(columns=list(SCHEMA_ACTUALS.keys()))


def load_transport() -> pd.DataFrame:
    """Load inbound transport rates (Transport sheet)."""
    from utils.transport import SCHEMA_TRANSPORT, default_transport_df
    try:
        return _read("transport", SCHEMA_TRANSPORT)
    except Exception:
        return default_transport_df()


def load_outbound() -> pd.DataFrame:
    """Load outbound shipping routes (Outbound sheet)."""
    from utils.transport import SCHEMA_OUTBOUND, default_outbound_df
    try:
        return _read("outbound", SCHEMA_OUTBOUND)
    except Exception:
        return default_outbound_df()


def load_nre() -> pd.DataFrame:
    """Load NRE / engineering cost items (NRE sheet)."""
    from utils.nre import SCHEMA_NRE, default_nre_df
    try:
        return _read("nre", SCHEMA_NRE)
    except Exception:
        return default_nre_df()


def load_risk() -> pd.DataFrame:
    """Load risk register (Risk sheet)."""
    from utils.escalation import SCHEMA_RISK, default_risk_df
    try:
        return _read("risk", SCHEMA_RISK)
    except Exception:
        return default_risk_df()


def load_escalation() -> pd.DataFrame:
    """Load escalation indices (Escalation sheet)."""
    from utils.escalation import SCHEMA_ESCALATION, default_escalation_df
    try:
        return _read("escalation", SCHEMA_ESCALATION)
    except Exception:
        return default_escalation_df()


def load_milestones() -> pd.DataFrame:
    """Load milestone payment schedule (Milestones sheet)."""
    from utils.contract import SCHEMA_MILESTONES, default_milestones
    try:
        return _read("milestones", SCHEMA_MILESTONES)
    except Exception:
        return pd.DataFrame(columns=list(SCHEMA_MILESTONES.keys()))


def load_cost_timeline() -> pd.DataFrame:
    """Load cost outflow timeline (CostTimeline sheet)."""
    from utils.contract import SCHEMA_COST_TIMELINE
    try:
        return _read("cost_timeline", SCHEMA_COST_TIMELINE)
    except Exception:
        return pd.DataFrame(columns=list(SCHEMA_COST_TIMELINE.keys()))


def load_change_orders() -> pd.DataFrame:
    """Load change order register (ChangeOrders sheet)."""
    from utils.change_orders import SCHEMA_CHANGE_ORDERS
    try:
        return _read("change_orders", SCHEMA_CHANGE_ORDERS)
    except Exception:
        return pd.DataFrame(columns=list(SCHEMA_CHANGE_ORDERS.keys()))


# Keep for backwards compat (Download Center used it)
def paths() -> dict:
    return {k: WORKBOOK for k in SHEET_MAP}
