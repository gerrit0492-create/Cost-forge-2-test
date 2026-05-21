"""
NRE (Non-Recurring Engineering) cost module.
Covers design hours, PM, testing, tooling, documentation, commissioning.
"""
from __future__ import annotations

import pandas as pd

SCHEMA_NRE = {
    "nre_id":        "string",
    "category":      "string",   # Engineering / PM / Testing / Tooling / Documentation / Commissioning / Other
    "description":   "string",
    "hours":         "float64",
    "rate_eur_h":    "float64",
    "fixed_eur":     "float64",  # fixed lump cost (e.g. tooling purchase price)
    "amortize_over": "float64",  # number of units to spread this over
    "status":        "string",   # Active / Complete / On Hold
    "notes":         "string",
}

NRE_CATEGORIES = [
    "Engineering",
    "Project Management",
    "Testing & Qualification",
    "Tooling",
    "Documentation",
    "Commissioning",
    "Prototyping",
    "Other",
]


def default_nre_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(SCHEMA_NRE.keys()))


def _cost_series(nre_df: pd.DataFrame) -> pd.Series:
    hours = pd.to_numeric(nre_df["hours"],     errors="coerce").fillna(0)
    rate  = pd.to_numeric(nre_df["rate_eur_h"], errors="coerce").fillna(0)
    fixed = pd.to_numeric(nre_df["fixed_eur"],  errors="coerce").fillna(0)
    return hours * rate + fixed


def nre_total(nre_df: pd.DataFrame) -> float:
    """Total NRE cost (sum of all line items)."""
    if nre_df.empty:
        return 0.0
    return float(_cost_series(nre_df).sum())


def nre_by_category(nre_df: pd.DataFrame) -> pd.DataFrame:
    """Returns a summary DataFrame grouped by category."""
    if nre_df.empty:
        return pd.DataFrame(columns=["category", "cost_eur", "hours"])
    df = nre_df.copy()
    df["_cost"] = _cost_series(df)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
    return (
        df.groupby("category")
          .agg(cost_eur=("_cost", "sum"), hours=("hours", "sum"))
          .reset_index()
          .sort_values("cost_eur", ascending=False)
    )


def nre_per_unit(nre_df: pd.DataFrame, volume: float) -> float:
    """
    Amortized NRE cost per unit.
    Each line is amortized over its own amortize_over value,
    falling back to `volume` if not set.
    """
    if nre_df.empty or volume <= 0:
        return 0.0
    df = nre_df.copy()
    cost = _cost_series(df)
    amort = pd.to_numeric(df["amortize_over"], errors="coerce").fillna(volume).clip(lower=1)
    return float((cost / amort).sum())


def nre_cashflow(nre_df: pd.DataFrame) -> pd.DataFrame:
    """Returns per-line NRE breakdown for reporting."""
    if nre_df.empty:
        return pd.DataFrame()
    df = nre_df.copy()
    df["line_cost_eur"] = _cost_series(df)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
    df["rate_eur_h"] = pd.to_numeric(df["rate_eur_h"], errors="coerce").fillna(0)
    df["fixed_eur"] = pd.to_numeric(df["fixed_eur"], errors="coerce").fillna(0)
    df["amortize_over"] = pd.to_numeric(df["amortize_over"], errors="coerce").fillna(1)
    return df
