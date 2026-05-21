"""
Escalation, contingency and risk module.
Handles commodity price index escalation, labour escalation, and risk register.
"""
from __future__ import annotations

import pandas as pd

SCHEMA_ESCALATION = {
    "esc_id":        "string",
    "applies_to":    "string",   # material_id, "LABOUR", "GENERAL", or commodity group
    "description":   "string",
    "index_name":    "string",   # e.g. LME Copper, EU CPI, Steel HRC
    "base_value":    "float64",
    "current_value": "float64",
    "base_date":     "string",
    "override_pct":  "float64",  # manual override; if set, ignores base/current
    "notes":         "string",
}

SCHEMA_RISK = {
    "risk_id":          "string",
    "category":         "string",   # Material / Process / Schedule / Commercial / Technical / External
    "title":            "string",
    "description":      "string",
    "probability":      "float64",  # 0–1
    "cost_impact_eur":  "float64",  # maximum cost impact
    "status":           "string",   # Open / Mitigated / Closed
    "mitigation":       "string",
    "owner":            "string",
    "notes":            "string",
}

RISK_CATEGORIES = ["Material", "Process", "Schedule", "Commercial", "Technical", "External"]
RISK_STATUSES   = ["Open", "Mitigated", "Closed"]


def default_escalation_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(SCHEMA_ESCALATION.keys()))


def default_risk_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(SCHEMA_RISK.keys()))


def escalation_pct(row: pd.Series) -> float:
    """
    Return escalation factor for a single row.
    If override_pct is set, use it directly.
    Otherwise derive from base_value / current_value.
    """
    override = float(row.get("override_pct") or 0)
    if override:
        return override / 100.0
    base = float(row.get("base_value") or 0)
    curr = float(row.get("current_value") or 0)
    if base and curr:
        return (curr - base) / base
    return 0.0


def total_escalation_cost(
    base_cost: float,
    escalation_df: pd.DataFrame,
) -> float:
    """
    Estimate total escalation cost against a given base cost.
    Sums escalation_pct × base_cost for all GENERAL / LABOUR escalation rows.
    Material-specific escalation should be applied per-line in the pricing engine.
    """
    if escalation_df.empty or base_cost <= 0:
        return 0.0
    total_pct = sum(
        escalation_pct(row)
        for _, row in escalation_df.iterrows()
        if str(row.get("applies_to", "")).upper() in ("GENERAL", "LABOUR", "ALL")
    )
    return base_cost * total_pct


def risk_expected_value(risk_df: pd.DataFrame) -> float:
    """Sum of probability × cost_impact for all open risks."""
    if risk_df.empty:
        return 0.0
    open_risks = risk_df[risk_df["status"].str.upper() != "CLOSED"]
    prob   = pd.to_numeric(open_risks["probability"],     errors="coerce").fillna(0)
    impact = pd.to_numeric(open_risks["cost_impact_eur"], errors="coerce").fillna(0)
    return float((prob * impact).sum())


def risk_summary(risk_df: pd.DataFrame) -> pd.DataFrame:
    """Return risk_df with expected_value column added."""
    if risk_df.empty:
        return risk_df.copy()
    df = risk_df.copy()
    df["probability"]     = pd.to_numeric(df["probability"],     errors="coerce").fillna(0)
    df["cost_impact_eur"] = pd.to_numeric(df["cost_impact_eur"], errors="coerce").fillna(0)
    df["expected_value"]  = df["probability"] * df["cost_impact_eur"]
    return df
