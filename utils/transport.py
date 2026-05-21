"""
Transport & Logistics cost module.
Handles inbound freight, packaging, import duties, and outbound shipping.
"""
from __future__ import annotations

import pandas as pd

SCHEMA_TRANSPORT = {
    "material_id":      "string",
    "supplier":         "string",
    "freight_mode":     "string",   # AIR / SEA / ROAD / EXPRESS / LOCAL
    "inbound_eur_kg":   "float64",  # freight cost per kg (inbound from supplier)
    "min_freight_eur":  "float64",  # minimum freight charge per shipment
    "packaging_eur_kg": "float64",  # packaging / crating per kg
    "duties_pct":       "float64",  # import duty as fraction of material value (e.g. 0.03 = 3%)
    "notes":            "string",
}

SCHEMA_OUTBOUND = {
    "route_id":          "string",
    "destination":       "string",
    "freight_mode":      "string",
    "rate_eur_kg":       "float64",
    "min_charge_eur":    "float64",
    "insurance_pct":     "float64",  # of shipment value
    "handling_eur":      "float64",
    "incoterms":         "string",   # EXW, FCA, CPT, CIP, DAP, DDP
    "transit_days":      "float64",
    "notes":             "string",
}

FREIGHT_MODES = ["ROAD", "SEA", "AIR", "EXPRESS", "LOCAL", "RAIL"]
INCOTERMS = ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]


def default_transport_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(SCHEMA_TRANSPORT.keys()))


def default_outbound_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(SCHEMA_OUTBOUND.keys()))


def compute_inbound_costs(
    cost_df: pd.DataFrame,
    transport_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge transport rates onto cost_df and compute per-line inbound freight,
    packaging and duties costs.

    Adds columns:
        inbound_freight_eur  — freight + packaging per line
        duties_eur           — import duty on material value
    """
    df = cost_df.copy()
    df["inbound_freight_eur"] = 0.0
    df["duties_eur"] = 0.0

    if transport_df.empty:
        return df

    t = transport_df[
        ["material_id", "inbound_eur_kg", "min_freight_eur",
         "packaging_eur_kg", "duties_pct"]
    ].copy()
    for col in ["inbound_eur_kg", "min_freight_eur", "packaging_eur_kg", "duties_pct"]:
        t[col] = pd.to_numeric(t[col], errors="coerce").fillna(0)

    merged = df.merge(t, on="material_id", how="left")

    qty   = pd.to_numeric(merged["qty"],     errors="coerce").fillna(1)
    mass  = pd.to_numeric(merged["mass_kg"], errors="coerce").fillna(0)
    line_mass = qty * mass

    eur_kg  = merged["inbound_eur_kg"].fillna(0)
    min_f   = merged["min_freight_eur"].fillna(0)
    pkg_kg  = merged["packaging_eur_kg"].fillna(0)
    duties  = merged["duties_pct"].fillna(0)

    raw_freight = line_mass * eur_kg
    # Apply minimum charge only where there is a rate and mass
    has_rate = (eur_kg > 0) & (line_mass > 0)
    freight  = raw_freight.where(~has_rate | (raw_freight >= min_f), min_f).where(has_rate, 0)
    packaging = line_mass * pkg_kg

    merged["inbound_freight_eur"] = (freight + packaging).fillna(0)
    merged["duties_eur"] = (merged["material_cost"] * duties).fillna(0)

    # Drop the helper columns from transport
    drop_cols = ["inbound_eur_kg", "min_freight_eur", "packaging_eur_kg", "duties_pct"]
    merged = merged.drop(columns=[c for c in drop_cols if c in merged.columns])
    return merged


def outbound_cost(
    total_mass_kg: float,
    sell_value: float,
    outbound: pd.Series,
) -> dict:
    """
    Compute outbound shipping cost from a single outbound route row (pd.Series).
    Returns dict with keys: freight, insurance, handling, total.
    """
    rate     = float(outbound.get("rate_eur_kg", 0) or 0)
    min_c    = float(outbound.get("min_charge_eur", 0) or 0)
    ins_pct  = float(outbound.get("insurance_pct", 0) or 0)
    handling = float(outbound.get("handling_eur", 0) or 0)

    freight   = max(total_mass_kg * rate, min_c) if total_mass_kg > 0 else 0
    insurance = sell_value * ins_pct

    return {
        "freight":   round(freight, 2),
        "insurance": round(insurance, 2),
        "handling":  round(handling, 2),
        "total":     round(freight + insurance + handling, 2),
    }
