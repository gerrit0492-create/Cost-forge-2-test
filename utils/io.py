from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

WORKBOOK = Path("data") / "cost_forge.xlsx"

SHEET_MAP = {
    "bom":       "BOM",
    "materials": "Materials",
    "processes": "Processes",
    "quotes":    "Quotes",
    "actuals":   "Actuals",
}

SCHEMA_MATERIALS = {
    "material_id": "string",
    "description": "string",
    "commodity": "string",
    "price_eur_per_kg": "float64",
}
SCHEMA_PROCESSES = {
    "process_id": "string",
    "machine_rate_eur_h": "float64",
    "labor_rate_eur_h": "float64",
    "overhead_pct": "float64",
    "margin_pct": "float64",
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


# Keep for backwards compat (Download Center used it)
def paths() -> dict:
    return {k: WORKBOOK for k in SHEET_MAP}
